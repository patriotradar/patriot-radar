"""Provider registry — ordered by priority."""

from __future__ import annotations

from trend_intelligence_engine.providers.base import TrendProvider
from trend_intelligence_engine.providers.blog_provider import BlogProvider
from trend_intelligence_engine.providers.forum_provider import ForumProvider
from trend_intelligence_engine.providers.google_trends_provider import GoogleTrendsProvider
from trend_intelligence_engine.providers.historical_provider import HistoricalProvider
from trend_intelligence_engine.providers.news_provider import NewsProvider
from trend_intelligence_engine.providers.reddit_provider import RedditProvider
from trend_intelligence_engine.providers.social_provider import SocialProvider
from trend_intelligence_engine.providers.tiktok_provider import TikTokApifyProvider
from trend_intelligence_engine.providers.youtube_provider import YouTubeProvider


def get_all_providers() -> list[TrendProvider]:
    """Return all providers sorted by priority (lowest number first)."""
    providers: list[TrendProvider] = [
        TikTokApifyProvider(),
        GoogleTrendsProvider(),
        RedditProvider(),
        YouTubeProvider(),
        NewsProvider(),
        BlogProvider(),
        ForumProvider(),
        SocialProvider(),
        HistoricalProvider(),
    ]
    return sorted(providers, key=lambda p: p.priority)


def get_provider_map() -> dict[str, TrendProvider]:
    return {p.name: p for p in get_all_providers()}
