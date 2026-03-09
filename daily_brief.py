import os
import requests
from datetime import datetime

PERPLEXITY_API_KEY = os.environ["PERPLEXITY_API_KEY"]
TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]

CATEGORIES = [
    {
        "emoji": "🤖",
        "label": "AI",
        "prompt": "What is the single most significant AI model release, tool launch, or breakthrough in the last 24 hours? One sentence. Be specific about the name and why it matters."
    },
    {
        "emoji": "🏀",
        "label": "NBA / Suns",
        "prompt": "What happened with the Phoenix Suns in the last 24 hours? If nothing Suns-specific, what is the most important NBA news? One sentence max."
    },
    {
        "emoji": "☸️",
        "label": "Dharma / Consciousness",
        "prompt": "Give me one brief insight, teaching, or quote from Buddhist, Dzogchen, or consciousness studies worth reflecting on today. One or two sentences max."
    },
    {
        "emoji": "🏎️",
        "label": "F1 / Boxing",
        "prompt": "Did anything significant happen in Formula 1 or professional boxing in the last 24 hours? If yes, one sentence. If nothing notable, say Nothing major today."
    },
    {
        "emoji": "💼",
        "label": "AVC / MPI Signal",
        "prompt": "What is one emerging trend in AI-powered coaching, mental performance technology, or elite performance consulting relevant to an AI consulting firm or mental performance startup? One sentence, forward-looking."
    },
]


def query_perplexity(prompt):
    response = requests.post(
        "https://api.perplexity.ai/chat/completions",
        headers={
            "Authorization": f"Bearer {PERPLEXITY_API_KEY}",
            "Content-Type": "application/json"
        },
        json={
            "model": "sonar-pro",
            "messages": [
                {
                    "role": "system",
                    "content": "You are a concise intelligence briefer. Respond in 1-2 sentences maximum. No preamble, no filler. Just the signal."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "max_tokens": 120
        }
    )
    response.raise_for_status()
    return response.json()["choices"][0]["message"]["content"].strip()


def send_telegram(message):
    requests.post(
        f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
        json={
            "chat_id": TELEGRAM_CHAT_ID,
            "text": message,
            "parse_mode": "Markdown"
        }
    )


def build_brief():
    today = datetime.now().strftime("%A, %B %d")
    lines = [f"*Rock Daily Brief - {today}*\n"]
    for cat in CATEGORIES:
        try:
            result = query_perplexity(cat["prompt"])
        except Exception as e:
            result = f"_(unavailable: {str(e)[:40]})_"
        lines.append(f"{cat['emoji']} *{cat['label']}*\n{result}\n")
    lines.append("_Stay focused. Stay present. Make it count._")
    return "\n".join(lines)


if __name__ == "__main__":
    brief = build_brief()
    send_telegram(brief)
    print("Brief sent.")
