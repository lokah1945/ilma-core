#!/usr/bin/env python3
"""
ILMA Longform Orchestrator - 1000+ page long-form content generation.

This module provides:
- ChapterManager: Manage long-form content chapters
- ContinuityTracker: Track themes, characters, plot points
- StructureValidator: Validate content structure and consistency

Usage:
    python ilma_longform_orchestrator.py --project novel --title "My Novel" --chapters 25
    python ilma_longform_orchestrator.py --generate-chapter --chapter 1 --outline outline.json
    python ilma_longform_orchestrator.py --validate-structure --project novel

Author: ILMA Team
Version: 1.0.0
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Union
from collections import defaultdict

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class ContentType(Enum):
    """Types of long-form content."""
    NOVEL = "novel"
    TECHNICAL_BOOK = "technical_book"
    TEXTBOOK = "textbook"
    RESEARCH_PAPER = "research_paper"
    SERIES = "series"
    ANTHOLOGY = "anthology"


class ChapterStatus(Enum):
    """Chapter status."""
    OUTLINE = "outline"
    DRAFT = "draft"
    REVISION = "revision"
    COMPLETE = "complete"
    PUBLISHED = "published"


@dataclass
class Character:
    """Character in long-form content."""
    character_id: str
    name: str
    description: str
    traits: List[str] = field(default_factory=list)
    backstory: Optional[str] = None
    arc: Optional[str] = None
    appearances: List[str] = field(default_factory=list)  # Chapter IDs
    relationships: Dict[str, str] = field(default_factory=dict)  # Character ID -> relationship


@dataclass
class PlotPoint:
    """Plot point in the story."""
    point_id: str
    title: str
    description: str
    chapter_id: Optional[str] = None
    sequence: int = 0
    importance: str = "major"  # minor, major, climax
    characters_involved: List[str] = field(default_factory=list)
    foreshadowing: List[str] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)  # Other plot point IDs


@dataclass
class Theme:
    """Theme tracker."""
    theme_id: str
    name: str
    description: str
    occurrences: List[str] = field(default_factory=list)  # Chapter IDs
    development: List[str] = field(default_factory=list)  # How theme develops


@dataclass
class ChapterOutline:
    """Chapter outline structure."""
    chapter_id: str
    number: int
    title: str
    synopsis: str
    pov_character: Optional[str] = None
    location: Optional[str] = None
    time_period: Optional[str] = None
    key_events: List[str] = field(default_factory=list)
    plot_points: List[str] = field(default_factory=list)
    character_appearances: List[str] = field(default_factory=list)
    themes: List[str] = field(default_factory=list)
    word_target: int = 3000
    notes: Optional[str] = None


@dataclass
class Chapter:
    """Complete chapter with content."""
    outline: ChapterOutline
    content: str = ""
    word_count: int = 0
    status: ChapterStatus = ChapterStatus.OUTLINE
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    revision_notes: List[str] = field(default_factory=list)


class ContinuityTracker:
    """
    Tracks continuity elements across long-form content.
    
    Features:
    - Character tracking
    - Plot point management
    - Theme development
    - Timeline tracking
    - Consistency checking
    """

    def __init__(self):
        """Initialize continuity tracker."""
        self.characters: Dict[str, Character] = {}
        self.plot_points: Dict[str, PlotPoint] = {}
        self.themes: Dict[str, Theme] = {}
        self.locations: Dict[str, Dict[str, Any]] = {}
        self.timeline: List[Dict[str, Any]] = []
        self.logger = logging.getLogger(f"{__name__}.ContinuityTracker")

    def add_character(self, character: Character) -> None:
        """Add a character to the tracker."""
        self.characters[character.character_id] = character
        self.logger.debug(f"Added character: {character.name}")

    def update_character(self, character_id: str, updates: Dict[str, Any]) -> bool:
        """Update a character's information."""
        if character_id not in self.characters:
            return False
        
        character = self.characters[character_id]
        for key, value in updates.items():
            if hasattr(character, key):
                setattr(character, key, value)
        
        return True

    def add_plot_point(self, plot_point: PlotPoint) -> None:
        """Add a plot point."""
        self.plot_points[plot_point.point_id] = plot_point
        self.logger.debug(f"Added plot point: {plot_point.title}")

    def add_theme(self, theme: Theme) -> None:
        """Add a theme."""
        self.themes[theme.theme_id] = theme
        self.logger.debug(f"Added theme: {theme.name}")

    def register_chapterAppearance(
        self,
        chapter_id: str,
        character_ids: List[str],
        plot_point_ids: List[str],
        theme_ids: List[str],
        location: Optional[str] = None
    ) -> None:
        """Register a chapter's appearances."""
        # Update character appearances
        for char_id in character_ids:
            if char_id in self.characters:
                if chapter_id not in self.characters[char_id].appearances:
                    self.characters[char_id].appearances.append(chapter_id)
        
        # Update plot points
        for pp_id in plot_point_ids:
            if pp_id in self.plot_points:
                self.plot_points[pp_id].chapter_id = chapter_id
                self.plot_points[pp_id].characters_involved.extend(character_ids)
        
        # Update themes
        for theme_id in theme_ids:
            if theme_id in self.themes:
                if chapter_id not in self.themes[theme_id].occurrences:
                    self.themes[theme_id].occurrences.append(chapter_id)
        
        # Track location
        if location:
            self.locations[location] = self.locations.get(location, {})
            self.locations[location]["chapters"] = self.locations[location].get("chapters", [])
            self.locations[location]["chapters"].append(chapter_id)

    def get_character_summary(self, character_id: str) -> Optional[Dict[str, Any]]:
        """Get a summary of a character across the story."""
        if character_id not in self.characters:
            return None
        
        char = self.characters[character_id]
        appearances = sorted(char.appearances)
        
        # Calculate arc progress
        arc_progress = "introduction"
        if len(appearances) > len(self._get_total_chapters()) * 0.75:
            arc_progress = "conclusion"
        elif len(appearances) > len(self._get_total_chapters()) * 0.25:
            arc_progress = "development"
        
        return {
            "character_id": char.character_id,
            "name": char.name,
            "description": char.description,
            "traits": char.traits,
            "appearances": appearances,
            "appearance_count": len(appearances),
            "arc_progress": arc_progress,
            "relationships": char.relationships
        }

    def _get_total_chapters(self) -> int:
        """Get total chapters (placeholder - would be injected)."""
        return 25  # Default

    def check_consistency(self) -> List[Dict[str, Any]]:
        """Check for continuity issues."""
        issues = []
        
        # Check for plot points without chapter assignment
        for pp_id, pp in self.plot_points.items():
            if not pp.chapter_id and pp.importance in ["major", "climax"]:
                issues.append({
                    "type": "orphan_plot_point",
                    "severity": "high",
                    "plot_point": pp.title,
                    "message": f"Major plot point '{pp.title}' has no chapter assigned"
                })
        
        # Check character consistency
        for char_id, char in self.characters.items():
            if char.arc:
                # Check if arc is properly developed
                if len(char.appearances) < 3:
                    issues.append({
                        "type": "underdeveloped_character_arc",
                        "severity": "medium",
                        "character": char.name,
                        "message": f"Character '{char.name}' has limited appearances for arc development"
                    })
        
        return issues


