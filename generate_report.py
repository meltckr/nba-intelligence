"""
AVC NBA Week in Review — Automated Pipeline
Accelerated Velocity Consulting
Runs every Monday via GitHub Actions
"""

import os
import json
import requests
from datetime import datetime, timedelta
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
import io
import base64

# ─── CONFIG ───────────────────────────────────────────────────────────────────
BDL_KEY = os.environ.get("BDL_API_KEY", "")
PPLX_KEY = os.environ.get("PERPLEXITY_API_KEY", "")
BDL_BASE = "https://api.balldontlie.io/v1"
PPLX_BASE = "https://api.perplexity.ai"

SUNS_TEAM_ID = 24  # Ball Don't Lie team ID for Phoenix Suns

# AVC Brand Colors
PURPLE = (29, 17, 96)        # #1D1160
ORANGE = (229, 96, 32)       # #E56020
DARK_BG = (10, 12, 28)       # #0A0C1C
LIGHT_BLUE = (96, 165, 250)  # #60A5FA

# ─── DATE HELPERS ─────────────────────────────────────────────────────────────
def get_week_range():
    today = datetime.now()
    week_ago = today - timedelta(days=7)
    return week_ago, today

def format_date(d):
    return d.strftime("%Y-%m-%d")

def format_display_date(d):
    return d.strftime("%B %d, %Y")

# ─── BALL DON'T LIE API ───────────────────────────────────────────────────────
def bdl_get(endpoint, params=None):
    headers = {"Authorization": BDL_KEY}
    resp = requests.get(f"{BDL_BASE}{endpoint}", headers=headers, params=params or {})
    resp.raise_for_status()
    return resp.json()

def fetch_standings():
    try:
        data = bdl_get("/standings", {"season": 2025})
        teams = data.get("data", [])
        west = sorted(
            [t for t in teams if t.get("conference") == "West"],
            key=lambda x: (-x.get("wins", 0), x.get("losses", 0))
        )
        east = sorted(
            [t for t in teams if t.get("conference") == "East"],
            key=lambda x: (-x.get("wins", 0), x.get("losses", 0))
        )
        return west, east
    except Exception as e:
        print(f"Standings fetch failed: {e}")
        return [], []

def fetch_suns_games():
    start, end = get_week_range()
    try:
        data = bdl_get("/games", {
            "team_ids[]": SUNS_TEAM_ID,
            "start_date": format_date(start),
            "end_date": format_date(end),
            "per_page": 10
        })
        return data.get("data", [])
    except Exception as e:
        print(f"Suns games fetch failed: {e}")
        return []

def fetch_league_games():
    start, end = get_week_range()
    try:
        data = bdl_get("/games", {
            "start_date": format_date(start),
            "end_date": format_date(end),
            "per_page": 100
        })
        return data.get("data", [])
    except Exception as e:
        print(f"League games fetch failed: {e}")
        return []

def fetch_suns_player_stats():
    start, end = get_week_range()
    try:
        data = bdl_get("/stats", {
            "team_ids[]": SUNS_TEAM_ID,
            "start_date": format_date(start),
            "end_date": format_date(end),
            "per_page": 100
        })
        # Aggregate by player
        player_totals = {}
        for stat in data.get("data", []):
            pid = stat["player"]["id"]
            name = f"{stat['player']['first_name']} {stat['player']['last_name']}"
            if pid not in player_totals:
                player_totals[pid] = {"name": name, "games": 0, "pts": 0, "reb": 0, "ast": 0, "min": 0}
            player_totals[pid]["games"] += 1
            player_totals[pid]["pts"] += stat.get("pts", 0) or 0
            player_totals[pid]["reb"] += stat.get("reb", 0) or 0
            player_totals[pid]["ast"] += stat.get("ast", 0) or 0
        # Compute averages
        leaders = []
        for pid, p in player_totals.items():
            if p["games"] > 0:
                leaders.append({
                    "name": p["name"],
                    "games": p["games"],
                    "ppg": round(p["pts"] / p["games"], 1),
                    "rpg": round(p["reb"] / p["games"], 1),
                    "apg": round(p["ast"] / p["games"], 1),
                })
        return sorted(leaders, key=lambda x: -x["ppg"])[:5]
    except Exception as e:
        print(f"Player stats fetch failed: {e}")
        return []

