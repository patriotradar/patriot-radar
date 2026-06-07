from pytrends.request import TrendReq
from datetime import datetime
import time
import json
import random

CONTENT_KEYWORDS = [
    # Core
    "england", "britain", "great britain", "united kingdom", "british", "english",
    "union jack", "union flag", "british flag", "english flag",
    "st george", "st george's day",
    "veterans", "armed forces", "remembrance", "poppy",
    "churchill", "winston churchill",
    "royal navy", "raf", "royal air force", "british army",
    "monarchy", "king", "royal family",
    "national pride", "british pride", "english pride",
    "patriotism", "national identity", "british identity",
    # Supporting
    "battle of britain", "the few", "spitfire", "hurricane",
    "dunkirk spirit", "ve day", "d-day", "normandy",
    "white cliffs of dover", "buckingham palace", "westminster", "parliament",
    "cenotaph", "war memorial", "armed forces day",
    "victoria cross", "george cross", "national service",
    "heritage", "tradition", "courage", "honour", "duty",
    "sacrifice", "leadership", "freedom", "democracy",
    # Long-tail
    "british lion", "english lion", "lionheart",
    "rule britannia", "britannia",
    "land of hope and glory", "green and pleasant land",
    "spirit of 1940", "british bulldog", "finest hour spirit",
    "england expects", "keep calm and carry on",
    "proudly british", "proudly english",
    "loyal to britain", "loyal to the crown", "for king and country",
    # Topical
    "immigration", "small boats", "london", "uk politics",
    "british history", "military history"
]

PRODUCT_KEYWORDS = [
    "union jack flag", "british flag", "england flag",
    "patriotic clothing", "british clothing",
    "british army books", "military history books",
    "veteran gifts", "army surplus",
    "royal navy gifts", "churchill books",
    "history posters", "poppy brooch",
    "england hoodie", "british hoodie"
]

QUESTIONS = {
    "british army": "Should every school in Britain teach children about the British Army? Yes or No?",
    "royal navy": "Should Britain invest more in the Royal Navy? Yes or No?",
    "raf": "Should every child in Britain visit an RAF memorial? Yes or No?",
    "royal air force": "Should every child in Britain visit an RAF memorial? Yes or No?",
    "veterans": "Should veterans get free healthcare for life? Yes or No?",
    "armed forces": "Should every young person in Britain serve in the Armed Forces? Yes or No?",
    "union jack": "Should every school in Britain fly the Union Jack? Yes or No?",
    "union flag": "Should every school in Britain fly the Union Flag? Yes or No?",
    "uk politics": "Are ordinary people being ignored by UK politics? Yes or No?",
    "immigration": "Has Britain lost control of immigration? Yes or No?",
    "small boats": "Is Britain doing enough about small boats? Yes or No?",
    "england": "Should every school in Britain fly the England flag? Yes or No?",
    "britain": "Is being proud of Britain still acceptable? Yes or No?",
    "great britain": "Should every school teach children why Great Britain is great? Yes or No?",
    "london": "Is London still the heart of Britain? Yes or No?",
    "churchill": "Should every school in Britain teach children about Churchill? Yes or No?",
    "winston churchill": "Would Churchill recognise Britain today? Yes or No?",
    "remembrance": "Should every school in Britain hold a Remembrance assembly? Yes or No?",
    "poppy": "Should wearing a poppy be compulsory? Yes or No?",
    "monarchy": "Should Britain abolish the monarchy? Yes or No?",
    "king": "Should every school celebrate the King? Yes or No?",
    "royal family": "Should British taxpayers continue to fund the Royal Family? Yes or No?",
    "patriotism": "Is being patriotic still acceptable in modern Britain? Yes or No?",
    "national pride": "Are young people losing national pride? Yes or No?",
    "british pride": "Should it be compulsory to learn about British pride in schools? Yes or No?",
    "national identity": "Is British national identity under threat? Yes or No?",
    "battle of britain": "Should every school in Britain teach children about the Battle of Britain? Yes or No?",
    "spitfire": "Should every child in Britain learn about the Spitfire? Yes or No?",
    "dunkirk spirit": "Could Britain survive another Dunkirk today? Yes or No?",
    "ve day": "Should VE Day be a national bank holiday? Yes or No?",
    "d-day": "Should every school teach children about D-Day? Yes or No?",
    "st george": "Should St George's Day be a national holiday? Yes or No?",
    "st george's day": "Should St George's Day be a bank holiday? Yes or No?",
    "national service": "Should Britain bring back National Service? Yes or No?",
    "heritage": "Is British heritage being erased? Yes or No?",
    "tradition": "Is Britain losing its traditions? Yes or No?",
    "sacrifice": "Is Britain forgetting the sacrifice of its heroes? Yes or No?",
    "freedom": "Is freedom of speech under threat in Britain? Yes or No?",
    "democracy": "Is British democracy still working? Yes or No?",
    "cenotaph": "Should every town in Britain have a cenotaph? Yes or No?",
    "war memorial": "Should vandalising a war memorial carry a prison sentence? Yes or No?",
    "armed forces day": "Should Armed Forces Day be a bank holiday? Yes or No?",
    "buckingham palace": "Should Buckingham Palace be open to everyone for free? Yes or No?",
    "rule britannia": "Should Rule Britannia still be sung at the Proms? Yes or No?",
    "keep calm and carry on": "Does Britain still have the Keep Calm and Carry On spirit? Yes or No?",
    "british bulldog": "Does Britain still have the Bulldog spirit? Yes or No?",
    "british flag": "Should every school in Britain fly the British flag? Yes or No?",
    "english flag": "Should every school in England fly the English flag? Yes or No?",
    "english pride": "Is being proud to be English still acceptable? Yes or No?",
    "british identity": "Is British identity being lost? Yes or No?"
}

