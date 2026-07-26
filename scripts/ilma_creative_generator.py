#!/usr/bin/env python3
"""
ILMA Creative Generator - Song lyrics, stories, and creative concepts.

This module provides:
- GenreTemplates: Pre-built genre-specific templates
- RhymeEngine: Advanced rhyme generation and selection
- StoryArcGenerator: Generate story structures and plot arcs

Usage:
    python ilma_creative_generator.py --type song --genre pop --theme "love"
    python ilma_creative_generator.py --type story --genre thriller --length medium
    python ilma_creative_generator.py --concept --seed "A detective in space"

Author: ILMA Team
Version: 1.0.0
"""

from __future__ import annotations

import argparse
import json
import logging
import random
import re
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Union

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class CreativeType(Enum):
    """Types of creative output."""
    SONG = "song"
    STORY = "story"
    POEM = "poem"
    SCREENPLAY = "screenplay"
    CONCEPT = "concept"


class Genre(Enum):
    """Creative genres."""
    # Music
    POP = "pop"
    ROCK = "rock"
    HIP_HOP = "hip_hop"
    COUNTRY = "country"
    RNB = "rnb"
    JAZZ = "jazz"
    CLASSICAL = "classical"
    ELECTRONIC = "electronic"
    FOLK = "folk"
    
    # Writing
    THRILLER = "thriller"
    ROMANCE = "romance"
    SCIFI = "scifi"
    FANTASY = "fantasy"
    MYSTERY = "mystery"
    HORROR = "horror"
    LITERARY = "literary"
    HUMOR = "humor"


class RhymeScheme(Enum):
    """Rhyme schemes for lyrics/poetry."""
    AABB = "aabb"
    ABAB = "abab"
    ABBA = "abba"
    FREE = "free"
    CUSTOM = "custom"


@dataclass
class Verse:
    """Represents a verse/stanza."""
    lines: List[str]
    rhyme_scheme: Optional[str] = None
    meter: Optional[str] = None


@dataclass
class SongStructure:
    """Complete song structure."""
    title: str
    genre: Genre
    theme: str
    verses: List[Verse] = field(default_factory=list)
    chorus: Optional[Verse] = None
    bridge: Optional[Verse] = None
    intro: Optional[Verse] = None
    outro: Optional[Verse] = None
    tempo: Optional[str] = None
    key: Optional[str] = None


@dataclass
class StoryArc:
    """Story arc structure."""
    arc_id: str
    title: str
    genre: Genre
    premise: str
    setup: str  # Act 1
    confrontation: str  # Act 2
    resolution: str  # Act 3
    themes: List[str] = field(default_factory=list)
    characters: List[Dict[str, str]] = field(default_factory=list)
    plot_points: List[Dict[str, str]] = field(default_factory=list)


