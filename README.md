# AVC NBA Week in Review — Automated Pipeline
### Accelerated Velocity Consulting | Phoenix Suns Ownership Intelligence

This GitHub Actions pipeline automatically generates a branded NBA intelligence brief every **Monday morning at 7:00 AM Arizona time**, publishes it to GitHub Pages, and produces a shareable URL with a professional OG image for iMessage link previews.

---

## 📋 Setup (One Time — ~10 Minutes)

### Step 1: Create Your GitHub Repository

1. Go to [github.com](https://github.com) and click **New Repository**
2. Name it: `nba-intelligence` (or whatever you prefer)
3. Set to **Private** (your content stays confidential)
4. Click **Create repository**

### Step 2: Upload These Files

Upload the following files maintaining the folder structure:
```
.github/
  workflows/
    nba-weekly.yml
generate_report.py
requirements.txt
README.md
docs/
  (empty — the pipeline creates this)
```

### Step 3: Add Your API Keys as Secrets

This is where your Ball Don't Lie and Perplexity keys live — securely, never in code.

1. In your repo, go to **Settings → Secrets and Variables → Actions**
2. Click **New repository secret** and add:

| Secret Name | Value |
|-------------|-------|
| `BDL_API_KEY` | Your Ball Don't Lie API key |
| `PERPLEXITY_API_KEY` | Your Perplexity API key |

> ⚠️ **Important:** Use freshly regenerated keys. Never paste API keys in chat or code.

### Step 4: Enable GitHub Pages

1. Go to **Settings → Pages**
2. Under **Source**, select **GitHub Actions**
3. Click **Save**

### Step 5: Set Your Timezone (Optional Adjustment)

The pipeline runs at `0 14 * * 1` (UTC), which is 7:00 AM MST / Arizona time.
If you need a different time, edit `.github/workflows/nba-weekly.yml` and adjust the cron expression.

[Cron Time Converter](https://crontab.guru/)

---

## 🚀 Running It

### Automatic
Every Monday at 7 AM Arizona time. Nothing to do.

### Manual (Trigger Anytime)
1. Go to your repo on GitHub
2. Click **Actions** tab
3. Click **NBA Week in Review — Auto-Generate**
4. Click **Run workflow → Run workflow**

The report will be live at your GitHub Pages URL within ~2 minutes.

---

## 🔗 Your URL

After first run, your report will be at:
```
https://[your-github-username].github.io/nba-intelligence/
```

This is the URL you text to Mat. The OG image and meta tags ensure it displays as a rich link card in iMessage showing the week, Suns record, and AVC branding.

### Archive
All previous weeks are automatically saved at:
```
https://[your-github-username].github.io/nba-intelligence/archive/
```

---

## 🔧 How It Works

```
Every Monday 7 AM
       ↓
GitHub Actions fires
       ↓
Ball Don't Lie API → Standings + Suns games + Player stats
       ↓
Perplexity sonar-pro → Narrative intelligence (web-search enabled)
       ↓
generate_report.py → HTML report + OG image
       ↓
Commits to repo → GitHub Pages deploys
       ↓
URL is live. Text it to Mat.
```

---

## 📦 Data Sources

| Source | What It Provides |
|--------|-----------------|
| Ball Don't Lie API | Live standings, game scores, player stats |
| Perplexity sonar-pro | AI narrative with live web search (injuries, news, analysis) |

---

## ✏️ Customization

The HTML template is fully self-contained in `generate_report.py` inside the `generate_html()` function. AVC branding (logo, colors, fonts) is embedded. To update the logo or colors, edit the `AVC_LOGO_SVG` constant and the CSS variables at the top of the `generate_html()` function.

---

*Built by Accelerated Velocity Consulting | Confidential*
