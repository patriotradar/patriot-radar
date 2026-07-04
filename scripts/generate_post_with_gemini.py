"""
Generate a complete TikTok post for the user's product/topic using Gemini.
Outputs hook, caption, hashtags, image prompt, animation prompt, voiceover, stock terms.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any


def load_json(path: Path) -> Any:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def pick_viral_pattern(product_category: str, patterns: list[dict]) -> dict:
    category_map = {
        "t-shirt": "apparel",
        "hoodie": "apparel",
        "cap": "apparel",
        "mug": "drinkware",
        "flask": "drinkware",
        "glass": "drinkware",
        "flag": "flags and banners",
        "banner": "flags and banners",
        "book": "books and history guides",
        "guide": "books and history guides",
        "sticker": "stickers and patches",
        "patch": "stickers and patches",
        "poster": "home decor",
        "decor": "home decor",
        "digital": "digital products",
    }
    canonical = category_map.get(product_category.lower(), product_category.lower())
    for pattern in patterns:
        if canonical in pattern.get("best_for", []):
            return pattern
    return patterns[0]


def build_gemini_prompt(
    product: str,
    topic: str,
    audience: dict,
    pattern: dict,
    recent_trends: list[str],
    recent_buyer_questions: list[str],
) -> str:
    trend_text = "\n - ".join([""] + recent_trends[:8]) if recent_trends else ""
    question_text = "\n - ".join([""] + recent_buyer_questions[:6]) if recent_buyer_questions else ""

    return f"""You are a TikTok content strategist for a British patriotic audience.

AUDIENCE PROFILE:
- Primary: {audience['demographics']['female_pct']}% female, {audience['demographics']['male_pct']}% male
- Age: {audience['demographics']['age_55_plus']}% are 55+
- Location: {audience['demographics']['location']}
- Best posting time: {audience['active_times']['best_day']}, {audience['active_times']['best_hours']}
- Content triggers: {', '.join(audience['content_triggers'])}

VIRAL FORMAT TO USE: {pattern['name']}
Format description: {pattern['description']}
Recommended duration: {pattern['duration_seconds']} seconds
Elements to include: {', '.join(pattern['elements'])}

CURRENT TRENDING CONTEXT:{trend_text}

BUYER QUESTIONS PEOPLE ARE ASKING:{question_text}

TASK:
Create a complete TikTok post for this product/topic: **{product}**
Angle or theme: **{topic}**

Return ONLY raw JSON in this exact structure (no markdown, no code fences, no commentary):

{{
  "hook": "first 3 seconds text overlay/voiceover hook",
  "caption": "full TikTok caption under 300 characters, with emotional CTA",
  "hashtags": ["hashtag1", "hashtag2", "hashtag3", "hashtag4", "hashtag5"],
  "imagePrompt": "detailed image generation prompt for Gemini to create the main visual. British, patriotic, suitable for 55+ audience. No text in image.",
  "animationPrompt": "short follow-up prompt to paste back into Gemini: 'Animate this image: [describe motion, camera, mood]'. Keep subtle and emotional.",
  "voiceover": "words the creator should speak or use TikTok text-to-speech. Under 40 words. Slow, clear.",
  "stockSearchTerms": ["term1", "term2", "term3"],
  "postingTime": "Saturday 12am-1am UK time",
  "videoDurationSeconds": {pattern['duration_seconds']},
  "whyItWorks": "one sentence explaining why this post should work for this audience"
}}
"""


def call_gemini(prompt: str, api_key: str) -> str:
    import urllib.request
    import urllib.error

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={api_key}"
    body = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.85,
            "maxOutputTokens": 1200,
            "responseMimeType": "text/plain",
        },
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"Gemini API error: {exc.code} {exc.reason} {exc.read().decode('utf-8', errors='ignore')}")

    candidates = data.get("candidates", [])
    if not candidates:
        raise RuntimeError("Gemini returned no candidates")
    text = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "")
    if not text:
        raise RuntimeError("Gemini returned empty text")
    return text


def clean_json(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        text = text.replace("json", "", 1).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        # Try to extract JSON from any surrounding text
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            return json.loads(text[start : end + 1])
        raise RuntimeError(f"Could not parse Gemini output as JSON: {exc}")


def main() -> None:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY environment variable required")

    product = os.getenv("POST_PRODUCT", "")
    topic = os.getenv("POST_TOPIC", "")
    if not product or not topic:
        raise RuntimeError("POST_PRODUCT and POST_TOPIC environment variables required")

    base = Path(__file__).resolve().parent.parent
    audience = load_json(base / "data" / "audience_profile.json")
    patterns = load_json(base / "data" / "viral_pattern_library.json")

    # Load optional recent trend / buyer signals if available
    recent_trends: list[str] = []
    recent_buyer_questions: list[str] = []
    feed_path = base / "data" / "trend_intelligence_feed_latest.json"
    buyer_path = base / "data" / "buyer_intent_signals_latest.json"
    if feed_path.exists():
        try:
            feed = load_json(feed_path)
            if isinstance(feed, dict):
                recent_trends = [str(x) for x in feed.get("trends", [])[:10]]
        except Exception:
            pass
    if buyer_path.exists():
        try:
            buyer = load_json(buyer_path)
            if isinstance(buyer, dict):
                recent_buyer_questions = [str(x) for x in buyer.get("questions", [])[:8]]
        except Exception:
            pass

    pattern = pick_viral_pattern(product, patterns)
    prompt = build_gemini_prompt(product, topic, audience, pattern, recent_trends, recent_buyer_questions)
    raw = call_gemini(prompt, api_key)
    result = clean_json(raw)

    # Enrich
    result["product"] = product
    result["topic"] = topic
    result["pattern"] = pattern["name"]

    output_path = base / "data" / "generated_post.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)

    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