class RhymeEngine:
    """
    Advanced rhyme generation and selection.
    
    Features:
    - Perfect rhyme generation
    - Near rhyme suggestions
    - Rhyme scheme enforcement
    - Syllable counting
    - Word bank management
    """

    # Phonetic vowel sounds for rhyme grouping
    VOWEL_GROUPS = {
        "ae": ["a", "ai", "ay", "eigh", "ey"],
        "ee": ["ee", "ea", "ie", "y"],
        "oe": ["o", "oa", "ow", "ough"],
        "ue": ["u", "oo", "ue", "ew"],
        "ah": ["i", "y", "igh", "ie"],
        "oh": ["o", "oa", "ow"],
        "uh": ["u", "ou", "oo"],
        "ar": ["ar", "er", "ir", "or", "ur"],
        "or": ["or", "ore", "our", "aw"],
        "ay": ["ay", "ey", "ai", "a"],
    }

    # Common rhyme word banks by category
    RHYME_BANKS: Dict[str, List[str]] = {
        "love": ["heart", "start", "part", "art", "apart", "sweet", "beat", "heat", "meet", "feet", "treat", "street", "kiss", "miss", "bliss", "wish", "dish", "glow", "show", "flow", "know", "grow", "slow"],
        "sad": ["rain", "pain", "chain", "brain", "fall", "call", "wall", "all", "alone", "phone", "bone", "stone", "gone", "wrong", "long", "song", "tears", "fears", "years", "ears", "blue", "true", "new", "you", "through"],
        "party": ["dance", "chance", "glance", "prance", "night", "light", "right", "bright", "fun", "sun", "one", "done", "win", "spin", "begin", "skin", "celebrate", "late", "great", "fate"],
        "dreams": ["sky", "high", "fly", "try", "free", "be", "see", "me", "sea", "key", "way", "day", "say", "play", "stay", "dream", "stream", "seem", "team", "theme"],
        "nature": ["sun", "run", "fun", "one", "sky", "fly", "high", "try", "tree", "free", "see", "be", "sea", "meadow", "shadow", "follow", "hollow", "wind", "find", "mind", "behind"],
    }

    def __init__(self):
        """Initialize rhyme engine."""
        self.logger = logging.getLogger(f"{__name__}.RhymeEngine")
        self.custom_words: Set[str] = set()

    def get_rhyming_words(
        self,
        word: str,
        count: int = 10,
        rhyme_type: str = "perfect"
    ) -> List[str]:
        """
        Get words that rhyme with the given word.
        
        Args:
            word: Word to find rhymes for
            count: Number of rhyming words to return
            rhyme_type: "perfect" or "near"
            
        Returns:
            List of rhyming words
        """
        word = word.lower().strip()
        
        # Find the ending sound
        ending = self._get_word_ending(word)
        
        # Find all words with same ending
        rhyming = []
        
        for category_words in self.RHYME_BANKS.values():
            for w in category_words:
                if w != word and self._get_word_ending(w) == ending:
                    if rhyme_type == "perfect" or not rhyming:
                        rhyming.append(w)
        
        # Add near rhymes if needed
        if rhyme_type == "near" and len(rhyming) < count:
            near_rhymes = self._get_near_rhymes(ending)
            for nr in near_rhymes:
                if nr not in rhyming and nr != word:
                    rhyming.append(nr)
        
        return rhyming[:count]

    def _get_word_ending(self, word: str) -> str:
        """Get the phonetic ending of a word."""
        # Simple approximation - get last 2-3 letters
        word = word.lower()
        
        # Handle common endings
        if word.endswith("tion") or word.endswith("sion"):
            return word[-4:]
        if word.endswith("ing"):
            return word[-3:]
        if word.endswith("ed"):
            return word[-2:]
        if len(word) > 3:
            return word[-3:]
        return word

    def _get_near_rhymes(self, ending: str) -> List[str]:
        """Get near rhymes (similar endings)."""
        near = []
        
        # Find similar endings
        for category_words in self.RHYME_BANKS.values():
            for w in category_words:
                if w[-2:] == ending[-2:] and w != ending:
                    near.append(w)
        
        return near

    def count_syllables(self, word: str) -> int:
        """
        Count syllables in a word.
        
        Args:
            word: Word to count syllables
            
        Returns:
            Syllable count
        """
        word = word.lower()
        
        # Count vowel groups
        vowels = "aeiouy"
        count = 0
        prev_vowel = False
        
        for char in word:
            is_vowel = char in vowels
            if is_vowel and not prev_vowel:
                count += 1
            prev_vowel = is_vowel
        
        # Adjust for silent e
        if word.endswith("e") and count > 1:
            count -= 1
        
        # Adjust for common endings
        if word.endswith("le") and len(word) > 2 and word[-3] not in vowels:
            count += 1
        
        return max(1, count)

    def generate_rhyming_lines(
        self,
        rhyme_a: str,
        rhyme_b: str,
        count: int = 4
    ) -> List[Tuple[str, str]]:
        """
        Generate rhyming line pairs.
        
        Args:
            rhyme_a: First rhyme word
            rhyme_b: Second rhyme word
            count: Number of pairs to generate
            
        Returns:
            List of (line_a, line_b) tuples
        """
        words_a = self.get_rhyming_words(rhyme_a, count * 2)
        words_b = self.get_rhyming_words(rhyme_b, count * 2)
        
        lines = []
        for i in range(count):
            if i < len(words_a) and i < len(words_b):
                line_a = f"Some words that {words_a[i]}"
                line_b = f"Other words that {words_b[i]}"
                lines.append((line_a, line_b))
        
        return lines


