"""Guards on the privacy design: no table may pair identity with health analysis."""
import re

from app.db import Base

IDENTITY = re.compile(r"(author|username|user_name|profile_url|person|commenter|handle|full_name)", re.I)


def test_no_identity_columns_in_content_or_analysis_tables(db):
    for name, table in Base.metadata.tables.items():
        if name == "business_accounts":
            continue
        for col in table.columns:
            assert not IDENTITY.search(col.name), f"{name}.{col.name} looks like identity data"


def test_business_accounts_not_linked_to_comments(db):
    t = Base.metadata.tables["business_accounts"]
    assert not t.foreign_keys
    for name, table in Base.metadata.tables.items():
        for fk in table.foreign_keys:
            assert fk.column.table.name != "business_accounts", name


def test_seed_topics_created(db):
    from sqlalchemy import select

    from app.models import Topic

    slugs = set(db.scalars(select(Topic.slug)))
    assert {"fatigue_low_energy", "sleep_problems", "ibs", "burnout"} <= slugs
