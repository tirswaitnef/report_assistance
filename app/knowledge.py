"""Offline, deterministic BM25 retrieval over checksum-verified OWASP snapshots."""
import hashlib
import json
import math
import re
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "data" / "owasp"


def tokens(text: str) -> list[str]:
    return re.findall(r"[a-z0-9_]+", text.lower())


QUERIES = {
    "sql_injection": "SQL injection prevention prepared statements parameterized queries",
    "excessive_privileges": "database permissions least privilege accounts administrative privileges",
    "tls_disabled": "database transport encryption TLS encrypted connections certificates",
    "exposed_database": "database network isolation firewall localhost restrict connections",
    "weak_auth": "database authentication passwords accounts strong credentials",
    "audit_logging": "logging security events audit database authentication failures",
    "secrets_management": "secrets credentials rotation password storage management",
    "other": "database security configuration verification",
}


class KnowledgeBase:
    def __init__(self, directory: Path = CORPUS):
        manifest = json.loads((directory / "manifest.json").read_text())
        self.sources = manifest["sources"]
        self.chunks = []
        for source in self.sources:
            raw = (directory / source["file"]).read_bytes()
            if hashlib.sha256(raw).hexdigest() != source["sha256"]:
                raise RuntimeError(f"OWASP snapshot checksum mismatch: {source['id']}")
            section, lines, parts = source["title"], [], []

            def emit():
                text = "\n".join(lines).strip()
                if text:
                    # Bound each chunk and preserve section identity and deterministic IDs.
                    for start in range(0, len(text), 1800):
                        parts.append((section, text[start:start + 1800]))

            for line in raw.decode().splitlines():
                if re.match(r"^#{1,6} ", line):
                    emit()
                    section, lines = line.lstrip("# ").strip(), []
                else:
                    lines.append(line)
            emit()
            source["chunks"] = len(parts)
            for index, (heading, content) in enumerate(parts):
                self.chunks.append({
                    "id": f"{source['id']}:{index:03d}", "source_id": source["id"],
                    "title": source["title"], "url": source["url"], "section": heading,
                    "text": content, "revision": source["revision"],
                    "snapshot_url": source["snapshot_url"],
                })
        self.term_counts = [Counter(tokens(c["section"] + " " + c["text"])) for c in self.chunks]
        self.lengths = [sum(c.values()) for c in self.term_counts]
        self.average_length = sum(self.lengths) / max(1, len(self.lengths))
        self.df = Counter(word for c in self.term_counts for word in c)

    def search(self, category: str, query: str, limit: int = 3) -> list[dict]:
        words = set(tokens(QUERIES[category] + " " + query))
        scored = []
        for index, counts in enumerate(self.term_counts):
            score = 0.0
            for word in words:
                frequency = counts[word]
                if not frequency:
                    continue
                inverse = math.log(1 + (len(self.chunks) - self.df[word] + 0.5) / (self.df[word] + 0.5))
                score += inverse * frequency * 2.5 / (frequency + 1.5 * (0.25 + 0.75 * self.lengths[index] / self.average_length))
            if score:
                scored.append((score, index))
        return [dict(self.chunks[index], score=round(score, 4))
                for score, index in sorted(scored, key=lambda x: (-x[0], x[1]))[:limit]]
