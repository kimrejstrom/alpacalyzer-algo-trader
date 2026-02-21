"""
Reddit data access for fetching posts.

This module provides data-fetching primitives from Reddit that are used
by trading and other packages. The scanning/aggregation logic stays in
scanners/.

See docs/architecture/overview.md for import boundary rules.
"""

from __future__ import annotations

import time

import requests


def fetch_reddit_posts(subreddit: str, limit: int = 50) -> list[dict[str, str]]:
    """Fetch recent Reddit posts from a subreddit, filtered to last 24 hours."""
    url = f"https://www.reddit.com/r/{subreddit}/new.json?limit={limit}"
    return _fetch_and_filter_reddit_posts(url)


def fetch_user_posts(username: str, limit: int = 50) -> list[dict[str, str]]:
    """Fetch recent Reddit posts from a user, filtered to last 24 hours."""
    url = f"https://www.reddit.com/user/{username}/submitted.json?limit={limit}"
    return _fetch_and_filter_reddit_posts(url)


def _fetch_and_filter_reddit_posts(url: str) -> list[dict[str, str]]:
    """Fetch and filter Reddit posts from a given URL."""
    headers = {"User-Agent": "SwingTradeAnalyzer/1.0"}
    response = requests.get(url, headers=headers, timeout=15)

    if response.status_code != 200:
        raise Exception(f"Error fetching Reddit data: {response.status_code}")

    posts = response.json().get("data", {}).get("children", [])
    current_time = time.time()
    last_24_hours = current_time - 86400

    return [
        {
            "title": post["data"]["title"],
            "body": post["data"].get("selftext", "").strip(),
            "created_utc": post["data"]["created_utc"],
        }
        for post in posts
        if post["data"]["created_utc"] >= last_24_hours
    ]