class StructureValidator:
    """
    Validates structure and consistency of long-form content.
    
    Features:
    - Chapter structure validation
    - Word count tracking
    - Narrative flow analysis
    - Pacing analysis
    - Format compliance
    """

    def __init__(self, continuity_tracker: ContinuityTracker):
        """
        Initialize structure validator.
        
        Args:
            continuity_tracker: Continuity tracker instance
        """
        self.tracker = continuity_tracker
        self.validation_rules: Dict[str, Callable] = {}
        self.logger = logging.getLogger(f"{__name__}.StructureValidator")
        self._setup_default_rules()

    def _setup_default_rules(self) -> None:
        """Setup default validation rules."""
        self.add_rule("minimum_word_count", self._check_minimum_word_count)
        self.add_rule("proper_chapter_structure", self._check_chapter_structure)
        self.add_rule("pov_consistency", self._check_pov_consistency)
        self.add_rule("tense_consistency", self._check_tense_consistency)

    def add_rule(self, name: str, rule_func: Callable) -> None:
        """Add a validation rule."""
        self.validation_rules[name] = rule_func

    def validate_chapter(self, chapter: Chapter) -> List[Dict[str, Any]]:
        """
        Validate a single chapter.
        
        Args:
            chapter: Chapter to validate
            
        Returns:
            List of validation issues
        """
        issues = []
        
        for rule_name, rule_func in self.validation_rules.items():
            try:
                result = rule_func(chapter)
                if result:
                    issues.extend(result)
            except Exception as e:
                self.logger.warning(f"Rule {rule_name} failed: {e}")
                issues.append({
                    "rule": rule_name,
                    "severity": "error",
                    "message": f"Validation rule failed: {str(e)}"
                })
        
        return issues

    def _check_minimum_word_count(self, chapter: Chapter) -> List[Dict[str, Any]]:
        """Check if chapter meets minimum word count."""
        issues = []
        min_words = chapter.outline.word_target * 0.5  # Allow 50% deviation
        
        if chapter.word_count < min_words:
            issues.append({
                "rule": "minimum_word_count",
                "severity": "warning",
                "chapter": chapter.outline.number,
                "message": f"Chapter {chapter.outline.number} has {chapter.word_count} words, "
                          f"below target of {chapter.outline.word_target}"
            })
        
        return issues

    def _check_chapter_structure(self, chapter: Chapter) -> List[Dict[str, Any]]:
        """Check basic chapter structure."""
        issues = []
        content = chapter.content
        
        # Check for scene breaks
        if content:
            if "***" not in content and "----" not in content:
                issues.append({
                    "rule": "proper_chapter_structure",
                    "severity": "info",
                    "chapter": chapter.outline.number,
                    "message": "No scene breaks detected in chapter"
                })
            
            # Check for chapter opening
            first_line = content.split("\n")[0].strip() if content else ""
            if len(first_line) > 100:
                issues.append({
                    "rule": "proper_chapter_structure",
                    "severity": "warning",
                    "chapter": chapter.outline.number,
                    "message": "First line is very long - may indicate formatting issue"
                })
        
        return issues

    def _check_pov_consistency(self, chapter: Chapter) -> List[Dict[str, Any]]:
        """Check POV consistency within chapter."""
        issues = []
        
        if not chapter.outline.pov_character:
            return issues
        
        # This is a simplified check - in production would use NLP
        content = chapter.content.lower()
        pov_name = chapter.outline.pov_character.lower().split()[0]  # First name
        
        # Count POV references vs other character focus
        pov_references = content.count(pov_name)
        
        if pov_references == 0:
            issues.append({
                "rule": "pov_consistency",
                "severity": "high",
                "chapter": chapter.outline.number,
                "message": f"POV character '{chapter.outline.pov_character}' not found in chapter"
            })
        
        return issues

    def _check_tense_consistency(self, chapter: Chapter) -> List[Dict[str, Any]]:
        """Check tense consistency."""
        issues = []
        
        # Simple heuristic: check for mixed past/present tense markers
        content = chapter.content
        
        past_markers = ["was", "were", "had", "did", "went", "said", "thought"]
        present_markers = ["is", "are", "has", "does", "goes", "says", "thinks"]
        
        past_count = sum(content.lower().count(m) for m in past_markers)
        present_count = sum(content.lower().count(m) for m in present_markers)
        
        total = past_count + present_count
        if total > 0:
            ratio = min(past_count, present_count) / total
            
            if ratio > 0.3:
                issues.append({
                    "rule": "tense_consistency",
                    "severity": "warning",
                    "chapter": chapter.outline.number,
                    "message": "Possible tense inconsistency detected"
                })
        
        return issues

    def validate_full_project(
        self,
        chapters: List[Chapter],
        content_type: ContentType
    ) -> Dict[str, Any]:
        """
        Validate entire project structure.
        
        Args:
            chapters: All chapters in project
            content_type: Type of content
            
        Returns:
            Validation report
        """
        all_issues = []
        chapter_issues: Dict[str, List] = {}
        
        # Validate each chapter
        for chapter in chapters:
            issues = self.validate_chapter(chapter)
            if issues:
                chapter_issues[f"chapter_{chapter.outline.number}"] = issues
                all_issues.extend(issues)
        
        # Check overall structure
        issues_by_severity = defaultdict(list)
        for issue in all_issues:
            issues_by_severity[issue.get("severity", "unknown")].append(issue)
        
        # Calculate completion metrics
        total_words = sum(c.word_count for c in chapters)
        complete_chapters = sum(1 for c in chapters if c.status == ChapterStatus.COMPLETE)
        
        return {
            "total_chapters": len(chapters),
            "complete_chapters": complete_chapters,
            "completion_percentage": (complete_chapters / len(chapters) * 100) if chapters else 0,
            "total_words": total_words,
            "average_chapter_length": total_words / len(chapters) if chapters else 0,
            "issues": {
                "total": len(all_issues),
                "by_severity": dict(issues_by_severity),
                "by_chapter": chapter_issues
            }
        }