class GenreTemplates:
    """
    Genre-specific creative templates.
    
    Provides templates and patterns for different genres.
    """

    TEMPLATES: Dict[Genre, Dict[str, Any]] = {
        Genre.POP: {
            "structure": ["intro", "verse", "pre-chorus", "chorus", "verse", "chorus", "bridge", "chorus", "outro"],
            "characteristics": ["catchy hook", "simple rhyme scheme", "repetitive chorus", "4-minute length"],
            "common_themes": ["love", "party", "summer", "self-expression", "dreams"],
            "line_length": "moderate",
            "rhyme_preference": "AABB or ABAB"
        },
        Genre.ROCK: {
            "structure": ["intro", "verse", "pre-chorus", "chorus", "verse", "chorus", "solo", "chorus", "outro"],
            "characteristics": ["powerful chorus", "guitar-driven", "emotional intensity", "5-7 minute length"],
            "common_themes": ["rebellion", "love", "struggle", "freedom", "pain"],
            "line_length": "varied",
            "rhyme_preference": "ABAB or free"
        },
        Genre.HIP_HOP: {
            "structure": ["intro", "verse", "hook", "verse", "hook", "verse", "hook", "outro"],
            "characteristics": ["flow patterns", "rhythm focus", "beat drops", "3-4 minute length"],
            "common_themes": ["street life", "success", "struggle", "money", "power"],
            "line_length": "short, punchy",
            "rhyme_preference": "AAA or complex multi-syllable"
        },
        Genre.THRILLER: {
            "structure": ["setup", "inciting_incident", "rising_action", "midpoint", "climax", "falling_action", "resolution"],
            "characteristics": ["suspense", "twists", "pacing", "moral ambiguity"],
            "common_themes": ["crime", "conspiracy", "survival", "betrayal", "justice"],
            "pacing": "fast with cliffhangers"
        },
        Genre.ROMANCE: {
            "structure": ["introduction", "meeting", "attraction", "obstacles", " declaration", "climax", "resolution"],
            "characteristics": ["emotional depth", "character chemistry", "tension building", "satisfying ending"],
            "common_themes": ["love", "passion", "sacrifice", "trust", "redemption"],
            "pacing": "moderate, building"
        },
        Genre.SCIFI: {
            "structure": ["world_building", "introduction", "conflict", "discovery", "confrontation", "resolution"],
            "characteristics": ["world building", "technology focus", "speculation", "exploration"],
            "common_themes": ["AI", "space", "future", "humanity", "ethics"],
            "pacing": "varied"
        }
    }

    def get_template(self, genre: Genre) -> Dict[str, Any]:
        """Get template for a genre."""
        return self.TEMPLATES.get(genre, self.TEMPLATES[Genre.POP])