# ─── PERPLEXITY NARRATIVE ─────────────────────────────────────────────────────
def fetch_perplexity_narrative(west_standings, east_standings, suns_games, league_games):
    start, end = get_week_range()
    week_label = f"{format_display_date(start)} – {format_display_date(end)}"

    # Build standings summary for context
    west_summary = " | ".join([
        f"{i+1}. {t.get('team', {}).get('full_name', 'Unknown')} ({t.get('wins', 0)}-{t.get('losses', 0)})"
        for i, t in enumerate(west_standings[:8])
    ])
    east_summary = " | ".join([
        f"{i+1}. {t.get('team', {}).get('full_name', 'Unknown')} ({t.get('wins', 0)}-{t.get('losses', 0)})"
        for i, t in enumerate(east_standings[:8])
    ])

    # Suns game results
    suns_results = ""
    for g in suns_games:
        home = g.get("home_team", {}).get("full_name", "")
        away = g.get("visitor_team", {}).get("full_name", "")
        hs = g.get("home_team_score", 0)
        vs = g.get("visitor_team_score", 0)
        suns_results += f"{away} @ {home}: {vs}-{hs} | "

    prompt = f"""You are an elite NBA intelligence analyst briefing Phoenix Suns ownership.
    
Write a concise, sharp NBA Week in Review for the week of {week_label}.

CURRENT STANDINGS:
West (Top 8): {west_summary}
East (Top 8): {east_summary}

SUNS GAMES THIS WEEK: {suns_results or "No games this week"}

Write the following sections. Be direct, intelligent, and ownership-focused. No filler. Use real current NBA news from your web search:

1. EXECUTIVE_SUMMARY: 4-5 bullet points (start each with •) covering the most important things an NBA owner needs to know this week — injuries, seeding implications, league news, competitive threats.

2. LEAGUE_OFFICE: 2-3 paragraphs covering league business — trades, suspensions, CBA news, broadcast/revenue, commissioner activity, anything affecting the business of basketball.

3. WEST_ANALYSIS: 2-3 paragraphs on the Western Conference — who's surging, who's slipping, what matters for Phoenix's playoff positioning specifically.

4. EAST_ANALYSIS: 1-2 paragraphs — which East teams are legitimate Finals threats that Phoenix might face.

5. SUNS_CORNER: 2-3 paragraphs specifically on the Phoenix Suns — performance, injuries, roster, upcoming schedule, what ownership should be focused on.

6. STORYLINES: 3 forward-looking storylines, each with a title and 2-3 sentences.

7. STAT_OF_WEEK: One remarkable statistic from this week with a 2-sentence explanation of why it matters.

Format each section with its label exactly as shown above followed by a colon. Keep total response under 1200 words."""

    try:
        resp = requests.post(
            f"{PPLX_BASE}/chat/completions",
            headers={
                "Authorization": f"Bearer {PPLX_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": "sonar-pro",
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 2000,
                "temperature": 0.3
            }
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]
    except Exception as e:
        print(f"Perplexity call failed: {e}")
        return None

def parse_narrative(text):
    """Parse Perplexity output into sections dict."""
    sections = {
        "EXECUTIVE_SUMMARY": "",
        "LEAGUE_OFFICE": "",
        "WEST_ANALYSIS": "",
        "EAST_ANALYSIS": "",
        "SUNS_CORNER": "",
        "STORYLINES": "",
        "STAT_OF_WEEK": ""
    }
    if not text:
        return sections

    current = None
    buffer = []
    for line in text.split("\n"):
        for key in sections:
            if line.strip().startswith(f"{key}:") or line.strip() == key:
                if current and buffer:
                    sections[current] = "\n".join(buffer).strip()
                current = key
                remainder = line.split(":", 1)[-1].strip() if ":" in line else ""
                buffer = [remainder] if remainder else []
                break
        else:
            if current:
                buffer.append(line)

    if current and buffer:
        sections[current] = "\n".join(buffer).strip()

    return sections