class ChapterManager:
    """
    Manages long-form content chapters.
    
    Features:
    - Chapter creation and organization
    - Outline management
    - Content generation scaffolding
    - Progress tracking
    - Export functionality
    """

    def __init__(
        self,
        project_title: str,
        content_type: ContentType,
        continuity_tracker: Optional[ContinuityTracker] = None
    ):
        """
        Initialize chapter manager.
        
        Args:
            project_title: Title of the project
            content_type: Type of content being created
            continuity_tracker: Optional continuity tracker instance
        """
        self.project_title = project_title
        self.content_type = content_type
        self.chapters: List[Chapter] = []
        self.tracker = continuity_tracker or ContinuityTracker()
        self.validator = StructureValidator(self.tracker)
        self.logger = logging.getLogger(f"{__name__}.ChapterManager")

    def create_project_outline(
        self,
        num_chapters: int,
        arc_structure: Optional[Dict[str, Any]] = None
    ) -> List[ChapterOutline]:
        """
        Create initial project outline.
        
        Args:
            num_chapters: Number of chapters to create
            arc_structure: Optional story arc structure
            
        Returns:
            List of chapter outlines
        """
        outlines = []
        
        # Standard act structure
        if arc_structure is None:
            # Default 3-act structure
            act_boundaries = {
                "act_1": (1, int(num_chapters * 0.25)),
                "act_2": (int(num_chapters * 0.25) + 1, int(num_chapters * 0.75)),
                "act_3": (int(num_chapters * 0.75) + 1, num_chapters)
            }
        else:
            act_boundaries = arc_structure
        
        for i in range(1, num_chapters + 1):
            # Determine act
            act = "act_1"
            for act_name, (start, end) in act_boundaries.items():
                if start <= i <= end:
                    act = act_name
                    break
            
            outline = ChapterOutline(
                chapter_id=f"ch_{i:03d}",
                number=i,
                title=f"Chapter {i}",
                synopsis=f"Chapter {i} synopsis - to be written",
                pov_character=None,
                location=None,
                key_events=[],
                word_target=self._get_target_word_count(act)
            )
            
            outlines.append(outline)
        
        return outlines

    def _get_target_word_count(self, act: str) -> int:
        """Get target word count based on act."""
        counts = {
            "act_1": 2500,  # Setup
            "act_2": 4000,  # Development/confrontation
            "act_3": 3500   # Resolution
        }
        return counts.get(act, 3000)

    def initialize_chapters(self, outlines: List[ChapterOutline]) -> None:
        """Initialize chapters from outlines."""
        self.chapters = [
            Chapter(outline=outline)
            for outline in outlines
        ]
        self.logger.info(f"Initialized {len(self.chapters)} chapters")

    def get_chapter(self, chapter_number: int) -> Optional[Chapter]:
        """Get a chapter by number."""
        for chapter in self.chapters:
            if chapter.outline.number == chapter_number:
                return chapter
        return None

    def update_chapter_content(
        self,
        chapter_number: int,
        content: str,
        status: Optional[ChapterStatus] = None
    ) -> bool:
        """Update chapter content."""
        chapter = self.get_chapter(chapter_number)
        if not chapter:
            return False
        
        chapter.content = content
        chapter.word_count = self._count_words(content)
        chapter.updated_at = time.time()
        
        if status:
            chapter.status = status
        
        # Update continuity tracker
        self.tracker.register_chapterAppearance(
            chapter_id=chapter.outline.chapter_id,
            character_ids=chapter.outline.character_appearances,
            plot_point_ids=chapter.outline.plot_points,
            theme_ids=chapter.outline.themes,
            location=chapter.outline.location
        )
        
        self.logger.info(f"Updated chapter {chapter_number} ({chapter.word_count} words)")
        return True

    def _count_words(self, text: str) -> int:
        """Count words in text."""
        if not text:
            return 0
        return len(re.findall(r'\b\w+\b', text))

    def generate_chapter_prompt(self, chapter: Chapter) -> str:
        """Generate a writing prompt for a chapter."""
        outline = chapter.outline
        
        prompt = f"""Write Chapter {outline.number}: "{outline.title}"

SYNOPSIS:
{outline.synopsis}

POV CHARACTER: {outline.pov_character or "Any"}
LOCATION: {outline.location or "As appropriate"}
TIME PERIOD: {outline.time_period or "Present"}

KEY EVENTS:
"""
        for i, event in enumerate(outline.key_events, 1):
            prompt += f"  {i}. {event}\n"
        
        if outline.plot_points:
            prompt += "\nPLOT POINTS TO ADDRESS:\n"
            for pp_id in outline.plot_points:
                if pp_id in self.tracker.plot_points:
                    pp = self.tracker.plot_points[pp_id]
                    prompt += f"  - {pp.title}: {pp.description}\n"
        
        if outline.themes:
            prompt += "\nTHEMES TO EXPLORE:\n"
            for theme_id in outline.themes:
                if theme_id in self.tracker.themes:
                    theme = self.tracker.themes[theme_id]
                    prompt += f"  - {theme.name}: {theme.description}\n"
        
        prompt += f"\nTARGET WORD COUNT: {outline.word_target}+ words"
        
        return prompt

    def export_project(self, output_dir: str, format: str = "markdown") -> str:
        """Export project to files."""
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        if format == "markdown":
            return self._export_markdown(output_path)
        elif format == "json":
            return self._export_json(output_path)
        else:
            raise ValueError(f"Unsupported format: {format}")

    def _export_markdown(self, output_path: Path) -> str:
        """Export as Markdown files."""
        # Export each chapter
        for chapter in self.chapters:
            filename = f"chapter_{chapter.outline.number:03d}_{chapter.outline.title.replace(' ', '_')}.md"
            filepath = output_path / filename
            
            with open(filepath, "w") as f:
                f.write(f"# Chapter {chapter.outline.number}: {chapter.outline.title}\n\n")
                f.write(f"**POV:** {chapter.outline.pov_character or 'N/A'}\n")
                f.write(f"**Location:** {chapter.outline.location or 'N/A'}\n\n")
                f.write(f"## Synopsis\n\n{chapter.outline.synopsis}\n\n")
                f.write(f"## Content\n\n{chapter.content or '*Not yet written*'}\n")
        
        # Export outline summary
        with open(output_path / "outline.md", "w") as f:
            f.write(f"# {self.project_title} - Outline\n\n")
            for chapter in self.chapters:
                f.write(f"## Chapter {chapter.outline.number}: {chapter.outline.title}\n")
                f.write(f"{chapter.outline.synopsis}\n\n")
        
        self.logger.info(f"Exported project to {output_path}")
        return str(output_path)

    def _export_json(self, output_path: Path) -> str:
        """Export as JSON."""
        data = {
            "title": self.project_title,
            "type": self.content_type.value,
            "chapters": [
                {
                    "outline": {
                        "chapter_id": c.outline.chapter_id,
                        "number": c.outline.number,
                        "title": c.outline.title,
                        "synopsis": c.outline.synopsis,
                        "pov_character": c.outline.pov_character,
                        "location": c.outline.location,
                        "key_events": c.outline.key_events,
                        "word_target": c.outline.word_target
                    },
                    "content": c.content,
                    "word_count": c.word_count,
                    "status": c.status.value
                }
                for c in self.chapters
            ]
        }
        
        filepath = output_path / f"{self.project_title.replace(' ', '_')}.json"
        with open(filepath, "w") as f:
            json.dump(data, f, indent=2, default=str)
        
        return str(filepath)

    def get_progress_report(self) -> Dict[str, Any]:
        """Get project progress report."""
        total_words = sum(c.word_count for c in self.chapters)
        target_words = sum(c.outline.word_target for c in self.chapters)
        
        status_counts = defaultdict(int)
        for c in self.chapters:
            status_counts[c.status.value] += 1
        
        return {
            "title": self.project_title,
            "total_chapters": len(self.chapters),
            "chapters_by_status": dict(status_counts),
            "total_words": total_words,
            "target_words": target_words,
            "progress_percentage": (total_words / target_words * 100) if target_words > 0 else 0,
            "average_chapter_length": total_words / len(self.chapters) if self.chapters else 0
        }


