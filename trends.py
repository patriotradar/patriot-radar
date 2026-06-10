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

def scan_reddit():
    discovered = []
    subreddits = ["unitedkingdom", "CasualUK", "ukpolitics", "BritishMilitary", "AskUK"]
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"}

    for sub in subreddits:
        try:
            url = f"https://old.reddit.com/r/{sub}/hot/.json?limit=25"
            resp = requests.get(url, headers=headers, timeout=10)
            if resp.status_code != 200:
                print(f"Reddit r/{sub}: HTTP {resp.status_code}")
                continue

            posts = resp.json().get("data", {}).get("children", [])
            for post in posts:
                data = post.get("data", {})
                title = data.get("title", "").lower()
                score = data.get("score", 0)
                num_comments = data.get("num_comments", 0)

                if score < 50:
                    continue

                if is_patriotic_relevant(title) and title not in ALL_KNOWN_KEYWORDS:
                    words = title.split()
                    clean_title = " ".join(words[:10]) if len(words) > 10 else title
                    clean_title = clean_title[:60].strip()
                    if len(clean_title) > 10:
                        engagement = score + (num_comments * 3)
                        discovered.append({
                            "keyword": clean_title,
                            "source_keyword": f"Reddit r/{sub}",
                            "rise_value": min(500, engagement),
                            "discovery_type": "reddit",
                            "reddit_score": score,
                            "reddit_comments": num_comments
                        })

            time.sleep(1)

        except Exception as e:
            print(f"Reddit r/{sub} failed: {e}")

    discovered.sort(key=lambda x: x["rise_value"], reverse=True)
    return discovered[:10]

def scan_twitter_trends():
    discovered = []
    try:
        url = "https://trends24.in/united-kingdom/"
        headers = {"User-Agent": "PatriotRadar/1.0"}
        resp = requests.get(url, headers=headers, timeout=10)

        if resp.status_code == 200:
            import re
            trends = re.findall(r'<a[^>]*class="trend-link"[^>]*>([^<]+)</a>', resp.text)
            if not trends:
                trends = re.findall(r'>#([^<]+)</a>', resp.text)

            for trend in trends[:30]:
                t = trend.strip().lower().replace("#", "")
                if t and is_patriotic_relevant(t) and t not in ALL_KNOWN_KEYWORDS:
                    discovered.append({
                        "keyword": t[:60],
                        "source_keyword": "Twitter UK",
                        "rise_value": 250,
                        "discovery_type": "twitter"
                    })
    except Exception as e:
        print(f"Twitter trends failed: {e}")

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

    seen = set()
    unique = []
    for d in discovered:
        if d["keyword"] not in seen:
            seen.add(d["keyword"])
            unique.append(d)

    return unique[:8]

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
        "movies", "movie", "drink", "knife", "login", "shirt"
    ]
    seeds = CONTENT_KEYWORDS[:15] + creator_seeds

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
                    is_relevant = is_patriotic_relevant(s) or is_creator_seed
                    if s != seed and s not in ALL_KNOWN_KEYWORDS and len(s) > 10 and is_relevant:
                        words = s.split()
                        clean = " ".join(words[:8]) if len(words) > 8 else s
                        discovered.append({
                            "keyword": clean[:60],
                            "source_keyword": seed,
                            "rise_value": 150,
                            "discovery_type": "autocomplete"
                        })
            time.sleep(1)
        except Exception as e:
            print(f"Autocomplete failed for {seed}: {e}")

    seen = set()
    unique = []
    for d in discovered:
        if d["keyword"] not in seen:
            seen.add(d["keyword"])
            unique.append(d)

    return unique[:10]

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
            "question": QUESTIONS.get(keyword, f"Is {keyword.title()} being ignored in modern Britain? Yes or No?"),
            "caption": make_caption(keyword),
            "product": make_product(keyword)
        })

    fallback.sort(key=lambda x: x["viral_score"], reverse=True)
    return fallback

def save_results(results, emerging, product_trends=None):
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
        "product_trends": product_trends or [],
        "last_updated": now
    }

    with open("results.json", "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)

    print("\n".join(lines))
    print(f"Results saved. {len(results)} main, {len(emerging)} emerging.")

def main():
    print("Starting Patriot Radar scanner...")

    pytrends = TrendReq(hl="en-GB", tz=0)

    product_results = analyse_keywords(pytrends, PRODUCT_KEYWORDS[:10], "product")

    content_results = analyse_keywords(pytrends, CONTENT_KEYWORDS, "content")

    all_results = content_results

    if not all_results:
        print("No live Google Trends results. Using fallback results.")
        all_results = fallback_results()

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
    autocomplete_discovered = scan_autocomplete()

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
            time.sleep(3)
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

    product_trends = sorted(product_results, key=lambda x: x["viral_score"], reverse=True)

    save_results(all_results, scored_emerging, product_trends)

if __name__ == "__main__":
    main()
