import json
from datetime import datetime

import httpx
from sqlalchemy import func, select

from app.connectors import unsupported_reason
from app.connectors.base import FetchRequest
from app.connectors.reddit import RedditConnector
from app.connectors.tabular import TabularImport, load_records, records_to_posts
from app.connectors.urls import detect_platform, url_kind, youtube_video_id
from app.connectors.youtube import YouTubeConnector
from app.ingest import run_connector
from app.models import Comment, Community, Post


def test_url_detection():
    assert detect_platform("https://www.instagram.com/p/abc/") == "instagram"
    assert url_kind("https://www.instagram.com/p/abc/") == "post"
    assert url_kind("https://www.instagram.com/somepage/") == "community"
    assert detect_platform("https://twitter.com/a/status/1") == "x"
    assert url_kind("https://x.com/a/status/1") == "post"
    assert youtube_video_id("https://youtu.be/dQw4w9WgXcQ") == "dQw4w9WgXcQ"
    assert youtube_video_id("https://www.youtube.com/shorts/abcdefgh") == "abcdefgh"
    assert url_kind("https://www.youtube.com/@somechannel") == "community"
    assert url_kind("https://www.reddit.com/r/saudiarabia/comments/xyz/title/") == "post"
    assert "provider" in unsupported_reason("https://www.tiktok.com/@a/video/1")


CSV = """platform,community_name,post_url,post_text,comment_text,comment_date,comment_likes,username
instagram,Healthy Riyadh,https://www.instagram.com/p/AAA/,Energy tips,تعبانه طول اليوم وش الحل؟,2025-01-05,3,sara_123
instagram,Healthy Riyadh,https://www.instagram.com/p/AAA/,Energy tips,تعبانه طول اليوم وش الحل؟,2025-01-05,3,dup_user
instagram,Healthy Riyadh,https://www.instagram.com/p/AAA/,Energy tips,call me +966 55 123 4567,2025-01-06,0,spam
instagram,Healthy Riyadh,https://www.instagram.com/p/BBB/,Sleep,ما اقدر انام,2024-01-01,1,x
"""


def test_csv_import_drops_identity_and_dedupes(db):
    recs = load_records(CSV.encode(), "x.csv")
    req = FetchRequest(country="SA", date_from=datetime(2024, 6, 1))
    run = run_connector(db, TabularImport(recs), req)
    assert run.status == "done", run.error
    assert run.stats["comments_new"] == 2 and run.stats["comments_duplicate"] == 1
    texts = list(db.scalars(select(Comment.text)))
    assert all("sara_123" not in t for t in texts)
    assert any("[phone]" in t for t in texts)
    assert db.scalar(select(Community.country)) == "SA"
    # date filter excluded the 2024-01-01 comment (post still registered)
    assert db.scalar(select(func.count()).select_from(Post)) == 2


def test_nested_provider_json():
    data = [{
        "url": "https://www.instagram.com/p/CCC/", "caption": "Gut health", "ownerUsername": "brand",
        "latestComments": [{"text": "انتفاخ كل يوم", "ownerUsername": "a", "likesCount": 2},
                           {"text": "same!", "ownerUsername": "b"}],
    }]
    posts = records_to_posts(data)
    assert len(posts) == 1 and len(posts[0].comments) == 2
    assert posts[0].text == "Gut health"
    assert posts[0].comments[0].like_count == 2


def _mock(handler):
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_youtube_connector_video(db):
    def handler(req: httpx.Request):
        path = req.url.path
        if path.endswith("/videos"):
            return httpx.Response(200, json={"items": [{"id": "vid12345", "snippet": {
                "channelId": "UC1", "channelTitle": "Doha Wellness", "title": "Sleep", "publishedAt": "2025-02-01T00:00:00Z"},
                "statistics": {"likeCount": "10", "commentCount": "2", "viewCount": "100"}}]})
        if path.endswith("/commentThreads"):
            return httpx.Response(200, json={"items": [{"snippet": {"totalReplyCount": 1, "topLevelComment": {
                "id": "c1", "snippet": {"textOriginal": "I can't sleep since months, any advice?", "likeCount": 4,
                                         "publishedAt": "2025-02-02T00:00:00Z", "authorDisplayName": "Somebody"}}},
                "replies": {"comments": [{"id": "c2", "snippet": {"textOriginal": "magnesium helped me",
                                                                  "publishedAt": "2025-02-03T00:00:00Z"}}]}}]})
        return httpx.Response(404)

    yt = YouTubeConnector(api_key="k", client=_mock(handler))
    run = run_connector(db, yt, FetchRequest(urls=["https://www.youtube.com/watch?v=vid12345"], country="QA"))
    assert run.status == "done", run.error
    assert run.stats["comments_new"] == 2
    post = db.scalar(select(Post))
    assert post.view_count == 100 and post.community.name == "Doha Wellness"


def test_reddit_connector(db):
    def handler(req: httpx.Request):
        if "access_token" in str(req.url):
            return httpx.Response(200, json={"access_token": "t"})
        if "/comments/abc" in req.url.path:
            return httpx.Response(200, json=[
                {"data": {"children": [{"data": {"id": "abc", "subreddit": "dubai", "title": "Burnout?",
                                                 "permalink": "/r/dubai/comments/abc/x/", "created_utc": 1735689600,
                                                 "num_comments": 2, "score": 5}}]}},
                {"data": {"children": [
                    {"kind": "t1", "data": {"id": "k1", "body": "Totally burned out at work", "created_utc": 1735689700,
                                            "author": "u1", "score": 3, "replies": {"data": {"children": [
                                                {"kind": "t1", "data": {"id": "k2", "body": "same here",
                                                                        "created_utc": 1735689800}}]}}}},
                    {"kind": "more", "data": {}}]}},
            ])
        return httpx.Response(404)

    rc = RedditConnector("id", "secret", client=_mock(handler))
    run = run_connector(db, rc, FetchRequest(urls=["https://www.reddit.com/r/dubai/comments/abc/x/"], country="AE"))
    assert run.status == "done", run.error
    assert run.stats["comments_new"] == 2
    assert db.scalar(select(Community.name)) == "r/dubai"


def test_failed_connector_records_error(db):
    yt = YouTubeConnector(api_key="")
    run = run_connector(db, yt, FetchRequest(urls=["https://youtu.be/x"]))
    assert run.status == "error" and "YOUTUBE_API_KEY" in run.error