class StoryArcGenerator:
    """
    Generates story structures and plot arcs.
    
    Features:
    - Three-act structure generation
    - Character arc creation
    - Plot point placement
    - Theme integration
    - Genre-specific pacing
    """

    def __init__(self):
        """Initialize story arc generator."""
        self.logger = logging.getLogger(f"{__name__}.StoryArcGenerator")

    def generate_story_arc(
        self,
        genre: Genre,
        premise: str,
        length: str = "medium"
    ) -> StoryArc:
        """
        Generate a complete story arc.
        
        Args:
            genre: Story genre
            premise: One-sentence premise
            length: "short", "medium", or "novel"
            
        Returns:
            Complete StoryArc object
        """
        arc_id = f"arc_{uuid.uuid4().hex[:8]}"
        
        # Generate structure based on genre and length
        if length == "short":
            acts = self._generate_short_form(genre, premise)
        elif length == "novel":
            acts = self._generate_novel_form(genre, premise)
        else:
            acts = self._generate_medium_form(genre, premise)
        
        # Generate characters
        characters = self._generate_characters(genre, acts["setup"])
        
        # Generate plot points
        plot_points = self._generate_plot_points(genre, acts, length)
        
        return StoryArc(
            arc_id=arc_id,
            title=self._generate_title(genre, premise),
            genre=genre,
            premise=premise,
            setup=acts["setup"],
            confrontation=acts["confrontation"],
            resolution=acts["resolution"],
            themes=self._extract_themes(premise),
            characters=characters,
            plot_points=plot_points
        )

    def _generate_short_form(self, genre: Genre, premise: str) -> Dict[str, str]:
        """Generate short form structure."""
        return {
            "setup": f"In {premise}, we meet the protagonist in their ordinary world. A disruption occurs that sets the story in motion.",
            "confrontation": f"The protagonist faces challenges arising from the inciting incident, leading to a key confrontation.",
            "resolution": f"The story reaches its climax and resolution, with the protagonist transformed by their journey."
        }

    def _generate_medium_form(self, genre: Genre, premise: str) -> Dict[str, str]:
        """Generate medium form (novella) structure."""
        return {
            "setup": f"The story opens with {premise}. We are introduced to the protagonist, their world, and the status quo. An inciting incident disrupts this balance and forces them to act.",
            "confrontation": f"The protagonist ventures into the unknown, facing escalating challenges. They meet allies and enemies, discover new aspects of the conflict, and reach a midpoint revelation that changes everything.",
            "resolution": f"All threads converge in a final confrontation. The protagonist must use everything they've learned. A resolution brings change to their world."
        }

    def _generate_novel_form(self, genre: Genre, premise: str) -> Dict[str, str]:
        """Generate novel form structure."""
        return {
            "setup": f"Act One: {premise}. We meet the protagonist in their ordinary world, learn their backstory and desires. An inciting incident presents the story's central conflict. The protagonist reluctantly commits to the journey.",
            "confrontation": f"Act Two (Part 1): The protagonist faces initial successes and growing complications. They form alliances, encounter obstacles. Midpoint: A major revelation raises the stakes. Act Two (Part 2): The protagonist's resolve is tested. They face their greatest challenge yet. All seems lost.",
            "resolution": f"Act Three: The climax brings protagonist and antagonist to final confrontation. The protagonist's arc completes. The resolution shows the new status quo and how the protagonist has changed."
        }

    def _generate_characters(self, genre: Genre, setup: str) -> List[Dict[str, str]]:
        """Generate characters for the story."""
        characters = []
        
        # Protagonist
        characters.append({
            "role": "protagonist",
            "name": self._generate_name(),
            "description": "The main character who drives the story forward",
            "arc": "growth through challenges"
        })
        
        # Antagonist
        if genre not in [Genre.ROMANCE, Genre.LITERARY]:
            characters.append({
                "role": "antagonist",
                "name": self._generate_name(),
                "description": "The force opposing the protagonist",
                "arc": "conflict with protagonist's goals"
            })
        
        # Supporting characters
        characters.append({
            "role": "mentor",
            "name": self._generate_name(),
            "description": "Guides and supports the protagonist",
            "arc": "helps protagonist grow"
        })
        
        return characters

    def _generate_plot_points(self, genre: Genre, acts: Dict[str, str], length: str) -> List[Dict[str, str]]:
        """Generate plot points."""
        points = []
        
        plot_point_templates = [
            {"name": "Inciting Incident", "position": "early", "description": "The event that starts the story"},
            {"name": "First Plot Point", "position": "early", "description": "Protagonist commits to the journey"},
            {"name": "Rising Action", "position": "middle", "description": "Challenges escalate"},
            {"name": "Midpoint", "position": "middle", "description": "Major revelation or reversal"},
            {"name": "Crisis", "position": "late", "description": "Protagonist faces their darkest moment"},
            {"name": "Climax", "position": "late", "description": "Final confrontation"},
            {"name": "Resolution", "position": "end", "description": "Story concludes"}
        ]
        
        if length == "short":
            plot_point_templates = [plot_point_templates[i] for i in [0, 2, 5, 6]]
        elif length == "novel":
            # Add more plot points for novels
            pass
        
        return plot_point_templates

    def _generate_title(self, genre: Genre, premise: str) -> str:
        """Generate a title based on premise."""
        title_templates = {
            Genre.THRILLER: ["The {} Mystery", "Deep {} Secrets", "The {} Conspiracy"],
            Genre.ROMANCE: ["Love and {}", "Hearts {}", "The {} Journey"],
            Genre.SCIFI: ["The {} Frontier", "{} Rising", "Beyond {}"],
            Genre.FANTASY: ["The {} Chronicles", "Realm of {}", "The {} Prophecy"],
        }
        
        templates = title_templates.get(genre, ["The {} Story"])
        template = random.choice(templates)
        
        # Extract key word from premise
        words = premise.split()
        key_words = [w for w in words if len(w) > 4 and w not in ["when", "that", "this", "from", "with"]]
        key = random.choice(key_words) if key_words else "Unknown"
        
        return template.format(key.capitalize())

    def _generate_name(self) -> str:
        """Generate a random name."""
        first_names = ["Alex", "Jordan", "Taylor", "Morgan", "Casey", "Riley", "Quinn", "Avery", "Cameron", "Drew"]
        last_names = ["Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis", "Wilson", "Anderson"]
        return f"{random.choice(first_names)} {random.choice(last_names)}"

    def _extract_themes(self, premise: str) -> List[str]:
        """Extract themes from premise."""
        theme_keywords = {
            "love": ["love", "heart", "romance", "passion"],
            "loss": ["lost", "death", "grief", "mourning"],
            "redemption": ["redemption", "forgive", "atone", "second chance"],
            "power": ["power", "control", "dominate", "rule"],
            "survival": ["survive", "escape", "fight", "struggle"],
            "identity": ["identity", "discover", "true self", "become"]
        }
        
        themes = []
        premise_lower = premise.lower()
        
        for theme, keywords in theme_keywords.items():
            if any(kw in premise_lower for kw in keywords):
                themes.append(theme)
        
        return themes if themes else ["journey"]


