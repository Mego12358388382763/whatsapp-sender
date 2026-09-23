"""YouTube Data API v3 connector (official, API key).

Quota (default 10k units/day): search.list = 100 units, videos/channels/
playlistItems/commentThreads.list = 1 unit per page. Comment author fields
returned by the API are ignored.
"""
from __future__ import annotations

from typing import Iterator

import httpx

from ..config import settings
from .base import Connector, ConnectorError, FetchRequest, RawComment, RawPost, in_range, parse_dt, register, to_int
from .urls import detect_platform, url_kind, youtube_channel_ref, youtube_video_id

API = "https://www.googleapis.com/youtube/v3"


@register
class YouTubeConnector(Connector):
    name = "youtube_api"
    platform = "youtube"
    kind = "api"

    def __init__(self, api_key: str | None = None, client: httpx.Client | None = None):
        self.api_key = api_key if api_key is not None else settings.youtube_api_key
        self.client = client or httpx.Client(timeout=30)

    def available(self) -> bool:
        return bool(self.api_key)

    def supports_url(self, url: str) -> bool:
        return detect_platform(url) == "youtube"

    def supports_keywords(self) -> bool:
        return True

    def _get(self, endpoint: str, **params) -> dict:
        params["key"] = self.api_key
        r = self.client.get(f"{API}/{endpoint}", params=params)
        if r.status_code == 403 and "commentsDisabled" in r.text:
            return {"items": []}
        if r.status_code >= 400:
            raise ConnectorError(f"YouTube API {endpoint} {r.status_code}: {r.text[:300]}")
        return r.json()

    # ---- discovery -------------------------------------------------------
    def _channel_id(self, url: str) -> str:
        ref = youtube_channel_ref(url)
        if not ref:
            raise ConnectorError(f"Unrecognised YouTube channel URL: {url}")
        kind, value = ref
        if kind == "id":
            return value
        data = self._get("channels", part="id", forHandle=value)
        items = data.get("items") or []
        if not items:
            raise ConnectorError(f"YouTube channel not found: {value}")
        return items[0]["id"]

    def _channel_video_ids(self, channel_id: str, req: FetchRequest) -> list[str]:
        ch = self._get("channels", part="contentDetails", id=channel_id)
        items = ch.get("items") or []
        if not items:
            return []
        uploads = items[0]["contentDetails"]["relatedPlaylists"]["uploads"]
        ids: list[str] = []
        token = None
        while len(ids) < req.max_posts:
            params = {"part": "contentDetails", "playlistId": uploads, "maxResults": 50}
            if token:
                params["pageToken"] = token
            data = self._get("playlistItems", **params)
            for it in data.get("items", []):
                dt = parse_dt(it["contentDetails"].get("videoPublishedAt"))
                if req.date_from and dt and dt < req.date_from:
                    return ids  # uploads are newest-first
                if in_range(dt, req):
                    ids.append(it["contentDetails"]["videoId"])
            token = data.get("nextPageToken")
            if not token:
                break
        return ids[: req.max_posts]

    def _search_video_ids(self, req: FetchRequest) -> list[str]:
        params = {
            "part": "id",
            "type": "video",
            "q": " | ".join(req.keywords),
            "maxResults": min(50, req.max_posts),
            "order": "relevance",
        }
        if req.country:
            params["regionCode"] = req.country
        if req.language:
            params["relevanceLanguage"] = req.language
        if req.date_from:
            params["publishedAfter"] = req.date_from.strftime("%Y-%m-%dT%H:%M:%SZ")
        if req.date_to:
            params["publishedBefore"] = req.date_to.strftime("%Y-%m-%dT%H:%M:%SZ")
        data = self._get("search", **params)
        return [it["id"]["videoId"] for it in data.get("items", []) if it.get("id", {}).get("videoId")]

    # ---- fetching --------------------------------------------------------
    def _videos(self, ids: list[str]) -> list[dict]:
        out: list[dict] = []
        for i in range(0, len(ids), 50):
            data = self._get("videos", part="snippet,statistics", id=",".join(ids[i : i + 50]))
            out.extend(data.get("items", []))
        return out

    def _comments(self, video_id: str, req: FetchRequest) -> list[RawComment]:
        out: list[RawComment] = []
        token = None
        while len(out) < req.max_comments_per_post:
            params = {"part": "snippet,replies", "videoId": video_id, "maxResults": 100,
                      "textFormat": "plainText", "order": "relevance"}
            if token:
                params["pageToken"] = token
            data = self._get("commentThreads", **params)
            for th in data.get("items", []):
                top = th["snippet"]["topLevelComment"]
                sn = top["snippet"]
                dt = parse_dt(sn.get("publishedAt"))
                if in_range(dt, req):
                    out.append(RawComment(text=sn.get("textOriginal") or sn.get("textDisplay") or "",
                                          external_id=top.get("id"), published_at=dt,
                                          like_count=to_int(sn.get("likeCount")),
                                          reply_count=to_int(th["snippet"].get("totalReplyCount"))))
                for rep in (th.get("replies") or {}).get("comments", []):
                    rs = rep["snippet"]
                    rdt = parse_dt(rs.get("publishedAt"))
                    if in_range(rdt, req):
                        out.append(RawComment(text=rs.get("textOriginal") or rs.get("textDisplay") or "",
                                              external_id=rep.get("id"), published_at=rdt,
                                              like_count=to_int(rs.get("likeCount")), is_reply=True))
            token = data.get("nextPageToken")
            if not token:
                break
        return out[: req.max_comments_per_post]

    def fetch(self, req: FetchRequest) -> Iterator[RawPost]:
        if not self.available():
            raise ConnectorError("YOUTUBE_API_KEY is not configured")
        ids: list[str] = []
        for url in req.urls:
            if detect_platform(url) != "youtube":
                continue
            if url_kind(url) == "post":
                vid = youtube_video_id(url)
                if vid:
                    ids.append(vid)
            else:
                ids.extend(self._channel_video_ids(self._channel_id(url), req))
        if req.keywords and not req.urls:
            ids.extend(self._search_video_ids(req))
        seen: set[str] = set()
        ids = [i for i in ids if not (i in seen or seen.add(i))]
        for v in self._videos(ids):
            sn, st = v["snippet"], v.get("statistics", {})
            yield RawPost(
                platform="youtube",
                url=f"https://www.youtube.com/watch?v={v['id']}",
                community_url=f"https://www.youtube.com/channel/{sn['channelId']}",
                community_name=sn.get("channelTitle") or sn["channelId"],
                external_id=v["id"],
                title=sn.get("title"),
                text=(sn.get("description") or "")[:2000],
                published_at=parse_dt(sn.get("publishedAt")),
                like_count=to_int(st.get("likeCount")),
                comment_count=to_int(st.get("commentCount")),
                view_count=to_int(st.get("viewCount")),
                comments=self._comments(v["id"], req),
            )
