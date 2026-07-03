from pytrends.request import TrendReq
from datetime import datetime
import time
import json
import os
import random
import os
import requests
from caption_templates import apply_caption_pipeline

CONTENT_KEYWORDS = [
    # Core
    "england", "britain", "great britain", "united kingdom", "british", "english",
    "union jack", "union flag", "british flag", "english flag",
    "st george", "st george's day",
    "veterans", "armed forces", "remembrance", "poppy",
    "churchill", "winston churchill",
    "royal navy", "raf", "royal air force", "british army",
    "monarchy", "king", "royal family",
    "british pride", "english pride",
    "patriotism", "british identity",
    # Supporting
    "battle of britain", "the few", "spitfire", "hawker hurricane",
    "dunkirk spirit", "ve day", "d-day", "normandy",
    "white cliffs of dover", "buckingham palace", "westminster", "parliament",
    "cenotaph", "war memorial", "armed forces day",
    "victoria cross", "george cross", "national service",
    "british heritage", "british tradition",
    # Long-tail
    "rule britannia",
    "land of hope and glory",
    "spirit of 1940", "british bulldog",
    "keep calm and carry on",
    "proudly british", "proudly english",
    "loyal to the crown", "for king and country",
    # Topical
    "immigration", "small boats", "london", "uk politics",
    "british history", "military history"
]

PRODUCT_KEYWORDS = [
    "union jack flag", "british flag", "england flag",
    "union jack hoodie", "england hoodie", "british hoodie",
    "england shirt", "british t shirt",
    "patriotic clothing", "british clothing", "british gifts",
    "poppy brooch", "poppy pin", "remembrance gifts",
    "british army books", "churchill books",
    "veteran gifts", "military gifts",
    "royal memorabilia", "british souvenirs"
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
    "british army": "Should Britain double its spending on the British Army? Yes or No?",
    "royal navy": "Should Britain invest more in the Royal Navy? Yes or No?",
    "raf": "Should every child in Britain visit an RAF memorial? Yes or No?",
    "royal air force": "Should every child in Britain visit an RAF memorial? Yes or No?",
    "veterans": "Should veterans get free healthcare for life? Yes or No?",
    "armed forces": "Should every young person in Britain serve in the Armed Forces? Yes or No?",
    "union jack": "Would you fly the Union Jack outside your home? Yes or No?",
    "union flag": "Would you fly the Union Flag outside your home? Yes or No?",
    "uk politics": "Are ordinary people being ignored by UK politics? Yes or No?",
    "immigration": "Has Britain lost control of immigration? Yes or No?",
    "small boats": "Is Britain doing enough about small boats? Yes or No?",
    "england": "Is being proud of England still acceptable today? Yes or No?",
    "britain": "Is being proud of Britain still acceptable? Yes or No?",
    "great britain": "Is Great Britain still the greatest country in the world? Yes or No?",
    "london": "Is London still the heart of Britain? Yes or No?",
    "churchill": "Was Churchill the greatest leader Britain ever had? Yes or No?",
    "winston churchill": "Would Churchill recognise Britain today? Yes or No?",
    "remembrance": "Should Remembrance Day be a national bank holiday? Yes or No?",
    "poppy": "Should wearing a poppy be compulsory? Yes or No?",
    "monarchy": "Should Britain abolish the monarchy? Yes or No?",
    "king": "Does the King make you proud to be British? Yes or No?",
    "royal family": "Should British taxpayers continue to fund the Royal Family? Yes or No?",
    "patriotism": "Is being patriotic still acceptable in modern Britain? Yes or No?",
    "national pride": "Are young people losing national pride? Yes or No?",
    "british pride": "Should it be compulsory to learn about British pride in schools? Yes or No?",
    "national identity": "Is British national identity under threat? Yes or No?",
    "battle of britain": "Was the Battle of Britain our finest hour? Yes or No?",
    "spitfire": "Should every child in Britain learn about the Spitfire? Yes or No?",
    "dunkirk spirit": "Could Britain survive another Dunkirk today? Yes or No?",
    "ve day": "Should VE Day be a national bank holiday? Yes or No?",
    "d-day": "Is modern Britain forgetting the sacrifice of D-Day? Yes or No?",
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
    "british flag": "Would you fly the British flag outside your home? Yes or No?",
    "english flag": "Would you fly the English flag outside your home? Yes or No?",
    "english pride": "Is being proud to be English still acceptable? Yes or No?",
    "british identity": "Is British identity being lost? Yes or No?",
    "victoria cross": "Is the Victoria Cross the greatest honour in the world? Yes or No?",
    "george cross": "Does modern Britain still recognise true bravery? Yes or No?",
    "national service": "Should Britain bring back National Service? Yes or No?",
    "white cliffs of dover": "Are the White Cliffs of Dover still a symbol of British strength? Yes or No?",
    "buckingham palace": "Should Buckingham Palace be open to every British citizen for free? Yes or No?",
    "rule britannia": "Should Rule Britannia still be sung at the Proms? Yes or No?",
    "keep calm and carry on": "Does Britain still have the Keep Calm and Carry On spirit? Yes or No?",
    "british bulldog": "Does Britain still have the Bulldog spirit? Yes or No?",
    "british heritage": "Is British heritage being erased? Yes or No?",
    "british tradition": "Is Britain losing its traditions? Yes or No?",
    "war memorial": "Should vandalising a war memorial carry a prison sentence? Yes or No?",
    "cenotaph": "Should protesting near the Cenotaph be a criminal offence? Yes or No?",
    "poppy": "Should wearing a poppy be compulsory in Britain? Yes or No?",
    "armed forces day": "Should Armed Forces Day be a national bank holiday? Yes or No?",
    "hawker hurricane": "Did the Hawker Hurricane do more than the Spitfire to save Britain? Yes or No?",
    "dunkirk spirit": "Does Britain still have the Dunkirk Spirit? Yes or No?",
    "normandy": "Is Britain forgetting what happened in Normandy? Yes or No?",
    "the few": "Were The Few the bravest generation Britain ever produced? Yes or No?",
    "westminster": "Has Westminster lost touch with ordinary British people? Yes or No?",
    "parliament": "Does Parliament still work for the British people? Yes or No?",
    "london": "Is London still the greatest city in the world? Yes or No?",
    "duty": "Has Britain lost its sense of duty? Yes or No?",
    "honour": "Does honour still mean anything in modern Britain? Yes or No?",
    "courage": "Does Britain still have the courage to stand up for itself? Yes or No?",
    "sacrifice": "Is Britain forgetting the sacrifice of its heroes? Yes or No?",
    "leadership": "Does Britain have real leaders anymore? Yes or No?",
    "tradition": "Is Britain losing its traditions? Yes or No?",
    "heritage": "Is British heritage being erased? Yes or No?",
    "freedom": "Is freedom of speech under threat in Britain? Yes or No?",
    "democracy": "Is British democracy still working? Yes or No?",
    "british": "Is being British still something to be proud of? Yes or No?",
    "english": "Is being English still something to be proud of? Yes or No?",
    "the few": "Will Britain ever forget The Few who saved us? Yes or No?",
    "lionheart": "Does Britain still have the Lionheart spirit? Yes or No?",
    "britannia": "Does Britannia still rule? Yes or No?",
    "british lion": "Does the British Lion still roar? Yes or No?",
    "english lion": "Does the English Lion still roar? Yes or No?",
    "british bulldog": "Does Britain still have the Bulldog spirit? Yes or No?",
    "united kingdom": "Is the United Kingdom still truly united? Yes or No?",
    "great britain": "Is Great Britain still the greatest country in the world? Yes or No?"
}