# ─── OG IMAGE GENERATOR ───────────────────────────────────────────────────────
def generate_og_image(week_label, suns_record=""):
    """Generate 1200x630 OG image with AVC branding."""
    W, H = 1200, 630
    img = Image.new("RGB", (W, H), DARK_BG)
    draw = ImageDraw.Draw(img)

    # Background gradient effect — layered rectangles
    for i in range(H):
        alpha = i / H
        r = int(DARK_BG[0] * (1 - alpha * 0.3) + PURPLE[0] * alpha * 0.3)
        g = int(DARK_BG[1] * (1 - alpha * 0.3) + PURPLE[1] * alpha * 0.3)
        b = int(DARK_BG[2] * (1 - alpha * 0.3) + PURPLE[2] * alpha * 0.3)
        draw.line([(0, i), (W, i)], fill=(r, g, b))

    # Decorative pulse ring (AVC logo mark, drawn as circles)
    cx, cy = 160, 315
    for r, opacity in [(110, 25), (80, 45), (52, 70), (28, 95)]:
        alpha = int(255 * opacity / 100)
        overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        ov_draw = ImageDraw.Draw(overlay)
        ov_draw.ellipse([cx-r, cy-r, cx+r, cy+r], outline=(*LIGHT_BLUE, alpha), width=2)
        img.paste(Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB"))

    # Arrow inside ring
    draw.line([(cx-20, cy), (cx+20, cy)], fill=(*LIGHT_BLUE,), width=3)
    draw.polygon([(cx+12, cy-7), (cx+22, cy), (cx+12, cy+7)], fill=LIGHT_BLUE)

    # Orange accent bar at top
    draw.rectangle([0, 0, W, 8], fill=ORANGE)

    # Purple bar at bottom
    draw.rectangle([0, H-8, W, H], fill=PURPLE)

    # Vertical divider
    draw.line([(260, 60), (260, 570)], fill=(70, 70, 100), width=1)

    # Try to use default font, fallback gracefully
    try:
        font_large = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 72)
        font_med = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 38)
        font_small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 26)
        font_tiny = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 20)
    except:
        font_large = ImageFont.load_default()
        font_med = font_large
        font_small = font_large
        font_tiny = font_large

    # AVC text (right of divider)
    draw.text((300, 60), "ACCELERATED VELOCITY", font=font_small, fill=(241, 245, 249))
    draw.text((300, 92), "CONSULTING", font=font_tiny, fill=(100, 116, 139))

    # Confidential badge
    draw.rectangle([300, 120, 500, 148], fill=PURPLE)
    draw.text((310, 124), "OWNERSHIP INTELLIGENCE", font=font_tiny, fill=(200, 200, 220))

    # Main headline
    draw.text((300, 175), "NBA", font=font_large, fill=ORANGE)
    draw.text((300, 268), "WEEK IN REVIEW", font=font_med, fill=(241, 245, 249))

    # Week label
    draw.text((300, 330), week_label, font=font_small, fill=LIGHT_BLUE)

    # Suns record if available
    if suns_record:
        draw.text((300, 380), f"Phoenix Suns  {suns_record}", font=font_small, fill=(180, 180, 200))

    # Bottom strip
    draw.text((300, 575), "acceleratedvelocityconsulting.com", font=font_tiny, fill=(80, 80, 110))

    # Save
    Path("docs").mkdir(exist_ok=True)
    img.save("docs/og-image.png", "PNG", optimize=True)
    print("✓ OG image generated")

# ─── HTML GENERATOR ───────────────────────────────────────────────────────────
AVC_LOGO_SVG = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 420 80" width="280" height="53">
  <defs><style>@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;800&display=swap');</style></defs>
  <g transform="translate(8, 8)">
    <circle cx="32" cy="32" r="30" stroke="#60a5fa" stroke-width="1.5" fill="none" opacity="0.15"/>
    <circle cx="32" cy="32" r="22" stroke="#60a5fa" stroke-width="2" fill="none" opacity="0.35"/>
    <circle cx="32" cy="32" r="14" stroke="#60a5fa" stroke-width="2.5" fill="none" opacity="0.6"/>
    <line x1="24" y1="32" x2="44" y2="32" stroke="#93c5fd" stroke-width="3" stroke-linecap="round"/>
    <polyline points="38,26 44,32 38,38" stroke="#93c5fd" stroke-width="3" stroke-linecap="round" stroke-linejoin="round" fill="none"/>
  </g>
  <line x1="82" y1="18" x2="82" y2="62" stroke="#334155" stroke-width="1"/>
  <text x="98" y="32" font-family="Inter,Arial,sans-serif" font-size="18" font-weight="800" letter-spacing="3" fill="#f1f5f9">ACCELERATED</text>
  <text x="98" y="52" font-family="Inter,Arial,sans-serif" font-size="18" font-weight="300" letter-spacing="3" fill="#60a5fa">VELOCITY</text>
  <text x="98" y="68" font-family="Inter,Arial,sans-serif" font-size="10" font-weight="400" letter-spacing="5.5" fill="#64748b">CONSULTING</text>
