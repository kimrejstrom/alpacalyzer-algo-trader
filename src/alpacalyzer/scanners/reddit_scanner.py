# Fetch Reddit posts
import time

import requests


def fetch_reddit_posts(subreddit: str, limit: int = 50) -> list[dict[str, str]]:
    """
    Fetch recent Reddit posts from a given subreddit and filter only those from the last 24 hours.

    Args:
        subreddit (str): The name of the subreddit.
        limit (int): The maximum number of posts to retrieve.

    Returns:
        List[Dict[str, str]]: A list of dictionaries containing post titles and bodies.
    """
    url = f"https://www.reddit.com/r/{subreddit}/new.json?limit={limit}"
    return _fetch_and_filter_reddit_posts(url)


def fetch_user_posts(username: str, limit: int = 50) -> list[dict[str, str]]:
    """
    Fetch recent Reddit posts from a specific user and filter only those from the last 24 hours.

    Args:
        username (str): The Reddit username.
        limit (int): The maximum number of posts to retrieve.

    Returns:
        List[Dict[str, str]]: A list of dictionaries containing post titles and bodies.
    """
    url = f"https://www.reddit.com/user/{username}/submitted.json?limit={limit}"
    return _fetch_and_filter_reddit_posts(url)


def _fetch_and_filter_reddit_posts(url: str) -> list[dict[str, str]]:
    """
    Helper function to fetch and filter Reddit posts from a given URL.

    Args:
        url (str): The Reddit API URL to fetch posts from.

    Returns:
        List[Dict[str, str]]: A list of filtered posts.
    """
    headers = {"User-Agent": "SwingTradeAnalyzer/1.0"}
    response = requests.get(url, headers=headers, timeout=15)

    if response.status_code != 200:
        raise Exception(f"Error fetching Reddit data: {response.status_code}")

    posts = response.json().get("data", {}).get("children", [])
    current_time = time.time()
    last_24_hours = current_time - 86400  # 24 hours in seconds

    # Filter posts within the last 24 hours
    return [
        {
            "title": post["data"]["title"],
            "body": post["data"].get("selftext", "").strip(),
            "created_utc": post["data"]["created_utc"],
        }
        for post in posts
        if post["data"]["created_utc"] >= last_24_hours
    ]
