# Reddit scanner — re-exports from data layer.
# The actual fetching logic lives in alpacalyzer.data.reddit.
# This module exists for backward compatibility within the scanners layer.

from alpacalyzer.data.reddit import fetch_reddit_posts, fetch_user_posts

__all__ = ["fetch_reddit_posts", "fetch_user_posts"]
