import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("LLM_PROVIDER", "none")


@pytest.fixture()
def db():
    from app import db as dbmod

    dbmod.init_engine("sqlite://")
    from app.analysis.topics import ensure_seed_topics

    s = dbmod.new_session()
    ensure_seed_topics(s)
    s.commit()
    yield s
    s.close()