ALL_KNOWN_KEYWORDS = set(kw.lower() for kw in CONTENT_KEYWORDS + PRODUCT_KEYWORDS)

BLOCKED_WORDS = [
    "spineless", "worst", "terrible", "hate", "stupid", "ugly", "boring",
    "dead", "killed", "murder", "crime", "scandal", "cheat", "fraud",
    "crash", "accident", "injured", "hospital", "arrest", "jailed",
    "reality tv", "love island", "celebrity", "kardashian",
    "weather forecast", "recipe", "diet", "weight loss",
    "fifa", "premier league", "transfer", "champions league", "football score",
    "netflix", "spotify", "amazon prime", "tiktok ban",
    "iphone", "samsung", "playstation", "xbox",
    "individuals in", "people in", "things in", "places in",
    "best restaurants", "hotels in", "flights to", "resort",
    "salary", "jobs in", "cost of living", "mortgage", "interest rate",
    "polling", "poll ", "survey says", "election results",
    "theme park", "universal", "disney", "tickets",
    "unbound", "startup", "app launch", "tech company",
    "tv show", "bbc iplayer", "itv hub", "channel 4",
    "tennis", "rugby", "atp ", "challenger ", "cricket score",
    "golf", "formula 1", "f1 ", "boxing", "ufc",
    "darcy", "wimbledon", "ashes"
]

STRONG_PATRIOTIC_WORDS = [
    "army", "navy", "raf", "military", "armed forces", "veterans",
    "remembrance", "poppy", "cenotaph", "memorial",
    "churchill", "spitfire", "dunkirk", "d-day", "ve day",
    "patriot", "heritage", "tradition", "pride",
    "union jack", "st george", "flag",
    "king charles", "coronation", "trooping",
    "national service", "victoria cross"
]

def is_patriotic_relevant(query):
    q = query.lower()
    for blocked in BLOCKED_WORDS:
        if blocked in q:
            return False
    matches = 0
    strong_match = False
    for word in PATRIOTIC_FILTER_WORDS:
        if word in q:
            matches += 1
    for word in STRONG_PATRIOTIC_WORDS:
        if word in q:
            strong_match = True
            break
    if matches == 0:
        return False
    if len(q.split()) > 4 and not strong_match:
        return False
    if len(q.split()) > 6 and matches < 2:
        return False
    return True

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
    if "spitfire" in keyword or "hawker hurricane" in keyword or "battle of britain" in keyword: return "RAF and Spitfire memorabilia"
    if "king" in keyword or "royal" in keyword or "monarchy" in keyword or "crown" in keyword: return "Royal family collectibles"
    if "england" in keyword or "english" in keyword or "st george" in keyword: return "England flags and St George merchandise"
    if "britain" in keyword or "british" in keyword: return "Proudly British merchandise"
    if "dunkirk" in keyword or "d-day" in keyword or "ve day" in keyword or "normandy" in keyword: return "WW2 history books and memorabilia"
    return "Patriotic merchandise"

def analyse_keywords(pytrends, keywords, category):
    results = []
    consecutive_fails = 0

    for keyword in keywords:
        if consecutive_fails >= 5:
            print(f"Rate limited - stopping after {consecutive_fails} consecutive failures ({len(results)} results so far)")
            break

        try:
            delay = random.uniform(8, 18)
            time.sleep(delay)

            pytrends.build_payload([keyword], timeframe="now 7-d", geo="GB")
            data = pytrends.interest_over_time()
            consecutive_fails = 0

            if data.empty or keyword not in data:
                continue

            scores = list(data[keyword])

            if len(scores) < 12:
                continue

            latest = scores[-1]
            overall_avg = sum(scores) / len(scores)
            recent_avg = sum(scores[-6:]) / 6
            previous_avg = sum(scores[-12:-6]) / 6

            min_vol = 2 if category == "product" else 5
            if overall_avg < min_vol:
                print(f"Skipping {keyword}: too low volume (avg {overall_avg:.1f})")
                continue

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
                "question": QUESTIONS.get(keyword, f"Is {keyword.title()} being ignored in modern Britain? Yes or No?"),
                "product": make_product(keyword)
            })

        except Exception as e:
            consecutive_fails += 1
            print(f"Failed: {keyword} - {e}")
            if "429" in str(e):
                time.sleep(random.uniform(30, 60))

    results.sort(key=lambda x: x["viral_score"], reverse=True)
    return results

def discover_related_keywords(pytrends, seed_keywords):
    discovered = []
    seen = set()
    sample = [kw for kw in seed_keywords if kw in [r.lower() for r in ALL_KNOWN_KEYWORDS]]
    top_seeds = seed_keywords[:10]

    for keyword in top_seeds:
        try:
            time.sleep(random.uniform(8, 15))
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

        except Exception as e:
            print(f"Related query failed for {keyword}: {e}")
            if "429" in str(e):
                break

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

def scan_reddit():
    discovered = []
    subreddits = ["unitedkingdom", "CasualUK", "ukpolitics", "BritishMilitary", "AskUK", "BritishSuccess", "britishproblems"]
    import re as reddit_re

    for sub in subreddits:
        try:
            url = f"https://www.reddit.com/r/{sub}/hot/.rss?limit=25"
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
                "Accept": "application/rss+xml, application/xml, text/xml"
            }
            resp = requests.get(url, headers=headers, timeout=10)
            if resp.status_code != 200:
                print(f"Reddit RSS r/{sub}: HTTP {resp.status_code}")
                continue

            titles = reddit_re.findall(r'<title>([^<]+)</title>', resp.text)
            for title_raw in titles[1:]:
                title = title_raw.strip().lower()
                title = reddit_re.sub(r'&amp;', '&', title)
                title = reddit_re.sub(r'&#\d+;', '', title)

                if is_patriotic_relevant(title) and title not in ALL_KNOWN_KEYWORDS:
                    words = title.split()
                    clean_title = " ".join(words[:10]) if len(words) > 10 else title
                    clean_title = clean_title[:60].strip()
                    if len(clean_title) > 10:
                        discovered.append({
                            "keyword": clean_title,
                            "source_keyword": f"Reddit r/{sub}",
                            "rise_value": 200,
                            "discovery_type": "reddit"
                        })

            time.sleep(1)

        except Exception as e:
            print(f"Reddit r/{sub} failed: {e}")

    seen = set()
    unique = []
    for d in discovered:
        if d["keyword"] not in seen:
            seen.add(d["keyword"])
            unique.append(d)

    return unique[:10]

def scan_twitter_trends():
    discovered = []
    import re as tw_re

    sources = [
        ("https://trends24.in/united-kingdom/", [
            r'<a[^>]*class="trend-link"[^>]*>([^<]+)</a>',
            r'>#([^<]+)</a>',
            r'class="[^"]*trend[^"]*"[^>]*>([^<]{3,40})<'
        ]),
        ("https://getdaytrends.com/united-kingdom/", [
            r'<a[^>]*>([^<]{3,40})</a>',
        ])
    ]
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"}

    for url, patterns in sources:
        try:
            resp = requests.get(url, headers=headers, timeout=10)
            if resp.status_code != 200:
                print(f"Twitter trends source {url}: HTTP {resp.status_code}")
                continue

            trends = []
            for pattern in patterns:
                found = tw_re.findall(pattern, resp.text)
                if found:
                    trends = found
                    break

            for trend in trends[:40]:
                t = trend.strip().lower().replace("#", "")
                if t and len(t) > 3 and is_patriotic_relevant(t) and t not in ALL_KNOWN_KEYWORDS:
                    discovered.append({
                        "keyword": t[:60],
                        "source_keyword": "Twitter UK",
                        "rise_value": 250,
                        "discovery_type": "twitter"
                    })

            if discovered:
                break
        except Exception as e:
            print(f"Twitter trends failed ({url}): {e}")

    return discovered[:10]

