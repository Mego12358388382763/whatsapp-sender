"""Connector interface. The only contract between data sources and the core.

A connector yields `RawPost` objects that carry `RawComment`s. These dataclasses
intentionally have NO author/identity fields, so identity can never reach the
database, whatever a source provides.

To add a platform or data provider: subclass `Connector`, decorate it with
`@register`, and import the module in `connectors/__init__.py`.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Iterator


@dataclass
class RawComment:
    text: str
    external_id: str | None = None
    published_at: datetime | None = None
    like_count: int | None = None
    reply_count: int | None = None
    is_reply: bool = False


@dataclass
class RawPost:
    platform: str
    url: str
    community_url: str
    community_name: str
    external_id: str | None = None
    title: str | None = None
    text: str | None = None
    published_at: datetime | None = None
    like_count: int | None = None
    comment_count: int | None = None
    share_count: int | None = None
    view_count: int | None = None
    community_country: str | None = None  # ISO-2, when the source row states it
    community_city: str | None = None
    comments: list[RawComment] = field(default_factory=list)


@dataclass
class FetchRequest:
    urls: list[str] = field(default_factory=list)
    keywords: list[str] = field(default_factory=list)
    country: str | None = None  # ISO-2: SA AE KW QA BH OM
    city: str | None = None
    platform: str | None = None
    date_from: datetime | None = None
    date_to: datetime | None = None
    max_posts: int = 20
    max_comments_per_post: int = 300
    language: str | None = "ar"


class ConnectorError(RuntimeError):
    pass


class Connector(ABC):
    name: str = "base"
    platform: str = "other"
    kind: str = "api"  # api | provider | csv

    def available(self) -> bool:
        """True when required credentials are configured."""
        return True

    def supports_url(self, url: str) -> bool:
        return False

    def supports_keywords(self) -> bool:
        return False

    @abstractmethod
    def fetch(self, req: FetchRequest) -> Iterator[RawPost]: ...


REGISTRY: dict[str, type[Connector]] = {}


def register(cls: type[Connector]) -> type[Connector]:
    REGISTRY[cls.name] = cls
    return cls


def in_range(dt: datetime | None, req: FetchRequest) -> bool:
    if dt is None:
        return True
    if req.date_from and dt < req.date_from:
        return False
    if req.date_to and dt > req.date_to:
        return False
    return True


def parse_dt(value) -> datetime | None:
    """Parse ISO strings, epoch seconds/ms, or common date formats to naive UTC."""
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        return value.replace(tzinfo=None)
    if isinstance(value, (int, float)) or (isinstance(value, str) and value.strip().isdigit()):
        v = float(value)
        if v > 1e12:
            v /= 1000
        from datetime import timezone

        return datetime.fromtimestamp(v, tz=timezone.utc).replace(tzinfo=None)
    s = str(value).strip().replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(s)
        if dt.tzinfo:
            from datetime import timezone

            dt = dt.astimezone(timezone.utc)
        return dt.replace(tzinfo=None)
    except ValueError:
        pass
    for fmt in ("%Y-%m-%d %H:%M:%S", "%d/%m/%Y %H:%M", "%d/%m/%Y", "%m/%d/%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    return None


def to_int(value) -> int | None:
    if value in (None, ""):
        return None
    try:
        s = str(value).replace(",", "").strip().upper()
        mult = 1
        if s.endswith("K"):
            mult, s = 1000, s[:-1]
        elif s.endswith("M"):
            mult, s = 1_000_000, s[:-1]
        return int(float(s) * mult)
    except (TypeError, ValueError):
        return None
