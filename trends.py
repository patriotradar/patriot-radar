from pytrends.request import TrendReq
import time
from datetime import datetime

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
    "british history",
    "military history",
    "veteran gifts",
    "british clothing",
    "army",
    "royal navy",
    "churchill",
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
    "british history": 10,
    "military history": 10,
    "veteran gifts": 9,
    "british clothing": 8,
    "army": 8,
    "royal navy": 8,
    "churchill": 8,
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
    "british history": "What British history should every patriot know?",
    "military history": "What military history should every British patriot learn?",
    "veteran gifts": "What veteran gifts show real respect?",
    "british clothing": "Would you wear British clothing that shows national pride?",
    "army": "What army history should every Brit know?",
    "royal navy": "What Royal Navy history are you proud of?",
    "churchill": "Is Churchill still important to British history?",
    "uk travel": "What UK travel places show the best of British history?",
}

AFFILIATE_VIDEO_IDEAS = {
    "union jack flag": "Show 3 ways to display a Union Jack flag at home, in the garden, or at events.",
    "british history": "Make a video about British history books, documentaries, or heritage products.",
    "military history": "Make a video about military history books or documentaries.",
    "veteran gifts": "Make a video about respectful veteran gifts people can buy to show support.",
    "british clothing": "Make a video about British clothing ideas for people proud of Britain.",
    "army": "Make a video about army books, military fitness, or British Army history.",
    "royal navy": "Make a video about Royal Navy books or naval history.",
    "churchill": "Make a video about Churchill books or wartime history.",
    "uk travel": "Make a video about UK heritage places every patriot should visit.",
}

output_lines = []


def add_line(text=""):
    print(text)
    output_lines.append(str(text))


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

            confidence_score = (latest * 0.7) + (rise_percent * 0.3)
            extra_score = extra_scores.get(keyword, 0)
            final_score = confidence_score + extra_score

            results.append({
                "keyword": keyword,
                "latest": round(latest, 1),
                "recent_avg": round(recent_avg, 1),
                "previous_avg": round(previous_avg, 1),
                "rise_percent": round(rise_percent, 1),
                "extra_score": extra_score,
                "final_score": round(final_score, 1),
            })

            time.sleep(3)

        except Exception as e:
            add_line(f"Failed: {keyword} - {e}")

    results.sort(key=lambda x: x["final_score"], reverse=True)
    return results


content_results = analyse_keywords(CONTENT_KEYWORDS, AUDIENCE_SCORES)
affiliate_results = analyse_keywords(AFFILIATE_KEYWORDS, AFFILIATE_SCORES)

add_line("PATRIOT RADAR RESULTS")
add_line(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
add_line("=" * 50)

add_line("\nTOP CONTENT OPPORTUNITIES\n")

for item in content_results[:5]:
    keyword = item["keyword"]

    add_line(f"Keyword: {keyword}")
    add_line(f"Latest Score: {item['latest']}")
    add_line(f"Recent Avg: {item['recent_avg']}")
    add_line(f"Previous Avg: {item['previous_avg']}")
    add_line(f"Rise %: {item['rise_percent']}")
    add_line(f"Audience Score: {item['extra_score']}")
    add_line(f"Final Score: {item['final_score']}")
    add_line(f"Question: {CONTENT_QUESTIONS.get(keyword, f'What do you think about {keyword}?')}")
    add_line(f"Caption: {keyword.title()} is being searched today. What do you think?")
    add_line("-" * 40)

add_line("\nTOP AFFILIATE OPPORTUNITIES\n")

for item in affiliate_results[:5]:
    keyword = item["keyword"]

    add_line(f"Keyword: {keyword}")
    add_line(f"Latest Score: {item['latest']}")
    add_line(f"Recent Avg: {item['recent_avg']}")
    add_line(f"Previous Avg: {item['previous_avg']}")
    add_line(f"Rise %: {item['rise_percent']}")
    add_line(f"Affiliate Score: {item['extra_score']}")
    add_line(f"Final Score: {item['final_score']}")
    add_line(f"Question: {AFFILIATE_QUESTIONS.get(keyword, f'What do you think about {keyword}?')}")
    add_line(f"Video Idea: {AFFILIATE_VIDEO_IDEAS.get(keyword, f'Make a video about {keyword}.')}")
    add_line(f"Caption: {keyword.title()} is trending. Would you use or buy this?")
    add_line("-" * 40)

with open("results.txt", "w", encoding="utf-8") as f:
    f.write("\n".join(output_lines))

add_line("Results saved to results.txt")
