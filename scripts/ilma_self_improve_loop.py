#!/usr/bin/env python3
"""
ILMA Self-Improvement Loop Automation
=====================================
Automated self-improvement scanning and upgrade recommendation system.

This module implements the self-improvement loop for ILMA,
scanning learning files and generating prioritized upgrade recommendations.

Author: ILMA Runtime System
Version: 1.0.0
"""

import argparse
import logging
import os
import sys
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple, Union
from dataclasses import dataclass, field, asdict
from enum import Enum
import subprocess

# Configuration
# Use explicit path to avoid Path.home() expansion issues
PROFILE_PATH = Path("/root/.hermes/profiles/ilma")
LEARNINGS_PATH = PROFILE_PATH / ".learnings"
UPGRADE_RECOMMENDATIONS_PATH = LEARNINGS_PATH / "upgrade_recommendations.md"

# Learning files to scan
LEARNING_FILES = {
    "learnings": LEARNINGS_PATH / "LEARNINGS.md",
    "errors": LEARNINGS_PATH / "ERRORS.md",
    "feature_requests": LEARNINGS_PATH / "FEATURE_REQUESTS.md"
}


class Priority(Enum):
    """Improvement priority levels."""
    P1_CRITICAL = "P1"
    P2_HIGH = "P2"
    P3_MEDIUM = "P3"


class ImpactLevel(Enum):
    """Impact assessment levels."""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass
class LearningItem:
    """Represents a single learning item from scan."""
    id: str
    source_file: str
    category: str
    content: str
    timestamp: Optional[str] = None
    context: Optional[str] = None
    raw_line: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ScoredImprovement:
    """Represents a scored improvement recommendation."""
    id: str
    title: str
    description: str
    priority: Priority
    impact: ImpactLevel
    source_items: List[str]
    effort_estimate: str
    expected_benefit: str
    implementation_notes: str
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    score: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        result = asdict(self)
        result['priority'] = self.priority.value
        result['impact'] = self.impact.value
        return result
    
    def to_markdown(self) -> str:
        """Convert to markdown format for recommendations file."""
        source_list = "\n".join(f"- {s}" for s in self.source_items) if self.source_items else "- (derived)"
        return f"""## {self.id}: {self.title}

**Priority**: {self.priority.value} | **Impact**: {self.impact.value} | **Score**: {self.score:.2f}

### Description

{self.description}

### Expected Benefit

{self.expected_benefit}

### Implementation Notes

{self.implementation_notes}

### Effort Estimate

{effort_estimate}

### Source Items

{source_list}

**Created**: {self.created_at}

---
"""
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ScoredImprovement':
        """Create from dictionary."""
        data['priority'] = Priority(data['priority'])
        data['impact'] = ImpactLevel(data['impact'])
        return cls(**data)