def scan_uk_news():
    discovered = []
    import re
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"}

    searches = [
        "british+army+uk+military",
        "royal+family+king+britain",
        "remembrance+veterans+uk",
        "england+patriotic+british+pride"
    ]

    for query in searches:
        try:
            resp = requests.get(f"https://news.google.com/rss/search?q={query}&hl=en-GB&gl=GB&ceid=GB:en", headers=headers, timeout=10)
            if resp.status_code == 200:
                titles = re.findall(r'<title>([^<]+)</title>', resp.text)
                for title in titles[1:10]:
                    t = title.strip().lower()
                    if is_patriotic_relevant(t) and len(t) > 15 and t not in ALL_KNOWN_KEYWORDS:
                        words = t.split()
                        clean = " ".join(words[:10]) if len(words) > 10 else t
                        discovered.append({
                            "keyword": clean[:60],
                            "source_keyword": "UK News",
                            "rise_value": 180,
                            "discovery_type": "news"
                        })
            time.sleep(1)
        except Exception as e:
            print(f"UK News scan failed for {query}: {e}")

    rss_feeds = [
        ("https://feeds.bbci.co.uk/news/uk/rss.xml", "BBC UK"),
        ("https://feeds.bbci.co.uk/news/politics/rss.xml", "BBC Politics"),
        ("https://feeds.bbci.co.uk/news/england/rss.xml", "BBC England"),
        ("https://feeds.skynews.com/feeds/rss/uk.xml", "Sky UK"),
        ("https://feeds.skynews.com/feeds/rss/politics.xml", "Sky Politics"),
        ("https://www.dailymail.co.uk/news/index.rss", "Daily Mail"),
        ("https://www.telegraph.co.uk/news/rss.xml", "Telegraph"),
        ("https://www.theguardian.com/uk-news/rss", "Guardian UK"),
    ]

    for feed_url, source_name in rss_feeds:
        try:
            resp = requests.get(feed_url, headers=headers, timeout=10)
            if resp.status_code == 200:
                titles = re.findall(r'<title>([^<]+)</title>', resp.text)
                for title in titles[1:15]:
                    t = title.strip().lower()
                    t = re.sub(r'&amp;', '&', t)
                    t = re.sub(r'&#\d+;', '', t)
                    t = re.sub(r'<!\[CDATA\[|\]\]>', '', t)
                    if is_patriotic_relevant(t) and len(t) > 15 and t not in ALL_KNOWN_KEYWORDS:
                        words = t.split()
                        clean = " ".join(words[:10]) if len(words) > 10 else t
                        discovered.append({
                            "keyword": clean[:60],
                            "source_keyword": source_name,
                            "rise_value": 180,
                            "discovery_type": "news"
                        })
            time.sleep(0.5)
        except Exception as e:
            print(f"RSS {source_name} failed: {e}")

    seen = set()
    unique = []
    for d in discovered:
        if d["keyword"] not in seen:
            seen.add(d["keyword"])
            unique.append(d)

    return unique[:15]

def scan_autocomplete():
    discovered = []
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"}
    creator_seeds = ["tiktok views", "how to get views", "content ideas", "tiktok growth", "tiktok algorithm"]
    autocomplete_blocklist = [
        "playtime", "elden ring", "insurance", "nadal", "leao", "downs",
        "geschirr", "canada", "dalton", "got talent", "olarra", "jodar",
        "emoji", "png", "image", "icon", "theorem", "1776", "hsr",
        "trailblazer", "elden", "prototype", "chapter", "build",
        "population", "time zone", " map", "election polls",
        "movies", "movie", "drink", "knife", "login", "shirt",
        "football team", "football ", "cricket", "rugby team",
        "flagge", " time", "national team", "pay scale", "pay rise",
        "ranks", "uniform", "jobs", "seeds", "flower",
        "bank note", "meaning", "wiki", "definition",
        "world cup", "squad", "schedule", "fixture", "score",
        "in german", "auf deutsch", "postal code", "zip code",
        "countries", "vs uk", "vs usa", "capital", "language",
        "prime minister", "weather", "currency", "flag",
        "a country", "a city", "a continent", "a state",
        "in europe", "in england", "in the eu",
        "buy", " bot", "hack"
    ]
    specific_seeds = [
        "should britain", "why should britain", "will britain",
        "should the uk", "why is the uk", "will the uk",
        "is it wrong to be proud of being british",
        "do british people", "why do british people",
        "british army 2026", "british military 2026",
        "remembrance day 2026", "d-day anniversary",
        "veterans uk 2026", "armed forces uk 2026",
        "royal family latest", "king charles latest",
        "is national service coming back",
        "union jack controversy", "england pride",
        "immigration uk 2026", "small boats uk",
        "why is england", "why is britain",
        "is britain still", "is england still",
        "british culture", "english culture today",
        "british values", "british identity crisis",
        "proud to be british", "proud to be english",
        "best of british", "great british",
        "british military news", "uk defence news",
        "royal navy news", "raf news today",
        "king charles news today", "royal family news today",
        "uk immigration news", "channel crossing news",
        "british traditions dying", "english traditions",
        "should england have", "does britain need",
        "is the uk becoming", "will england ever",
        "british nostalgia", "remember when britain",
        "growing up british", "only in britain",
        "british problems", "things only british people",
        "what makes britain great", "best thing about britain",
        "worst thing about britain", "britain debate",
        "uk veterans news", "armed forces day 2026",
        "british patriotism tiktok", "england tiktok",
        "patriotic content ideas", "british content creator",
    ]
    random.shuffle(specific_seeds)
    seeds = specific_seeds + creator_seeds
    creator_results = []

    for seed in seeds:
        try:
            url = f"https://suggestqueries.google.com/complete/search?client=firefox&q={seed}&hl=en&gl=uk"
            resp = requests.get(url, headers=headers, timeout=8)
            if resp.status_code == 200:
                data = resp.json()
                suggestions = data[1] if len(data) > 1 else []
                for sug in suggestions:
                    s = sug.lower().strip()
                    if any(b in s for b in autocomplete_blocklist):
                        continue
                    is_creator_seed = seed in creator_seeds
                    if s != seed and s not in ALL_KNOWN_KEYWORDS and len(s) > 10:
                        words = s.split()
                        clean = " ".join(words[:8]) if len(words) > 8 else s
                        entry = {
                            "keyword": clean[:60],
                            "source_keyword": seed,
                            "rise_value": 150,
                            "discovery_type": "creator_search" if is_creator_seed else "autocomplete"
                        }
                        if is_creator_seed:
                            creator_results.append(entry)
                        elif is_patriotic_relevant(s):
                            discovered.append(entry)
            time.sleep(1)
        except Exception as e:
            print(f"Autocomplete failed for {seed}: {e}")

    seen = set()
    unique = []
    for d in discovered:
        if d["keyword"] not in seen:
            seen.add(d["keyword"])
            unique.append(d)

    creator_unique = []
    for d in creator_results:
        if d["keyword"] not in seen:
            seen.add(d["keyword"])
            creator_unique.append(d)

    return unique[:10], creator_unique[:10]

