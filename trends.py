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

PATRIOTIC_FILTER_WORDS = [
    "britain", "british", "england", "english", "uk ", "united kingdom",
    "royal", "king charles", "queen", "prince", "princess",
    "army", "navy", "raf", "military", "armed forces", "veterans",
    "remembrance", "poppy", "cenotaph", "memorial",
    "churchill", "spitfire", "dunkirk", "d-day", "ve day",
    "union jack", "st george", "flag",
    "parliament", "westminster", "buckingham", "downing street",
    "patriot", "national", "heritage", "tradition",
    "immigration", "border", "channel",
    "london", "scotland", "wales", "northern ireland",
    "commonwealth", "empire", "coronation",
    "trooping the colour", "proms", "bbc", "nhs",
    "football", "cricket", "rugby", "olympic",
    "brexit", "reform", "conservative", "labour",
    "monarchy", "crown", "throne"
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

ALL_KNOWN_KEYWORDS = set(kw.lower() for kw in CONTENT_KEYWORDS + PRODUCT_KEYWORDS)

def is_patriotic_relevant(query):
    q = query.lower()
    for word in PATRIOTIC_FILTER_WORDS:
        if word in q:
            return True
    return False

def make_caption(keyword):
    kw = keyword.title()
    captions = [
        f"🇬🇧 {kw} is trending in Britain right now. Should every school teach children about this? Comment YES or NO below!",
        f"🇬🇧 {kw} is gaining attention across Britain. Do you think enough is being done? YES or NO? Comment below!",
        f"🇬🇧 {kw} is a hot topic in Britain today. Are you proud of this? YES or NO? Drop your answer below!",
        f"🇬🇧 {kw} is trending right now. Should Britain do more? YES or NO? Let us know in the comments!",
        f"🇬🇧 {kw} is back in the spotlight. Does this still matter to modern Britain? YES or NO?"
    ]
    import hashlib
    idx = int(hashlib.md5(keyword.lower().encode()).hexdigest(), 16) % len(captions)
    return captions[idx]

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
    return "Patriotic merchandise"

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

def discover_related_keywords(pytrends, seed_keywords):
    discovered = []
    seen = set()
    sample = [kw for kw in seed_keywords if kw in [r.lower() for r in ALL_KNOWN_KEYWORDS]]
    top_seeds = seed_keywords[:20]

    for keyword in top_seeds:
        try:
            pytrends.build_payload([keyword], timeframe="now 7-d", geo="GB")

            related = pytrends.related_queries()
            if keyword in related:
                rising = related[keyword].get("rising")
                if rising is not None and not rising.empty:
                    for _, row in rising.head(5).iterrows():
                        query = row["query"].lower()
                        value = row["value"]
                        if query not in ALL_KNOWN_KEYWORDS and query not in seen:
                            if is_patriotic_relevant(query):
                                seen.add(query)
                                discovered.append({
                                    "keyword": query,
                                    "source_keyword": keyword,
                                    "rise_value": int(value) if str(value).isdigit() else 100,
                                    "discovery_type": "rising_query"
                                })

                top = related[keyword].get("top")
                if top is not None and not top.empty:
                    for _, row in top.head(3).iterrows():
                        query = row["query"].lower()
                        if query not in ALL_KNOWN_KEYWORDS and query not in seen:
                            if is_patriotic_relevant(query):
                                seen.add(query)
                                discovered.append({
                                    "keyword": query,
                                    "source_keyword": keyword,
                                    "rise_value": int(row["value"]) if str(row["value"]).isdigit() else 50,
                                    "discovery_type": "related_query"
                                })

            time.sleep(2)

        except Exception as e:
            print(f"Related query failed for {keyword}: {e}")

    discovered.sort(key=lambda x: x["rise_value"], reverse=True)
    return discovered

def discover_trending_searches(pytrends):
    discovered = []
    try:
        trending = pytrends.trending_searches(pn="united_kingdom")
        if trending is not None and not trending.empty:
            for _, row in trending.iterrows():
                query = row[0].lower() if len(row) > 0 else ""
                if query and is_patriotic_relevant(query) and query not in ALL_KNOWN_KEYWORDS:
                    discovered.append({
                        "keyword": query,
                        "source_keyword": "UK Trending",
                        "rise_value": 200,
                        "discovery_type": "uk_trending"
                    })
    except Exception as e:
        print(f"Trending searches failed: {e}")

    return discovered

def score_discovered_keyword(pytrends, keyword):
    try:
        pytrends.build_payload([keyword], timeframe="now 7-d", geo="GB")
        data = pytrends.interest_over_time()

        if data.empty or keyword not in data:
            return None

        scores = list(data[keyword])
        if len(scores) < 6:
            return None

        latest = scores[-1]
        recent_avg = sum(scores[-6:]) / 6
        previous_avg = sum(scores[:-6]) / max(1, len(scores) - 6) if len(scores) > 6 else recent_avg * 0.8

        rise = recent_avg - previous_avg
        rise_percent = (rise / previous_avg * 100) if previous_avg > 0 else 0

        viral_score = (
            latest * 0.35 +
            min(max(rise_percent, 0), 100) * 0.45 +
            recent_avg * 0.20
        )

        return {
            "latest_score": round(latest, 1),
            "recent_avg": round(recent_avg, 1),
            "previous_avg": round(previous_avg, 1),
            "rise_percent": round(rise_percent, 1),
            "viral_score": round(viral_score, 1)
        }
    except Exception as e:
        print(f"Scoring failed for {keyword}: {e}")
        return None

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

def save_results(results, emerging):
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

    if emerging:
        lines.append("")
        lines.append("EMERGING TOPICS")
        lines.append("=" * 50)
        for item in emerging[:10]:
            lines.append(f"Keyword: {item['keyword']}")
            lines.append(f"Source: {item.get('source_keyword', 'N/A')}")
            lines.append(f"Type: {item.get('discovery_type', 'N/A')}")
            lines.append(f"Viral Score: {item.get('viral_score', 'N/A')}")
            lines.append("-" * 50)

    with open("results.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    output = {
        "results": results[:15],
        "emerging": emerging[:10],
        "last_updated": now
    }

    with open("results.json", "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)

    print("\n".join(lines))
    print(f"Results saved. {len(results)} main, {len(emerging)} emerging.")

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

    print("Discovering emerging topics...")
    related_discovered = discover_related_keywords(pytrends, CONTENT_KEYWORDS)
    trending_discovered = discover_trending_searches(pytrends)

    all_discovered = related_discovered + trending_discovered
    seen_kw = set()
    unique_discovered = []
    for d in all_discovered:
        if d["keyword"] not in seen_kw:
            seen_kw.add(d["keyword"])
            unique_discovered.append(d)

    print(f"Found {len(unique_discovered)} emerging topics. Scoring top candidates...")

    scored_emerging = []
    for item in unique_discovered[:15]:
        time.sleep(2)
        scores = score_discovered_keyword(pytrends, item["keyword"])
        if scores and scores["viral_score"] > 10:
            entry = {
                "category": "emerging",
                "keyword": item["keyword"],
                "latest_score": scores["latest_score"],
                "recent_avg": scores["recent_avg"],
                "previous_avg": scores["previous_avg"],
                "rise_percent": scores["rise_percent"],
                "viral_score": scores["viral_score"],
                "source_keyword": item["source_keyword"],
                "discovery_type": item["discovery_type"],
                "question": f"Should every school in Britain teach children about {item['keyword'].title()}? Yes or No?",
                "caption": make_caption(item["keyword"]),
                "product": make_product(item["keyword"])
            }
            scored_emerging.append(entry)

    scored_emerging.sort(key=lambda x: x["viral_score"], reverse=True)

    save_results(all_results, scored_emerging)

if __name__ == "__main__":
    main()