class LearningScanner:
    """Scans learning files and extracts items."""
    
    # Patterns for extracting items from different file types
    MARKDOWN_ITEM_PATTERN = re.compile(r'^[-*]\s+(.+)', re.MULTILINE)
    TIMESTAMP_PATTERN = re.compile(r'\d{4}-\d{2}-\d{2}[T\s]\d{2}:\d{2}:\d{2}')
    
    def __init__(self, learnings_path: Path = LEARNINGS_PATH):
        self.learnings_path = learnings_path
        self.logger = logging.getLogger("ilma.self_improve.scanner")
    
    def scan_file(self, file_path: Path) -> List[LearningItem]:
        """Scan a single learning file and extract items."""
        items = []
        
        if not file_path.exists():
            self.logger.warning(f"Learning file not found: {file_path}")
            return items
        
        try:
            content = file_path.read_text(encoding='utf-8')
            category = self._determine_category(file_path.name)
            
            # Extract items based on file type
            if file_path.suffix == '.md':
                items = self._scan_markdown(content, file_path.name, category)
            elif file_path.suffix == '.json':
                items = self._scan_json(content, file_path.name, category)
            else:
                items = self._scan_text(content, file_path.name, category)
            
            self.logger.info(f"Scanned {file_path.name}: found {len(items)} items")
            
        except Exception as e:
            self.logger.error(f"Error scanning {file_path}: {e}")
        
        return items
    
    def scan_all(self) -> List[LearningItem]:
        """Scan all learning files."""
        all_items = []
        
        for name, path in LEARNING_FILES.items():
            items = self.scan_file(path)
            all_items.extend(items)
        
        self.logger.info(f"Total items scanned: {len(all_items)}")
        return all_items
    
    def _determine_category(self, filename: str) -> str:
        """Determine category from filename."""
        filename_lower = filename.lower()
        if 'learn' in filename_lower:
            return 'learning'
        elif 'error' in filename_lower:
            return 'error'
        elif 'feature' in filename_lower or 'request' in filename_lower:
            return 'feature_request'
        else:
            return 'general'
    
    def _scan_markdown(self, content: str, source: str, category: str) -> List[LearningItem]:
        """Scan markdown format learning file."""
        items = []
        lines = content.split('\n')
        
        item_id = 0
        current_item = []
        
        for line in lines:
            stripped = line.strip()
            
            # Check for list items
            if stripped.startswith('- ') or stripped.startswith('* '):
                if current_item:
                    content_text = '\n'.join(current_item).strip()
                    if content_text:
                        items.append(self._create_item(
                            content_text, source, category, item_id
                        ))
                        item_id += 1
                    current_item = []
                current_item.append(stripped[2:])
            
            # Check for headings (new item boundary)
            elif stripped.startswith('#') and current_item:
                content_text = '\n'.join(current_item).strip()
                if content_text:
                    items.append(self._create_item(
                        content_text, source, category, item_id
                    ))
                    item_id += 1
                current_item = []
            
            # Continuation of previous item
            elif current_item and stripped:
                current_item.append(stripped)
            
            # Empty line - skip
            else:
                continue
        
        # Don't forget the last item
        if current_item:
            content_text = '\n'.join(current_item).strip()
            if content_text:
                items.append(self._create_item(
                    content_text, source, category, item_id
                ))
        
        return items
    
    def _scan_text(self, content: str, source: str, category: str) -> List[LearningItem]:
        """Scan plain text format learning file."""
        items = []
        lines = content.split('\n')
        
        item_id = 0
        current_item = []
        
        for line in lines:
            stripped = line.strip()
            
            if not stripped:
                if current_item:
                    content_text = '\n'.join(current_item).strip()
                    if content_text:
                        items.append(self._create_item(
                            content_text, source, category, item_id
                        ))
                        item_id += 1
                    current_item = []
            else:
                current_item.append(stripped)
        
        # Handle last item
        if current_item:
            content_text = '\n'.join(current_item).strip()
            if content_text:
                items.append(self._create_item(
                    content_text, source, category, item_id
                ))
        
        return items
    
    def _scan_json(self, content: str, source: str, category: str) -> List[LearningItem]:
        """Scan JSON format learning file."""
        items = []
        
        try:
            data = json.loads(content)
            
            if isinstance(data, list):
                for idx, item in enumerate(data):
                    if isinstance(item, dict):
                        content_text = item.get('content', item.get('text', item.get('description', str(item))))
                        items.append(self._create_item(
                            content_text, source, category, idx
                        ))
                    elif isinstance(item, str):
                        items.append(self._create_item(item, source, category, idx))
            
            elif isinstance(data, dict):
                for key, value in data.items():
                    if isinstance(value, str):
                        items.append(self._create_item(value, source, category, 
                                                       hash(key) % 1000))
                    elif isinstance(value, (list, dict)):
                        content_text = json.dumps(value)
                        items.append(self._create_item(content_text, source, category,
                                                       hash(key) % 1000))
        
        except json.JSONDecodeError as e:
            self.logger.error(f"JSON parse error in {source}: {e}")
        
        return items
    
    def _create_item(self, content: str, source: str, category: str, item_id: int) -> LearningItem:
        """Create a LearningItem from content."""
        timestamp_match = self.TIMESTAMP_PATTERN.search(content)
        timestamp = timestamp_match.group(0) if timestamp_match else None
        
        return LearningItem(
            id=f"{source.split('.')[0]}_{category}_{item_id}",
            source_file=source,
            category=category,
            content=content[:500],  # Truncate very long content
            timestamp=timestamp,
            raw_line=content[:200]
        )


