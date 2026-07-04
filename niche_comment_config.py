"""
Niche configuration for the Niche-Aware Comment Signal system.

Used ONLY by niche_comment_signals.py and related isolated modules.
Does not affect existing trend pipelines or Google Trends logic.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

DEFAULT_CONFIG_PATH = (
    Path(__file__).resolve().parent / "data" / "niche_comment_config.json"
)

# Default niche: British patriotism / history / culture creator space
DEFAULT_NICHE_CONFIG: dict[str, Any] = {
    "niche_id": "british_patriot_culture",
    "label": "British Patriot Culture",
    "keywords": [
        "british",
        "britain",
        "uk",
        "england",
        "patriot",
        "patriotism",
        "veteran",
        "history",
        "heritage",
        "crown",
        "union jack",
        "st george",
        "ww2",
        "dunkirk",
        "churchill",
        "immigration",
        "debate",
        "pride",
        "council estate",
        "working class",
        "northern",
        "manchester",
        "scotland",
        "wales",
    ],
    "excluded_topics": [
        "crypto",
        "nft",
        "onlyfans",
        "giveaway",
        "promo code",
        "affiliate",
        "dropshipping",
        "forex",
        "casino",
        "gambling",
    ],
    "curiosity_phrases": [
        "what is this",
        "what's this",
        "wait what",
        "how do",
        "how does",
        "how did",
        "why is",
        "why does",
        "why did",
        "can someone explain",
        "explain this",
        "i don't understand",
        "i dont understand",
        "confused",
        "what happened",
        "who is",
        "where is",
        "is this real",
        "am i missing",
    ],
}


def load_niche_config(config_path: str | Path | None = None) -> dict[str, Any]:
    """Load niche config from JSON file with env override, falling back to defaults."""
    config = dict(DEFAULT_NICHE_CONFIG)

    path = Path(config_path) if config_path else None
    if path is None:
        env_path = os.getenv("NICHE_COMMENT_CONFIG_PATH")
        path = Path(env_path) if env_path else DEFAULT_CONFIG_PATH

    if path.exists():
        try:
            with open(path, encoding="utf-8") as f:
                file_config = json.load(f)
            if isinstance(file_config, dict):
                for key in ("niche_id", "label", "keywords", "excluded_topics", "curiosity_phrases"):
                    if key in file_config:
                        config[key] = file_config[key]
        except Exception:
            pass

    env_keywords = os.getenv("NICHE_COMMENT_KEYWORDS")
    if env_keywords:
        config["keywords"] = [k.strip() for k in env_keywords.split(",") if k.strip()]

    env_excluded = os.getenv("NICHE_COMMENT_EXCLUDED_TOPICS")
    if env_excluded:
        config["excluded_topics"] = [t.strip() for t in env_excluded.split(",") if t.strip()]

    return config