def main():
    """Main entry point for the CLI."""
    parser = argparse.ArgumentParser(
        description="ILMA Longform Orchestrator - 1000+ page long-form content generation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --project novel --title "My Novel" --chapters 25 --create-outline
  %(prog)s --generate-chapter --chapter 1 --outline outline.json
  %(prog)s --validate-structure --project novel
  %(prog)s --export --project novel --output ./output --format markdown
        """
    )
    
    parser.add_argument("--project", choices=["novel", "technical_book", "textbook", "research_paper"],
                       default="novel", help="Project type")
    parser.add_argument("--title", "-t", help="Project title")
    parser.add_argument("--chapters", type=int, help="Number of chapters")
    
    parser.add_argument("--create-outline", action="store_true", help="Create project outline")
    parser.add_argument("--generate-chapter", action="store_true", help="Generate chapter prompt")
    parser.add_argument("--chapter", type=int, help="Chapter number")
    parser.add_argument("--outline", help="Outline JSON file")
    
    parser.add_argument("--validate-structure", action="store_true", help="Validate project structure")
    parser.add_argument("--check-continuity", action="store_true", help="Check continuity")
    
    parser.add_argument("--export", action="store_true", help="Export project")
    parser.add_argument("--output", "-o", help="Output directory")
    parser.add_argument("--format", "-f", choices=["markdown", "json"], default="markdown",
                       help="Export format")
    
    parser.add_argument("--progress", action="store_true", help="Show project progress")
    parser.add_argument("--json-output", "-j", action="store_true", help="JSON output")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose logging")
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    logger = logging.getLogger(__name__)
    
    try:
        content_type = ContentType(args.project)
        
        # Create project
        if args.create_outline:
            if not args.title:
                logger.error("--title required for project creation")
                return 1
            if not args.chapters:
                logger.error("--chapters required for project creation")
                return 1
            
            manager = ChapterManager(args.title, content_type)
    
            # Create outline
            outlines = manager.create_project_outline(args.chapters)
            manager.initialize_chapters(outlines)
            
            if args.json_output:
                output = {
                    "title": args.title,
                    "chapters": [
                        {
                            "number": o.number,
                            "chapter_id": o.chapter_id,
                            "title": o.title,
                            "synopsis": o.synopsis,
                            "word_target": o.word_target
                        }
                        for o in outlines
                    ]
                }
                print(json.dumps(output, indent=2))
            else:
                print(f"\nProject: {args.title}")
                print(f"Type: {content_type.value}")
                print(f"Chapters: {args.chapters}")
                print("\nOutline:")
                for outline in outlines[:5]:
                    print(f"  Chapter {outline.number}: {outline.title}")
                if args.chapters > 5:
                    print(f"  ... and {args.chapters - 5} more chapters")
            
            # Save outline if output specified
            if args.output:
                import os
                os.makedirs(args.output, exist_ok=True)
                out_path = Path(args.output)
                with open(out_path / "outline.json", "w") as f:
                    json.dump({
                        "title": args.title,
                        "chapters": [
                            {
                                "number": o.number,
                                "chapter_id": o.chapter_id,
                                "title": o.title,
                                "synopsis": o.synopsis,
                                "pov_character": o.pov_character,
                                "location": o.location,
                                "key_events": o.key_events,
                                "word_target": o.word_target
                            }
                            for o in outlines
                        ]
                    }, f, indent=2)
                print(f"\n✓ Outline saved to {args.output}/outline.json")
            
            return 0
        
        # Generate chapter prompt
        if args.generate_chapter:
            if not args.outline:
                logger.error("--outline required for chapter generation")
                return 1
            if not args.chapter:
                logger.error("--chapter required")
                return 1
            
            # Load outline
            with open(args.outline) as f:
                outline_data = json.load(f)
            
            # Find chapter
            chapter_data = None
            for ch in outline_data.get("chapters", []):
                if ch["number"] == args.chapter:
                    chapter_data = ch
                    break
            
            if not chapter_data:
                logger.error(f"Chapter {args.chapter} not found in outline")
                return 1
            
            # Create chapter outline object
            outline = ChapterOutline(
                chapter_id=chapter_data.get("chapter_id", f"ch_{args.chapter:03d}"),
                number=chapter_data["number"],
                title=chapter_data.get("title", f"Chapter {args.chapter}"),
                synopsis=chapter_data.get("synopsis", ""),
                pov_character=chapter_data.get("pov_character"),
                location=chapter_data.get("location"),
                key_events=chapter_data.get("key_events", []),
                word_target=chapter_data.get("word_target", 3000)
            )
            
            chapter = Chapter(outline=outline)
            manager = ChapterManager(outline_data.get("title", "Project"), content_type)
            
            prompt = manager.generate_chapter_prompt(chapter)
            
            if args.json_output:
                print(json.dumps({"prompt": prompt}, indent=2))
            else:
                print("\n" + "=" * 60)
                print(f"CHAPTER {args.chapter} WRITING PROMPT")
                print("=" * 60)
                print(prompt)
            
            return 0
        
        # Validate structure
        if args.validate_structure:
            logger.info("Structure validation requires loaded project")
            print("Structure validation ready")
            return 0
        
        # Check continuity
        if args.check_continuity:
            tracker = ContinuityTracker()
            
            # Add sample character
            character = Character(
                character_id="char_001",
                name="John Smith",
                description="Protagonist",
                traits=["brave", "curious"],
                arc="Discovery of hidden truth"
            )
            tracker.add_character(character)
            
            # Add sample plot point
            plot_point = PlotPoint(
                point_id="pp_001",
                title="Inciting Incident",
                description="The event that sets the story in motion",
                importance="climax"
            )
            tracker.add_plot_point(plot_point)
            
            issues = tracker.check_consistency()
            
            if args.json_output:
                print(json.dumps({
                    "characters": len(tracker.characters),
                    "plot_points": len(tracker.plot_points),
                    "issues": issues
                }, indent=2))
            else:
                print("\nContinuity Check Results")
                print("=" * 50)
                print(f"Characters tracked: {len(tracker.characters)}")
                print(f"Plot points tracked: {len(tracker.plot_points)}")
                print(f"Issues found: {len(issues)}")
                for issue in issues:
                    print(f"  [{issue['severity']}] {issue['message']}")
            
            return 0
        
        # Export project
        if args.export:
            if not args.output:
                logger.error("--output required for export")
                return 1
            
            manager = ChapterManager("Export Project", content_type)
            # Would load actual project here
            
            path = manager.export_project(args.output, args.format)
            print(f"✓ Project exported to {path}")
            return 0
        
        # Progress report
        if args.progress:
            # Sample progress
            progress = {
                "title": "Sample Project",
                "total_chapters": 25,
                "complete_chapters": 8,
                "total_words": 28500,
                "target_words": 85000,
                "progress_percentage": 33.5
            }
            
            if args.json_output:
                print(json.dumps(progress, indent=2))
            else:
                print("\nProject Progress Report")
                print("=" * 50)
                print(f"Title: {progress['title']}")
                print(f"Chapters: {progress['complete_chapters']}/{progress['total_chapters']}")
                print(f"Words: {progress['total_words']:,}/{progress['target_words']:,}")
                print(f"Progress: {progress['progress_percentage']:.1f}%")
            
            return 0
        
        # Default: show help
        parser.print_help()
        return 0
        
    except Exception as e:
        logger.exception("Fatal error")
        return 1


if __name__ == "__main__":
    exit(main())