class SongGenerator:
    """Generate songs based on genre and theme."""

    def __init__(self):
        """Initialize song generator."""
        self.rhyme_engine = RhymeEngine()
        self.templates = GenreTemplates()
        self.logger = logging.getLogger(f"{__name__}.SongGenerator")

    def generate_song(
        self,
        genre: Genre,
        theme: str,
        title: Optional[str] = None,
        verse_count: int = 2
    ) -> SongStructure:
        """
        Generate a complete song.
        
        Args:
            genre: Song genre
            theme: Song theme
            title: Optional title
            verse_count: Number of verses
            
        Returns:
            Complete SongStructure
        """
        template = self.templates.get_template(genre)
        
        if not title:
            title = self._generate_title(genre, theme)
        
        song = SongStructure(
            title=title,
            genre=genre,
            theme=theme
        )
        
        # Generate verses
        for i in range(verse_count):
            verse = self._generate_verse(genre, theme, i + 1)
            song.verses.append(verse)
        
        # Generate chorus
        song.chorus = self._generate_chorus(genre, theme, title)
        
        # Generate bridge
        song.bridge = self._generate_bridge(genre, theme)
        
        return song

    def _generate_title(self, genre: Genre, theme: str) -> str:
        """Generate song title."""
        templates = [
            f"The {theme.title()} Song",
            f"{theme.title()} Nights",
            f"Dancing {theme.title()}",
            f"Heart of {theme.title()}",
            f"{theme.title()} Forever"
        ]
        return random.choice(templates)

    def _generate_verse(self, genre: Genre, theme: str, number: int) -> Verse:
        """Generate a verse."""
        lines = [
            f"Verse {number} line 1 - {theme}",
            f"Verse {number} line 2",
            f"Verse {number} line 3",
            f"Verse {number} line 4"
        ]
        return Verse(lines=lines, rhyme_scheme="ABAB")

    def _generate_chorus(self, genre: Genre, theme: str, title: str) -> Verse:
        """Generate the chorus."""
        lines = [
            f"This is the chorus - {theme}",
            f"Singing {theme.title()} all night long",
            f"The {title} feeling",
            f"It feels so right"
        ]
        return Verse(lines=lines, rhyme_scheme="AABB")

    def _generate_bridge(self, genre: Genre, theme: str) -> Verse:
        """Generate the bridge."""
        lines = [
            "Bridge - taking it somewhere new",
            f"Everything changes about {theme}",
            "But the beat goes on",
            "And we carry on"
        ]
        return Verse(lines=lines, rhyme_scheme="ABAB")

    def to_lyrics(self, song: SongStructure) -> str:
        """Convert song structure to lyrics string."""
        lines = []
        
        lines.append(f"# {song.title}")
        lines.append(f"Genre: {song.genre.value}")
        lines.append(f"Theme: {song.theme}")
        lines.append("")
        
        # Add intro if present
        if song.intro:
            lines.append("[Intro]")
            lines.extend(song.intro.lines)
            lines.append("")
        
        # Add verses and chorus
        for i, verse in enumerate(song.verses):
            lines.append(f"[Verse {i+1}]")
            lines.extend(verse.lines)
            lines.append("")
            
            if song.chorus and i == 0:
                lines.append("[Chorus]")
                lines.extend(song.chorus.lines)
                lines.append("")
        
        # Add remaining chorus
        if song.chorus and len(song.verses) > 1:
            lines.append("[Chorus]")
            lines.extend(song.chorus.lines)
            lines.append("")
        
        # Add bridge
        if song.bridge:
            lines.append("[Bridge]")
            lines.extend(song.bridge.lines)
            lines.append("")
        
        # Add outro if present
        if song.outro:
            lines.append("[Outro]")
            lines.extend(song.outro.lines)
            lines.append("")
        
        return "\n".join(lines)