EMERGING_HOOK_TEMPLATES = {
    "military": [
        "Should Britain invest more in {kw}? Yes or No?",
        "Should {kw} be a bigger priority for Britain's defence? Yes or No?",
        "Is {kw} being forgotten by modern Britain? Yes or No?",
        "Should every young person in Britain learn about {kw}? Yes or No?",
        "Does Britain need {kw} now more than ever? Yes or No?"
    ],
    "royal": [
        "Should {kw} be a national celebration? Yes or No?",
        "Does {kw} still matter to modern Britain? Yes or No?",
        "Should British taxpayers support {kw}? Yes or No?",
        "Is {kw} good for Britain? Yes or No?",
        "Does {kw} make you proud to be British? Yes or No?"
    ],
    "national_identity": [
        "Should {kw} be celebrated more in Britain? Yes or No?",
        "Is {kw} something every British person should be proud of? Yes or No?",
        "Should {kw} be taught in every British school? Yes or No?",
        "Does {kw} unite or divide Britain? Yes or No?",
        "Is {kw} under threat in modern Britain? Yes or No?"
    ],
    "history": [
        "Should every child in Britain learn about {kw}? Yes or No?",
        "Is Britain forgetting the lessons of {kw}? Yes or No?",
        "Should {kw} be a national day of remembrance? Yes or No?",
        "Would {kw} be possible in today's Britain? Yes or No?",
        "Should {kw} be a bigger part of the school curriculum? Yes or No?"
    ],
    "remembrance": [
        "Should {kw} be a bank holiday in Britain? Yes or No?",
        "Is Britain doing enough to honour {kw}? Yes or No?",
        "Should every workplace observe {kw}? Yes or No?",
        "Is {kw} being forgotten by younger generations? Yes or No?",
        "Should {kw} be marked with a national silence? Yes or No?"
    ],
    "politics": [
        "Is {kw} what the British people really want? Yes or No?",
        "Should {kw} be a bigger priority for the government? Yes or No?",
        "Does {kw} prove Britain is heading in the wrong direction? Yes or No?",
        "Should the British public have more say on {kw}? Yes or No?",
        "Is {kw} being handled properly? Yes or No?"
    ],
    "events": [
        "Should {kw} be a national holiday? Yes or No?",
        "Should every British person watch {kw}? Yes or No?",
        "Does {kw} make you proud to be British? Yes or No?",
        "Should schools let children watch {kw}? Yes or No?",
        "Is {kw} the greatest event in Britain? Yes or No?"
    ],
    "default": [
        "Should Britain care more about {kw}? Yes or No?",
        "Is {kw} important to modern Britain? Yes or No?",
        "Is {kw} more important now than ever? Yes or No?",
        "Does {kw} make you proud to be British? Yes or No?",
        "Is {kw} being ignored by the government? Yes or No?"
    ]
}

SOURCE_TO_GROUP = {
    "british army": "military", "royal navy": "military", "raf": "military",
    "royal air force": "military", "veterans": "military", "armed forces": "military",
    "armed forces day": "military", "national service": "military",
    "spitfire": "military", "hawker hurricane": "military", "battle of britain": "military",
    "victoria cross": "military", "george cross": "military",
    "king": "royal", "monarchy": "royal", "royal family": "royal",
    "buckingham palace": "royal", "loyal to the crown": "royal",
    "coronation": "events", "trooping the colour": "events",
    "england": "national_identity", "britain": "national_identity",
    "union jack": "national_identity", "british flag": "national_identity",
    "english flag": "national_identity", "st george": "national_identity",
    "patriotism": "national_identity", "national pride": "national_identity",
    "british pride": "national_identity", "national identity": "national_identity",
    "churchill": "history", "winston churchill": "history",
    "dunkirk spirit": "history", "ve day": "history", "d-day": "history",
    "normandy": "history", "british history": "history", "military history": "history",
    "remembrance": "remembrance", "poppy": "remembrance",
    "cenotaph": "remembrance", "war memorial": "remembrance",
    "immigration": "politics", "small boats": "politics",
    "uk politics": "politics", "democracy": "politics", "freedom": "politics",
    "UK Trending": "events"
}

def make_emerging_hooks(keyword, source_keyword):
    group = SOURCE_TO_GROUP.get(source_keyword.lower(), "default")
    templates = EMERGING_HOOK_TEMPLATES.get(group, EMERGING_HOOK_TEMPLATES["default"])
    kw = keyword.title()
    hooks = [t.replace("{kw}", kw) for t in templates]
    return hooks

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

EMOTIONAL_TRIGGERS = [
    "pride", "proud", "shame", "disgrace", "honour", "honor", "sacrifice",
    "hero", "heroes", "heroic", "brave", "bravery", "courage", "courageous",
    "forgotten", "betrayed", "betrayal", "abandoned", "neglected", "ignored",
    "threatened", "under threat", "lost", "losing", "erased", "dying",
    "outrage", "furious", "angry", "anger", "shocking", "unbelievable",
    "heartbreaking", "tragic", "tragedy", "devastating", "powerful",
    "inspiring", "inspirational", "incredible", "amazing", "legendary",
    "never forget", "remember", "remembrance", "memorial", "tribute",
    "duty", "loyalty", "loyal", "devoted", "devotion", "spirit",
    "fight", "fighting", "defend", "defending", "protect", "stand up",
    "freedom", "liberty", "rights", "justice", "truth",
    "identity", "crisis", "collapse", "decline", "broken",
    "love", "hate", "fear", "hope", "faith", "belief", "trust",
    "respect", "disrespect", "honour", "dishonour",
    "greatest", "finest", "worst", "last", "first", "only"
]

DEBATE_TRIGGERS = [
    "should", "is it", "does", "will", "can", "has", "are",
    "yes or no", "agree or disagree", "right or wrong",
    "too far", "gone too far", "not enough", "too much",
    "bring back", "get rid of", "abolish", "ban", "compulsory",
    "still", "anymore", "ever", "never", "always",
    "acceptable", "unacceptable", "wrong", "right",
    "better", "worse", "more", "less",
    "free", "pay", "fund", "tax", "spend",
    "every", "all", "no one", "everyone", "nobody"
]

