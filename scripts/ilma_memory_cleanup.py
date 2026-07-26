#!/usr/bin/env python3
"""
ILMA Memory Cleanup/Compaction - Maintenance and space recovery.

This module provides memory cleanup and compaction capabilities including:
- Duplicate detection and removal
- Low-importance entry pruning
- Storage compaction
- Access-pattern-based cleanup
- Tag-based removal

Usage:
    python ilma_memory_cleanup.py --dedup
    python ilma_memory_cleanup.py --prune --threshold 0.3
    python ilma_memory_cleanup.py --compact

Author: ILMA Memory Category
Date: 2026-05-09
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import re
import sys
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Any

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('/root/.hermes/profiles/ilma/logs/memory_cleanup.log')
    ]
)
logger = logging.getLogger(__name__)

# Constants
MEMORY_DIR = Path('/root/.hermes/profiles/ilma/memories')
SEMANTIC_FILE = MEMORY_DIR / 'semantic.json'
DEFAULT_THRESHOLD = 0.3
DEFAULT_MAX_AGE_DAYS = 30
DEFAULT_MIN_ACCESS_COUNT = 3


@dataclass
class CleanupStats:
    """Statistics from cleanup operation."""
    duplicates_removed: int = 0
    entries_pruned: int = 0
    space_recovered_bytes: int = 0
    tags_removed: int = 0
    compacted: bool = False
    duration_seconds: float = 0

    def to_dict(self) -> dict:
        return {
            'duplicates_removed': self.duplicates_removed,
            'entries_pruned': self.entries_pruned,
            'space_recovered_bytes': self.space_recovered_bytes,
            'tags_removed': self.tags_removed,
            'compacted': self.compacted,
            'duration_seconds': self.duration_seconds
        }


@dataclass
class MemoryEntry:
    """A memory entry for cleanup operations."""
    key: str
    content: str
    metadata: dict[str, Any] = field(default_factory=dict)
    tags: set[str] = field(default_factory=set)
    importance: float = 0.5
    created_at: datetime = field(default_factory=datetime.now)
    access_count: int = 0
    last_accessed: Optional[datetime] = None
    id: str = ""

    def content_hash(self) -> str:
        """Compute hash of content for duplicate detection."""
        return hashlib.sha256(self.content.encode()).hexdigest()

    def age_days(self) -> float:
        """Get age of entry in days."""
        return (datetime.now() - self.created_at).total_seconds() / 86400

    def is_stale(self, max_age_days: int = DEFAULT_MAX_AGE_DAYS, min_access: int = DEFAULT_MIN_ACCESS_COUNT) -> bool:
        """Check if entry is stale (old and rarely accessed)."""
        if self.access_count >= min_access:
            return False
        return self.age_days() > max_age_days

    def is_low_importance(self, threshold: float = DEFAULT_THRESHOLD) -> bool:
        """Check if importance is below threshold."""
        return self.importance < threshold


class MemoryCleanup:
    """
    ILMA Memory Cleanup and Compaction.
    Provides maintenance operations for memory storage.
    """

    def __init__(self, storage_file: Optional[Path] = None):
        self.storage_file = storage_file or SEMANTIC_FILE
        self.entries: dict[str, MemoryEntry] = {}
        self._load()
        logger.info(f"MemoryCleanup initialized with {len(self.entries)} entries")

    def _load(self) -> None:
        """Load entries from storage."""
        if not self.storage_file.exists():
            logger.warning(f"Storage file not found: {self.storage_file}")
            return

        try:
            data = json.loads(self.storage_file.read_text())
            self.entries = {}
            for key, val in data.get('entries', {}).items():
                self.entries[key] = MemoryEntry(
                    key=key,
                    id=val.get('id', ''),
                    content=val.get('content', ''),
                    metadata=val.get('metadata', {}),
                    tags=set(val.get('tags', [])),
                    importance=val.get('importance', 0.5),
                    created_at=datetime.fromisoformat(val.get('created_at', datetime.now().isoformat())),
                    access_count=val.get('access_count', 0),
                    last_accessed=datetime.fromisoformat(val['last_accessed']) if val.get('last_accessed') else None
                )
            logger.info(f"Loaded {len(self.entries)} entries")
        except Exception as e:
            logger.error(f"Failed to load entries: {e}")
            raise

    def _save(self) -> None:
        """Save entries to storage."""
        data = {
            'entries': {
                key: {
                    'id': e.id or hashlib.md5(e.content.encode()).hexdigest()[:12],
                    'content': e.content,
                    'metadata': e.metadata,
                    'tags': list(e.tags),
                    'importance': e.importance,
                    'created_at': e.created_at.isoformat(),
                    'access_count': e.access_count,
                    'last_accessed': e.last_accessed.isoformat() if e.last_accessed else None
                } for key, e in self.entries.items()
            }
        }
        self.storage_file.write_text(json.dumps(data, indent=2))
        logger.debug(f"Saved {len(self.entries)} entries")

    def find_duplicates(self) -> dict[str, list[str]]:
        """
        Find duplicate entries based on content hash.

        Returns:
            Dictionary mapping canonical key to list of duplicate keys
        """
        hash_map: dict[str, list[str]] = {}

        for key, entry in self.entries.items():
            content_hash = entry.content_hash()
            if content_hash not in hash_map:
                hash_map[content_hash] = []
            hash_map[content_hash].append(key)

        # Filter to only groups with duplicates
        duplicates = {h: keys for h, keys in hash_map.items() if len(keys) > 1}

        logger.info(f"Found {len(duplicates)} groups of duplicates")
        return duplicates

    def remove_duplicates(self, keep_strategy: str = 'newest') -> int:
        """
        Remove duplicate entries, keeping one from each group.

        Args:
            keep_strategy: 'newest', 'oldest', 'highest_importance', 'most_accessed'

        Returns:
            Number of duplicates removed
        """
        duplicates = self.find_duplicates()
        removed = 0

        for content_hash, keys in duplicates.items():
            if len(keys) <= 1:
                continue

            # Sort keys based on strategy
            if keep_strategy == 'newest':
                sorted_keys = sorted(keys, key=lambda k: self.entries[k].created_at, reverse=True)
            elif keep_strategy == 'oldest':
                sorted_keys = sorted(keys, key=lambda k: self.entries[k].created_at)
            elif keep_strategy == 'highest_importance':
                sorted_keys = sorted(keys, key=lambda k: self.entries[k].importance, reverse=True)
            elif keep_strategy == 'most_accessed':
                sorted_keys = sorted(keys, key=lambda k: self.entries[k].access_count, reverse=True)
            else:
                sorted_keys = keys

            # Keep first, remove rest
            keep_key = sorted_keys[0]
            for key in sorted_keys[1:]:
                del self.entries[key]
                removed += 1
                logger.debug(f"Removed duplicate: {key} (kept {keep_key})")

        if removed > 0:
            self._save()

        logger.info(f"Removed {removed} duplicate entries")
        return removed

    def prune_low_importance(self, threshold: float = DEFAULT_THRESHOLD) -> int:
        """
        Remove entries with importance below threshold.

        Args:
            threshold: Minimum importance value (0.0-1.0)

        Returns:
            Number of entries pruned
        """
        to_remove = [
            key for key, entry in self.entries.items()
            if entry.is_low_importance(threshold)
        ]

        for key in to_remove:
            del self.entries[key]
            logger.debug(f"Pruned low importance: {key}")

        if to_remove:
            self._save()

        count = len(to_remove)
        logger.info(f"Pruned {count} low-importance entries (threshold: {threshold})")
        return count

    def prune_stale(self, max_age_days: int = DEFAULT_MAX_AGE_DAYS, min_access_count: int = DEFAULT_MIN_ACCESS_COUNT) -> int:
        """
        Remove stale entries (old and rarely accessed).

        Args:
            max_age_days: Maximum age in days
            min_access_count: Minimum access count to be considered active

        Returns:
            Number of entries pruned
        """
        to_remove = [
            key for key, entry in self.entries.items()
            if entry.is_stale(max_age_days, min_access_count)
        ]

        for key in to_remove:
            del self.entries[key]
            logger.debug(f"Pruned stale: {key}")

        if to_remove:
            self._save()

        count = len(to_remove)
        logger.info(f"Pruned {count} stale entries (max age: {max_age_days} days, min access: {min_access_count})")
        return count

    def prune_by_tag(self, tags: list[str], match_all: bool = False) -> int:
        """
        Remove entries matching specific tags.

        Args:
            tags: List of tags to match
            match_all: If True, all tags must match; if False, any tag matches

        Returns:
            Number of entries removed
        """
        def should_remove(entry: MemoryEntry) -> bool:
            entry_tags = {t.lower() for t in entry.tags}
            match_tags = {t.lower() for t in tags}

            if match_all:
                return match_tags.issubset(entry_tags)
            else:
                return bool(entry_tags & match_tags)

        to_remove = [key for key, entry in self.entries.items() if should_remove(entry)]

        for key in to_remove:
            del self.entries[key]

        if to_remove:
            self._save()

        count = len(to_remove)
        mode = "all" if match_all else "any"
        logger.info(f"Pruned {count} entries matching tags {tags} ({mode} match)")
        return count

    def analyze_content_similarity(self, threshold: float = 0.85) -> list[tuple[str, str, float]]:
        """
        Find similar content using simple n-gram comparison.

        Args:
            threshold: Similarity threshold (0.0-1.0)

        Returns:
            List of (key1, key2, similarity) tuples
        """
        def get_ngrams(text: str, n: int = 3) -> set[str]:
            text = text.lower()
            text = re.sub(r'[^a-z0-9\s]', ' ', text)
            words = text.split()
            return set(' '.join(words[i:i+n]) for i in range(len(words) - n + 1))

        similarities = []
        keys = list(self.entries.keys())

        for i in range(len(keys)):
            for j in range(i + 1, len(keys)):
                entry1 = self.entries[keys[i]]
                entry2 = self.entries[keys[j]]

                ngrams1 = get_ngrams(entry1.content)
                ngrams2 = get_ngrams(entry2.content)

                if not ngrams1 or not ngrams2:
                    continue

                intersection = len(ngrams1 & ngrams2)
                union = len(ngrams1 | ngrams2)
                similarity = intersection / union if union > 0 else 0

                if similarity >= threshold:
                    similarities.append((keys[i], keys[j], similarity))

        logger.info(f"Found {len(similarities)} similar content pairs")
        return similarities

    def remove_similar(self, threshold: float = 0.85, keep_strategy: str = 'newest') -> int:
        """
        Remove similar content pairs.

        Args:
            threshold: Similarity threshold
            keep_strategy: Which to keep on similarity

        Returns:
            Number of entries removed
        """
        similar_pairs = self.analyze_content_similarity(threshold)
        to_remove: set[str] = set()

        for key1, key2, sim in similar_pairs:
            if key1 in to_remove or key2 in to_remove:
                continue

            entry1 = self.entries[key1]
            entry2 = self.entries[key2]

            # Determine which to keep
            if keep_strategy == 'newest':
                keep = key1 if entry1.created_at > entry2.created_at else key2
            elif keep_strategy == 'oldest':
                keep = key1 if entry1.created_at < entry2.created_at else key2
            elif keep_strategy == 'highest_importance':
                keep = key1 if entry1.importance > entry2.importance else key2
            elif keep_strategy == 'most_accessed':
                keep = key1 if entry1.access_count > entry2.access_count else key2
            else:
                keep = key1

            remove = key2 if keep == key1 else key1
            to_remove.add(remove)
            logger.debug(f"Removing similar content: {remove} (similar to {keep}, sim={sim:.2f})")

        for key in to_remove:
            del self.entries[key]

        if to_remove:
            self._save()

        count = len(to_remove)
        logger.info(f"Removed {count} similar entries")
        return count

    def compact(self) -> bool:
        """
        Compact storage by rewriting with minimal whitespace.

        Returns:
            True if compaction successful
        """
        try:
            # Rewrite with minimal spacing
            data = {
                'entries': {
                    key: {
                        'id': e.id or hashlib.md5(e.content.encode()).hexdigest()[:12],
                        'content': e.content,
                        'metadata': e.metadata,
                        'tags': list(e.tags),
                        'importance': e.importance,
                        'created_at': e.created_at.isoformat(),
                        'access_count': e.access_count,
                        'last_accessed': e.last_accessed.isoformat() if e.last_accessed else None
                    } for key, e in self.entries.items()
                }
            }

            original_size = self.storage_file.stat().st_size if self.storage_file.exists() else 0

            # Write compact JSON (no indent)
            self.storage_file.write_text(json.dumps(data, separators=(',', ':')))

            new_size = self.storage_file.stat().st_size
            saved = original_size - new_size

            logger.info(f"Compacted storage: {original_size} -> {new_size} bytes (saved {saved})")
            return True

        except Exception as e:
            logger.error(f"Compaction failed: {e}")
            return False

    def full_cleanup(
        self,
        dedup: bool = True,
        prune_importance: Optional[float] = None,
        prune_stale: bool = True,
        max_age_days: int = DEFAULT_MAX_AGE_DAYS,
        min_access: int = DEFAULT_MIN_ACCESS_COUNT,
        compact: bool = True
    ) -> CleanupStats:
        """
        Perform full cleanup operation.

        Args:
            dedup: Enable duplicate removal
            prune_importance: Threshold for importance pruning (None to skip)
            prune_stale: Enable stale pruning
            max_age_days: Max age for stale detection
            min_access: Min access count for stale detection
            compact: Enable storage compaction

        Returns:
            CleanupStats with operation results
        """
        start_time = datetime.now()
        stats = CleanupStats()

        logger.info("Starting full cleanup...")

        if dedup:
            stats.duplicates_removed = self.remove_duplicates()

        if prune_importance is not None:
            stats.entries_pruned += self.prune_low_importance(prune_importance)

        if prune_stale:
            stats.entries_pruned += self.prune_stale(max_age_days, min_access)

        if compact:
            stats.compacted = self.compact()

        stats.duration_seconds = (datetime.now() - start_time).total_seconds()

        logger.info(f"Cleanup complete: {stats.duration_seconds:.2f}s")
        return stats

    def get_statistics(self) -> dict[str, Any]:
        """Get cleanup statistics and memory analysis."""
        entries = list(self.entries.values())

        importance_dist = Counter(e.importance for e in entries)
        age_dist = {
            'lt_1d': sum(1 for e in entries if e.age_days() < 1),
            '1_7d': sum(1 for e in entries if 1 <= e.age_days() < 7),
            '7_30d': sum(1 for e in entries if 7 <= e.age_days() < 30),
            'gt_30d': sum(1 for e in entries if e.age_days() >= 30)
        }

        all_tags = Counter(tag for e in entries for tag in e.tags)

        return {
            'total_entries': len(entries),
            'total_content_size': sum(len(e.content) for e in entries),
            'avg_importance': sum(e.importance for e in entries) / max(len(entries), 1),
            'importance_distribution': dict(importance_dist),
            'age_distribution': age_dist,
            'total_tags': len(all_tags),
            'top_tags': all_tags.most_common(10),
            'total_accesses': sum(e.access_count for e in entries),
            'avg_access_count': sum(e.access_count for e in entries) / max(len(entries), 1)
        }

    def health_check(self) -> dict[str, Any]:
        """Health check endpoint."""
        return {
            "ok": True,
            "module": "memory_cleanup",
            "entries": len(self.entries),
            "storage_file": str(self.storage_file)
        }


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description='ILMA Memory Cleanup/Compaction - Maintenance operations',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument('--dedup', action='store_true', help='Remove duplicate entries')
    parser.add_argument('--similar', action='store_true', help='Remove similar content')
    parser.add_argument('--similarity', type=float, default=0.85, help='Similarity threshold (default: 0.85)')
    parser.add_argument('--prune', action='store_true', help='Prune low importance entries')
    parser.add_argument('--threshold', '-t', type=float, default=DEFAULT_THRESHOLD, help='Importance threshold')
    parser.add_argument('--stale', action='store_true', help='Prune stale entries')
    parser.add_argument('--max-age', type=int, default=DEFAULT_MAX_AGE_DAYS, help='Max age in days')
    parser.add_argument('--min-access', type=int, default=DEFAULT_MIN_ACCESS_COUNT, help='Min access count')
    parser.add_argument('--tag', '-g', type=str, action='append', help='Prune entries with tag')
    parser.add_argument('--match-all-tags', action='store_true', help='Tag matching requires all tags')
    parser.add_argument('--compact', '-c', action='store_true', help='Compact storage')
    parser.add_argument('--full', action='store_true', help='Full cleanup (dedup + stale + compact)')
    parser.add_argument('--stats', '-s', action='store_true', help='Show cleanup statistics')
    parser.add_argument('--analyze', action='store_true', help='Analyze memory content')
    parser.add_argument('--health', action='store_true', help='Health check')

    args = parser.parse_args()

    try:
        cleanup = MemoryCleanup()

        if args.health:
            health = cleanup.health_check()
            print(f"\n[Health] {health}")
            sys.exit(0 if health['ok'] else 1)

        if args.analyze:
            stats = cleanup.get_statistics()
            print("\n[Memory Analysis]")
            print(f"  Total entries: {stats['total_entries']}")
            print(f"  Total content size: {stats['total_content_size']} bytes")
            print(f"  Avg importance: {stats['avg_importance']:.3f}")
            print(f"  Total accesses: {stats['total_accesses']}")
            print(f"  Total tags: {stats['total_tags']}")
            print(f"  Top tags: {', '.join(f'{t[0]}({t[1]})' for t in stats['top_tags'][:5])}")

        elif args.dedup:
            removed = cleanup.remove_duplicates()
            print(f"[OK] Removed {removed} duplicate entries")

        elif args.similar:
            removed = cleanup.remove_similar(threshold=args.similarity)
            print(f"[OK] Removed {removed} similar entries")

        elif args.prune:
            removed = cleanup.prune_low_importance(args.threshold)
            print(f"[OK] Pruned {removed} low-importance entries (threshold: {args.threshold})")

        elif args.stale:
            removed = cleanup.prune_stale(args.max_age, args.min_access)
            print(f"[OK] Pruned {removed} stale entries")

        elif args.tag:
            removed = cleanup.prune_by_tag(args.tag, match_all=args.match_all_tags)
            print(f"[OK] Pruned {removed} entries matching tags: {args.tag}")

        elif args.compact:
            if cleanup.compact():
                print("[OK] Storage compacted")
            else:
                print("[ERROR] Compaction failed")
                sys.exit(1)

        elif args.full:
            stats = cleanup.full_cleanup(
                dedup=True,
                prune_importance=args.threshold,
                prune_stale=True,
                max_age_days=args.max_age,
                min_access_count=args.min_access,
                compact=True
            )
            print("\n[Full Cleanup Complete]")
            print(f"  Duplicates removed: {stats.duplicates_removed}")
            print(f"  Entries pruned: {stats.entries_pruned}")
            print(f"  Compacted: {stats.compacted}")
            print(f"  Duration: {stats.duration_seconds:.2f}s")

        elif args.stats:
            stats = cleanup.get_statistics()
            print("\n[Cleanup Statistics]")
            print(f"  Total entries: {stats['total_entries']}")
            print(f"  Age distribution: {stats['age_distribution']}")
            print(f"  Top tags: {stats['top_tags'][:5]}")

        else:
            parser.print_help()

    except Exception as e:
        logger.error(f"Error: {e}")
        print(f"[ERROR] {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()