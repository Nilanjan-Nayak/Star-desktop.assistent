"""Persistent memory (SQLite) with relevance search that works for Bangla text.

Memory is *advice*, not truth: every hit carries confidence/staleness so the Brain re-verifies
anything that matters (paths, permissions, current state) before acting on it.
"""
from __future__ import annotations

import json
import math
import sqlite3
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path

from ..text import tokens, trigrams

KINDS = ("preference", "project", "conversation", "task", "skill", "learning")


@dataclass
class Memory:
    id: int
    kind: str
    key: str
    content: str
    meta: dict = field(default_factory=dict)
    confidence: float = 0.7
    created: float = 0.0
    updated: float = 0.0
    last_used: float = 0.0
    uses: int = 0
    stale: bool = False
    source: str = "user"


@dataclass
class Hit:
    memory: Memory
    score: float


class MemoryStore:
    def __init__(self, path: Path | str = ":memory:"):
        if path != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._db = sqlite3.connect(str(path), check_same_thread=False)
        self._db.row_factory = sqlite3.Row
        with self._lock:
            self._db.executescript("""
                CREATE TABLE IF NOT EXISTS memories(
                    id INTEGER PRIMARY KEY AUTOINCREMENT, kind TEXT NOT NULL, key TEXT NOT NULL,
                    content TEXT NOT NULL, meta TEXT NOT NULL DEFAULT '{}', confidence REAL NOT NULL DEFAULT 0.7,
                    created REAL NOT NULL, updated REAL NOT NULL, last_used REAL NOT NULL DEFAULT 0,
                    uses INTEGER NOT NULL DEFAULT 0, stale INTEGER NOT NULL DEFAULT 0, source TEXT NOT NULL DEFAULT 'user');
                CREATE INDEX IF NOT EXISTS idx_mem_kind ON memories(kind);
                CREATE TABLE IF NOT EXISTS runs(
                    id INTEGER PRIMARY KEY AUTOINCREMENT, ts REAL NOT NULL, intent TEXT, claimed_ok INTEGER,
                    verified_ok INTEGER, partial INTEGER, steps INTEGER, seconds REAL, skill TEXT, detail TEXT);
            """)
            self._db.commit()

    @property
    def db(self) -> sqlite3.Connection:
        return self._db

    @property
    def lock(self) -> threading.RLock:
        return self._lock

    # CRUD ------------------------------------------------------------------------------
    @staticmethod
    def _row(r: sqlite3.Row) -> Memory:
        return Memory(r["id"], r["kind"], r["key"], r["content"], json.loads(r["meta"]), r["confidence"],
                      r["created"], r["updated"], r["last_used"], r["uses"], bool(r["stale"]), r["source"])

    def add(self, kind: str, key: str, content: str, meta: dict | None = None,
            confidence: float = 0.7, source: str = "user") -> int:
        if kind not in KINDS:
            raise ValueError(f"unknown memory kind {kind!r}")
        now = time.time()
        with self._lock:
            if kind == "preference":  # one live value per preference key
                row = self._db.execute("SELECT id FROM memories WHERE kind=? AND key=?", (kind, key)).fetchone()
                if row:
                    self._db.execute("UPDATE memories SET content=?, meta=?, confidence=?, updated=?, stale=0 WHERE id=?",
                                     (content, json.dumps(meta or {}, ensure_ascii=False), confidence, now, row["id"]))
                    self._db.commit()
                    return row["id"]
            cur = self._db.execute(
                "INSERT INTO memories(kind,key,content,meta,confidence,created,updated,source) VALUES(?,?,?,?,?,?,?,?)",
                (kind, key, content, json.dumps(meta or {}, ensure_ascii=False), confidence, now, now, source))
            self._db.commit()
            return int(cur.lastrowid)

    def get(self, mem_id: int) -> Memory | None:
        with self._lock:
            r = self._db.execute("SELECT * FROM memories WHERE id=?", (mem_id,)).fetchone()
        return self._row(r) if r else None

    def all(self, kind: str | None = None) -> list[Memory]:
        with self._lock:
            rows = (self._db.execute("SELECT * FROM memories WHERE kind=?", (kind,)) if kind
                    else self._db.execute("SELECT * FROM memories")).fetchall()
        return [self._row(r) for r in rows]

    def count(self, kind: str | None = None) -> int:
        with self._lock:
            q, a = ("SELECT COUNT(*) FROM memories WHERE kind=?", (kind,)) if kind else ("SELECT COUNT(*) FROM memories", ())
            return int(self._db.execute(q, a).fetchone()[0])

    def forget(self, mem_id: int) -> bool:
        with self._lock:
            n = self._db.execute("DELETE FROM memories WHERE id=?", (mem_id,)).rowcount
            self._db.commit()
        return n > 0

    def mark_stale(self, mem_id: int, stale: bool = True) -> None:
        with self._lock:
            self._db.execute("UPDATE memories SET stale=?, updated=? WHERE id=?", (int(stale), time.time(), mem_id))
            self._db.commit()

    def mark_used(self, ids: list[int]) -> None:
        with self._lock:
            for i in ids:
                self._db.execute("UPDATE memories SET uses=uses+1, last_used=? WHERE id=?", (time.time(), i))
            self._db.commit()

    def prune_conversation(self, keep: int = 60) -> None:
        with self._lock:
            self._db.execute("""DELETE FROM memories WHERE kind='conversation' AND id NOT IN
                                (SELECT id FROM memories WHERE kind='conversation' ORDER BY id DESC LIMIT ?)""", (keep,))
            self._db.commit()

    # search ----------------------------------------------------------------------------
    def search(self, query: str, kinds: tuple | list | None = None, limit: int = 6,
               min_score: float = 0.15) -> list[Hit]:
        q_tokens = set(tokens(query))
        if not q_tokens:
            return []
        rows = [m for m in self.all() if (not kinds or m.kind in kinds)]
        if not rows:
            return []
        doc_tokens = [set(tokens(f"{m.key} {m.content}")) for m in rows]
        n = len(rows)
        df: dict[str, int] = {}
        for dt in doc_tokens:
            for t in dt:
                df[t] = df.get(t, 0) + 1
        idf = lambda t: math.log(1 + (n + 1) / (1 + df.get(t, 0)))
        q_weight = sum(idf(t) for t in q_tokens) or 1.0
        q_tri = trigrams(query)
        now = time.time()
        hits = []
        for m, dt in zip(rows, doc_tokens):
            coverage = sum(idf(t) for t in q_tokens & dt) / q_weight
            d_tri = trigrams(f"{m.key} {m.content}")
            jac = len(q_tri & d_tri) / len(q_tri | d_tri) if q_tri and d_tri else 0.0
            score = 0.65 * coverage + 0.35 * jac
            age_days = (now - max(m.updated, m.created)) / 86400
            score *= (0.85 + 0.15 * math.exp(-age_days / 60)) * (0.5 + 0.5 * m.confidence) * (0.5 if m.stale else 1.0)
            if score >= min_score:
                hits.append(Hit(m, score))
        hits.sort(key=lambda h: h.score, reverse=True)
        return hits[:limit]
