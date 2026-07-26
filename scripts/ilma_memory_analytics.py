#!/usr/bin/env python3
"""
ILMA Memory Analytics - Insight generation and pattern detection.

This module provides memory analytics capabilities including:
- Access pattern analysis
- Tag and topic clustering
- Importance trending
- Retention recommendations
- Memory health scoring

Usage:
    python ilma_memory_analytics.py --report
    python ilma_memory_analytics.py --trends
    python ilma_memory_analytics.py --score

Author: ILMA Memory Category
Date: 2026-05-09
"""

from __future__ import annotations

import argparse
import json
import logging
import math
import random
import sys
from collections import Counter, defaultdict
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
        logging.FileHandler('/root/.hermes/profiles/ilma/logs/memory_analytics.log')
    ]
)
logger = logging.getLogger(__name__)

# Constants
MEMORY_DIR = Path('/root/.hermes/profiles/ilma/memories')
SEMANTIC_FILE = MEMORY_DIR / 'semantic.json'
MEMORY_MD = MEMORY_DIR / 'MEMORY.md'
ANALYTICS_DIR = MEMORY_DIR / 'analytics'
ANALYTICS_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class MemoryEntry:
    """A memory entry for analytics."""
    key: str
    content: str
    metadata: dict[str, Any] = field(default_factory=dict)
    tags: set[str] = field(default_factory=set)
    importance: float = 0.5
    created_at: datetime = field(default_factory=datetime.now)
    access_count: int = 0
    last_accessed: Optional[datetime] = None
    id: str = ""


@dataclass
class MemoryScore:
    """Overall memory health and quality score."""
    overall: float = 0.0
    coverage: float = 0.0
    freshness: float = 0.0
    utilization: float = 0.0
    diversity: float = 0.0

    def to_dict(self) -> dict:
        return {
            'overall': round(self.overall, 3),
            'coverage': round(self.coverage, 3),
            'freshness': round(self.freshness, 3),
            'utilization': round(self.utilization, 3),
            'diversity': round(self.diversity, 3)
        }


@dataclass
class TrendData:
    """Trend analysis data."""
    timestamps: list[datetime] = field(default_factory=list)
    counts: list[int] = field(default_factory=list)
    avg_importance: list[float] = field(default_factory=list)
    tag_frequencies: list[dict[str, int]] = field(default_factory=list)