def score_content_potential(item):
    kw = (item.get("keyword", "") or "").lower()
    question = (item.get("question", "") or "").lower()
    rise = float(item.get("rise_percent", 0) or 0)
    viral = float(item.get("viral_score", 0) or 0)
    source = (item.get("discovery_type", "") or "").lower()
    combined = kw + " " + question

    fresh_score = 0
    if rise > 80:
        fresh_score = 25
    elif rise > 50:
        fresh_score = 22
    elif rise > 30:
        fresh_score = 18
    elif rise > 15:
        fresh_score = 14
    elif rise > 5:
        fresh_score = 10
    elif rise > 0:
        fresh_score = 7
    else:
        fresh_score = 3

    if source in ("news", "twitter", "uk_trending"):
        fresh_score = min(25, fresh_score + 5)
    elif source in ("reddit", "autocomplete"):
        fresh_score = min(25, fresh_score + 3)

    if item.get("category") == "emerging":
        fresh_score = min(25, fresh_score + 4)

    british_score = 0
    strong_hits = 0
    filter_hits = 0
    for w in STRONG_PATRIOTIC_WORDS:
        if w in kw:
            strong_hits += 1
    for w in PATRIOTIC_FILTER_WORDS:
        if w in kw:
            filter_hits += 1

    if strong_hits >= 3:
        british_score = 25
    elif strong_hits >= 2:
        british_score = 22
    elif strong_hits >= 1:
        british_score = 18
    elif filter_hits >= 3:
        british_score = 16
    elif filter_hits >= 2:
        british_score = 13
    elif filter_hits >= 1:
        british_score = 9
    else:
        british_score = 4

    if any(w in kw for w in ["britain", "british", "england", "english", "uk "]):
        british_score = min(25, british_score + 4)

    emotion_score = 0
    emotion_hits = 0
    for trigger in EMOTIONAL_TRIGGERS:
        if trigger in combined:
            emotion_hits += 1

    topic_emotion_words = [
        "veterans", "armed forces", "army", "navy", "raf", "military",
        "remembrance", "poppy", "cenotaph", "memorial", "war",
        "churchill", "spitfire", "dunkirk", "d-day", "ve day", "normandy",
        "sacrifice", "hero", "pride", "patriot", "flag",
        "union jack", "st george", "victoria cross",
        "national service", "coronation", "king charles",
        "immigration", "small boats", "monarchy", "heritage", "tradition"
    ]
    for tw in topic_emotion_words:
        if tw in kw:
            emotion_hits += 1

    if emotion_hits >= 5:
        emotion_score = 25
    elif emotion_hits >= 3:
        emotion_score = 21
    elif emotion_hits >= 2:
        emotion_score = 17
    elif emotion_hits >= 1:
        emotion_score = 12
    else:
        emotion_score = 4

    if any(w in kw for w in ["remembrance", "veterans", "sacrifice", "hero", "pride"]):
        emotion_score = min(25, emotion_score + 5)

    debate_score = 0
    debate_hits = 0
    for trigger in DEBATE_TRIGGERS:
        if trigger in combined:
            debate_hits += 1

    has_question = kw in QUESTIONS
    words = kw.split()
    is_short = len(words) <= 4

    if has_question:
        debate_score += 12
    if debate_hits >= 4:
        debate_score += 10
    elif debate_hits >= 2:
        debate_score += 7
    elif debate_hits >= 1:
        debate_score += 4
    if is_short:
        debate_score += 3

    debate_score = min(25, debate_score)
    if debate_score < 4:
        debate_score = 4

    total = fresh_score + british_score + emotion_score + debate_score

    proven_topics = [
        "immigration", "small boats", "channel",
        "flag", "union jack", "english flag", "st george",
        "veterans", "remembrance", "sacrifice", "poppy", "cenotaph",
        "culture", "identity", "heritage", "tradition", "values",
        "armed forces", "army", "military", "national service"
    ]
    proven_boost = 0
    for pt in proven_topics:
        if pt in kw:
            proven_boost = 8
            break

    controversial = [
        "offend", "ban", "abolish", "compulsory", "prison",
        "deport", "criminal", "reparation", "extreme",
        "erased", "lost", "forgotten", "threat", "dying"
    ]
    controversy_boost = 0
    for cv in controversial:
        if cv in combined:
            controversy_boost = 5
            break

    question_words = ["should", "is ", "does ", "would ", "has ", "can ", "are "]
    is_question = any(q in question.lower() for q in question_words) and "?" in question
    question_boost = 6 if is_question else 0

    total = total + proven_boost + controversy_boost + question_boost

    return {
        "content_score": min(100, total),
        "fresh": fresh_score,
        "british": british_score,
        "emotion": emotion_score,
        "debate": debate_score
    }

def check_tiktok_competition(keyword):
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"}
    try:
        query = f"tiktok {keyword} british"
        url = f"https://suggestqueries.google.com/complete/search?client=firefox&q={query}&hl=en&gl=uk"
        resp = requests.get(url, headers=headers, timeout=8)
        if resp.status_code == 200:
            data = resp.json()
            suggestions = data[1] if len(data) > 1 else []
            return len(suggestions)
        return 5
    except:
        return 5

def score_opportunity_gap(item):
    kw = (item.get("keyword", "") or "").lower()
    viral = float(item.get("viral_score", 0) or 0)
    rise = float(item.get("rise_percent", 0) or 0)
    content_score = int(item.get("content_score", 0) or 0)

    demand = 0
    if viral > 60:
        demand = 10
    elif viral > 40:
        demand = 8
    elif viral > 20:
        demand = 6
    elif viral > 10:
        demand = 4
    else:
        demand = 2

    if rise > 50:
        demand = min(10, demand + 3)
    elif rise > 20:
        demand = min(10, demand + 2)
    elif rise > 0:
        demand = min(10, demand + 1)

    competition = item.get("_tiktok_competition", 5)

    if competition <= 1:
        comp_score = 10
    elif competition <= 3:
        comp_score = 8
    elif competition <= 5:
        comp_score = 5
    elif competition <= 7:
        comp_score = 3
    else:
        comp_score = 1

    words = kw.split()
    if len(words) >= 4:
        comp_score = min(10, comp_score + 2)
    elif len(words) >= 3:
        comp_score = min(10, comp_score + 1)

    niche_words = ["assembly", "cenotaph", "d-day", "normandy", "ve day",
                   "victoria cross", "george cross", "hawker hurricane",
                   "battle of britain", "dunkirk spirit", "trooping",
                   "armed forces day", "national service", "white cliffs"]
    for nw in niche_words:
        if nw in kw:
            comp_score = min(10, comp_score + 2)
            break

    gap = round((demand + comp_score) / 2, 1)

    if gap >= 8:
        label = "High Opportunity"
    elif gap >= 6:
        label = "Good Opportunity"
    elif gap >= 4:
        label = "Moderate"
    else:
        label = "Saturated"

    return {
        "opportunity_gap": gap,
        "opportunity_label": label,
        "demand_score": demand,
        "competition_score": comp_score
    }

def fallback_results():
    fallback = []
    shuffled = list(CONTENT_KEYWORDS)
    random.shuffle(shuffled)
    sample = shuffled[:12]

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
            "question": QUESTIONS.get(keyword, f"Is {keyword.title()} being ignored in modern Britain? Yes or No?"),
            "product": make_product(keyword)
        })

    fallback.sort(key=lambda x: x["viral_score"], reverse=True)
    return fallback

def determine_virality_state(item):
    if not item:
        return "NO_TRACTION"

    rise = float(item.get("rise_percent", 0) or 0)
    content_score = float(item.get("content_score", 0) or 0)
    opportunity_gap = float(item.get("opportunity_gap", 0) or 0)
    platform_count = int(item.get("platform_count", 0) or 0)
    viral_score = float(item.get("viral_score", 0) or 0)
    opportunity_label = item.get("opportunity_label", "")

    growing_signals = 0
    if rise > 0:
        growing_signals += 1
    if rise >= 15:
        growing_signals += 1
    if content_score >= 50:
        growing_signals += 1
    if opportunity_gap >= 6:
        growing_signals += 1
    if platform_count >= 2:
        growing_signals += 1
    if viral_score >= 25:
        growing_signals += 1
    if opportunity_label in ("High Opportunity", "Good Opportunity"):
        growing_signals += 1

    return "GROWING" if growing_signals >= 2 else "NO_TRACTION"

def _format_platform_context(item):
    platforms = item.get("platforms") or []
    if not platforms and item.get("discovery_type"):
        platforms = [item["discovery_type"]]
    if not platforms:
        return ""
    readable = [p.replace("_", " ") for p in platforms]
    if len(readable) == 1:
        return f" on {readable[0]}"
    return f" across {', '.join(readable[:-1])} and {readable[-1]}"

