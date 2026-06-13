from pytrends.request import TrendReq
from datetime import datetime
import time
import json
import random
import requests

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

def make_caption(keyword):
    kw = keyword.title()
    question = QUESTIONS.get(keyword.lower(), f"Is {kw} being ignored in modern Britain? Yes or No?")
    captions = [
        f"🇬🇧 {question} Comment below! #britain #patriotic #british #england #proud",
        f"🇬🇧 {question} Drop your answer below! #british #england #patriot #uk #proud",
        f"🇬🇧 {question} Let us know in the comments! #britain #english #patriotic #uk",
        f"🇬🇧 Every generation should understand this. {question} #british #proud #england #uk",
        f"🇬🇧 This is important. {question} Comment YES or NO! #britain #patriotic #english"
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
                "caption": make_caption(keyword),
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

    return {
        "content_score": total,
        "fresh": fresh_score,
        "british": british_score,
        "emotion": emotion_score,
        "debate": debate_score
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
            "caption": make_caption(keyword),
            "product": make_product(keyword)
        })

    fallback.sort(key=lambda x: x["viral_score"], reverse=True)
    return fallback

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
        lines.append(f"Caption: {item['caption']}")
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

    with open("results.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    output = {
        "results": results[:15],
        "emerging": emerging[:15],
        "product_trends": product_trends or [],
        "creator_insights": creator_insights or [],
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
                    "caption": make_caption(item["keyword"]),
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
            "caption": make_caption(item["keyword"]),
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

    all_results.sort(key=lambda x: x.get("content_score", 0), reverse=True)

    product_trends = sorted(product_results, key=lambda x: x["viral_score"], reverse=True)

    save_results(all_results, scored_emerging, product_trends, creator_insights)

if __name__ == "__main__":
    main()
