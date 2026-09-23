"""Privacy controls applied at the connector boundary.

* Identity fields never pass the boundary (`strip_identity`).
* Comment text is scrubbed of @mentions, emails, phone numbers and URLs.
* Platform comment IDs are one-way hashed (dedup only, not reversible to a person).
"""
from __future__ import annotations

import hashlib
import os
import re

from .text.normalize import normalize

_SALT = os.environ.get("APP_SALT", "ghci-default-salt-change-me")

_URL = re.compile(r"(https?://\S+|www\.\S+)", re.I)
_EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
_MENTION = re.compile(r"(?<![\w@])@[\w.]{2,}", re.UNICODE)
# 8+ digits allowing spaces, dashes, dots, parentheses and a leading +
_PHONE = re.compile(r"(?:\+|00)?(?:[\d٠-٩][\s\-.()]{0,2}){8,}")

# Any key in a raw record matching these is dropped before storage.
IDENTITY_KEYS = re.compile(
    r"(author|user(name)?|owner|profile|handle|display_?name|full_?name|avatar|"
    r"channel_?id_?of_?author|commenter|screen_?name|from_?user|by_?user)",
    re.I,
)


def scrub(text: str) -> str:
    if not text:
        return ""
    t = _URL.sub("[link]", text)
    t = _EMAIL.sub("[email]", t)
    t = _MENTION.sub("@user", t)
    t = _PHONE.sub(lambda m: "[phone]" if sum(c.isdigit() for c in m.group()) >= 8 else m.group(), t)
    return re.sub(r"\s+", " ", t).strip()


def strip_identity(record: dict) -> dict:
    """Return a copy of a raw provider record without identity-bearing keys."""
    return {k: v for k, v in record.items() if not IDENTITY_KEYS.search(str(k))}


def hash_id(platform: str, external_id: str | None) -> str | None:
    if not external_id:
        return None
    return hashlib.sha256(f"{_SALT}|{platform}|{external_id}".encode()).hexdigest()


def text_hash(text: str) -> str:
    return hashlib.sha256(normalize(text).encode()).hexdigest()