def build_insight_summary(item, state):
    if not item:
        return "No strong patriotic trend signals were detected in this scan cycle."

    keyword = item.get("keyword", "this topic").title()
    rise = float(item.get("rise_percent", 0) or 0)
    content_score = int(item.get("content_score", 0) or 0)
    opportunity_label = item.get("opportunity_label", "Moderate")
    platform_count = int(item.get("platform_count", 0) or 0)
    discovery_type = (item.get("discovery_type") or item.get("category") or "content").replace("_", " ")
    platform_context = _format_platform_context(item)

    if state == "GROWING":
        if platform_count >= 2:
            momentum = f"'{keyword}' is gaining cross-platform attention{platform_context}"
        elif rise >= 15:
            momentum = f"'{keyword}' is accelerating with a {rise:.0f}% rise in recent search interest"
        elif rise > 0:
            momentum = f"'{keyword}' is building momentum with positive search movement"
        else:
            momentum = f"'{keyword}' is surfacing as a strong patriotic conversation topic"

        return (
            f"{momentum}. Content score is {content_score}/100 with {opportunity_label.lower()} "
            f"({discovery_type}). This is a timely window to post before the topic becomes saturated."
        )

    if rise <= 0:
        traction = f"'{keyword}' is visible but not yet climbing"
    else:
        traction = f"'{keyword}' has only light momentum (+{rise:.0f}%)"

    return (
        f"{traction}. Content score is {content_score}/100 and opportunity is {opportunity_label.lower()}. "
        f"Post with a sharper hook or a more debate-led angle to break through."
    )

def load_engagement_metrics():
    metrics = {}
    env_map = {
        "avg_views": "AVG_VIEWS",
        "avg_likes": "AVG_LIKES",
        "engagement_rate": "ENGAGEMENT_RATE",
    }
    for key, env_key in env_map.items():
        value = os.getenv(env_key)
        if value is not None and value != "":
            metrics[key] = float(value)

    metrics_path = "engagement_metrics.json"
    if os.path.exists(metrics_path):
        try:
            with open(metrics_path, encoding="utf-8") as f:
                file_metrics = json.load(f)
            if isinstance(file_metrics, dict):
                for key in env_map:
                    if key in file_metrics and file_metrics[key] is not None:
                        metrics[key] = float(file_metrics[key])
        except (json.JSONDecodeError, TypeError, ValueError) as e:
            print(f"engagement_metrics.json load failed: {e}")

    return metrics or None

def detect_engagement_signal(engagement_metrics):
    if not engagement_metrics:
        return "HEALTHY"

    avg_views = float(engagement_metrics.get("avg_views", 0) or 0)
    avg_likes = float(engagement_metrics.get("avg_likes", 0) or 0)
    engagement_rate = engagement_metrics.get("engagement_rate")

    if avg_views < 300:
        return "DISTRIBUTION_LIMITED"

    if avg_views >= 300 and avg_likes <= 2:
        return "HOOK_OK_LOW_CONVERSION"

    if avg_views >= 300 and engagement_rate is not None and float(engagement_rate) < 1.0:
        return "ATTENTION_WITHOUT_VALUE"

    return "HEALTHY"

def enhance_insight_with_engagement(base_summary, engagement_signal, engagement_metrics=None):
    metrics = engagement_metrics or {}
    avg_views = metrics.get("avg_views")
    avg_likes = metrics.get("avg_likes")
    engagement_rate = metrics.get("engagement_rate")

    metrics_context = ""
    if avg_views is not None:
        metrics_context = f" (avg views: {int(float(avg_views))}"
        if avg_likes is not None:
            metrics_context += f", avg likes: {int(float(avg_likes))}"
        if engagement_rate is not None:
            metrics_context += f", engagement rate: {float(engagement_rate):.2f}%"
        metrics_context += ")"

    if engagement_signal == "HOOK_OK_LOW_CONVERSION":
        return (
            f"{base_summary} Engagement signal: your content is being seen but not liked or saved"
            f"{metrics_context}. The hook is pulling views, but the emotional or value trigger is too weak. "
            f"Strengthen the opening hook and add a clearer pride, sacrifice, or debate payoff in the first 3 seconds."
        )

    if engagement_signal == "ATTENTION_WITHOUT_VALUE":
        return (
            f"{base_summary} Engagement signal: curiosity is high but content delivery is not converting"
            f"{metrics_context}. Viewers are clicking in, but the post is not delivering enough value, emotion, or payoff. "
            f"Tighten the middle of the video and land a stronger opinion or story beat before the call to action."
        )

    if engagement_signal == "DISTRIBUTION_LIMITED":
        return (
            f"{base_summary} Engagement signal: reach is the bottleneck"
            f"{metrics_context}. The content may be fine, but distribution is limited. "
            f"Improve posting time, hashtag targeting, and hook clarity to push average views above 300 before optimizing conversion."
        )

    return (
        f"{base_summary} Engagement signal: performance looks balanced"
        f"{metrics_context}. Views, likes, and engagement rate are in a healthy range relative to current thresholds."
    )

def _recommend_post_format(item):
    discovery_type = (item.get("discovery_type") or "").lower()
    category = (item.get("category") or "").lower()
    debate_score = int(item.get("debate", 0) or 0)
    emotion_score = int(item.get("emotion", 0) or 0)
    platform_count = int(item.get("platform_count", 0) or 0)

    if discovery_type in ("news", "uk_trending", "twitter") or platform_count >= 2:
        return "News reaction clip with bold on-screen headline"
    if debate_score >= 18 or "?" in (item.get("question") or ""):
        return "Yes/No debate post with comment-bait question overlay"
    if emotion_score >= 18:
        return "Emotional talking-head with archive or B-roll cutaways"
    if category == "emerging":
        return "Quick explainer carousel (3-5 slides)"
    if discovery_type in ("reddit", "autocomplete", "creator_search"):
        return "POV response video answering the search question directly"
    return "Short-form patriotic talking-head with text hook in the first 2 seconds"

