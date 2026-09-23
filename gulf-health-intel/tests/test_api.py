import os

import pytest
from fastapi.testclient import TestClient

SAMPLE = os.path.join(os.path.dirname(__file__), "..", "sample_data", "synthetic_comments.csv")


@pytest.fixture()
def client(db):
    from app.main import app

    return TestClient(app)


def test_dashboard_and_meta(client):
    assert "Gulf Health Community Intelligence" in client.get("/").text
    m = client.get("/api/meta").json()
    assert set(m["countries"]) == {"SA", "AE", "KW", "QA", "BH", "OM"}
    assert m["llm_provider"].startswith("none")


def test_file_import_and_dashboard_endpoints(client):
    with open(SAMPLE, "rb") as f:
        r = client.post("/api/ingest/file", files={"file": ("demo.csv", f, "text/csv")})
    assert r.status_code == 200, r.text
    assert r.json()["run"]["status"] == "done"
    ov = client.get("/api/overview").json()
    assert ov["communities"] == 8 and ov["relevant"] > 0
    assert client.get("/api/overview?country=SA").json()["communities"] == 2
    top = client.get("/api/topics/top").json()
    assert top and top[0]["count"] >= top[-1]["count"]
    comms = client.get("/api/communities").json()
    assert comms and "opportunity_score" in comms[0]
    assert client.get("/api/posts?country=AE").json()
    cm = client.get("/api/comments?min_relevance=40&limit=5").json()
    assert cm["total"] > 0 and len(cm["items"]) == 5
    identity = {"author", "username", "user", "profile", "profile_url", "name"}
    assert not identity & set(cm["items"][0])
    assert client.get("/api/scorecards").json()
    assert client.get("/api/scorecards?country=SA").json()
    assert client.get("/api/content-ideas").json()
    s = client.get("/api/search", params={"q": "burnout Dubai"}).json()
    assert s["parsed"]["city"] == "Dubai"
    assert client.get("/api/trends").json()


def test_url_ingest_without_keys_reports_unsupported(client):
    r = client.post("/api/ingest/urls", json={"urls": ["https://www.instagram.com/p/abc/"], "country": "SA"}).json()
    assert r["runs"] == [] and "provider" in r["unsupported"][0]["reason"]
    assert client.post("/api/ingest/urls", json={}).status_code == 400


def test_exports(client):
    with open(SAMPLE, "rb") as f:
        client.post("/api/ingest/file", files={"file": ("demo.csv", f, "text/csv")})
    for kind in ["communities", "posts", "comments", "topics", "scorecards", "content_ideas", "b2b"]:
        r = client.get(f"/api/export/{kind}.csv")
        assert r.status_code == 200 and r.headers["content-type"].startswith("text/csv"), kind
    header = client.get("/api/export/comments.csv").text.lstrip("﻿").splitlines()[0]
    assert "author" not in header and "user" not in header
    assert client.get("/api/export/nope.csv").status_code == 404


def test_b2b_crud(client):
    r = client.post("/api/business", json={"business_name": "Demo Clinic", "country": "AE", "category": "physio",
                                           "public_email": "info@demo.example", "partnership_relevance": 80})
    bid = r.json()["id"]
    assert client.get("/api/business").json()[0]["business_name"] == "Demo Clinic"
    assert "Demo Clinic" in client.get("/api/export/b2b.csv").text
    assert client.delete(f"/api/business/{bid}").status_code == 200
