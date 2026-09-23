"""Platform detection and URL parsing."""
from __future__ import annotations

import re
from urllib.parse import parse_qs, urlparse

PLATFORMS = ["instagram", "facebook", "tiktok", "youtube", "reddit", "x", "web"]

_HOSTS = {
    "instagram": ("instagram.com",),
    "facebook": ("facebook.com", "fb.com", "fb.watch"),
    "tiktok": ("tiktok.com",),
    "youtube": ("youtube.com", "youtu.be"),
    "reddit": ("reddit.com", "redd.it"),
    "x": ("x.com", "twitter.com"),
}


def detect_platform(url: str) -> str:
    host = (urlparse(url if "://" in url else f"https://{url}").hostname or "").lower()
    for platform, hosts in _HOSTS.items():
        if any(host == h or host.endswith("." + h) for h in hosts):
            return platform
    return "web"


def url_kind(url: str) -> str:
    """'post' or 'community' (page/profile/channel/subreddit)."""
    p = urlparse(url if "://" in url else f"https://{url}")
    path = p.path.rstrip("/")
    plat = detect_platform(url)
    if plat == "youtube":
        return "post" if youtube_video_id(url) else "community"
    if plat == "reddit":
        return "post" if "/comments/" in path else "community"
    if plat == "x":
        return "post" if "/status/" in path else "community"
    if plat == "instagram":
        return "post" if re.search(r"/(p|reel|reels|tv)/", path) else "community"
    if plat == "tiktok":
        return "post" if "/video/" in path else "community"
    if plat == "facebook":
        return "post" if re.search(r"/(posts|videos|reel|permalink|photo|story\.php)", path + "?" + p.query) else "community"
    return "post"


def youtube_video_id(url: str) -> str | None:
    p = urlparse(url if "://" in url else f"https://{url}")
    if p.hostname and p.hostname.endswith("youtu.be"):
        return p.path.strip("/") or None
    if p.path == "/watch":
        return (parse_qs(p.query).get("v") or [None])[0]
    m = re.match(r"^/(shorts|live|embed)/([\w-]{6,})", p.path)
    return m.group(2) if m else None


def youtube_channel_ref(url: str) -> tuple[str, str] | None:
    """Return ('handle', '@x') or ('id', 'UC...') for channel URLs."""
    path = urlparse(url if "://" in url else f"https://{url}").path
    m = re.match(r"^/(@[\w.-]+)", path)
    if m:
        return ("handle", m.group(1))
    m = re.match(r"^/channel/([\w-]+)", path)
    if m:
        return ("id", m.group(1))
    return None


def reddit_subreddit(url: str) -> str | None:
    m = re.search(r"/r/([\w]+)", urlparse(url).path)
    return m.group(1) if m else None


def reddit_post_id(url: str) -> str | None:
    m = re.search(r"/comments/([a-z0-9]+)", urlparse(url).path)
    return m.group(1) if m else None


def x_status_id(url: str) -> str | None:
    m = re.search(r"/status/(\d+)", urlparse(url).path)
    return m.group(1) if m else None


def x_handle(url: str) -> str | None:
    m = re.match(r"^/([A-Za-z0-9_]{1,15})(/|$)", urlparse(url).path)
    return m.group(1) if m else None


def community_from_post_url(url: str) -> tuple[str, str]:
    """Best-effort (community_url, community_name) for a post URL."""
    p = urlparse(url if "://" in url else f"https://{url}")
    plat = detect_platform(url)
    base = f"{p.scheme or 'https'}://{p.hostname}"
    parts = [x for x in p.path.split("/") if x]
    if plat == "reddit" and (sub := reddit_subreddit(url)):
        return f"https://www.reddit.com/r/{sub}", f"r/{sub}"
    if plat in ("x", "tiktok") and parts:
        return f"{base}/{parts[0]}", parts[0]
    if plat == "facebook" and parts and parts[0] not in ("permalink.php", "story.php", "watch"):
        return f"{base}/{parts[0]}", parts[0]
    return f"{base}/", p.hostname or "unknown"