def main():
    """Main entry point for the CLI."""
    parser = argparse.ArgumentParser(
        description="ILMA Creative Generator - Song lyrics, stories, and creative concepts",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --type song --genre pop --theme "love" --title "My Love Song"
  %(prog)s --type story --genre thriller --length medium --premise "A detective must solve a murder"
  %(prog)s --concept --seed "A robot who dreams"
  %(prog)s --rhyme-word "heart" --count 10
        """
    )
    
    parser.add_argument("--type", choices=["song", "story", "poem", "screenplay", "concept"],
                       help="Type of creative output")
    
    # Song options
    parser.add_argument("--genre", "-g", help="Genre (pop, rock, thriller, etc.)")
    parser.add_argument("--theme", "-t", help="Theme or topic")
    parser.add_argument("--title", help="Title for the work")
    
    # Story options
    parser.add_argument("--premise", "-p", help="Story premise (one sentence)")
    parser.add_argument("--length", choices=["short", "medium", "novel"],
                       default="medium", help="Story length")
    
    # Concept options
    parser.add_argument("--concept", action="store_true", help="Generate creative concept")
    parser.add_argument("--seed", help="Seed idea for concept")
    
    # Rhyme engine
    parser.add_argument("--rhyme-word", help="Word to find rhymes for")
    parser.add_argument("--count", type=int, default=10, help="Number of results")
    
    # Output
    parser.add_argument("--output", "-o", help="Output file")
    parser.add_argument("--format", "-f", choices=["text", "json"],
                       default="text", help="Output format")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose logging")
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    logger = logging.getLogger(__name__)
    
    try:
        # Rhyme word lookup
        if args.rhyme_word:
            engine = RhymeEngine()
            rhymes = engine.get_rhyming_words(args.rhyme_word, args.count)
            
            if args.format == "json":
                print(json.dumps({
                    "word": args.rhyme_word,
                    "rhymes": rhymes
                }, indent=2))
            else:
                print(f"Words that rhyme with '{args.rhyme_word}':")
                for rhyme in rhymes:
                    syllables = engine.count_syllables(rhyme)
                    print(f"  {rhyme} ({syllables} syllables)")
            return 0
        
        # Creative concept generation
        if args.concept or args.type == "concept":
            if not args.seed:
                logger.error("--seed required for concept generation")
                return 1
            
            # Generate concept from seed
            concept = {
                "seed": args.seed,
                "title": f"The {args.seed.title()} Project",
                "themes": ["discovery", "transformation"],
                "characters": ["The Seeker", "The Guide"],
                "premise": f"What if {args.seed}?",
                "arc": "A journey from understanding to mastery"
            }
            
            if args.format == "json":
                print(json.dumps(concept, indent=2))
            else:
                print("\n" + "=" * 60)
                print("CREATIVE CONCEPT")
                print("=" * 60)
                print(f"Seed: {concept['seed']}")
                print(f"Title: {concept['title']}")
                print(f"Premise: {concept['premise']}")
                print(f"Themes: {', '.join(concept['themes'])}")
                print(f"Characters: {', '.join(concept['characters'])}")
                print(f"Arc: {concept['arc']}")
            return 0
        
        # Song generation
        if args.type == "song":
            if not args.genre:
                logger.error("--genre required for song generation")
                return 1
            if not args.theme:
                logger.error("--theme required for song generation")
                return 1
            
            try:
                genre = Genre(args.genre.lower())
            except ValueError:
                logger.error(f"Unknown genre: {args.genre}")
                return 1
            
            generator = SongGenerator()
            song = generator.generate_song(
                genre=genre,
                theme=args.theme,
                title=args.title
            )
            
            lyrics = generator.to_lyrics(song)
            
            if args.output:
                with open(args.output, "w") as f:
                    f.write(lyrics)
                print(f"✓ Song saved to {args.output}")
            else:
                print("\n" + lyrics)
            
            return 0
        
        # Story generation
        if args.type == "story":
            if not args.premise:
                logger.error("--premise required for story generation")
                return 1
            if not args.genre:
                logger.error("--genre required for story generation")
                return 1
            
            try:
                genre = Genre(args.genre.lower())
            except ValueError:
                logger.error(f"Unknown genre: {args.genre}")
                return 1
            
            generator = StoryArcGenerator()
            arc = generator.generate_story_arc(
                genre=genre,
                premise=args.premise,
                length=args.length
            )
            
            story_data = {
                "title": arc.title,
                "genre": arc.genre.value,
                "premise": arc.premise,
                "setup": arc.setup,
                "confrontation": arc.confrontation,
                "resolution": arc.resolution,
                "themes": arc.themes,
                "characters": arc.characters,
                "plot_points": arc.plot_points
            }
            
            if args.format == "json":
                print(json.dumps(story_data, indent=2))
            else:
                print("\n" + "=" * 60)
                print(f"STORY ARC: {arc.title}")
                print("=" * 60)
                print(f"\nGenre: {arc.genre.value}")
                print(f"Length: {args.length}")
                print(f"\nPremise: {arc.premise}")
                print(f"\n--- SETUP (Act 1) ---")
                print(arc.setup)
                print(f"\n--- CONFRONTATION (Act 2) ---")
                print(arc.confrontation)
                print(f"\n--- RESOLUTION (Act 3) ---")
                print(arc.resolution)
                print(f"\nThemes: {', '.join(arc.themes)}")
                print("\nCharacters:")
                for char in arc.characters:
                    print(f"  - {char['role'].title()}: {char['name']}")
                    print(f"    {char['description']}")
                print("\nPlot Points:")
                for pp in arc.plot_points:
                    print(f"  - {pp['name']} ({pp['position']}): {pp['description']}")
            
            if args.output:
                with open(args.output, "w") as f:
                    json.dump(story_data, f, indent=2)
                print(f"\n✓ Story outline saved to {args.output}")
            
            return 0
        
        # Default: show help
        parser.print_help()
        return 0
        
    except Exception as e:
        logger.exception("Fatal error")
        return 1


if __name__ == "__main__":
    exit(main())