class MemoryAnalytics:
    """
    ILMA Memory Analytics - Pattern detection and insights.
    Provides comprehensive analytics for memory system.
    """

    def __init__(self, storage_file: Optional[Path] = None):
        self.storage_file = storage_file or SEMANTIC_FILE
        self.entries: dict[str, MemoryEntry] = {}
        self.analytics_file = ANALYTICS_DIR / 'last_report.json'
        self._load()
        logger.info(f"MemoryAnalytics initialized with {len(self.entries)} entries")

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

    def _save_analytics(self, data: dict[str, Any]) -> None:
        """Save analytics report."""
        self.analytics_file.write_text(json.dumps(data, indent=2))

    def compute_scores(self) -> MemoryScore:
        """
        Compute comprehensive memory health scores.

        Returns:
            MemoryScore with component and overall scores
        """
        entries = list(self.entries.values())
        score = MemoryScore()

        if not entries:
            return score

        # Coverage: What fraction of possible topics are covered?
        all_tags = set()
        for e in entries:
            all_tags.update(e.tags)
        unique_content_types = len(set(e.content[:50] for e in entries))  # Rough content diversity
        score.coverage = min(1.0, unique_content_types / max(len(entries), 1)) * 0.5 + min(1.0, len(all_tags) / 20) * 0.5

        # Freshness: How recent is the memory?
        now = datetime.now()
        ages = [(now - e.created_at).total_seconds() / 3600 for e in entries]  # hours
        avg_age_hours = sum(ages) / len(ages)
        score.freshness = math.exp(-avg_age_hours / (24 * 30))  # Decay over 30 days

        # Utilization: How well is memory being accessed?
        total_accesses = sum(e.access_count for e in entries)
        score.utilization = min(1.0, total_accesses / (len(entries) * 5))  # Target 5 accesses per entry

        # Diversity: Tags, importance distribution
        tag_diversity = len(all_tags) / max(20, len(entries))
        importance_spread = max(e.importance for e in entries) - min(e.importance for e in entries)
        score.diversity = min(1.0, tag_diversity * 0.7 + importance_spread * 0.3)

        # Overall: weighted combination
        score.overall = (
            0.30 * score.coverage +
            0.25 * score.freshness +
            0.25 * score.utilization +
            0.20 * score.diversity
        )

        return score

    def analyze_access_patterns(self) -> dict[str, Any]:
        """Analyze how memory is being accessed."""
        entries = list(self.entries.values())

        if not entries:
            return {'patterns': [], 'hot_tags': [], 'cold_tags': []}

        # Tag access analysis
        tag_access: dict[str, int] = defaultdict(int)
        tag_entries: dict[str, int] = defaultdict(int)

        for e in entries:
            for tag in e.tags:
                tag_access[tag] += e.access_count
                tag_entries[tag] += 1

        # Compute average access per tag
        tag_avg_access = {t: tag_access[t] / max(tag_entries[t], 1) for t in tag_access}

        # Sort tags by average access
        hot_tags = sorted(tag_avg_access.items(), key=lambda x: x[1], reverse=True)[:5]
        cold_tags = sorted(tag_avg_access.items(), key=lambda x: x[1])[:5]

        # Access distribution
        accesses = sorted([e.access_count for e in entries])
        access_percentiles = {
            'p50': accesses[len(accesses) // 2] if accesses else 0,
            'p90': accesses[int(len(accesses) * 0.9)] if accesses else 0,
            'p99': accesses[int(len(accesses) * 0.99)] if accesses else 0
        }

        # Entries with zero accesses
        zero_access_count = sum(1 for e in entries if e.access_count == 0)

        return {
            'patterns': {
                'total_accesses': sum(e.access_count for e in entries),
                'avg_per_entry': sum(e.access_count for e in entries) / max(len(entries), 1),
                'max_single_entry_accesses': max(e.access_count for e in entries) if entries else 0
            },
            'hot_tags': [{'tag': t, 'avg_access': a} for t, a in hot_tags],
            'cold_tags': [{'tag': t, 'avg_access': a} for t, a in cold_tags],
            'access_percentiles': access_percentiles,
            'zero_access_entries': zero_access_count,
            'zero_access_percent': zero_access_count / max(len(entries), 1) * 100
        }

    def analyze_trends(self, days: int = 7) -> TrendData:
        """
        Analyze memory trends over time.

        Args:
            days: Number of days to analyze

        Returns:
            TrendData with time series information
        """
        now = datetime.now()
        entries = list(self.entries.values())

        trends = TrendData()
        buckets: dict[str, list[MemoryEntry]] = defaultdict(list)

        # Group entries by day
        for e in entries:
            days_ago = (now - e.created_at).days
            bucket = f"day_{days_ago}"
            buckets[bucket].append(e)

        # Build time series
        for day_offset in range(days - 1, -1, -1):
            bucket_name = f"day_{day_offset}"
            day_entries = buckets.get(bucket_name, [])

            trends.timestamps.append(now - timedelta(days=day_offset))
            trends.counts.append(len(day_entries))

            if day_entries:
                trends.avg_importance.append(sum(e.importance for e in day_entries) / len(day_entries))
            else:
                trends.avg_importance.append(0.0)

        # Tag frequency per day (simplified - just overall)
        all_tag_freq = Counter()
        for e in entries:
            all_tag_freq.update(e.tags)
        trends.tag_frequencies.append(dict(all_tag_freq.most_common(20)))

        return trends

    def generate_recommendations(self) -> list[dict[str, Any]]:
        """
        Generate recommendations based on analytics.

        Returns:
            List of recommendation dictionaries
        """
        recommendations = []
        entries = list(self.entries.values())

        if not entries:
            return [{'type': 'init', 'priority': 'high', 'message': 'No memory entries found. Start building memory.'}]

        # Check for low utilization
        zero_access = sum(1 for e in entries if e.access_count == 0)
        if zero_access > len(entries) * 0.5:
            recommendations.append({
                'type': 'utilization',
                'priority': 'high',
                'message': f'{zero_access} entries ({zero_access/len(entries)*100:.0f}%) have never been accessed. Consider reviewing or removing.',
                'action': 'Run cleanup with --stale flag'
            })

        # Check for stale entries
        stale = sum(1 for e in entries if (datetime.now() - e.created_at).days > 30 and e.access_count < 3)
        if stale > 0:
            recommendations.append({
                'type': 'stale',
                'priority': 'medium',
                'message': f'{stale} entries are older than 30 days with low access. Consider pruning.',
                'action': 'Run cleanup with --stale --max-age 30'
            })

        # Check for low diversity
        all_tags = set()
        for e in entries:
            all_tags.update(e.tags)
        if len(all_tags) < 5 and len(entries) > 10:
            recommendations.append({
                'type': 'diversity',
                'priority': 'low',
                'message': 'Low tag diversity. Consider adding more structured tags.',
                'action': 'Review entries and add descriptive tags'
            })

        # Check for importance clustering
        importance_values = [e.importance for e in entries]
        avg_imp = sum(importance_values) / len(importance_values)
        low_imp_count = sum(1 for imp in importance_values if imp < avg_imp * 0.5)
        if low_imp_count > len(entries) * 0.3:
            recommendations.append({
                'type': 'importance',
                'priority': 'medium',
                'message': f'{low_imp_count} entries have very low importance scores.',
                'action': 'Run cleanup with --prune --threshold 0.3'
            })

        # Check for content gaps (no entries in last 24h)
        now = datetime.now()
        recent_entries = [e for e in entries if (now - e.created_at).total_seconds() < 86400]
        if not recent_entries and len(entries) > 5:
            recommendations.append({
                'type': 'freshness',
                'priority': 'medium',
                'message': 'No new entries in the last 24 hours. Memory may be stale.',
                'action': 'Consider adding new memories or reviewing existing ones'
            })

        return recommendations

    def cluster_by_tag(self) -> dict[str, list[str]]:
        """
        Cluster entries by tag co-occurrence.

        Returns:
            Dictionary mapping cluster ID to list of entry keys
        """
        entries = list(self.entries.values())
        clusters: dict[str, list[str]] = {}
        assigned: set[str] = set()

        # Create clusters based on tag overlap
        for i, entry in enumerate(entries):
            if entry.key in assigned:
                continue

            cluster_id = f"cluster_{i}"
            clusters[cluster_id] = [entry.key]
            assigned.add(entry.key)

            # Find entries with overlapping tags
            for other in entries:
                if other.key in assigned:
                    continue
                if entry.tags & other.tags:
                    clusters[cluster_id].append(other.key)
                    assigned.add(other.key)

        # Add unassigned entries as singletons
        for entry in entries:
            if entry.key not in assigned:
                clusters[f"cluster_{len(clusters)}"] = [entry.key]

        logger.info(f"Created {len(clusters)} tag clusters")
        return clusters

    def compute_topic_model(self, num_topics: int = 5) -> dict[str, list[str]]:
        """
        Simple topic modeling based on content keywords.

        Args:
            num_topics: Number of topics to extract

        Returns:
            Dictionary mapping topic labels to related entry keys
        """
        entries = list(self.entries.values())

        # Extract keywords from all content
        all_words: Counter = Counter()
        for e in entries:
            words = e.content.lower().split()
            all_words.update([w for w in words if len(w) > 4])

        # Get top keyword clusters
        top_keywords = [kw for kw, _ in all_words.most_common(num_topics * 10)]

        # Group entries by keyword presence
        topic_entries: dict[str, list[str]] = {}
        keywords_per_topic = top_keywords[:num_topics * 5]

        for kw in keywords_per_topic[:num_topics]:
            topic_entries[kw] = []

        for e in entries:
            content_lower = e.content.lower()
            for kw in keywords_per_topic[:num_topics]:
                if kw in content_lower:
                    topic_entries[kw].append(e.key)

        # Filter to non-empty topics
        topic_entries = {k: v for k, v in topic_entries.items() if v}

        return topic_entries

    def generate_report(self) -> dict[str, Any]:
        """
        Generate comprehensive analytics report.

        Returns:
            Dictionary with full analytics report
        """
        scores = self.compute_scores()
        access_patterns = self.analyze_access_patterns()
        trends = self.analyze_trends()
        recommendations = self.generate_recommendations()
        clusters = self.cluster_by_tag()

        report = {
            'generated_at': datetime.now().isoformat(),
            'scores': scores.to_dict(),
            'access_patterns': access_patterns,
            'trends': {
                'days_analyzed': len(trends.counts),
                'counts': trends.counts,
                'avg_importance': [round(x, 3) for x in trends.avg_importance]
            },
            'recommendations': recommendations,
            'clusters': {k: len(v) for k, v in list(clusters.items())[:10]},
            'total_entries': len(self.entries),
            'total_tags': len(set(tag for e in self.entries.values() for tag in e.tags)),
            'total_accesses': sum(e.access_count for e in self.entries.values())
        }

        self._save_analytics(report)
        logger.info("Analytics report generated")

        return report

    def format_report_text(self, report: dict[str, Any]) -> str:
        """Format report as human-readable text."""
        lines = [
            "=" * 60,
            "ILMA MEMORY ANALYTICS REPORT",
            "=" * 60,
            f"Generated: {report['generated_at']}",
            "",
            "MEMORY HEALTH SCORES",
            "-" * 40,
            f"  Overall:      {report['scores']['overall']:.1%}",
            f"  Coverage:     {report['scores']['coverage']:.1%}",
            f"  Freshness:    {report['scores']['freshness']:.1%}",
            f"  Utilization:  {report['scores']['utilization']:.1%}",
            f"  Diversity:    {report['scores']['diversity']:.1%}",
            "",
            "MEMORY STATISTICS",
            "-" * 40,
            f"  Total entries:    {report['total_entries']}",
            f"  Total tags:       {report['total_tags']}",
            f"  Total accesses:   {report['total_accesses']}",
            "",
            "ACCESS PATTERNS",
            "-" * 40,
            f"  Hot tags: {', '.join(t['tag'] for t in report['access_patterns'].get('hot_tags', [])[:3])}",
            f"  Zero-access entries: {report['access_patterns'].get('zero_access_entries', 0)}",
            "",
            "TRENDS",
            "-" * 40,
            f"  Entries this week: {sum(report['trends']['counts'])}",
            "",
            "RECOMMENDATIONS",
            "-" * 40,
        ]

        for rec in report.get('recommendations', []):
            lines.append(f"  [{rec['priority'].upper()}] {rec['message']}")
            lines.append(f"           Action: {rec.get('action', 'N/A')}")

        lines.append("")
        lines.append("=" * 60)

        return "\n".join(lines)

    def health_check(self) -> dict[str, Any]:
        """Health check endpoint."""
        scores = self.compute_scores()
        return {
            "ok": True,
            "module": "memory_analytics",
            "entries": len(self.entries),
            "health_score": scores.overall,
            "analytics_dir": str(ANALYTICS_DIR)
        }


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description='ILMA Memory Analytics - Insights and pattern detection',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument('--report', '-r', action='store_true', help='Generate full analytics report')
    parser.add_argument('--scores', '-s', action='store_true', help='Show memory health scores')
    parser.add_argument('--access', '-a', action='store_true', help='Show access pattern analysis')
    parser.add_argument('--trends', '-t', action='store_true', help='Show trend analysis')
    parser.add_argument('--recommend', action='store_true', help='Show recommendations')
    parser.add_argument('--clusters', action='store_true', help='Show tag clusters')
    parser.add_argument('--topics', action='store_true', help='Show topic model')
    parser.add_argument('--json', '-j', action='store_true', help='Output as JSON')
    parser.add_argument('--health', action='store_true', help='Health check')
    parser.add_argument('--days', type=int, default=7, help='Days to analyze for trends (default: 7)')

    args = parser.parse_args()

    try:
        analytics = MemoryAnalytics()

        if args.health:
            health = analytics.health_check()
            print(f"\n[Health] {health}")
            sys.exit(0 if health['ok'] else 1)

        if args.scores:
            scores = analytics.compute_scores()
            print("\n[Memory Health Scores]")
            print(f"  Overall:      {scores.overall:.1%}")
            print(f"  Coverage:     {scores.coverage:.1%}")
            print(f"  Freshness:    {scores.freshness:.1%}")
            print(f"  Utilization:  {scores.utilization:.1%}")
            print(f"  Diversity:    {scores.diversity:.1%}")

        elif args.access:
            patterns = analytics.analyze_access_patterns()
            print("\n[Access Patterns]")
            print(f"  Total accesses: {patterns['patterns']['total_accesses']}")
            print(f"  Avg per entry: {patterns['patterns']['avg_per_entry']:.2f}")
            print(f"  Hot tags: {', '.join(t['tag'] for t in patterns.get('hot_tags', [])[:3])}")
            print(f"  Cold tags: {', '.join(t['tag'] for t in patterns.get('cold_tags', [])[:3])}")
            print(f"  Zero-access entries: {patterns.get('zero_access_entries', 0)}")

        elif args.trends:
            trends = analytics.analyze_trends(days=args.days)
            print(f"\n[Trend Analysis - Last {args.days} days]")
            for i, (ts, count, avg_imp) in enumerate(zip(trends.timestamps, trends.counts, trends.avg_importance)):
                print(f"  {ts.strftime('%Y-%m-%d')}: {count} entries, avg importance {avg_imp:.2f}")

        elif args.recommend:
            recs = analytics.generate_recommendations()
            print("\n[Recommendations]")
            for rec in recs:
                print(f"  [{rec['priority'].upper()}] {rec['message']}")

        elif args.clusters:
            clusters = analytics.cluster_by_tag()
            print(f"\n[Tag Clusters - {len(clusters)} clusters]")
            for cid, keys in list(clusters.items())[:10]:
                print(f"  {cid}: {len(keys)} entries")

        elif args.topics:
            topics = analytics.compute_topic_model()
            print("\n[Topic Model]")
            for topic, keys in topics.items():
                print(f"  {topic}: {len(keys)} entries")

        elif args.report:
            report = analytics.generate_report()
            if args.json:
                print(json.dumps(report, indent=2))
            else:
                print(analytics.format_report_text(report))

        else:
            parser.print_help()

    except Exception as e:
        logger.error(f"Error: {e}")
        print(f"[ERROR] {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()