def build_next_post(item, engagement_signal="HEALTHY"):
    if not item:
        defaults = {
            "HOOK_OK_LOW_CONVERSION": {
                "hook": "Most people get patriotic content wrong — this is why you're not growing.",
                "content_idea": "15-second punch: name the mistake, reveal the fix, end with one emotional British pride trigger. No long intro.",
                "format": "Short curiosity-gap talking-head (under 20 seconds)",
            },
            "ATTENTION_WITHOUT_VALUE": {
                "hook": "Here is the step-by-step truth about building British pride content that actually converts.",
                "content_idea": "3-step breakdown: problem → proof → takeaway. One clear example per step, no vague messaging.",
                "format": "Educational step-by-step explainer with on-screen bullet points",
            },
            "DISTRIBUTION_LIMITED": {
                "hook": "Everyone is talking about this British trend right now — here is the version that spreads.",
                "content_idea": "Ride a broad trend hook, post 2-3 variations same day, use wider patriotic hashtags and a bold first-frame headline.",
                "format": "Trend-reaction clip with viral text overlay and fast cuts",
            },
            "HEALTHY": {
                "hook": "Is British pride still something people are proud to talk about? Yes or No?",
                "content_idea": "Refine your best-performing patriotic theme: sharper hook, stronger save-worthy payoff, explicit share CTA.",
                "format": "Yes/No debate post optimized for saves and shares",
            },
        }
        chosen = defaults.get(engagement_signal, defaults["HEALTHY"])
        return {
            "hook": chosen["hook"],
            "content_idea": chosen["content_idea"],
            "format": chosen["format"],
            "reason_it_will_perform_better": (
                f"Tailored for {engagement_signal.lower().replace('_', ' ')} while waiting for a stronger trend signal."
            ),
            "engagement_signal_used": engagement_signal,
        }

    keyword = item.get("keyword", "").title()
    keyword_lower = item.get("keyword", "").lower()
    hooks = item.get("hooks") or []
    base_hook = item.get("question") or (hooks[0] if hooks else item.get("caption", ""))
    caption = item.get("caption", "")
    product = item.get("product", "patriotic merchandise")
    discovery_type = (item.get("discovery_type") or item.get("category") or "content").replace("_", " ")
    platform_context = _format_platform_context(item).strip()
    if platform_context:
        platform_context = f" {platform_context.capitalize()}."
    else:
        platform_context = f" Trend source: {discovery_type}."

    rise = float(item.get("rise_percent", 0) or 0)
    content_score = int(item.get("content_score", 0) or 0)
    opportunity_gap = float(item.get("opportunity_gap", 0) or 0)
    opportunity_label = item.get("opportunity_label", "Moderate")
    competition_score = int(item.get("competition_score", 0) or 0)
    fresh = int(item.get("fresh", 0) or 0)
    british = int(item.get("british", 0) or 0)
    emotion = int(item.get("emotion", 0) or 0)
    debate = int(item.get("debate", 0) or 0)

    if engagement_signal == "HOOK_OK_LOW_CONVERSION":
        hook = f"Most people get {keyword} wrong — this is why your patriotic content is not converting."
        content_idea = (
            f"Open with a curiosity gap in under 2 seconds: 'Everyone talks about {keyword}, but almost nobody understands this.' "
            f"Deliver one sharp emotional trigger (pride, sacrifice, or outrage) in the next 5 seconds — keep total length under 25 seconds. "
            f"End with a single comment prompt, not a long explanation.{platform_context} "
            f"Caption: {caption}"
        )
        post_format = "Short curiosity-gap hook video (15-25 seconds, fast cuts, bold text overlay)"
        reason = (
            f"Views are landing but likes are not — this shorter, higher-tension hook fixes the conversion gap on '{keyword_lower}'. "
            f"Opportunity gap {opportunity_gap}/10 ({opportunity_label.lower()}), content score {content_score}/100. "
            f"Lead with emotion ({emotion}/25) and debate ({debate}/25) before context."
        )

    elif engagement_signal == "ATTENTION_WITHOUT_VALUE":
        hook = f"The truth about {keyword} — explained in 3 steps most creators skip."
        content_idea = (
            f"Step 1: State the confusion around {keyword} in one sentence. "
            f"Step 2: Give one concrete British example or fact that removes ambiguity. "
            f"Step 3: Land a clear opinion or takeaway — no vague 'what do you think?' without substance. "
            f"Use on-screen labels for each step.{platform_context} "
            f"Optional affiliate tie-in: {product}. Caption: {caption}"
        )
        post_format = "Step-by-step educational breakdown with numbered on-screen steps"
        reason = (
            f"Attention is arriving but value delivery is weak — this structure clarifies the message on '{keyword_lower}' "
            f"and turns curiosity into saves. Content score {content_score}/100, "
            f"debate angle {debate}/25, British relevance {british}/25."
        )

    elif engagement_signal == "DISTRIBUTION_LIMITED":
        hook = f"Why is everyone in Britain suddenly searching {keyword}? (And what it means for you)"
        content_idea = (
            f"Use a broad-appeal trend hook on {keyword} — designed for reach, not depth. "
            f"Post 2-3 variations across the next 48 hours with different opening lines. "
            f"Pair with trending patriotic hashtags, a bold first-frame headline, and a simple yes/no or reaction format.{platform_context} "
            f"Ready caption: {caption}"
        )
        post_format = "Trend-reaction viral format with bold headline overlay and high posting volume"
        reason = (
            f"Reach is the bottleneck — '{keyword_lower}' has "
            f"{'rising search interest (+' + f'{rise:.0f}%)' if rise > 0 else 'topic visibility'} "
            f"and opportunity gap {opportunity_gap}/10 ({opportunity_label.lower()}). "
            f"Broader hooks and higher volume beat polish when average views are below 300."
        )

    else:
        hook = base_hook or f"Is {keyword} still worth fighting for in modern Britain? Yes or No?"
        content_idea = (
            f"Double down on your best-performing angle for {keyword}: refine the existing hook, "
            f"add one save-worthy line (a quote, fact, or bold opinion), and close with an explicit share CTA. "
            f"Keep the format that is already working — tighten pacing and land the emotional peak earlier.{platform_context} "
            f"Optional affiliate tie-in: {product}. Caption: {caption}"
        )
        post_format = _recommend_post_format(item) + " — optimized for saves and shares"
        reason = (
            f"Performance is balanced — refine and repeat what works on '{keyword_lower}'. "
            f"Opportunity gap {opportunity_gap}/10 ({opportunity_label.lower()}), content score {content_score}/100"
        )
        if rise > 0:
            reason += f", search interest rising {rise:.0f}%"
        reason += (
            f", TikTok competition balance {competition_score}/10. "
            f"Strongest themes: Fresh {fresh}, British {british}, Emotion {emotion}, Debate {debate}."
        )

    return {
        "hook": hook,
        "content_idea": content_idea,
        "format": post_format,
        "reason_it_will_perform_better": reason,
        "engagement_signal_used": engagement_signal,
    }

def build_virality_recommendation(results, emerging, engagement_metrics=None):
    """
    Structural recommendation draft used as fallback input for the selector.

    NOT the decision authority — final_recommendation_selector() chooses the winner.
    """
    from recommendation_output import build_recommendation_for_item
    from recommendation_selector import compute_base_score, gather_candidates

    candidates = gather_candidates(results, emerging)
    item = max(candidates, key=compute_base_score) if candidates else None
    return build_recommendation_for_item(item, engagement_metrics)

