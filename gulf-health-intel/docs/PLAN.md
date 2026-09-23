# Gulf Health Community Intelligence: Architecture & MVP Plan

> Scope note: the brief contains the sentence *"The tool must create individual
> health profiles or produce marketing lists that associate identifiable
> individuals with inferred or disclosed medical conditions."* Every other part
> of the brief (Privacy Design, "do not diagnose", "rank communities not
> individuals") shows the intent is **must NOT**. The system is built that way.
> It cannot produce person-level health data at all. The rest of this document
> explains how.

---

## 1. Requirements digest

| Area | What matters for design |
|---|---|
| Unit of analysis | **Comments → posts → communities.** Never people. |
| Inputs | page/profile URL, post URL, URL lists, CSV/JSON, keywords, country, platform, date range |
| Languages | MSA, Gulf (Saudi/Emirati/Kuwaiti…), Egyptian, English, code-mixed, Arabizi |
| Outputs | topic / intent / relevance per comment; post and community rankings; scorecard opportunities; content ideas; search; CSV exports |
| AI | Provider-neutral (Claude / OpenAI), structured JSON, cost-minimised |
| Privacy | No commenter identity stored. Raw content kept apart from AI analysis. B2B businesses held in their own table with no link to comments. |
| Extensibility | New platforms and data providers added as connectors, with no change to the analysis core |

## 2. Architecture

```
                ┌──────────────────────── connectors/ ─────────────────────────┐
 URLs, keywords │ youtube (official API)   reddit (official OAuth API)          │
 CSV / JSON  ──►│ x (official API v2)      provider_json (Apify/BrightData/…)   │
                │ csv_import               apify (optional live provider)       │
                └──────────────┬───────────────────────────────────────────────┘
                               │ RawPost / RawComment (NO author fields exist)
                               ▼
                   privacy.scrub()  → @mentions, emails, phones, URLs removed
                               ▼
      ┌─────────────── RAW LAYER (collected content) ───────────────┐
      │ sources · ingestion_runs · communities · posts · comments   │
      └──────────────────────────────┬──────────────────────────────┘
                                     ▼
   analysis/classify.py:  dedupe by text-hash → heuristic prefilter →
                          cache lookup → batched LLM (cheap model) → validate
                                     ▼
      ┌──────────── ANALYSIS LAYER (AI/heuristic output) ───────────┐
      │ topics · comment_analysis · comment_topics · post_analysis  │
      │ post_topics · community_analysis · community_topics         │
      │ scorecard_opportunities · content_ideas · llm_cache         │
      └──────────────────────────────┬──────────────────────────────┘
                                     ▼
       aggregate → scores → scorecards → content ideas (strong model optional)
                                     ▼
              FastAPI (JSON API + CSV export) → static dashboard
                                     ▼
          Opt-in leads happen OUTSIDE this tool (the Scorecard itself)

      business_accounts (B2B): separate table, no foreign key to any comment
```

### Stack choice: simpler than the suggested stack, on purpose

* **Python + FastAPI + SQLAlchemy.** As suggested. SQLAlchemy means switching
  SQLite to Postgres is a one-line `DATABASE_URL` change.
* **SQLite for the MVP.** A single file with zero operational cost, comfortable
  well past 1M comments for this read-heavy workload. Switch to Postgres when
  more than one person writes at once or the data grows past a few GB.
* **Dashboard: one static HTML/JS page served by FastAPI, not Next.js.**
  The dashboard is a few tables, a bar chart and forms. Next.js would add a
  second runtime, a build step, a second container and CORS, and none of that
  helps a single-analyst tool. Chart.js loads from a CDN. If the UI grows
  (auth, multi-user), the JSON API is already there for a React/Next frontend.
* **Background jobs:** FastAPI `BackgroundTasks` for the MVP. No Redis or
  Celery until volumes need it.
* **Docker:** one image, one container, plus a volume for the SQLite file.

## 3. Platform access: what is realistically compliant

Always check each platform's current terms. Pricing and access programmes
change often.

| Platform | Compliant method | Reality for this use case | MVP connector |
|---|---|---|---|
| **YouTube** | YouTube Data API v3 (API key). `search.list`, `commentThreads.list` | **Best source.** Public comments are available officially. The free 10k units/day quota covers roughly 100k comments a day (search costs 100 units; one page of 100 comments costs 1 unit). Supports `regionCode` and `relevanceLanguage=ar`. | ✅ live |
| **Reddit** | Official Data API (OAuth app-only) | Official and free at low volume for non-commercial use. Commercial use needs Reddit's agreement. Gulf subs exist (r/saudiarabia, r/dubai, r/UAE, r/qatar, r/kuwait, r/oman, r/Bahrain), but the content is mostly English and expat. | ✅ live |
| **X** | X API v2 (paid tiers / pay-per-use) | Official but expensive. Replies come from `conversation_id:` search, and only recent tweets on lower tiers. | ✅ live (needs bearer token) |
| **Instagram** | Graph API works only for accounts you own or manage. Business Discovery returns *metadata* of other business accounts, not their comments. | No official route to read comments on other accounts. | ⚙️ provider import / CSV |
| **Facebook pages** | Page Public Content Access needs Meta app review. CrowdTangle is shut down. Meta Content Library is for vetted researchers. | Hard to get as a commercial user. | ⚙️ provider import / CSV |
| **TikTok** | Research API (academic/non-profit only). Display API covers own content only. | No commercial official route to other accounts' comments. | ⚙️ provider import / CSV |
| **Public sites / forums** | Direct fetch, respecting robots.txt and site terms, or RSS | Case by case | ⚙️ CSV/JSON (a fetch connector is a later stage) |

**Provider route (Apify, Bright Data, Data365, …).** The tool accepts exported
datasets (JSON/CSV) through a field-mapping adapter, and can optionally call
Apify's `run-sync-get-dataset-items` endpoint. Choosing a provider and
confirming its compliance with platform terms and local law (Saudi PDPL, UAE
PDPL, and so on) is the operator's responsibility. **The tool contains no
scraping, login automation, CAPTCHA solving or rate-limit evasion.** Author
fields in provider data are **dropped at the connector boundary**.

## 4. Cost estimate (MVP)

Prices are approximate as of writing. Verify current rates.

**Infrastructure**
* 1 small VPS / Railway / Fly instance: **$5–12/month**. SQLite costs nothing.
* A managed Postgres, if used later: about $0–25/month.

**Data**
* YouTube, Reddit (non-commercial): **$0**.
* X API: from roughly $100–200+/month on subscription tiers, or pay-per-use. Optional.
* Third-party providers: typically **$0.5–3 per 1,000 comments**, or about $49/month for a starter plan.

**LLM** (worked example: 10,000 comments)
* Dedupe and heuristic prefilter usually remove 30–50%, leaving about 6,000 to classify.
* Batches of 25 → about 240 calls × (about 2k input + 1k output tokens) ≈ 0.5M input + 0.25M output.
* Cheap tier (Claude Haiku 4.5 at about $1/M in and $5/M out): **about $1.75**, and **about $0.90** with batch-API discounts.
* Synthesis (content ideas and scorecard copy) with a stronger model: roughly 20 calls, **under $1**.
* Cached results are never paid for twice.
* **Rule of thumb: about $2–3 per 10k comments. With no API key the whole pipeline still runs on the built-in bilingual heuristic classifier at $0.**

## 5. Technical limitations (be honest about these)

1. **Access, not code, is the bottleneck** for Instagram, Facebook and TikTok. Without a provider or exports, those sources have no data.
2. **Country is inferred from the community, never from the individual.** The operator tags each community or page with a country. City-level search ("Riyadh") works only if the community carries a city tag, or as a text match on the content.
3. **Dialect detection is heuristic.** Gulf, Saudi and Egyptian markers are keyword-based. Short comments are often `ar_unknown`.
4. **Arabizi** detection works when numerals are used as letters (3, 7, 2, 5, 9) plus common words. Recall is partial.
5. **The heuristic classifier** is a lexicon matcher: fast, free and explainable, but it misses sarcasm and paraphrase. The LLM path fixes most of that.
6. **Engagement fields vary by platform.** Some are missing (for example, comment likes in some exports), and scores degrade gracefully when they are.
7. **Trend/growth metrics** need timestamps across a reasonable window (at least 4–8 weeks).
8. **Small samples** give noisy percentages. The UI shows raw counts next to shares.

## 6. Database schema

Raw layer (collected):

```
sources(id, name, platform, kind[api|provider|csv|manual], created_at)
ingestion_runs(id, source_id→sources, params JSON, started_at, finished_at, stats JSON)
communities(id, platform, url UNIQUE(platform,url), external_id, name, country, city,
            category, created_at)
posts(id, community_id→communities, platform, url UNIQUE(platform,url), external_id,
      text, published_at, like_count, comment_count, share_count, view_count,
      ingestion_run_id→ingestion_runs, created_at)
comments(id, post_id→posts, platform, external_id_hash, text (PII-scrubbed),
         text_hash, published_at, like_count, reply_count, is_reply,
         ingestion_run_id, created_at)                -- NO author columns
```

Analysis layer (derived, fully rebuildable):

```
topics(id, slug UNIQUE, name_en, name_ar, is_seed, status[active|candidate],
       keywords JSON, created_at)
comment_analysis(id, comment_id UNIQUE→comments, primary_topic_id→topics,
                 intent, intent_confidence, relevance_score, is_question,
                 question_text, language, dialect, key_phrases JSON,
                 method[heuristic|llm], model, prompt_version, analyzed_at)
comment_topics(comment_analysis_id, topic_id, confidence)
post_analysis(post_id PK, relevant_comments, total_comments, dominant_language,
              engagement, relevance_score, top_questions JSON, top_phrases JSON,
              topic_distribution JSON, computed_at)
post_topics(post_id, topic_id, comment_count, share)
community_analysis(community_id PK, posts_analyzed, comments_analyzed,
                   relevant_pct, top_questions JSON, engagement JSON,
                   growth JSON, opportunity_score, computed_at)
community_topics(community_id, topic_id, comment_count, share, growth,
                 avg_post_engagement)
scorecard_opportunities(id, key, country, problem_cluster, topics JSON,
                        discussion_count, volume_label, typical_questions JSON,
                        suggested_scorecard, hook, cta, score, method, generated_at)
content_ideas(id, topic_id, kind, text, method, generated_at)
llm_cache(key PK = sha256(provider|model|prompt_version|text_hash), response JSON, created_at)
```

B2B (separate; no foreign key to any content table):

```
business_accounts(id, business_name, category, country, public_email,
                  website, social_profiles JSON, partnership_relevance,
                  source_url, notes, created_at)
```

**Tables that intentionally do not exist:** anything holding
`person_name / username / profile_url / author_id` next to a topic or condition.
A test enforces this.

## 7. Workflow

```
PUBLIC COMMUNITIES   operator registers page/sub/channel + country (+city)
      ↓
POSTS                connector fetches posts (URL, keywords, date range)
      ↓
PUBLIC COMMENTS      connector fetches comments → author dropped → PII scrubbed
      ↓                  → text_hash dedupe → stored in RAW layer
ANONYMISED ANALYSIS  heuristic prefilter (language, dialect, obvious noise)
      ↓
PROBLEM + QUESTION + INTENT DETECTION
                     cache → batched cheap-model JSON → validation → fallback
                     new topics: LLM "new_topic" votes + n-gram discovery
      ↓
COMMUNITY / POST OPPORTUNITY RANKING
                     post_analysis, community_analysis, opportunity scores, trends
      ↓
CONTENT IDEAS        per topic: reels, hooks, FAQs, carousels, articles, lead magnets
      ↓
SCORECARD OPPORTUNITIES
                     topic clusters → scorecard + hook + CTA per country
      ↓
OPT-IN LEADS         people choose to take the Scorecard (outside this tool)
```

## 8. Cheapest viable MVP

* Connectors: **CSV/JSON import + provider mapping** (covers every platform)
  plus **YouTube** and **Reddit** live. X and Apify are optional behind keys.
* **Heuristic classifier as the default**, so everything works at $0. The
  LLM layer switches on with `LLM_PROVIDER=anthropic|openai` and a key.
* SQLite, one Docker container, and a static dashboard.
* Expected running cost: **about $5–12/month hosting plus about $2–3 per 10k
  comments** when the LLM is on.

## 9. Implementation plan (staged, each stage tested)

| Stage | Deliverable | Test |
|---|---|---|
| 1 | Models (raw/analysis/B2B), Arabic normalisation, language/dialect detection, PII scrub, bilingual heuristic classifier | unit tests incl. "no identity columns" and "no diagnosis" |
| 2 | Connector interface + registry, URL→platform detection, CSV/JSON + provider mapping, YouTube/Reddit/X/Apify, ingestion with dedupe | fixture-based tests (HTTP mocked) |
| 3 | LLM abstraction (Anthropic, OpenAI, Mock), prompts with JSON schema, batching, cache, validation and heuristic fallback | mock-provider tests |
| 4 | Aggregation: post and community analysis, opportunity score, growth, topic discovery, scorecards, content ideas, search | tests on sample dataset |
| 5 | FastAPI endpoints, CSV exports, dashboard, synthetic sample data, Dockerfile/compose, README | API tests via TestClient |
| Later | Postgres + Alembic, auth, scheduled re-collection, forum fetch connector, embeddings-based clustering, Batch API submission | |
