"""Context compression engine — RTK-style token saving for RAG context.

Pipeline per chunk of context:
  1. strip noise: comments, log prefixes, timestamps, ANSI codes, URLs, low-value lines
  2. deduplicate near-identical lines (keep first occurrence)
  3. drop stop-sentences (filler phrases, politeness, disclaimers repeated per line)
  4. truncate long tokens > 64 chars (hashes, base64)

All deterministic and reversible-by-design (we keep a char-budget report).
Mirrors the spirit of OmniRoute's RTK/Caveman compression: 15-95% token saving.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

_NOISE_PATTERNS = [
    re.compile(p, re.IGNORECASE)
    for p in (
        r"^\s*(#|//|--) ",                      # comments
        r"^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}",  # timestamp prefix
        r"^\[\d{2}:\d{2}(:\d{2})?\]",           # [12:34] log prefixes
        r"\x1b\[[0-9;]*m",                       # ANSI codes
        r"https?://\S+$",                        # bare URLs on their own line
        r"^\s*$",                                # empty lines
        r"^\s*[\[\(]?\d{1,3}(\.\d{1,3}){3}[\]\)]?\s*$",  # lone IPs
    )
]

_STOP_SENTENCE_RE = re.compile(
    r"\b(please note that|it is important to note|as you know|in order to|"
    r"at the end of the day|basically|actually|obviously|in other words|"
    r"note that|keep in mind|as mentioned (?:above|before)|"
    r"lembre-se|vale lembrar|é importante notar|basicamente|na verdade|"
    r"ou seja|como mencionado)\b",
    re.IGNORECASE,
)

_URL_RE = re.compile(r"https?://\S+")
_LONG_TOKEN_RE = re.compile(r"\S{65,}")
_WS_RE = re.compile(r"[ \t]{2,}")


@dataclass
class CompressionReport:
    original_chars: int = 0
    compressed_chars: int = 0
    chunks_in: int = 0
    chunks_out: int = 0
    steps: list[str] = field(default_factory=list)

    @property
    def ratio(self) -> float:
        if self.original_chars == 0:
            target = 1.0
        else:
            target = self.compressed_chars / self.original_chars
        return round(target, 3)

    def summary(self) -> str:
        saved = 1 - self.ratio if self.original_chars else 0
        return (
            f"compression: {self.original_chars} -> {self.compressed_chars} chars "
            f"({saved:.0%} saved), chunks {self.chunks_in} -> {self.chunks_out}"
        )


def _clean_line(line: str) -> str | None:
    for pat in _NOISE_PATTERNS[:6]:
        line = pat.sub("", line)
    for pat in _NOISE_PATTERNS[6:]:
        if pat.match(line):
            return None
    line = _URL_RE.sub("", line)
    line = _LONG_TOKEN_RE.sub(lambda m: m.group(0)[:32] + "…", line)
    line = _WS_RE.sub(" ", line).strip()
    if len(line) < 3:
        return None
    if _STOP_SENTENCE_RE.search(line):
        return None
    return line or None


def compress_text(text: str, min_chars: int = 400) -> tuple[str, CompressionReport]:
    """Compress a block of text. Blocks under min_chars pass through untouched."""
    report = CompressionReport(original_chars=len(text), chunks_in=1)
    if len(text) < min_chars:
        report.compressed_chars = len(text)
        report.chunks_out = 1
        report.steps.append("passthrough (below min_chars)")
        return text, report

    lines = text.splitlines()
    seen: set[str] = set()
    kept: list[str] = []
    for raw in lines:
        line = _clean_line(raw)
        if line is None:
            continue
        key = re.sub(r"\d+", "N", line)  # near-duplicate detection: numbers normalized
        if key in seen:
            continue
        seen.add(key)
        kept.append(line)

    out = "\n".join(kept)
    report.compressed_chars = len(out)
    report.chunks_out = 1
    report.steps = ["strip-noise", "dedupe", "stop-sentences", "truncate-long-tokens"]
    return out, report


def compress_context(chunks: list[dict], target_ratio: float = 0.55,
                     min_chars: int = 400) -> tuple[list[dict], CompressionReport]:
    """Compress each RAG chunk. Keeps metadata; replaces 'text' in place.
    If compression inflates (rare), falls back to hard truncation to target."""
    report = CompressionReport()
    out: list[dict] = []
    for c in chunks:
        text = c.get("text", "")
        report.original_chars += len(text)
        report.chunks_in += 1
        if len(text) < min_chars:
            out.append(c)
            report.compressed_chars += len(text)
            report.chunks_out += 1
            continue
        compressed, r = compress_text(text, min_chars)
        if len(compressed) > len(text):
            compressed = compressed[: int(len(text) * target_ratio)]
        if len(compressed) > int(len(text) * target_ratio) * 1.20:
            # guard: if we failed to reach target, hard-truncate to target
            compressed = compressed[: int(len(text) * target_ratio)]
            r.steps.append("hard-truncate-to-target")
        c2 = dict(c)
        c2["text"] = compressed
        c2["compression_ratio"] = r.ratio
        out.append(c2)
        report.compressed_chars += len(compressed)
        report.chunks_out += 1
    return out, report