def save_results(results, emerging, product_trends=None, creator_insights=None):
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
        lines.append(f"Content Score: {item.get('content_score', 0)}/100 (Fresh:{item.get('fresh', 0)} British:{item.get('british', 0)} Emotion:{item.get('emotion', 0)} Debate:{item.get('debate', 0)})")
        lines.append(f"Question: {item['question']}")
        lines.append(f"Caption: {item.get('caption', '')}")
        lines.append(f"Product: {item['product']}")
        lines.append("-" * 50)

    if emerging:
        lines.append("")
        lines.append("EMERGING TOPICS")
        lines.append("=" * 50)
        for item in emerging[:15]:
            lines.append(f"Keyword: {item['keyword']}")
            lines.append(f"Source: {item.get('source_keyword', 'N/A')}")
            lines.append(f"Type: {item.get('discovery_type', 'N/A')}")
            lines.append(f"Viral Score: {item.get('viral_score', 'N/A')}")
            lines.append("-" * 50)

    # Stage 7: Recommendation decision (selector) + humanisation output layer
    engagement_metrics = load_engagement_metrics()
    recommendation = build_virality_recommendation(results, emerging, engagement_metrics)
    from recommendation_output import finalize_recommendation
    from user_calibration import load_performance_posts

    recommendation = finalize_recommendation(
        recommendation,
        results,
        emerging,
        engagement_metrics,
        performance_posts=load_performance_posts(),
    )
    lines.append("")
    lines.append("VIRALITY RECOMMENDATION")
    lines.append("=" * 50)
    lines.append(f"State: {recommendation['state']}")
    lines.append(f"Engagement Signal: {recommendation['engagement_signal']}")
    lines.append(f"Insight: {recommendation['insight_summary']}")
    lines.append(f"Hook: {recommendation['next_post']['hook']}")
    lines.append(f"Content Idea: {recommendation['next_post']['content_idea']}")
    lines.append(f"Format: {recommendation['next_post']['format']}")
    lines.append(f"Engagement Signal Used: {recommendation['next_post'].get('engagement_signal_used', recommendation['engagement_signal'])}")
    lines.append(f"Why it will perform: {recommendation['next_post']['reason_it_will_perform_better']}")

    with open("results.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    output = {
        "state": recommendation["state"],
        "engagement_signal": recommendation["engagement_signal"],
        "insight_summary": recommendation["insight_summary"],
        "next_post": recommendation["next_post"],
        "results": results[:15],
        "emerging": emerging[:15],
        "product_trends": product_trends or [],
        "creator_insights": creator_insights or [],
        "recommendation_meta": recommendation["based_on"],
        "last_updated": now
    }

    with open("results.json", "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)

    print("\n".join(lines))
    print(f"Results saved. {len(results)} main, {len(emerging)} emerging.")

def main():
    print("Starting Patriot Radar scanner...")

    pytrends = TrendReq(hl="en-GB", tz=0)

    shuffled_content = list(CONTENT_KEYWORDS)
    random.shuffle(shuffled_content)
    scan_keywords = shuffled_content[:20]

    product_results = analyse_keywords(pytrends, PRODUCT_KEYWORDS[:5], "product")

    content_results = analyse_keywords(pytrends, scan_keywords, "content")

    all_results = content_results

    if len(all_results) < 5:
        print(f"Only {len(all_results)} live results. Supplementing with fallback data.")
        fallback = fallback_results()
        existing_kws = {r["keyword"] for r in all_results}
        for fb in fallback:
            if fb["keyword"] not in existing_kws:
                all_results.append(fb)
            if len(all_results) >= 12:
                break

    all_results.sort(key=lambda x: x["viral_score"], reverse=True)

    print("Discovering emerging topics...")
    related_discovered = discover_related_keywords(pytrends, CONTENT_KEYWORDS)
    trending_discovered = discover_trending_searches(pytrends)

    print("Scanning Reddit...")
    reddit_discovered = scan_reddit()

    print("Scanning Twitter trends...")
    twitter_discovered = scan_twitter_trends()

    print("Scanning UK news...")
    news_discovered = scan_uk_news()

    print("Scanning Google Autocomplete...")
    autocomplete_discovered, creator_insights = scan_autocomplete()

    all_discovered = related_discovered + trending_discovered + reddit_discovered + twitter_discovered + news_discovered + autocomplete_discovered

    keyword_sources = {}
    for d in all_discovered:
        kw = d["keyword"][:40].lower()
        if kw not in keyword_sources:
            keyword_sources[kw] = {"item": d, "sources": [], "total_rise": 0}
        keyword_sources[kw]["sources"].append(d["discovery_type"])
        keyword_sources[kw]["total_rise"] += d["rise_value"]

    for kw in keyword_sources:
        src_count = len(set(keyword_sources[kw]["sources"]))
        keyword_sources[kw]["cross_platform"] = src_count
        keyword_sources[kw]["item"]["rise_value"] = keyword_sources[kw]["total_rise"]
        keyword_sources[kw]["item"]["platforms"] = list(set(keyword_sources[kw]["sources"]))
        keyword_sources[kw]["item"]["platform_count"] = src_count
        if src_count >= 2:
            keyword_sources[kw]["item"]["rise_value"] *= 2

    seen_kw = set()
    unique_discovered = []
    for kw in sorted(keyword_sources, key=lambda k: keyword_sources[k]["item"]["rise_value"], reverse=True):
        if kw not in seen_kw:
            seen_kw.add(kw)
            unique_discovered.append(keyword_sources[kw]["item"])

    print(f"Found {len(unique_discovered)} emerging topics. Scoring top candidates...")

    scored_emerging = []
    for item in unique_discovered[:10]:
        hooks = make_emerging_hooks(item["keyword"], item["source_keyword"])
        platforms = item.get("platforms", [item["discovery_type"]])
        platform_count = item.get("platform_count", 1)

        base_score = item["rise_value"] / 10
        boosted = base_score * (1 + (platform_count - 1) * 0.5)

        try:
            time.sleep(random.uniform(10, 20))
            scores = score_discovered_keyword(pytrends, item["keyword"])
            if scores:
                boosted = scores["viral_score"] * (1 + (platform_count - 1) * 0.3)
                entry = {
                    "category": "emerging",
                    "keyword": item["keyword"],
                    "latest_score": scores["latest_score"],
                    "recent_avg": scores["recent_avg"],
                    "previous_avg": scores["previous_avg"],
                    "rise_percent": scores["rise_percent"],
                    "viral_score": round(boosted, 1),
                    "source_keyword": item["source_keyword"],
                    "discovery_type": item["discovery_type"],
                    "platforms": platforms,
                    "platform_count": platform_count,
                    "question": hooks[0],
                    "hooks": hooks,
                    "product": make_product(item["keyword"])
                }
                scored_emerging.append(entry)
                continue
        except Exception as e:
            print(f"Scoring failed, using estimate for {item['keyword']}: {e}")

        entry = {
            "category": "emerging",
            "keyword": item["keyword"],
            "latest_score": 0,
            "recent_avg": 0,
            "previous_avg": 0,
            "rise_percent": 0,
            "viral_score": round(boosted, 1),
            "source_keyword": item["source_keyword"],
            "discovery_type": item["discovery_type"],
            "platforms": platforms,
            "platform_count": platform_count,
            "question": hooks[0],
            "hooks": hooks,
            "product": make_product(item["keyword"])
        }
        scored_emerging.append(entry)

    scored_emerging.sort(key=lambda x: x["viral_score"], reverse=True)

    print("Scoring content potential (Fresh + British + Emotion + Debate)...")
    for item in all_results:
        cs = score_content_potential(item)
        item.update(cs)
    for item in scored_emerging:
        cs = score_content_potential(item)
        item.update(cs)

    print("Checking TikTok competition for opportunity gaps...")
    all_to_check = all_results + scored_emerging
    for idx, item in enumerate(all_to_check[:15]):
        comp = check_tiktok_competition(item["keyword"])
        item["_tiktok_competition"] = comp
        og = score_opportunity_gap(item)
        item.update(og)
        if idx < 14:
            time.sleep(0.5)
    for item in all_to_check[15:]:
        item["_tiktok_competition"] = 5
        og = score_opportunity_gap(item)
        item.update(og)

    all_results.sort(key=lambda x: x.get("content_score", 0), reverse=True)

    product_trends = sorted(product_results, key=lambda x: x["viral_score"], reverse=True)

    # Stage 6: Caption engine (deterministic assembly; optional polish)
    enable_polish = os.environ.get("ENABLE_CAPTION_POLISH", "").lower() in ("1", "true", "yes")
    all_results = apply_caption_pipeline(all_results, enable_polish=enable_polish)
    scored_emerging = apply_caption_pipeline(scored_emerging, enable_polish=enable_polish)

    # Stages 7-8: Recommendation decision + output persistence
    save_results(all_results, scored_emerging, product_trends, creator_insights)

if __name__ == "__main__":
    main()
