"""
Final output layer: selection diversity + humanisation pass.

Templates and structural generation stay in trends.py; this module runs after
build_virality_recommendation() to produce creator-ready text.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from copy import deepcopy

HISTORY_FILE = "recommendation_history.json"
HISTORY_LIMIT = 3

BANNED_TERMS = (
    "trend",
    "viral",
    "score",
    "momentum",
    "engagement rate",
    "engagement signal",
    "performance increase",
    "content score",
    "opportunity gap",
    "opportunity label",
    "tiktok competition",
    "search interest",
    "avg views",
    "avg likes",
    "/100",
    "/25",
    "/10",
)

GENERIC_HOOK_MARKERS = (
    "yes or no?",
    "most people get",
    "double down on your best-performing",
    "open with a curiosity gap",
    "step 1:",
    "use a broad-appeal",
    "being ignored in modern britain",
    "still worth fighting for",
    "explained in 3 steps",
    "suddenly searching",
)

FORMAT_FAMILIES = (
    ("debate", ("yes/no", "debate", "comment-bait")),
    ("reaction", ("reaction", "news reaction", "trend-reaction")),
    ("explainer", ("explainer", "step-by-step", "educational", "carousel")),
    ("talking_head", ("talking-head", "talking head", "pov")),
    ("curiosity", ("curiosity-gap", "curiosity gap")),
)


def _candidate_rank_key(item):
    return (
        float(item.get("opportunity_gap", 0) or 0),
        float(item.get("content_score", 0) or 0),
        float(item.get("viral_score", 0) or 0),
    )


def rank_recommendation_candidates(results, emerging):
    candidates = []
    seen = set()
    for item in (results or [])[:5] + (emerging or [])[:5]:
        keyword = (item.get("keyword") or "").lower()
        if keyword and keyword in seen:
            continue
        if keyword:
            seen.add(keyword)
        candidates.append(item)
    return sorted(candidates, key=_candidate_rank_key, reverse=True)


def _stable_index(seed: str, modulo: int) -> int:
    digest = hashlib.md5(seed.encode("utf-8")).hexdigest()
    return int(digest[:8], 16) % modulo


def _format_family(post_format: str) -> str:
    lowered = (post_format or "").lower()
    for family, markers in FORMAT_FAMILIES:
        if any(marker in lowered for marker in markers):
            return family
    if "carousel" in lowered:
        return "explainer"
    if "clip" in lowered:
        return "reaction"
    return "talking_head"


def _dominant_emotion(item) -> str:
    if not item:
        return "pride"
    emotion = int(item.get("emotion", 0) or 0)
    debate = int(item.get("debate", 0) or 0)
    british = int(item.get("british", 0) or 0)
    if debate >= emotion and debate >= 18:
        return "debate"
    if emotion >= 18:
        return "pride"
    if british >= 18:
        return "British identity"
    return "curiosity"


def _emotional_trigger(item, engagement_signal: str, post_format: str) -> str:
    signal_map = {
        "HOOK_OK_LOW_CONVERSION": "curiosity",
        "ATTENTION_WITHOUT_VALUE": "education",
        "DISTRIBUTION_LIMITED": "reach",
        "HEALTHY": _dominant_emotion(item),
    }
    trigger = signal_map.get(engagement_signal, _dominant_emotion(item))
    family = _format_family(post_format)
    if family == "debate":
        return "debate"
    if family == "explainer":
        return "education"
    return trigger


def _topic_angle(keyword: str) -> str:
    kw = keyword.lower().strip()
    angles = {
        "british culture": "traditional British identity",
        "british pride": "what pride actually means to younger Brits",
        "patriotism": "everyday patriotism vs performative flag-waving",
        "national service": "whether service still defines British character",
        "remembrance": "how younger generations relate to remembrance",
        "union jack": "whether the flag still unites or divides",
        "st george": "English identity in a divided UK",
        "veterans": "how we actually treat veterans beyond November",
        "armed forces": "public respect vs real support for service families",
    }
    for key, angle in angles.items():
        if key in kw:
            return angle
    if "british" in kw or "uk" in kw:
        return f"how {keyword} is shifting among younger audiences"
    return f"what people really think about {keyword} right now"


def load_recommendation_history(path: str = HISTORY_FILE) -> list[dict]:
    if not os.path.exists(path):
        return []
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            return data[-HISTORY_LIMIT:]
    except (json.JSONDecodeError, OSError):
        pass
    return []


def save_recommendation_history(entry: dict, path: str = HISTORY_FILE) -> None:
    history = load_recommendation_history(path)
    history.append(entry)
    history = history[-HISTORY_LIMIT:]
    with open(path, "w", encoding="utf-8") as f:
        json.dump(history, f, indent=2)


def _repeats_topic_format(keyword: str, post_format: str, history: list[dict]) -> bool:
    topic = (keyword or "").lower().strip()
    family = _format_family(post_format)
    for past in history:
        if (past.get("keyword") or "").lower().strip() == topic and past.get("format_family") == family:
            return True
    return False


def _repeats_emotional_trigger(trigger: str, history: list[dict]) -> bool:
    if not history:
        return False
    last = history[-1]
    return last.get("emotional_trigger") == trigger


def _is_repetitive(keyword: str, post_format: str, trigger: str, history: list[dict]) -> bool:
    if _repeats_topic_format(keyword, post_format, history):
        return True
    if _repeats_emotional_trigger(trigger, history):
        return True
    return False


def _strip_analytics_language(text: str) -> str:
    if not text:
        return text
    cleaned = text
    replacements = [
        (r"\bcontent score is \d+/100\b", "this topic is resonating right now"),
        (r"\bcontent score \d+/100\b", "this angle is landing with viewers"),
        (r"\bopportunity gap \d+(?:\.\d+)?/10\b", "there is still room to stand out"),
        (r"\bopportunity is [a-z ]+\b", "the conversation is still open"),
        (r"\bengagement signal:?\s*", ""),
        (r"\bperformance (?:looks )?balanced\b", "your posts are getting steady traction"),
        (r"\bsearch interest rising \d+%\b", "more people are talking about this"),
        (r"\bsearch interest\b", "public attention"),
        (r"\btrend source:\s*", "People are discussing this via "),
        (r"\btiktok competition balance \d+/10\b", "not many creators are covering this well yet"),
        (r"\(avg views: [^)]+\)", ""),
        (r"\bemotion \(\d+/25\)\b", "a strong emotional pull"),
        (r"\bdebate \(\d+/25\)\b", "a debate they want to join"),
        (r"\bdebate angle \d+/25\b", "a debate-led angle"),
        (r"\bbritish relevance \d+/25\b", "a British angle your audience cares about"),
        (r"\bstrongest themes: [^.]+\.", ""),
        (r"\btrend hook\b", "timely hook"),
        (r"\bviral\b", "shareable"),
        (r"\btrend\b", "topic"),
        (r"\bviral score\b", ""),
        (r"\bscore\b", ""),
        (r"\bmomentum\b", "buzz"),
        (r"\bengagement rate\b", "how people respond"),
    ]
    for pattern, repl in replacements:
        cleaned = re.sub(pattern, repl, cleaned, flags=re.IGNORECASE)
    for term in BANNED_TERMS:
        cleaned = re.sub(re.escape(term), "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s{2,}", " ", cleaned)
    cleaned = re.sub(r"\s+([,.])", r"\1", cleaned)
    cleaned = re.sub(r"\.\s*\.", ".", cleaned)
    return cleaned.strip()


def _is_generic_hook(hook: str) -> bool:
    lowered = (hook or "").lower()
    return any(marker in lowered for marker in GENERIC_HOOK_MARKERS)


def _humanise_hook(hook: str, keyword: str, item, engagement_signal: str) -> str:
    keyword_title = (keyword or "this").title()
    angle = _topic_angle(keyword)
    seed = f"{keyword}:{engagement_signal}:{hook}"

    question_hooks = [
        f"Why are younger Brits starting to disconnect from {angle}?",
        f"What changed about {keyword_title} — and why is nobody saying it out loud?",
        f"Is {keyword_title} still something people are proud to talk about?",
        f"Why does {keyword_title} hit differently depending on your age?",
    ]
    contrarian_hooks = [
        f"Everyone says {keyword_title} is fading — I think they are reading it wrong.",
        f"Unpopular opinion: {keyword_title} matters more now than people admit.",
        f"Hot take: we talk about {keyword_title} all wrong in Britain.",
    ]
    opinion_hooks = [
        f"{keyword_title} is not dying — it is just changing, and older audiences hate that.",
        f"I will say what a lot of Brits think about {keyword_title} but will not post.",
        f"British audiences are split on {keyword_title}, and that is exactly why it works.",
    ]
    curiosity_hooks = [
        f"Nobody is connecting the dots on {keyword_title} yet.",
        f"The part of {keyword_title} people skip in the comments is the real story.",
        f"Something shifted around {keyword_title} this year — did you notice?",
    ]
    personal_hooks = [
        f"I grew up thinking {keyword_title} meant one thing. Britain changed that.",
        f"As a British creator, {keyword_title} is the post I have been avoiding — until now.",
    ]

    pools = {
        "HOOK_OK_LOW_CONVERSION": curiosity_hooks + question_hooks,
        "ATTENTION_WITHOUT_VALUE": opinion_hooks + personal_hooks,
        "DISTRIBUTION_LIMITED": question_hooks + contrarian_hooks,
        "HEALTHY": question_hooks + contrarian_hooks + opinion_hooks,
    }
    pool = pools.get(engagement_signal, question_hooks + opinion_hooks)

    if _is_generic_hook(hook) or not hook:
        choice = pool[_stable_index(seed, len(pool))]
        return _strip_analytics_language(choice)

    cleaned = hook
    cleaned = re.sub(r"\s*Yes or No\?\s*$", "", cleaned, flags=re.IGNORECASE).strip()
    cleaned = re.sub(r"^Most people get .+ wrong — this is why your patriotic content is not converting\.?$",
                     pool[_stable_index(seed, len(pool))], cleaned, flags=re.IGNORECASE)
    cleaned = _strip_analytics_language(cleaned)
    if _is_generic_hook(cleaned):
        return pool[_stable_index(seed, len(pool))]
    return cleaned


def _humanise_content_idea(raw: str, keyword: str, item, engagement_signal: str) -> str:
    keyword_title = (keyword or "this topic").title()
    angle = _topic_angle(keyword)
    seed = f"{keyword}:{engagement_signal}:idea"

    specific_frames = [
        f"Frame it around {angle} — use one real example from daily British life, then ask viewers which side they are on.",
        f"Open on a split screen: what older Brits assume about {keyword_title} vs what younger audiences actually say in the comments.",
        f"Tell one short story that shows how {keyword_title} shows up in pubs, schools, or family chats — keep it under 30 seconds before the punchline.",
        f"Pick one headline people are already arguing about and answer it with a clear opinion on {keyword_title}, not a vague overview.",
    ]
    signal_frames = {
        "HOOK_OK_LOW_CONVERSION": [
            f"Lead with tension: name the uncomfortable truth about {angle}, deliver one emotional beat (pride, frustration, or nostalgia), then ask one sharp question.",
            f"Skip the intro — start mid-thought on why {keyword_title} makes people defensive, and land the payoff before 20 seconds.",
        ],
        "ATTENTION_WITHOUT_VALUE": [
            f"Three beats only: what people get wrong about {keyword_title}, one concrete example, then your line in the sand.",
            f"Walk through one real scenario involving {angle} so viewers leave with a takeaway they can repeat in the comments.",
        ],
        "DISTRIBUTION_LIMITED": [
            f"Film two versions of the same {keyword_title} opener with different first lines and post both within 48 hours.",
            f"Use a bold on-screen headline about {angle} and keep the edit fast — hook, reaction, one opinion, done.",
        ],
        "HEALTHY": specific_frames,
    }
    frames = signal_frames.get(engagement_signal, specific_frames)
    chosen = frames[_stable_index(seed, len(frames))]

    if not raw or any(
        phrase in raw.lower()
        for phrase in (
            "double down on your best-performing",
            "open with a curiosity gap",
            "use a broad-appeal",
            "step 1:",
            "talk about",
            "refine the existing hook",
            "optional affiliate",
            "caption:",
            "ready caption:",
        )
    ):
        return _strip_analytics_language(chosen)

    cleaned = raw
    cleaned = re.sub(r"Optional affiliate tie-in: [^.]+\.\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"Caption: [^.]+\.\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"Ready caption: [^.]+\.\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"Trend source: [^.]+\.\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = _strip_analytics_language(cleaned)

    if len(cleaned) < 40 or "step 1" in cleaned.lower():
        return _strip_analytics_language(chosen)
    return cleaned


def _humanise_format(post_format: str) -> str:
    if not post_format:
        return "Short talking-head with a bold text hook in the first two seconds"
    cleaned = post_format
    cleaned = re.sub(r"\s*— optimized for saves and shares\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\bviral\b", "shareable", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\btrend-reaction\b", "timely reaction", cleaned, flags=re.IGNORECASE)
    return _strip_analytics_language(cleaned)


def _humanise_reason(
    raw: str,
    keyword: str,
    item,
    engagement_signal: str,
    post_format: str,
) -> str:
    emotion = _dominant_emotion(item)
    family = _format_family(post_format)
    family_labels = {
        "debate": "debate format",
        "reaction": "reaction-style clip",
        "explainer": "clear explainer",
        "talking_head": "direct talking-head",
        "curiosity": "curiosity-led opener",
    }
    format_label = family_labels.get(family, "format")

    signal_reasons = {
        "HOOK_OK_LOW_CONVERSION": (
            f"This works because it leads with tension around {emotion}, which your audience reacts to quickly, "
            f"and uses a {format_label} that invites comments without over-explaining."
        ),
        "ATTENTION_WITHOUT_VALUE": (
            f"This works because viewers already click on {keyword or 'this topic'} — a tighter {format_label} "
            f"with one clear takeaway gives them a reason to stay and save it."
        ),
        "DISTRIBUTION_LIMITED": (
            f"This works because a broader hook on {keyword or 'this topic'} is easier to share, "
            f"and your audience responds when the first frame states the argument plainly."
        ),
        "HEALTHY": (
            f"This works because it taps into {emotion}, which consistently drives strong engagement with your audience, "
            f"and uses a {format_label} they respond to well."
        ),
    }
    reason = signal_reasons.get(engagement_signal, signal_reasons["HEALTHY"])
    reason = _strip_analytics_language(reason)

    sentences = re.split(r"(?<=[.!?])\s+", reason)
    return " ".join(sentences[:2]).strip()


def _humanise_insight(insight_summary: str, item=None, state: str = "NO_TRACTION") -> str:
    if item:
        keyword = (item.get("keyword") or "this topic").title()
        platform_count = int(item.get("platform_count", 0) or 0)
        rise = float(item.get("rise_percent", 0) or 0)

        if state == "GROWING":
            if platform_count >= 2:
                return (
                    f"{keyword} is picking up across multiple platforms — a strong moment to post "
                    f"while people are still forming opinions."
                )
            if rise >= 15:
                return (
                    f"More people are talking about {keyword} right now. "
                    f"Lead with a clear opinion before the conversation gets crowded."
                )
            return (
                f"{keyword} is gaining traction with your audience. "
                f"Post soon with a hook that invites debate or personal reaction."
            )

        if rise > 0:
            return (
                f"{keyword} is on people's radar but has not fully broken through yet. "
                f"A sharper hook or stronger emotional angle should help it land."
            )
        return (
            f"{keyword} is visible but needs a bolder angle. "
            f"Try a contrarian opener or a question your audience cannot ignore."
        )

    if not insight_summary:
        return (
            "No standout patriotic conversation topic surfaced in this scan — "
            "lead with a sharp opinion hook on your strongest theme."
        )
    cleaned = _strip_analytics_language(insight_summary)
    sentences = re.split(r"(?<=[.!?])\s+", cleaned)
    return " ".join(sentences[:2]).strip()


def humanise_next_post(next_post: dict, item, engagement_signal: str) -> dict:
    keyword = (item.get("keyword") if item else "") or ""
    post = deepcopy(next_post or {})
    post_format = _humanise_format(post.get("format", ""))

    post["hook"] = _humanise_hook(post.get("hook", ""), keyword, item, engagement_signal)
    post["content_idea"] = _humanise_content_idea(
        post.get("content_idea", ""), keyword, item, engagement_signal
    )
    post["format"] = post_format
    post["reason_it_will_perform_better"] = _humanise_reason(
        post.get("reason_it_will_perform_better", ""),
        keyword,
        item,
        engagement_signal,
        post_format,
    )
    return post


def select_recommendation_with_diversity(
    results,
    emerging,
    engagement_metrics,
    history,
    build_recommendation_for_item,
):
    """
    Pick the highest-ranked candidate that does not repeat recent topic+format
    or consecutive emotional triggers. Falls back to top pick if all repeat.
    """
    from trends import detect_engagement_signal

    engagement_signal = detect_engagement_signal(engagement_metrics)
    ranked = rank_recommendation_candidates(results, emerging)
    if not ranked:
        return None, engagement_signal

    fallback = None
    for item in ranked:
        draft = build_recommendation_for_item(item, engagement_metrics)
        next_post = draft.get("next_post") or {}
        trigger = _emotional_trigger(
            item, engagement_signal, next_post.get("format", "")
        )
        keyword = item.get("keyword", "")
        post_format = next_post.get("format", "")

        if fallback is None:
            fallback = (item, draft, trigger)

        if not _is_repetitive(keyword, post_format, trigger, history):
            return item, draft, trigger

    item, draft, trigger = fallback
    return item, draft, trigger


def _build_recommendation_for_item(item, engagement_metrics):
    from trends import (
        build_insight_summary,
        build_next_post,
        determine_virality_state,
        detect_engagement_signal,
        enhance_insight_with_engagement,
    )

    state = determine_virality_state(item)
    engagement_signal = detect_engagement_signal(engagement_metrics)
    base_summary = build_insight_summary(item, state)
    insight_summary = enhance_insight_with_engagement(
        base_summary, engagement_signal, engagement_metrics
    )
    return {
        "state": state,
        "engagement_signal": engagement_signal,
        "insight_summary": insight_summary,
        "next_post": build_next_post(item, engagement_signal),
        "based_on": {
            "keyword": item.get("keyword") if item else None,
            "category": item.get("category") if item else None,
            "content_score": item.get("content_score") if item else None,
            "rise_percent": item.get("rise_percent") if item else None,
            "opportunity_gap": item.get("opportunity_gap") if item else None,
            "opportunity_label": item.get("opportunity_label") if item else None,
        },
    }


def finalize_recommendation(
    recommendation: dict,
    results,
    emerging,
    engagement_metrics=None,
    history_path: str = HISTORY_FILE,
) -> dict:
    """
    TEMPLATE → STRUCTURE (from trends.py) → HUMANISATION → FINAL OUTPUT
    """
    history = load_recommendation_history(history_path)

    selected = select_recommendation_with_diversity(
        results,
        emerging,
        engagement_metrics,
        history,
        _build_recommendation_for_item,
    )

    if selected[0] is None:
        final = deepcopy(recommendation)
        item = None
        trigger = "curiosity"
    else:
        item, final, trigger = selected

    engagement_signal = final.get("engagement_signal", "HEALTHY")
    final["insight_summary"] = _humanise_insight(
        final.get("insight_summary", ""), item=item, state=final.get("state", "NO_TRACTION")
    )
    final["next_post"] = humanise_next_post(
        final.get("next_post", {}), item, engagement_signal
    )

    keyword = (item.get("keyword") if item else final.get("based_on", {}).get("keyword")) or ""
    post_format = final["next_post"].get("format", "")

    save_recommendation_history(
        {
            "keyword": keyword,
            "format_family": _format_family(post_format),
            "emotional_trigger": trigger,
            "hook": final["next_post"].get("hook", ""),
        },
        path=history_path,
    )

    return final