class ImprovementScorer:
    """Score and prioritize improvement items."""
    
    # Keywords that indicate priority
    P1_KEYWORDS = ['critical', 'urgent', 'crash', 'failure', 'security', 'data loss', 'broken']
    P2_KEYWORDS = ['important', 'performance', 'error', 'bug', 'fix', 'improve', 'optimize']
    P3_KEYWORDS = ['feature', 'enhancement', 'nice to have', 'would be nice', 'optional']
    
    # Keywords that indicate high impact
    HIGH_IMPACT_KEYWORDS = ['all users', 'frequently', 'always', 'every', '100%', 'major']
    MEDIUM_IMPACT_KEYWORDS = ['sometimes', 'occasional', 'specific', 'certain', 'partial']
    
    def __init__(self):
        self.logger = logging.getLogger("ilma.self_improve.scorer")
    
    def score_item(self, item: LearningItem) -> Tuple[Priority, ImpactLevel, float]:
        """
        Score a single learning item.
        
        Returns:
            Tuple of (Priority, ImpactLevel, score)
        """
        content_lower = item.content.lower()
        source_lower = item.source_file.lower()
        
        # Determine priority
        priority = self._determine_priority(content_lower, source_lower)
        
        # Determine impact
        impact = self._determine_impact(content_lower)
        
        # Calculate numeric score
        score = self._calculate_score(priority, impact, item)
        
        return priority, impact, score
    
    def _determine_priority(self, content: str, source: str) -> Priority:
        """Determine priority based on content analysis."""
        # Errors are often P1 or P2
        if 'error' in source or 'err' in content:
            if any(kw in content for kw in self.P1_KEYWORDS):
                return Priority.P1_CRITICAL
            return Priority.P2_HIGH
        
        # Check P1 keywords
        if any(kw in content for kw in self.P1_KEYWORDS):
            return Priority.P1_CRITICAL
        
        # Check P2 keywords
        if any(kw in content for kw in self.P2_KEYWORDS):
            return Priority.P2_HIGH
        
        # Check P3 keywords
        if any(kw in content for kw in self.P3_KEYWORDS):
            return Priority.P3_MEDIUM
        
        # Default based on source
        if 'feature' in source:
            return Priority.P3_MEDIUM
        elif 'error' in source:
            return Priority.P2_HIGH
        
        return Priority.P3_MEDIUM
    
    def _determine_impact(self, content: str) -> ImpactLevel:
        """Determine impact level based on content analysis."""
        if any(kw in content for kw in self.HIGH_IMPACT_KEYWORDS):
            return ImpactLevel.HIGH
        elif any(kw in content for kw in self.MEDIUM_IMPACT_KEYWORDS):
            return ImpactLevel.MEDIUM
        return ImpactLevel.LOW
    
    def _calculate_score(self, priority: Priority, impact: ImpactLevel, item: LearningItem) -> float:
        """Calculate numeric score for sorting."""
        priority_weights = {
            Priority.P1_CRITICAL: 100,
            Priority.P2_HIGH: 50,
            Priority.P3_MEDIUM: 10
        }
        
        impact_weights = {
            ImpactLevel.HIGH: 3.0,
            ImpactLevel.MEDIUM: 2.0,
            ImpactLevel.LOW: 1.0
        }
        
        base_score = priority_weights[priority] * impact_weights[impact]
        
        # Bonus for timestamp (recent items weighted higher)
        if item.timestamp:
            base_score *= 1.2
        
        # Category bonus
        if item.category == 'error':
            base_score *= 1.5
        elif item.category == 'learning':
            base_score *= 1.1
        
        return base_score
    
    def score_all(self, items: List[LearningItem]) -> List[ScoredImprovement]:
        """Score all items and return sorted list."""
        improvements = []
        
        for item in items:
            priority, impact, score = self.score_item(item)
            
            improvement = ScoredImprovement(
                id=self._generate_improvement_id(item, len(improvements)),
                title=self._extract_title(item),
                description=item.content,
                priority=priority,
                impact=impact,
                source_items=[f"{item.source_file}: {item.raw_line[:50]}..." if item.raw_line else item.id],
                effort_estimate=self._estimate_effort(priority, item),
                expected_benefit=self._extract_benefit(item),
                implementation_notes=self._generate_notes(item, priority),
                score=score
            )
            
            improvements.append(improvement)
        
        # Sort by score descending
        improvements.sort(key=lambda x: x.score, reverse=True)
        
        # Re-number after sorting
        for idx, imp in enumerate(improvements):
            imp.id = f"IMP-{idx+1:03d}"
        
        self.logger.info(f"Scored {len(improvements)} improvements")
        
        return improvements
    
    def _generate_improvement_id(self, item: LearningItem, index: int) -> str:
        """Generate improvement ID."""
        return f"IMP-{item.category[:3].upper()}-{index+1:03d}"
    
    def _extract_title(self, item: LearningItem) -> str:
        """Extract a short title from the content."""
        content = item.content[:100]
        
        # Try to find a good title
        if ':' in content:
            title = content.split(':')[0].strip()
            if len(title) <= 50:
                return title
        
        # Fall back to first sentence or phrase
        sentences = content.split('.')
        if sentences:
            title = sentences[0].strip()[:50]
            if len(title) < len(content):
                title += "..."
        
        return title or f"Improvement from {item.source_file}"
    
    def _estimate_effort(self, priority: Priority, item: LearningItem) -> str:
        """Estimate implementation effort."""
        content = item.content.lower()
        
        if 'quick' in content or 'easy' in content or 'simple' in content:
            return "Low (1-2 hours)"
        
        if 'complex' in content or 'difficult' in content or 'major' in content:
            if priority == Priority.P1_CRITICAL:
                return "High (1-2 days)"
            return "Medium (4-8 hours)"
        
        # Default based on priority
        efforts = {
            Priority.P1_CRITICAL: "Medium (2-4 hours)",
            Priority.P2_HIGH: "Low (1-2 hours)",
            Priority.P3_MEDIUM: "Medium (4-8 hours)"
        }
        
        return efforts.get(priority, "Medium (4-8 hours)")
    
    def _extract_benefit(self, item: LearningItem) -> str:
        """Extract expected benefit from content."""
        content = item.content.lower()
        
        benefits = []
        
        if 'prevent' in content or 'avoid' in content:
            benefits.append("Prevents issues and reduces error rates")
        if 'improve' in content or 'better' in content:
            benefits.append("Improves system quality and user experience")
        if 'performance' in content or 'speed' in content:
            benefits.append("Enhances performance and response times")
        if 'security' in content:
            benefits.append("Strengthens security posture")
        if 'usability' in content or 'ux' in content:
            benefits.append("Improves user satisfaction")
        
        if not benefits:
            return f"Addresses issue in {item.category.replace('_', ' ')}"
        
        return " ".join(benefits)
    
    def _generate_notes(self, item: LearningItem, priority: Priority) -> str:
        """Generate implementation notes."""
        notes = []
        
        if priority == Priority.P1_CRITICAL:
            notes.append("⚠️ CRITICAL: Requires immediate attention")
            notes.append("Recommendation: Implement in current sprint")
        
        if item.category == 'error':
            notes.append("Source: Error log analysis")
            notes.append("Next step: Create fix and add regression test")
        
        if item.category == 'feature_request':
            notes.append("Source: Feature request analysis")
            notes.append("Next step: Evaluate feasibility and user impact")
        
        notes.append(f"Source file: {item.source_file}")
        
        return "\n".join(notes)


