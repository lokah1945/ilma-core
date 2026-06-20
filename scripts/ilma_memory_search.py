#!/usr/bin/env python3
"""
ILMA Memory Search/Retrieval - Semantic search with BM25 and cosine similarity.

This module provides advanced memory retrieval capabilities combining BM25 ranking
algorithm with TF-IDF cosine similarity for comprehensive semantic search.

Features:
- BM25-based text ranking for keyword matching
- Cosine similarity for semantic matching
- Combined scoring for improved relevance
- Tag-based and metadata filtering
- Access tracking for learning

Usage:
    python ilma_memory_search.py --query "python programming" --limit 10
    python ilma_memory_search.py --tag python
    python ilma_memory_search.py --stats

Author: ILMA Memory Category
Date: 2026-05-09
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import math
import re
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('/root/.hermes/profiles/ilma/logs/memory_search.log')
    ]
)
logger = logging.getLogger(__name__)

# Constants
MEMORY_DIR = Path('/root/.hermes/profiles/ilma/memories')
DEFAULT_STORAGE = MEMORY_DIR / 'semantic.json'
BM25_K1 = 1.5
BM25_B = 0.75


@dataclass
class MemoryEntry:
    """A single memory entry with content, metadata, and access tracking."""
    id: str
    content: str
    metadata: dict[str, Any] = field(default_factory=dict)
    tags: set[str] = field(default_factory=set)
    importance: float = 0.5
    created_at: datetime = field(default_factory=datetime.now)
    access_count: int = 0
    last_accessed: Optional[datetime] = None

    def to_dict(self) -> dict:
        """Convert entry to dictionary for serialization."""
        return {
            'id': self.id,
            'content': self.content,
            'metadata': self.metadata,
            'tags': list(self.tags),
            'importance': self.importance,
            'created_at': self.created_at.isoformat(),
            'access_count': self.access_count,
            'last_accessed': self.last_accessed.isoformat() if self.last_accessed else None
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'MemoryEntry':
        """Create entry from dictionary."""
        return cls(
            id=data['id'],
            content=data['content'],
            metadata=data.get('metadata', {}),
            tags=set(data.get('tags', [])),
            importance=data.get('importance', 0.5),
            created_at=datetime.fromisoformat(data.get('created_at', datetime.now().isoformat())),
            access_count=data.get('access_count', 0),
            last_accessed=datetime.fromisoformat(data['last_accessed']) if data.get('last_accessed') else None
        )


class BM25Ranker:
    """BM25 ranking algorithm implementation."""

    def __init__(self, k1: float = BM25_K1, b: float = BM25_B):
        self.k1 = k1
        self.b = b
        self.doc_freqs: dict[str, int] = {}
        self.avgdl: float = 0
        self.doc_lengths: list[int] = []
        self.doc_count: int = 0
        self.corpus: list[str] = []

    def index(self, corpus: list[str]) -> None:
        """Build BM25 index from corpus of documents."""
        self.corpus = corpus
        self.doc_count = len(corpus)
        self.doc_lengths = []
        self.doc_freqs = defaultdict(int)

        total_len = 0
        for doc in corpus:
            tokens = self._tokenize(doc)
            self.doc_lengths.append(len(tokens))
            total_len += len(tokens)

            unique_terms = set(tokens)
            for term in unique_terms:
                self.doc_freqs[term] += 1

        self.avgdl = total_len / max(self.doc_count, 1)
        logger.info(f"BM25 index built: {self.doc_count} docs, avg len {self.avgdl:.1f}")

    def _tokenize(self, text: str) -> list[str]:
        """Tokenize text into lowercase alphanumeric tokens."""
        text = text.lower()
        text = re.sub(r'[^a-z0-9\s]', ' ', text)
        tokens = text.split()
        return [t for t in tokens if len(t) > 2]

    def score(self, query: str, doc_idx: int) -> float:
        """Calculate BM25 score for query against document."""
        query_terms = self._tokenize(query)
        doc_tokens = self._tokenize(self.corpus[doc_idx])
        doc_len = len(doc_tokens)
        doc_tf = Counter(doc_tokens)

        score = 0.0
        for term in query_terms:
            if term not in doc_tf:
                continue

            tf = doc_tf[term]
            df = self.doc_freqs.get(term, 0)

            if df == 0:
                continue

            idf = math.log((self.doc_count - df + 0.5) / (df + 0.5) + 1)
            tf_component = (tf * (self.k1 + 1)) / (tf + self.k1 * (1 - self.b + self.b * doc_len / max(self.avgdl, 1)))

            score += idf * tf_component

        return score

    def get_scores(self, query: str) -> list[float]:
        """Get BM25 scores for all documents."""
        return [self.score(query, i) for i in range(self.doc_count)]


class MemorySearch:
    """
    ILMA Memory Search with semantic retrieval capabilities.
    Combines BM25 ranking and cosine similarity for comprehensive search.
    """

    def __init__(self, storage_file: Optional[Path] = None):
        self.storage_file = storage_file or DEFAULT_STORAGE
        self.storage_file.parent.mkdir(parents=True, exist_ok=True)
        self.entries: dict[str, MemoryEntry] = {}
        self.bm25: Optional[BM25Ranker] = None
        self._dirty = False
        self.load()
        logger.info(f"MemorySearch initialized with {len(self.entries)} entries")

    def _tokenize(self, text: str) -> list[str]:
        """Tokenize text for TF-IDF computation."""
        text = text.lower()
        text = re.sub(r'[^a-z0-9\s]', ' ', text)
        return [t for t in text.split() if len(t) > 2]

    def _compute_tf(self, tokens: list[str]) -> dict[str, float]:
        """Compute term frequency normalized by document length."""
        counts = Counter(tokens)
        total = len(tokens)
        return {t: c / total for t, c in counts.items()} if total > 0 else {}

    def _compute_idf(self, all_tokens: list[list[str]]) -> dict[str, float]:
        """Compute inverse document frequency."""
        doc_count = len(all_tokens)
        df = defaultdict(int)
        for tokens in all_tokens:
            for term in set(tokens):
                df[term] += 1

        return {t: math.log(doc_count / (df[t] + 1)) for t in df}

    def _cosine_sim(self, vec1: dict[str, float], vec2: dict[str, float]) -> float:
        """Compute cosine similarity between two TF-IDF vectors."""
        common_keys = set(vec1.keys()) & set(vec2.keys())
        if not common_keys:
            return 0.0

        dot_product = sum(vec1[k] * vec2[k] for k in common_keys)
        mag1 = math.sqrt(sum(v * v for v in vec1.values()))
        mag2 = math.sqrt(sum(v * v for v in vec2.values()))

        if mag1 == 0 or mag2 == 0:
            return 0.0

        return dot_product / (mag1 * mag2)

    def _build_tfidf(self, query: str, corpus_tokens: list[list[str]]) -> tuple[dict[str, float], list[dict[str, float]]]:
        """Build TF-IDF vectors for query and corpus."""
        idf = self._compute_idf(corpus_tokens)
        idf_keys = set(idf.keys())

        query_tokens = self._tokenize(query)
        query_tf = self._compute_tf(query_tokens)
        query_vec = {t: query_tf[t] * idf.get(t, 0) for t in query_tf if t in idf_keys}

        doc_vecs = []
        for tokens in corpus_tokens:
            doc_tf = self._compute_tf(tokens)
            doc_vec = {t: doc_tf[t] * idf.get(t, 0) for t in doc_tf if t in idf_keys}
            doc_vecs.append(doc_vec)

        return query_vec, doc_vecs

    def _rebuild_index(self) -> None:
        """Rebuild BM25 index."""
        if not self.entries:
            self.bm25 = None
            return

        corpus = [e.content for e in self.entries.values()]
        self.bm25 = BM25Ranker(k1=BM25_K1, b=BM25_B)
        self.bm25.index(corpus)

    def load(self) -> None:
        """Load memory entries from storage file."""
        if not self.storage_file.exists():
            logger.info("No existing memory storage found, starting fresh")
            return

        try:
            data = json.loads(self.storage_file.read_text())
            self.entries = {}
            for key, val in data.get('entries', {}).items():
                try:
                    self.entries[key] = MemoryEntry.from_dict(val)
                except Exception as e:
                    logger.warning(f"Failed to load entry {key}: {e}")
            self._rebuild_index()
            logger.info(f"Loaded {len(self.entries)} entries from storage")
        except Exception as e:
            logger.error(f"Error loading memory storage: {e}")
            self.entries = {}

    def save(self) -> None:
        """Save memory entries to storage file."""
        try:
            data = {
                'entries': {
                    key: entry.to_dict() for key, entry in self.entries.items()
                }
            }
            self.storage_file.write_text(json.dumps(data, indent=2))
            self._dirty = False
            logger.debug(f"Saved {len(self.entries)} entries to storage")
        except Exception as e:
            logger.error(f"Error saving memory: {e}")
            raise

    def store(
        self,
        key: str,
        content: str,
        metadata: Optional[dict] = None,
        tags: Optional[list[str]] = None,
        importance: float = 0.5
    ) -> str:
        """
        Store a new memory entry.

        Args:
            key: Unique identifier for the memory
            content: The memory content
            metadata: Optional metadata dictionary
            tags: Optional list of tags
            importance: Importance score 0.0-1.0

        Returns:
            The generated entry ID
        """
        entry = MemoryEntry(
            id=hashlib.md5(content.encode()).hexdigest()[:12],
            content=content,
            metadata=metadata or {},
            tags=set(tags or []),
            importance=importance,
            created_at=datetime.now()
        )
        self.entries[key] = entry
        self._dirty = True
        self._rebuild_index()

        if self._dirty:
            self.save()

        logger.info(f"Stored memory: {key} ({entry.id})")
        return entry.id

    def retrieve(
        self,
        query: str,
        limit: int = 10,
        use_bm25: bool = True,
        use_cosine: bool = True
    ) -> list[dict[str, Any]]:
        """
        Retrieve memories using combined BM25 and cosine similarity scoring.

        Args:
            query: Search query
            limit: Maximum number of results
            use_bm25: Use BM25 scoring
            use_cosine: Use cosine similarity

        Returns:
            List of result dictionaries with entry, scores, and key
        """
        if not self.entries:
            return []

        results = []
        keys = list(self.entries.keys())
        contents = [self.entries[k].content for k in keys]

        bm25_scores = []
        if use_bm25 and self.bm25:
            bm25_scores = self.bm25.get_scores(query)

        cosine_scores = []
        if use_cosine:
            corpus_tokens = [self._tokenize(c) for c in contents]
            query_vec, doc_vecs = self._build_tfidf(query, corpus_tokens)
            for doc_vec in doc_vecs:
                cosine_scores.append(self._cosine_sim(query_vec, doc_vec))

        for i, key in enumerate(keys):
            entry = self.entries[key]

            bm25_norm = bm25_scores[i] / max(bm25_scores) if bm25_scores and max(bm25_scores) > 0 else 0
            cosine_norm = cosine_scores[i] if cosine_scores else 0

            combined = (0.6 * bm25_norm + 0.4 * cosine_norm) if use_bm25 and use_cosine else (bm25_norm if use_bm25 else cosine_norm)
            combined *= (0.5 + 0.5 * entry.importance)

            results.append({
                'key': key,
                'entry': entry,
                'score': combined,
                'bm25': bm25_norm,
                'cosine': cosine_norm
            })

        results.sort(key=lambda x: x['score'], reverse=True)

        for r in results[:limit]:
            r['entry'].access_count += 1
            r['entry'].last_accessed = datetime.now()

        if self._dirty:
            self.save()

        return results[:limit]

    def get_by_tag(self, tag: str) -> list[MemoryEntry]:
        """Get all entries with a specific tag."""
        return [e for e in self.entries.values() if tag.lower() in [t.lower() for t in e.tags]]

    def get_by_metadata(self, key: str, value: Any) -> list[MemoryEntry]:
        """Get all entries with specific metadata value."""
        return [e for e in self.entries.values() if e.metadata.get(key) == value]

    def delete(self, key: str) -> bool:
        """Delete a memory entry by key."""
        if key in self.entries:
            del self.entries[key]
            self._rebuild_index()
            self.save()
            logger.info(f"Deleted memory: {key}")
            return True
        return False

    def get_statistics(self) -> dict[str, Any]:
        """Get memory statistics."""
        entries = list(self.entries.values())
        return {
            'total_entries': len(entries),
            'total_accesses': sum(e.access_count for e in entries),
            'avg_importance': sum(e.importance for e in entries) / max(len(entries), 1),
            'all_tags': list(set(tag for e in entries for tag in e.tags)),
            'newest': min((e.created_at for e in entries), default=None),
            'most_accessed': max((e.access_count for e in entries), default=0),
            'storage_file': str(self.storage_file)
        }

    def health_check(self) -> dict[str, Any]:
        """Health check endpoint."""
        return {
            "ok": True,
            "module": "memory_search",
            "entries": len(self.entries),
            "indexed": self.bm25 is not None,
            "dirty": self._dirty
        }


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description='ILMA Memory Search - Semantic retrieval with BM25 and cosine similarity',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument('--query', '-q', type=str, help='Search query')
    parser.add_argument('--limit', '-l', type=int, default=10, help='Maximum results (default: 10)')
    parser.add_argument('--tag', '-t', type=str, help='Filter by tag')
    parser.add_argument('--store', '-s', nargs=3, metavar=('KEY', 'CONTENT', 'TAGS'),
                        help='Store a memory: KEY CONTENT "tag1,tag2"')
    parser.add_argument('--delete', '-d', type=str, help='Delete a memory by key')
    parser.add_argument('--stats', action='store_true', help='Show memory statistics')
    parser.add_argument('--health', action='store_true', help='Health check')
    parser.add_argument('--no-bm25', action='store_true', help='Disable BM25 scoring')
    parser.add_argument('--no-cosine', action='store_true', help='Disable cosine similarity')

    args = parser.parse_args()

    try:
        search = MemorySearch()

        if args.store:
            key, content, tags = args.store
            tag_list = [t.strip() for t in tags.split(',')] if tags else []
            entry_id = search.store(key, content, tags=tag_list)
            print(f"[OK] Stored memory '{key}' with ID: {entry_id}")

        elif args.delete:
            if search.delete(args.delete):
                print(f"[OK] Deleted memory: {args.delete}")
            else:
                print(f"[WARN] Memory not found: {args.delete}")

        elif args.tag:
            entries = search.get_by_tag(args.tag)
            print(f"\n[Results] Found {len(entries)} entries with tag '{args.tag}':")
            for e in entries[:args.limit]:
                print(f"  [{e.importance:.2f}] {e.content[:80]}...")

        elif args.stats:
            stats = search.get_statistics()
            print("\n[Memory Statistics]")
            print(f"  Total entries: {stats['total_entries']}")
            print(f"  Total accesses: {stats['total_accesses']}")
            print(f"  Avg importance: {stats['avg_importance']:.3f}")
            print(f"  Most accessed: {stats['most_accessed']} times")
            print(f"  Tags: {', '.join(stats['all_tags'][:10])}{'...' if len(stats['all_tags']) > 10 else ''}")
            print(f"  Storage: {stats['storage_file']}")

        elif args.health:
            health = search.health_check()
            print(f"\n[Health] {health}")
            sys.exit(0 if health['ok'] else 1)

        elif args.query:
            results = search.retrieve(
                args.query,
                limit=args.limit,
                use_bm25=not args.no_bm25,
                use_cosine=not args.no_cosine
            )
            print(f"\n[Search] Query: '{args.query}' - Found {len(results)} results:")
            for r in results:
                print(f"  [{r['score']:.3f}] {r['entry'].content[:80]}...")
                print(f"         BM25: {r['bm25']:.3f}, Cosine: {r['cosine']:.3f}")
        else:
            parser.print_help()

    except Exception as e:
        logger.error(f"Error: {e}")
        print(f"[ERROR] {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()