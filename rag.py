"""RAG engine — local-first retrieval over project knowledge + event history.

Index sources:
  - docs/ and .md/.json files inside the command-center folder (specs, plans)
  - recent ledger events (for session summaries)

Deterministic extractive retriever: token-overlap scoring with idf weighting.
No external embeddings service needed; provenance is attached to every
retrieved chunk so the Copilot can cite where each claim came from.
"""
from __future__ import annotations

import json
import math
import re
from pathlib import Path
from typing import Any

from config import BASE_DIR, COMPRESSION_ENABLED, COMPRESSION_TARGET_RATIO, COMPRESSION_MIN_CHARS
from compression import compress_context

_TOKEN_RE = re.compile(r"[a-z0-9_]{3,}")
_STOP = {
    "the", "and", "for", "with", "that", "this", "from", "into", "are", "was",
    "not", "you", "your", "can", "will", "has", "have", "but", "all", "any",
    "que", "para", "com", "uma", "dos", "das", "não", "sim", "por", "como",
    "mais", "isso", "ele", "ela", "seu", "sua", "quando", "mais",
}


def _tokens(text: str) -> list[str]:
    return [t for t in _TOKEN_RE.findall(text.lower()) if t not in _STOP]


class RAGIndex:
    """Chunked, in-memory, deterministic TF-IDF retriever with provenance."""

    def __init__(self, roots: list[Path] | None = None):
        self.chunks: list[dict[str, Any]] = []
        self._df: dict[str, int] = {}
        self._roots = roots or [
            BASE_DIR,                                  # command-center docs + code
            BASE_DIR.parent,                           # parent project (PLANO, README...)
        ]
        self.rebuild()

    # -- indexing --------------------------------------------------------------
    def rebuild(self) -> int:
        self.chunks = []
        seen_files: set[Path] = set()
        for root in self._roots:
            if not root.exists():
                continue
            for pattern in ("*.md", "*.json"):
                for f in root.rglob(pattern):
                    if f in seen_files or not f.is_file():
                        continue
                    # never index env/secret files, node_modules, profiles, data dirs
                    sp = str(f).lower()
                    if any(x in sp for x in (".env", "node_modules", "playwright_profile",
                                             "chrome_profile", "data/", "logs/", "__pycache__",
                                             ".git", "extracted/football-blitz-command-center/reference-images")):
                        continue
                    # avoid pulling the whole 12MB zip dir's binaries via .json noise
                    if f.stat().st_size > 400_000:
                        continue
                    seen_files.add(f)
                    try:
                        text = f.read_text(encoding="utf-8", errors="ignore")
                    except OSError:
                        continue
                    self._index_file(f, text)
        self._compute_df()
        return len(self.chunks)

    def _index_file(self, path: Path, text: str) -> None:
        rel = path.name
        for root in self._roots:
            if path.is_relative_to(root):
                try:
                    rel = str(path.relative_to(root))
                    break
                except ValueError:
                    continue
        lines = text.splitlines()
        size = 700  # chars per chunk
        for i in range(0, len(lines), 12):
            block = "\n".join(lines[i:i + 12])
            if not block.strip():
                continue
            for j in range(0, len(block), size):
                piece = block[j:j + size]
                if len(piece.strip()) < 40:
                    continue
                self.chunks.append({
                    "text": piece,
                    "source": rel,
                    "line": i + 1,
                    "kind": path.suffix.lower(),
                })

    def index_events(self, events: list[dict[str, Any]]) -> None:
        """Add recent ledger events as chunks (for session summaries)."""
        for e in events[-200:]:
            self.chunks.append({
                "text": f"event {e.get('event_id','')} outcome={e.get('outcome','')} "
                        f"origin={e.get('data_origin','')} at={e.get('observed_at','')}",
                "source": f"ledger:{e.get('session_id', '')}",
                "line": 0,
                "kind": "event",
            })
        self._compute_df()

    def _compute_df(self) -> None:
        self._df = {}
        for c in self.chunks:
            for t in set(_tokens(c["text"])):
                self._df[t] = self._df.get(t, 0) + 1

    # -- retrieval ---------------------------------------------------------------
    def retrieve(self, query: str, k: int = 6, provenance: bool = True) -> list[dict[str, Any]]:
        q_tokens = _tokens(query)
        if not q_tokens or not self.chunks:
            return []
        n = len(self.chunks)
        scored: list[tuple[float, dict]] = []
        for c in self.chunks:
            c_tokens = _tokens(c["text"])
            if not c_tokens:
                continue
            tf: dict[str, int] = {}
            for t in c_tokens:
                tf[t] = tf.get(t, 0) + 1
            score = 0.0
            for t in q_tokens:
                if t in tf:
                    idf = math.log(1 + n / (1 + self._df.get(t, 0)))
                    score += tf[t] * idf
            if score > 0:
                scored.append((score, c))
        scored.sort(key=lambda x: x[0], reverse=True)
        results = []
        for score, c in scored[:k]:
            r = dict(c)
            r["score"] = round(score, 3)
            if provenance:
                r["provenance"] = {
                    "source": c["source"],
                    "line": c["line"],
                    "retrieval": "tfidf-extractive-v1",
                    "note": "chunk extracted from indexed file; consult source for full context",
                }
            results.append(r)
        return results

    def retrieve_compressed(self, query: str, k: int = 6) -> tuple[list[dict], dict]:
        """Retrieve + compress in one step. Returns (chunks, report_dict)."""
        chunks = self.retrieve(query, k=k)
        if not chunks:
            return [], {"enabled": COMPRESSION_ENABLED, "ratio": 1.0, "summary": "no chunks"}
        if COMPRESSION_ENABLED:
            chunks, report = compress_context(
                chunks, target_ratio=COMPRESSION_TARGET_RATIO, min_chars=COMPRESSION_MIN_CHARS
            )
        else:
            from compression import CompressionReport
            report = CompressionReport(original_chars=sum(len(c["text"]) for c in chunks),
                                       compressed_chars=sum(len(c["text"]) for c in chunks),
                                       chunks_in=len(chunks), chunks_out=len(chunks),
                                       steps=["disabled"])
        return chunks, {
            "enabled": COMPRESSION_ENABLED,
            "ratio": report.ratio,
            "original_chars": report.original_chars,
            "compressed_chars": report.compressed_chars,
            "summary": report.summary(),
        }