class UpgradeRecommender:
    """Generate upgrade recommendations file."""
    
    def __init__(self, output_path: Path = UPGRADE_RECOMMENDATIONS_PATH):
        self.output_path = output_path
        self.logger = logging.getLogger("ilma.self_improve.recommender")
    
    def generate(
        self,
        improvements: List[ScoredImprovement],
        include_stats: bool = True
    ) -> str:
        """
        Generate upgrade recommendations markdown file.
        
        Args:
            improvements: List of scored improvements
            include_stats: Include statistics section
        
        Returns:
            Path to generated file
        """
        self.logger.info(f"Generating recommendations for {len(improvements)} items")
        
        timestamp = datetime.now().isoformat()
        
        content_parts = [
            f"# ILMA Upgrade Recommendations",
            f"\n**Generated**: {timestamp}",
            f"**Total Improvements**: {len(improvements)}\n",
            ""
        ]
        
        # Group by priority
        by_priority: Dict[str, List[ScoredImprovement]] = {
            "P1": [],
            "P2": [],
            "P3": []
        }
        
        for imp in improvements:
            by_priority[imp.priority.value].append(imp)
        
        # Add priority sections
        for p_label in ["P1", "P2", "P3"]:
            items = by_priority[p_label]
            if items:
                content_parts.append(f"## {p_label} Priority Improvements ({len(items)})\n")
                
                for imp in items:
                    content_parts.append(imp.to_markdown())
                
                content_parts.append("")
        
        # Add statistics section
        if include_stats:
            content_parts.extend([
                "## Statistics\n",
                self._generate_stats(improvements),
                ""
            ])
        
        # Add footer
        content_parts.extend([
            "---\n",
            f"*Generated by ILMA Self-Improvement Loop*",
            f"*Next scan recommended in 24 hours*"
        ])
        
        full_content = "\n".join(content_parts)
        
        # Ensure directory exists
        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Write to file
        self.output_path.write_text(full_content, encoding='utf-8')
        
        self.logger.info(f"Wrote recommendations to {self.output_path}")
        
        return str(self.output_path)
    
    def _generate_stats(self, improvements: List[ScoredImprovement]) -> str:
        """Generate statistics section."""
        total = len(improvements)
        
        priority_counts = {"P1": 0, "P2": 0, "P3": 0}
        impact_counts = {"high": 0, "medium": 0, "low": 0}
        
        for imp in improvements:
            priority_counts[imp.priority.value] += 1
            impact_counts[imp.impact.value] += 1
        
        avg_score = sum(i.score for i in improvements) / total if total > 0 else 0
        
        stats = f"""- **Total Improvements**: {total}
- **Average Score**: {avg_score:.2f}
- **By Priority**:
  - P1 (Critical): {priority_counts['P1']}
  - P2 (High): {priority_counts['P2']}
  - P3 (Medium): {priority_counts['P3']}
- **By Impact**:
  - High: {impact_counts['high']}
  - Medium: {impact_counts['medium']}
  - Low: {impact_counts['low']}
"""
        return stats