</svg>"""

def format_bullet_html(text):
    """Convert bullet text to HTML list items."""
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    items = []
    for line in lines:
        clean = line.lstrip("•●-– ").strip()
        if clean:
            items.append(f'<li>{clean}</li>')
    return "\n".join(items)

def format_para_html(text):
    """Convert paragraph text to HTML paragraphs."""
    paras = [p.strip() for p in text.split("\n\n") if p.strip()]
    return "\n".join([f'<p>{p.replace(chr(10), " ")}</p>' for p in paras])

def format_storylines_html(text):
    """Parse and format storylines section."""
    blocks = []
    current_title = ""
    current_body = []
    for line in text.split("\n"):
        line = line.strip()
        if not line:
            if current_title and current_body:
                blocks.append((current_title, " ".join(current_body)))
                current_title = ""
                current_body = []
            continue
        # Detect title lines (numbered or bold-like)
        if (line[0].isdigit() and "." in line[:3]) or line.startswith("**"):
            if current_title and current_body:
                blocks.append((current_title, " ".join(current_body)))
                current_body = []
            current_title = line.lstrip("0123456789. *#").strip()
        else:
            current_body.append(line)
    if current_title and current_body:
        blocks.append((current_title, " ".join(current_body)))

    if not blocks:
        return f'<p>{text}</p>'

    html = ""
    for title, body in blocks[:3]:
        html += f"""
        <div class="storyline-card">
            <div class="storyline-num">▶</div>
            <div class="storyline-content">
                <div class="storyline-title">{title}</div>
                <div class="storyline-body">{body}</div>
            </div>
        </div>"""
    return html

def standings_html(teams, highlight_team="Phoenix Suns"):
    rows = ""
    for i, t in enumerate(teams[:10]):
        name = t.get("team", {}).get("full_name", "Unknown")
        w = t.get("wins", 0)
        l = t.get("losses", 0)
        pct = f".{int(w/(w+l)*1000):03d}" if (w+l) > 0 else ".000"
        is_suns = "Phoenix" in name
        row_class = "standings-row suns-row" if is_suns else "standings-row"
        rank_badge = f'<span class="rank">{i+1}</span>'
        rows += f"""
        <tr class="{row_class}">
            <td>{rank_badge} {name}</td>
            <td class="num">{w}</td>
            <td class="num">{l}</td>
            <td class="num">{pct}</td>
        </tr>"""
    return f"""
    <table class="standings-table">
        <thead>
            <tr>
                <th>TEAM</th><th>W</th><th>L</th><th>PCT</th>
            </tr>
        </thead>
        <tbody>{rows}</tbody>
    </table>"""

def suns_games_html(games):
    if not games:
        return '<p class="no-data">No games this week.</p>'
    rows = ""
    for g in games:
        home = g.get("home_team", {}).get("full_name", "")
        away = g.get("visitor_team", {}).get("full_name", "")
        hs = g.get("home_team_score", 0)
        vs = g.get("visitor_team_score", 0)
        date = g.get("date", "")[:10]
        is_home = "Phoenix" in home
        opp = away if is_home else home
        suns_score = hs if is_home else vs
        opp_score = vs if is_home else hs
        location = "HOME" if is_home else "AWAY"
        result = "W" if suns_score > opp_score else "L"
        result_class = "win" if result == "W" else "loss"
        rows += f"""
        <tr>
            <td class="game-date">{date}</td>
            <td class="game-loc {location.lower()}">{location}</td>
            <td class="game-opp">{opp}</td>
            <td class="game-score">{suns_score}–{opp_score}</td>
            <td class="game-result {result_class}">{result}</td>
        </tr>"""
    return f"""
    <table class="game-table">
        <thead><tr><th>DATE</th><th></th><th>OPPONENT</th><th>SCORE</th><th></th></tr></thead>
        <tbody>{rows}</tbody>
    </table>"""

def player_stats_html(leaders):
    if not leaders:
        return '<p class="no-data">Stats not available.</p>'
    rows = ""
    for p in leaders:
        rows += f"""
        <tr>
            <td class="player-name">{p['name']}</td>
            <td class="stat">{p['ppg']}</td>
            <td class="stat">{p['rpg']}</td>
            <td class="stat">{p['apg']}</td>
            <td class="stat gp">{p['games']}</td>
        </tr>"""
    return f"""
    <table class="stats-table">
        <thead><tr><th>PLAYER</th><th>PPG</th><th>RPG</th><th>APG</th><th>GP</th></tr></thead>
        <tbody>{rows}</tbody>
    </table>"""

def generate_html(sections, west, east, suns_games, player_stats, week_label, report_date):
    exec_bullets = format_bullet_html(sections.get("EXECUTIVE_SUMMARY", ""))
    league_paras = format_para_html(sections.get("LEAGUE_OFFICE", ""))
    west_paras = format_para_html(sections.get("WEST_ANALYSIS", ""))
    east_paras = format_para_html(sections.get("EAST_ANALYSIS", ""))
    suns_paras = format_para_html(sections.get("SUNS_CORNER", ""))
    storylines_html_content = format_storylines_html(sections.get("STORYLINES", ""))
    stat_raw = sections.get("STAT_OF_WEEK", "")

    # Extract stat number if possible
    stat_lines = [l.strip() for l in stat_raw.split("\n") if l.strip()]
    stat_headline = stat_lines[0] if stat_lines else "Stat of the Week"
    stat_body = " ".join(stat_lines[1:]) if len(stat_lines) > 1 else ""

    west_table = standings_html(west)
    east_table = standings_html(east)
    games_table = suns_games_html(suns_games)
    stats_table = player_stats_html(player_stats)

    # Determine Suns record from standings
    suns_w, suns_l = 0, 0
    for t in west:
        if "Phoenix" in t.get("team", {}).get("full_name", ""):
            suns_w = t.get("wins", 0)
            suns_l = t.get("losses", 0)
            break
    suns_record = f"{suns_w}–{suns_l}"

    # Find Suns seed
    suns_seed = next((i+1 for i, t in enumerate(west) if "Phoenix" in t.get("team", {}).get("full_name", "")), "?")

    page_title = f"NBA Week in Review — {week_label}"
    og_description = f"Phoenix Suns Ownership Intelligence Brief | {suns_record}, #{suns_seed} in West | AVC Strategic Report"

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{page_title}</title>

    <!-- Open Graph / iMessage / Twitter Card -->
    <meta property="og:type" content="article">
    <meta property="og:title" content="NBA Week in Review — {week_label}">
    <meta property="og:description" content="{og_description}">
    <meta property="og:image" content="og-image.png">
    <meta property="og:image:width" content="1200">
    <meta property="og:image:height" content="630">
    <meta property="og:site_name" content="Accelerated Velocity Consulting">

    <meta name="twitter:card" content="summary_large_image">
    <meta name="twitter:title" content="NBA Week in Review — {week_label}">
    <meta name="twitter:description" content="{og_description}">
    <meta name="twitter:image" content="og-image.png">

    <meta name="description" content="{og_description}">
    <meta name="author" content="Accelerated Velocity Consulting">

    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;800&family=DM+Mono:wght@400;500&display=swap" rel="stylesheet">

    <style>
        :root {{
            --purple: #1D1160;
            --orange: #E56020;
            --dark: #080C1C;
            --card: #0E1328;
            --card2: #121830;
            --border: rgba(255,255,255,0.07);
            --text: #E8EAF0;
            --muted: #6B7280;
            --blue: #60A5FA;
            --gold: #F59E0B;
        }}

        * {{ margin: 0; padding: 0; box-sizing: border-box; }}

        body {{
            font-family: 'Inter', system-ui, sans-serif;
            background: var(--dark);
            color: var(--text);
            min-height: 100vh;
            line-height: 1.6;
        }}

        /* TOP ORANGE BAR */
        .top-bar {{ height: 5px; background: linear-gradient(90deg, var(--purple), var(--orange), var(--purple)); }}

        /* HEADER */
        header {{
            background: linear-gradient(135deg, #0A0E22 0%, #1D1160 60%, #0D0828 100%);
            border-bottom: 1px solid rgba(229,96,32,0.3);
            padding: 24px 40px;
        }}
        .header-inner {{
            max-width: 1200px;
            margin: 0 auto;
            display: flex;
            justify-content: space-between;
            align-items: center;
            flex-wrap: wrap;
            gap: 16px;
        }}
        .header-right {{
            text-align: right;
        }}
        .report-title {{
            font-size: 11px;
            font-weight: 600;
            letter-spacing: 3px;
            color: var(--orange);
            text-transform: uppercase;
            margin-bottom: 4px;
        }}
        .report-week {{
            font-size: 22px;
            font-weight: 800;
            color: #F1F5F9;
            letter-spacing: -0.5px;
        }}
        .report-meta {{
            font-size: 12px;
            color: var(--muted);
            margin-top: 4px;
        }}
        .suns-badge {{
            display: inline-flex;
            align-items: center;
            gap: 8px;
            background: rgba(229,96,32,0.15);
            border: 1px solid rgba(229,96,32,0.4);
            border-radius: 20px;
            padding: 6px 16px;
            font-size: 13px;
            font-weight: 600;
            color: var(--orange);
            margin-top: 8px;
        }}

        /* MAIN LAYOUT */
        main {{
            max-width: 1200px;
            margin: 0 auto;
            padding: 40px 24px;
            display: grid;
            grid-template-columns: 1fr;
            gap: 32px;
        }}

        /* SECTION BLOCKS */
        .section {{
            background: var(--card);
            border: 1px solid var(--border);
            border-radius: 12px;
            overflow: hidden;
        }}
        .section-header {{
            background: linear-gradient(90deg, var(--purple), #2A1880);
            padding: 14px 24px;
            display: flex;
            align-items: center;
            gap: 10px;
        }}
        .section-icon {{ font-size: 18px; }}
        .section-title {{
            font-size: 12px;
            font-weight: 800;
            letter-spacing: 3px;
            text-transform: uppercase;
            color: #F1F5F9;
        }}
        .section-body {{ padding: 24px; }}
        .section-body p {{
            margin-bottom: 14px;
            font-size: 15px;
            color: #D1D5DB;
            line-height: 1.75;
        }}
        .section-body p:last-child {{ margin-bottom: 0; }}

        /* EXEC SUMMARY */
        .exec-list {{
            list-style: none;
            display: flex;
            flex-direction: column;
            gap: 14px;
        }}
        .exec-list li {{
            display: flex;
            gap: 14px;
            font-size: 15px;
            color: #D1D5DB;
            line-height: 1.65;
            padding: 14px;
            background: rgba(255,255,255,0.03);
            border-radius: 8px;
            border-left: 3px solid var(--orange);
        }}
        .exec-list li::before {{
            content: "→";
            color: var(--orange);
            font-weight: 700;
            flex-shrink: 0;
        }}

        /* TWO COLUMN LAYOUT for standings */
        .two-col {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 24px;
        }}
        @media (max-width: 768px) {{ .two-col {{ grid-template-columns: 1fr; }} }}

        .conf-block h3 {{
            font-size: 11px;
            font-weight: 700;
            letter-spacing: 3px;
            color: var(--orange);
            text-transform: uppercase;
            margin-bottom: 14px;
        }}

        /* STANDINGS TABLE */
        .standings-table, .game-table, .stats-table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 13px;
        }}
        .standings-table th, .game-table th, .stats-table th {{
            text-align: left;
            font-size: 10px;
            font-weight: 700;
            letter-spacing: 2px;
            color: var(--muted);
            padding: 8px 12px;
            border-bottom: 1px solid var(--border);
        }}
        .standings-table td, .game-table td, .stats-table td {{
            padding: 9px 12px;
            border-bottom: 1px solid rgba(255,255,255,0.04);
            color: #C9D1E0;
        }}
        .standings-table .num, .stats-table .stat {{
            text-align: right;
            font-family: 'DM Mono', monospace;
            font-size: 13px;
        }}
        .rank {{
            display: inline-flex;
            align-items: center;
            justify-content: center;
            width: 20px;
            height: 20px;
            font-size: 10px;
            font-weight: 700;
            color: var(--muted);
            background: rgba(255,255,255,0.06);
            border-radius: 4px;
            margin-right: 8px;
        }}
        .suns-row td {{
            background: rgba(229,96,32,0.08) !important;
            color: var(--orange) !important;
            font-weight: 600;
        }}
        .suns-row .rank {{ color: var(--orange); background: rgba(229,96,32,0.2); }}

        /* GAME TABLE */
        .game-date {{ font-family: 'DM Mono', monospace; font-size: 12px; color: var(--muted); }}
        .game-loc {{ font-size: 10px; font-weight: 700; letter-spacing: 1px; }}
        .game-loc.home {{ color: var(--orange); }}
        .game-loc.away {{ color: var(--blue); }}
        .game-score {{ font-family: 'DM Mono', monospace; font-weight: 600; }}
        .game-result {{ font-weight: 800; font-size: 13px; letter-spacing: 1px; }}
        .win {{ color: #22C55E; }}
        .loss {{ color: #EF4444; }}
        .player-name {{ font-weight: 600; }}
        .gp {{ color: var(--muted); }}

        /* STORYLINES */
        .storyline-card {{
            display: flex;
            gap: 16px;
            padding: 18px;
            background: var(--card2);
            border-radius: 10px;
            border: 1px solid var(--border);
            margin-bottom: 14px;
        }}
        .storyline-card:last-child {{ margin-bottom: 0; }}
        .storyline-num {{ color: var(--orange); font-size: 18px; flex-shrink: 0; padding-top: 2px; }}
        .storyline-title {{
            font-size: 14px;
            font-weight: 700;
            color: #F1F5F9;
            margin-bottom: 6px;
            letter-spacing: 0.3px;
        }}
        .storyline-body {{ font-size: 14px; color: #9CA3AF; line-height: 1.65; }}

        /* STAT OF THE WEEK */
        .stat-block {{
            background: linear-gradient(135deg, rgba(229,96,32,0.12), rgba(29,17,96,0.3));
            border: 1px solid rgba(229,96,32,0.25);
            border-radius: 12px;
            padding: 28px;
            text-align: center;
        }}
        .stat-number {{
            font-size: 80px;
            font-weight: 800;
            color: var(--orange);
            line-height: 1;
            letter-spacing: -4px;
            margin-bottom: 8px;
        }}
        .stat-headline {{
            font-size: 16px;
            font-weight: 600;
            color: #F1F5F9;
            margin-bottom: 12px;
        }}
        .stat-body {{ font-size: 14px; color: #9CA3AF; max-width: 600px; margin: 0 auto; line-height: 1.7; }}

        /* FOOTER */
        footer {{
            background: #060910;
            border-top: 1px solid rgba(229,96,32,0.2);
            padding: 28px 40px;
            margin-top: 20px;
        }}
        .footer-inner {{
            max-width: 1200px;
            margin: 0 auto;
            display: flex;
            justify-content: space-between;
            align-items: center;
            flex-wrap: wrap;
            gap: 16px;
        }}
        .footer-right {{
            font-size: 11px;
            color: var(--muted);
            text-align: right;
        }}
        .confidential {{
            font-size: 10px;
            font-weight: 700;
            letter-spacing: 2px;
            color: rgba(229,96,32,0.5);
            text-transform: uppercase;
            margin-top: 4px;
        }}

        /* ARCHIVE LINK */
        .archive-link {{
            display: inline-block;
            font-size: 12px;
            color: var(--blue);
            text-decoration: none;
            margin-top: 8px;
        }}
        .archive-link:hover {{ text-decoration: underline; }}

        .no-data {{ color: var(--muted); font-size: 14px; font-style: italic; }}

        /* Suns sub-header */
        .sub-section-title {{
            font-size: 11px;
            font-weight: 700;
            letter-spacing: 2.5px;
            color: var(--orange);
            text-transform: uppercase;
            margin: 20px 0 10px;
        }}
        .sub-section-title:first-child {{ margin-top: 0; }}
    </style>
</head>
<body>

<div class="top-bar"></div>

<header>
    <div class="header-inner">
        <div class="header-logo">
            {AVC_LOGO_SVG}
        </div>
        <div class="header-right">
            <div class="report-title">Ownership Intelligence Brief</div>
            <div class="report-week">NBA Week in Review</div>
            <div class="report-meta">{week_label}</div>
            <div class="suns-badge">☀ Phoenix Suns &nbsp; {suns_record} &nbsp; #{suns_seed} West</div>
        </div>
    </div>
</header>

<main>

    <!-- EXECUTIVE SUMMARY -->
    <div class="section">
        <div class="section-header">
            <span class="section-icon">⚡</span>
            <span class="section-title">Executive Summary — What Matters This Week</span>
        </div>
        <div class="section-body">
            <ul class="exec-list">
                {exec_bullets}
            </ul>
        </div>
    </div>

    <!-- SUNS CORNER -->
    <div class="section">
        <div class="section-header">
            <span class="section-icon">☀</span>
            <span class="section-title">Suns Corner</span>
        </div>
        <div class="section-body">
            <div class="sub-section-title">This Week's Results</div>
            {games_table}
            <div class="sub-section-title" style="margin-top:24px;">Player Performance</div>
            {stats_table}
            <div class="sub-section-title" style="margin-top:24px;">Analysis</div>
            {suns_paras}
        </div>
    </div>

    <!-- LEAGUE OFFICE -->
    <div class="section">
        <div class="section-header">
            <span class="section-icon">🏛</span>
            <span class="section-title">League Office &amp; Business</span>
        </div>
        <div class="section-body">
            {league_paras}
        </div>
    </div>

    <!-- STANDINGS -->
    <div class="section">
        <div class="section-header">
            <span class="section-icon">📊</span>
            <span class="section-title">Conference Standings</span>
        </div>
        <div class="section-body">
            <div class="two-col">
                <div class="conf-block">
                    <h3>🌵 Western Conference</h3>
                    {west_table}
                </div>
                <div class="conf-block">
                    <h3>🏙 Eastern Conference</h3>
                    {east_table}
                </div>
            </div>
        </div>
    </div>

    <!-- WEST ANALYSIS -->
    <div class="section">
        <div class="section-header">
            <span class="section-icon">🌵</span>
            <span class="section-title">Western Conference Analysis</span>
        </div>
        <div class="section-body">
            {west_paras}
        </div>
    </div>

    <!-- EAST ANALYSIS -->
    <div class="section">
        <div class="section-header">
            <span class="section-icon">🏙</span>
            <span class="section-title">Eastern Conference Pulse</span>
        </div>
        <div class="section-body">
            {east_paras}
        </div>
    </div>

    <!-- STORYLINES -->
    <div class="section">
        <div class="section-header">
            <span class="section-icon">👁</span>
            <span class="section-title">Storylines to Watch</span>
        </div>
        <div class="section-body">
            {storylines_html_content}
        </div>
    </div>

    <!-- STAT OF THE WEEK -->
    <div class="section">
        <div class="section-header">
            <span class="section-icon">📈</span>
            <span class="section-title">Stat of the Week</span>
        </div>
        <div class="section-body">
            <div class="stat-block">
                <div class="stat-headline">{stat_headline}</div>
                <div class="stat-body">{stat_body}</div>
            </div>
        </div>
    </div>

</main>

<footer>
    <div class="footer-inner">
        <div>
            {AVC_LOGO_SVG}
            <a href="archive/" class="archive-link">View Previous Reports →</a>
        </div>
        <div class="footer-right">
            <div>Generated {report_date} by AVC Intelligence Pipeline</div>
            <div class="confidential">⬛ Confidential — For Suns Ownership Use Only</div>
        </div>
    </div>
</footer>

</body>
</html>"""

