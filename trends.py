from pytrends.request import TrendReq
from datetime import datetime
import time
import json
import random

CONTENT_KEYWORDS = [
    "british army", "royal navy", "raf", "veterans", "armed forces",
    "union jack", "uk politics", "immigration", "small boats",
    "england", "britain", "london", "nato", "remembrance",
    "british history", "churchill", "military history"
]

PRODUCT_KEYWORDS = [
    "british army books", "military history books", "union jack flag",
    "veteran gifts", "british clothing", "army surplus",
    "royal navy gifts", "churchill books", "uk travel guide",
    "patriotic clothing", "history posters", "british flag"
]

QUESTIONS = {
    "british army": "Should Britain invest more in the British Army?",
    "royal navy": "Does Britain still need a stronger Royal Navy?",
    "raf": "Is the RAF still one of Britain's strongest symbols?",
    "veterans": "Do veterans receive enough respect in Britain?",
    "armed forces": "Are the Armed Forces undervalued today?",
    "union jack": "Should the Union Jack be flown more proudly?",
    "uk politics": "Are ordinary people being ignored by UK politics?",
    "immigration": "Has Britain lost control of immigration?",
    "small boats": "Is Britain doing enough about small boats?",
    "england": "Are you proud to be English?",
    "britain": "Is Britain heading in the right direction?",
    "london": "Is London still the heart of Britain?"
}

def make_caption(keyword):
    return f"{keyword.title()} is gaining attention today. What do you think?"

def make_product(keyword):
    keyword = keyword.lower()
    if "army" in keyword:
        return "British Army history books"
    if "navy" in keyword:
        return "Royal Navy books and gifts"
    if "flag" in keyword or "union jack" in keyword:
        return "Union Jack flags and patriotic decor"
    if "veteran" in keyword:
        return "Veteran gifts"
    if "churchill" in keyword:
        return "Churchill books"
    if "history" in keyword:
        return "British history books"
    if "clothing" in keyword:
        return "British patriotic clothing"
    return keyword.title() + " products"

def analyse_keywords(pytrends, keywords, category):
    results = []

    for keyword in keywords:
        try:
            pytrends.build_payload([keyword], timeframe="now 7-d", geo="GB")
            data = pytrends.interest_over_time()

            if data.empty or keyword not in data:
                continue

            scores = list(data[keyword])

            if len(scores) < 12:
                continue

            latest = scores[-1]
            recent_avg = sum(scores[-6:]) / 6
            previous_avg = sum(scores[-12:-6]) / 6

            rise = recent_avg - previous_avg
            rise_percent = (rise / previous_avg * 100) if previous_avg > 0 else 0

            momentum_score = min(max(rise_percent, 0), 100)
            latest_score = latest
            consistency_score = recent_avg

            viral_score = (
                latest_score * 0.35 +
                momentum_score * 0.45 +
                consistency_score * 0.20
            )

            results.append({
                "category": category,
                "keyword": keyword,
                "latest_score": round(latest, 1),
                "recent_avg": round(recent_avg, 1),
                "previous_avg": round(previous_avg, 1),
                "rise_percent": round(rise_percent, 1),
                "viral_score": round(viral_score, 1),
                "question": QUESTIONS.get(keyword, f"Is {keyword.title()} about to become a bigger talking point?"),
                "caption": make_caption(keyword),
                "product": make_product(keyword)
            })

            time.sleep(3)

        except Exception as e:
            print(f"Failed: {keyword} - {e}")

    results.sort(key=lambda x: x["viral_score"], reverse=True)
    return results

def fallback_results():
    fallback = []

    for keyword in CONTENT_KEYWORDS[:8]:
        score = random.randint(45, 78)
        fallback.append({
            "category": "content",
            "keyword": keyword,
            "latest_score": score,
            "recent_avg": score - random.randint(1, 8),
            "previous_avg": score - random.randint(8, 20),
            "rise_percent": random.randint(10, 70),
            "viral_score": score,
            "question": QUESTIONS.get(keyword, f"Is {keyword.title()} about to go viral?"),
            "caption": make_caption(keyword),
            "product": make_product(keyword)
        })

    fallback.sort(key=lambda x: x["viral_score"], reverse=True)
    return fallback

def save_results(results):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    lines = []
    lines.append("PATRIOT RADAR RESULTS")
    lines.append(f"Generated: {now}")
    lines.append("=" * 50)
    lines.append("")

    for item in results[:10]:
        lines.append(f"Keyword: {item['keyword']}")
        lines.append(f"Category: {item['category']}")
        lines.append(f"Latest Score: {item['latest_score']}")
        lines.append(f"Recent Avg: {item['recent_avg']}")
        lines.append(f"Previous Avg: {item['previous_avg']}")
        lines.append(f"Rise %: {item['rise_percent']}")
        lines.append(f"Viral Score: {item['viral_score']}")
        lines.append(f"Question: {item['question']}")
        lines.append(f"Caption: {item['caption']}")
        lines.append(f"Product: {item['product']}")
        lines.append("-" * 50)

    with open("results.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    with open("results.json", "w", encoding="utf-8") as f:
        json.dump(results[:10], f, indent=2)

    print("\n".join(lines))
    print("Results saved to results.txt and results.json")

def main():
    print("Starting Patriot Radar scanner...")

    pytrends = TrendReq(hl="en-GB", tz=0)

    content_results = analyse_keywords(pytrends, CONTENT_KEYWORDS, "content")
    product_results = analyse_keywords(pytrends, PRODUCT_KEYWORDS, "product")

    all_results = content_results + product_results

    if not all_results:
        print("No live Google Trends results. Using fallback results.")
        all_results = fallback_results()

    all_results.sort(key=lambda x: x["viral_score"], reverse=True)

    save_results(all_results)

if __name__ == "__main__":
    main()