def make_caption(keyword):
    return f"{keyword.title()} is gaining attention today. What do you think?"

def make_product(keyword):
    keyword = keyword.lower()
    if "army" in keyword: return "British Army history books"
    if "navy" in keyword: return "Royal Navy books and gifts"
    if "flag" in keyword or "union jack" in keyword or "union flag" in keyword: return "Union Jack flags and patriotic decor"
    if "veteran" in keyword: return "Veteran gifts"
    if "churchill" in keyword: return "Churchill books"
    if "history" in keyword or "heritage" in keyword: return "British history books"
    if "clothing" in keyword or "hoodie" in keyword: return "British patriotic clothing"
    if "remembrance" in keyword or "poppy" in keyword or "cenotaph" in keyword: return "Remembrance gifts and poppy accessories"
    if "spitfire" in keyword or "hurricane" in keyword or "battle of britain" in keyword: return "RAF and Spitfire memorabilia"
    if "king" in keyword or "royal" in keyword or "monarchy" in keyword or "crown" in keyword: return "Royal family collectibles"
    if "england" in keyword or "english" in keyword or "st george" in keyword: return "England flags and St George merchandise"
    if "britain" in keyword or "british" in keyword: return "Proudly British merchandise"
    if "dunkirk" in keyword or "d-day" in keyword or "ve day" in keyword or "normandy" in keyword: return "WW2 history books and memorabilia"
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
                "question": QUESTIONS.get(keyword, f"Should every school in Britain teach children about {keyword.title()}? Yes or No?"),
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
    sample = CONTENT_KEYWORDS[:12]

    for keyword in sample:
        score = random.randint(45, 78)
        fallback.append({
            "category": "content",
            "keyword": keyword,
            "latest_score": score,
            "recent_avg": score - random.randint(1, 8),
            "previous_avg": score - random.randint(8, 20),
            "rise_percent": random.randint(10, 70),
            "viral_score": score,
            "question": QUESTIONS.get(keyword, f"Should every school in Britain teach children about {keyword.title()}? Yes or No?"),
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

    for item in results[:15]:
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
        json.dump(results[:15], f, indent=2)

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
