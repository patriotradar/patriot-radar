from pytrends.request import TrendReq
import time

CONTENT_KEYWORDS = [
    "union jack",
    "british army",
    "veterans",
    "armed forces",
    "remembrance",
    "immigration",
    "small boats",
    "uk politics",
    "england",
    "britain",
    "london",
]

AFFILIATE_KEYWORDS = [
    "union jack flag",
    "british history books",
    "military history books",
    "veteran gifts",
    "british clothing",
    "army books",
    "royal navy books",
    "churchill books",
    "uk travel",
]

AUDIENCE_SCORES = {
    "union jack": 15,
    "british army": 12,
    "veterans": 15,
    "armed forces": 15,
    "remembrance": 12,
    "immigration": 10,
    "small boats": 10,
    "uk politics": 8,
    "england": 8,
    "britain": 8,
    "london": 5,
}

AFFILIATE_SCORES = {
    "union jack flag": 10,
    "british history books": 10,
    "military history books": 10,
    "veteran gifts": 9,
    "british clothing": 8,
    "army books": 9,
    "royal navy books": 9,
    "churchill books": 8,
    "uk travel": 5,
}

CONTENT_QUESTIONS = {
    "union jack": "Should every public building fly the Union Jack?",
    "british army": "Should Britain invest more in the British Army?",
    "veterans": "Do veterans receive enough support in Britain?",
    "armed forces": "Do the Armed Forces get the respect they deserve?",
    "remembrance": "Should Remembrance traditions be protected in Britain?",
    "immigration": "Should Britain change its immigration policy?",
    "small boats": "Is Britain doing enough about small boats?",
    "uk politics": "Do UK politics represent ordinary people anymore?",
    "england": "Are you proud to be English?",
    "britain": "Is Britain heading in the right direction?",
    "london": "Is London still the heart of Britain?",
}

AFFILIATE_QUESTIONS = {
    "union jack flag": "Should every patriot own a Union Jack flag?",
    "british history books": "What are the best British history books every patriot should read?",
    "military history books": "What are the best military history books for British patriots?",
    "veteran gifts": "What are the best veteran gifts to show respect?",
    "british clothing": "Would you wear British clothing that shows national pride?",
    "army books": "What army books should every military history fan read?",
    "royal navy books": "What Royal Navy books are worth reading?",
    "churchill books": "Are Churchill books still important for understanding Britain?",
    "uk travel": "What UK travel spots show the best of British history?",
}

AFFILIATE_VIDEO_IDEAS = {
    "union jack flag": "Show 3 ways to display a Union Jack flag at home, in the garden, or at events.",
    "british history books": "Make a video: 3 British history books every patriot should read.",
    "military history books": "Make a video: Top military history books for people who respect the Armed Forces.",
    "veteran gifts": "Make a video: Respectful veteran gifts people can buy to show support.",
    "british clothing": "Make a video: British clothing ideas for people proud of Britain.",
    "army books": "Make a video: Army books for British military history fans.",
    "royal navy books": "Make a video: Royal Navy books worth reading.",
    "churchill books": "Make a video: Churchill books that explain Britain’s wartime history.",
    "uk travel": "Make a video: UK travel places every patriot should visit.",
}

pytrends = TrendReq(hl="en-GB", tz=0)


def analyse_keywords(keywords, extra_scores):
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

            recent_scores = scores[-6:]
            previous_scores = scores[-12:-6]

            recent_avg = sum(recent_scores) / len(recent_scores)
            previous_avg = sum(previous_scores) / len(previous_scores)

            rise = recent_avg - previous_avg

            if previous_avg > 0:
                rise_percent = (rise / previous_avg) * 100
            else:
                rise_percent = 0

            base_score = latest + rise_percent
            extra_score = extra_scores.get(keyword, 0)
            final_score = base_score + extra_score

            results.append({
                "keyword": keyword,
                "latest": round(latest, 1),
                "recent_avg": round(recent_avg, 1),
                "previous_avg": round(previous_avg, 1),
                "rise_percent": round(rise_percent, 1),
                "extra_score": extra_score,
                "final_score": round(final_score, 1),
            })

            time.sleep(1)

        except Exception as e:
            print("Failed:", keyword, e)

    results.sort(key=lambda x: x["final_score"], reverse=True)
    return results


content_results = analyse_keywords(CONTENT_KEYWORDS, AUDIENCE_SCORES)
affiliate_results = analyse_keywords(AFFILIATE_KEYWORDS, AFFILIATE_SCORES)

print("\nTOP CONTENT OPPORTUNITIES\n")

for item in content_results[:5]:
    keyword = item["keyword"]

    print("Keyword:", keyword)
    print("Latest Score:", item["latest"])
    print("Recent Avg:", item["recent_avg"])
    print("Previous Avg:", item["previous_avg"])
    print("Rise %:", item["rise_percent"])
    print("Audience Score:", item["extra_score"])
    print("Final Score:", item["final_score"])
    print("Question:", CONTENT_QUESTIONS.get(keyword, f"What do you think about {keyword}?"))
    print("Caption:", f"{keyword.title()} is being searched today. What do you think?")
    print("-" * 40)

print("\nTOP AFFILIATE OPPORTUNITIES\n")

for item in affiliate_results[:5]:
    keyword = item["keyword"]

    print("Keyword:", keyword)
    print("Latest Score:", item["latest"])
    print("Recent Avg:", item["recent_avg"])
    print("Previous Avg:", item["previous_avg"])
    print("Rise %:", item["rise_percent"])
    print("Affiliate Score:", item["extra_score"])
    print("Final Score:", item["final_score"])
    print("Question:", AFFILIATE_QUESTIONS.get(keyword, f"What do you think about {keyword}?"))
    print("Video Idea:", AFFILIATE_VIDEO_IDEAS.get(keyword, f"Make a video about {keyword}."))
    print("Caption:", f"{keyword.title()} is trending. Would you use or buy this?")
    print("-" * 40)