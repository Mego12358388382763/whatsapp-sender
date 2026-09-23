# Gulf Health Community Intelligence

Anonymised audience research on **public** health and wellness discussions in
Saudi Arabia, the UAE, Kuwait, Qatar, Bahrain and Oman. It answers four questions:

* what problems people discuss and which questions they repeat
* in what language they talk about them
* which posts and communities hold the richest discussion
* which content and general wellness **Scorecards** would meet those needs

```
PUBLIC COMMUNITIES → POSTS → PUBLIC COMMENTS → ANONYMISED COMMENT ANALYSIS
→ PROBLEM + QUESTION + INTENT DETECTION → COMMUNITY / POST OPPORTUNITY RANKING
→ CONTENT IDEAS → SCORECARD OPPORTUNITIES → OPT-IN LEADS (via the Scorecard itself)
```

The full architecture, platform-access analysis, cost estimates, limitations and
schema are in **[docs/PLAN.md](docs/PLAN.md)**.

## Privacy by design

* **No commenter identity is ever stored.** Connector output types have no
  author fields. Author, username and profile columns in imports are dropped at
  the boundary. Comment text is scrubbed of @mentions, emails, phone numbers and
  links. A test fails the build if a content or analysis table gains an identity column.
* **Themes, not diagnoses.** "I'm exhausted every morning" becomes
  *topic: fatigue / low energy, intent: sharing experience*. Diagnosis-like
  labels proposed by an LLM are rejected.
* **Rankings are of communities and posts, never people.** There are no prospect lists.
* **B2B partners** (public business accounts) live in a separate table with no
  link to any comment or health data.
* Raw collected content (`sources, ingestion_runs, communities, posts, comments`)
  is kept apart from derived analysis (`comment_analysis, topics, post_*, community_*,
  scorecard_opportunities, content_ideas`). The analysis can be rebuilt at any time.

## Quick start

```bash
cd gulf-health-intel
pip install -r requirements-dev.txt
cp .env.example .env            # optional: API keys, LLM provider
python -m app.cli demo          # loads SYNTHETIC demo data and analyses it
uvicorn app.main:app --reload   # http://localhost:8000
pytest -q
```

Or with Docker:

```bash
docker compose up --build       # http://localhost:8000 (SQLite on a named volume)
docker compose exec app python -m app.cli demo
```

## Getting data in

| Input | How |
|---|---|
| Page / profile / channel / subreddit URL | Dashboard → *Add data*, or `POST /api/ingest/urls` |
| Post URL(s), multiple URLs | same (one per line) |
| Keywords + country + platform + date range | same; uses YouTube search (`regionCode`), Gulf subreddits, X recent search |
| CSV / JSON (any provider export) | Dashboard → *Import*, `POST /api/ingest/file`, or `python -m app.cli import FILE --country SA` |

Connectors: **YouTube Data API**, **Reddit API**, **X API v2** (official, key
required), an optional **Apify** provider adapter (`APIFY_TOKEN` + `APIFY_ACTORS`),
and the **CSV/JSON importer**, which recognises common provider field names. Instagram,
Facebook and TikTok offer no official route to other accounts' comments, so use
exports from a compliant provider. The tool never bypasses logins, CAPTCHAs or rate limits.

CSV minimum: `post_url, comment_text`. Useful extras: `platform, community_name,
community_url, country, city, post_title, post_date, post_likes, post_comments,
comment_date, comment_likes, comment_id`.

**Adding a platform or provider:** subclass `app.connectors.base.Connector`, yield
`RawPost`/`RawComment`, decorate with `@register`, and import it in
`app/connectors/__init__.py`. The analysis engine does not change.

## AI (optional)

With `LLM_PROVIDER=none` everything runs on the built-in bilingual heuristic
classifier (MSA, Gulf, Saudi, Egyptian, English, Arabizi) at $0.

Set `LLM_PROVIDER=anthropic` (or `openai`) plus the API key, and:

1. comments are **deduplicated** by normalised text hash
2. obvious noise (spam, greetings, off-topic) is **prefiltered** and never sent
3. results are **cached** by provider, model, prompt version and text
4. the **cheap model** classifies in **batches** of `LLM_BATCH_SIZE` with a JSON schema
   (Claude uses a forced tool call; OpenAI uses `json_schema`)
5. the **strong model** runs only for synthesis (content ideas, scorecard copy)
6. any error falls back to the heuristic result

Override models with `LLM_FAST_MODEL` / `LLM_STRONG_MODEL`.

## Dashboard

Overview (tiles and a top-problems chart), Communities (opportunity score),
Posts, Comment explorer (anonymous), Scorecards, Content ideas, Search
(for example "burnout Riyadh"), Add data, B2B partners, and Export.

CSV exports: `/api/export/{communities|posts|comments|topics|scorecards|content_ideas|b2b}.csv`.
The interactive API docs are at `/docs`.

## Scoring (summary)

* **Comment relevance (0–100):** how clearly a problem is stated, question or help
  intent, depth, duration cues and light engagement. With an LLM, the model scores
  against the same rubric.
* **Post score:** average relevance, relevant-comment volume, share of questions/help,
  and engagement.
* **Community opportunity score:** relevant share (30), volume (25), need share (20),
  engagement (15), growth and focus (10). Weights are renormalised when a signal is missing.
* **Scorecard score:** cluster volume (50), share of questions/help (30), topic co-occurrence (20).
  Health 360 appears when discussion spreads across four or more clusters.

## Layout

```
app/
  connectors/   base contract, URL parsing, youtube, reddit, x, apify, tabular import
  analysis/     heuristic, llm/ (anthropic, openai, mock, prompts), classify,
                topics (discovery), aggregate, scorecard, content, pipeline
  text/         normalisation, language/dialect detection, lexicons
  privacy.py    scrubbing, identity stripping, hashing
  ingest.py     raw-layer persistence and deduplication
  search.py     query parsing (topic / country / city) and aggregation
  export.py     CSV exports
  main.py       FastAPI app      static/  dashboard (vanilla JS)
sample_data/    synthetic demo generator + CSV
tests/          36 tests: privacy guards, connectors, classification, analysis, API
```