# ─── ARCHIVE INDEX GENERATOR ──────────────────────────────────────────────────
def update_archive(week_label):
    archive_dir = Path("docs/archive")
    archive_dir.mkdir(parents=True, exist_ok=True)
    index_file = archive_dir / "index.html"

    # Read existing entries
    entries = []
    if index_file.exists():
        content = index_file.read_text()
        import re
        entries = re.findall(r'href="\.\./(.*?)".*?>(.*?)</a>', content)

    # Add new entry
    dated_name = f"{datetime.now().strftime('%Y-%m-%d')}-report.html"
    entries.insert(0, (dated_name, week_label))

    entry_html = "\n".join([
        f'<li><a href="../{name}">{label}</a></li>' for name, label in entries
    ])

    index_file.write_text(f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8"><title>AVC NBA Reports Archive</title>
<style>body{{font-family:system-ui;background:#080C1C;color:#E8EAF0;padding:40px;max-width:600px;margin:0 auto}}
h1{{color:#E56020;margin-bottom:24px}}ul{{list-style:none;padding:0}}li{{margin-bottom:12px}}
a{{color:#60A5FA;text-decoration:none;font-size:16px}}a:hover{{text-decoration:underline}}</style>
</head><body><h1>NBA Week in Review Archive</h1><ul>{entry_html}</ul></body></html>""")
    print(f"✓ Archive updated with {week_label}")

# ─── MAIN ─────────────────────────────────────────────────────────────────────
def main():
    print("🏀 AVC NBA Week in Review Generator starting...")
    start, end = get_week_range()
    week_label = f"{format_display_date(start)} – {format_display_date(end)}"
    report_date = format_display_date(end)
    print(f"📅 Week: {week_label}")

    # Fetch data
    print("📡 Fetching standings...")
    west, east = fetch_standings()
    print(f"   West: {len(west)} teams | East: {len(east)} teams")

    print("📡 Fetching Suns games...")
    suns_games = fetch_suns_games()
    print(f"   {len(suns_games)} Suns games this week")

    print("📡 Fetching player stats...")
    player_stats = fetch_suns_player_stats()

    print("📡 Fetching league games...")
    league_games = fetch_league_games()
    print(f"   {len(league_games)} league games this week")

    print("🤖 Calling Perplexity for narrative intelligence...")
    narrative_text = fetch_perplexity_narrative(west, east, suns_games, league_games)
    sections = parse_narrative(narrative_text)
    print("   ✓ Narrative generated and parsed")

    # Determine Suns record
    suns_w, suns_l = 0, 0
    for t in west:
        if "Phoenix" in t.get("team", {}).get("full_name", ""):
            suns_w = t.get("wins", 0)
            suns_l = t.get("losses", 0)
            break

    # Generate OG image
    print("🖼  Generating OG image...")
    generate_og_image(week_label, f"{suns_w}–{suns_l}")

    # Generate HTML
    print("📝 Generating HTML report...")
    html = generate_html(sections, west, east, suns_games, player_stats, week_label, report_date)

    # Write to docs/
    Path("docs").mkdir(exist_ok=True)
    with open("docs/index.html", "w", encoding="utf-8") as f:
        f.write(html)
    print("   ✓ docs/index.html written")

    # Archive copy
    archive_dir = Path("docs/archive")
    archive_dir.mkdir(parents=True, exist_ok=True)
    dated = f"docs/archive/{datetime.now().strftime('%Y-%m-%d')}-report.html"
    with open(dated, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"   ✓ Archived as {dated}")

    update_archive(week_label)
    print("\n✅ Done! Report ready for GitHub Pages.")

if __name__ == "__main__":
    main()