class SelfImproveLoop:
    """
    Main Self-Improvement Loop class.
    
    Orchestrates scanning, scoring, and recommendation generation.
    """
    
    def __init__(
        self,
        learnings_path: Path = LEARNINGS_PATH,
        output_path: Path = UPGRADE_RECOMMENDATIONS_PATH
    ):
        self.learnings_path = learnings_path
        self.output_path = output_path
        self.scanner = LearningScanner(learnings_path)
        self.scorer = ImprovementScorer()
        self.recommender = UpgradeRecommender(output_path)
        self._setup_logging()
    
    def _setup_logging(self) -> None:
        """Configure logging."""
        self.logger = logging.getLogger("ilma.self_improve")
        self.logger.setLevel(logging.DEBUG)
        
        if not self.logger.handlers:
            handler = logging.StreamHandler(sys.stdout)
            handler.setLevel(logging.INFO)
            formatter = logging.Formatter(
                '%(asctime)s - SelfImprove - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
            
            # File handler
            log_dir = PROFILE_PATH / "logs"
            log_dir.mkdir(parents=True, exist_ok=True)
            file_handler = logging.FileHandler(log_dir / "self_improve.log")
            file_handler.setLevel(logging.DEBUG)
            file_handler.setFormatter(formatter)
            self.logger.addHandler(file_handler)
    
    def scan_learnings(self) -> List[LearningItem]:
        """
        Scan all learning files.
        
        Returns:
            List of extracted learning items
        """
        self.logger.info("Starting learning scan...")
        items = self.scanner.scan_all()
        self.logger.info(f"Scan complete: {len(items)} items extracted")
        return items
    
    def score_improvements(self, items: Optional[List[LearningItem]] = None) -> List[ScoredImprovement]:
        """
        Score improvements from learning items.
        
        Args:
            items: Optional pre-scanned items. If None, will scan first.
        
        Returns:
            List of scored improvements sorted by score
        """
        if items is None:
            self.logger.info("No items provided, scanning...")
            items = self.scan_learnings()
        
        self.logger.info(f"Scoring {len(items)} items...")
        improvements = self.scorer.score_all(items)
        self.logger.info(f"Scored {len(improvements)} improvements")
        
        return improvements
    
    def generate_upgrade_recommendations(
        self,
        improvements: Optional[List[ScoredImprovement]] = None,
        include_stats: bool = True
    ) -> str:
        """
        Generate and save upgrade recommendations.
        
        Args:
            improvements: Optional pre-scored improvements. If None, will run full pipeline.
            include_stats: Include statistics in output
        
        Returns:
            Path to generated recommendations file
        """
        if improvements is None:
            self.logger.info("No improvements provided, running full pipeline...")
            items = self.scan_learnings()
            improvements = self.score_improvements(items)
        
        self.logger.info(f"Generating recommendations for {len(improvements)} improvements...")
        output_path = self.recommender.generate(improvements, include_stats)
        
        return output_path
    
    def run_full_cycle(self) -> str:
        """
        Run the complete self-improvement cycle.
        
        Returns:
            Path to generated recommendations file
        """
        self.logger.info("Starting full self-improvement cycle...")
        
        items = self.scan_learnings()
        improvements = self.score_improvements(items)
        output_path = self.generate_upgrade_recommendations(improvements)
        
        self.logger.info(f"Full cycle complete. Recommendations at: {output_path}")
        
        return output_path


def create_cli_parser() -> argparse.ArgumentParser:
    """Create command-line interface parser."""
    parser = argparse.ArgumentParser(
        prog="ilma_self_improve_loop.py",
        description="ILMA Self-Improvement Loop - Automated scanning and upgrade recommendations",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --scan                    Scan all learning files
  %(prog)s --score                   Score improvements from scan
  %(prog)s --recommend               Generate upgrade recommendations
  %(prog)s --full                    Run complete cycle (scan + score + recommend)
  %(prog)s --view                    Display current recommendations
  %(prog)s --verbose                 Enable verbose output
        """
    )
    
    parser.add_argument(
        "--scan", "-s",
        action="store_true",
        help="Scan all learning files"
    )
    
    parser.add_argument(
        "--score", "-c",
        action="store_true",
        help="Score improvements from learning items"
    )
    
    parser.add_argument(
        "--recommend", "-r",
        action="store_true",
        help="Generate upgrade recommendations"
    )
    
    parser.add_argument(
        "--full", "-f",
        action="store_true",
        help="Run complete self-improvement cycle"
    )
    
    parser.add_argument(
        "--view", "-v",
        action="store_true",
        help="View current upgrade recommendations"
    )
    
    parser.add_argument(
        "--output", "-o",
        type=str,
        help="Custom output path for recommendations"
    )
    
    parser.add_argument(
        "--verbose", "-V",
        action="store_true",
        help="Enable verbose output"
    )
    
    parser.add_argument(
        "--json", "-j",
        action="store_true",
        help="Output in JSON format"
    )
    
    return parser


def main() -> int:
    """Main entry point for CLI."""
    parser = create_cli_parser()
    args = parser.parse_args()
    
    # Setup logging level
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Create output path
    output_path = Path(args.output) if args.output else UPGRADE_RECOMMENDATIONS_PATH
    
    # Create loop instance
    loop = SelfImproveLoop(output_path=output_path)
    
    # Handle --view
    if args.view:
        if output_path.exists():
            print(output_path.read_text(encoding='utf-8'))
            return 0
        else:
            print("No recommendations file found. Run with --recommend or --full first.")
            return 1
    
    # Handle --scan
    if args.scan:
        items = loop.scan_learnings()
        print(f"\nScanned {len(items)} learning items:")
        for item in items[:10]:  # Show first 10
            print(f"  [{item.category}] {item.content[:60]}...")
        if len(items) > 10:
            print(f"  ... and {len(items) - 10} more")
        return 0
    
    # Handle --score
    if args.score:
        items = loop.scan_learnings()
        improvements = loop.score_improvements(items)
        print(f"\nScored {len(improvements)} improvements:")
        for imp in improvements[:10]:  # Show first 10
            print(f"  {imp.id} ({imp.priority.value}): {imp.title[:50]}...")
        if len(improvements) > 10:
            print(f"  ... and {len(improvements) - 10} more")
        return 0
    
    # Handle --recommend
    if args.recommend:
        path = loop.generate_upgrade_recommendations()
        print(f"Recommendations generated: {path}")
        return 0
    
    # Handle --full
    if args.full:
        path = loop.run_full_cycle()
        print(f"Full cycle complete: {path}")
        return 0
    
    # Handle JSON output for full cycle
    if args.json:
        items = loop.scan_learnings()
        improvements = loop.score_improvements(items)
        json_output = json.dumps(
            [i.to_dict() for i in improvements],
            indent=2
        )
        print(json_output)
        return 0
    
    # No action specified, show help
    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())