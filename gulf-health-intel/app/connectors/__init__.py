"""Connector registry. Import new connector modules here to register them."""
from . import apify, reddit, tabular, x, youtube  # noqa: F401
from .base import REGISTRY, Connector, ConnectorError, FetchRequest, RawComment, RawPost  # noqa: F401
from .urls import detect_platform

# Official APIs are preferred; the provider adapter is the fallback.
_PREFERENCE = ["youtube_api", "reddit_api", "x_api", "apify_provider"]

NO_OFFICIAL_ROUTE = {
    "instagram": "Instagram does not offer official access to comments on accounts you do not manage.",
    "facebook": "Facebook page comments need Meta's Page Public Content Access approval.",
    "tiktok": "TikTok's Research API is limited to eligible academic and non-profit researchers.",
    "web": "Generic websites and forums are not fetched automatically in the MVP.",
}


def connector_for_url(url: str) -> Connector | None:
    for name in _PREFERENCE:
        c = REGISTRY[name]()
        if c.available() and c.supports_url(url):
            return c
    return None


def connectors_for_keywords(platform: str | None) -> list[Connector]:
    out = []
    for name in _PREFERENCE:
        c = REGISTRY[name]()
        if c.available() and c.supports_keywords() and (platform in (None, "", "any") or c.platform == platform):
            out.append(c)
    return out


def unsupported_reason(url: str) -> str:
    plat = detect_platform(url)
    base = NO_OFFICIAL_ROUTE.get(plat, f"No {plat} connector is configured (missing API key?).")
    return base + " Import a CSV/JSON export from a compliant data provider, or configure APIFY_ACTORS."


def status() -> list[dict]:
    out = []
    for name, cls in REGISTRY.items():
        if name == "file_import":
            continue
        c = cls()
        out.append({"name": name, "platform": c.platform, "kind": c.kind, "available": c.available()})
    out.append({"name": "file_import", "platform": "any", "kind": "csv", "available": True})
    return out
