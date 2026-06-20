"""
ILMA v5.0 — HYPER-LOCALIZED INDONESIAN NLP & SEO TUNING ENGINE
Principal NLP Engineer: ILMA v5.0

Modul untuk mendeteksi target audience (B2B Profesional vs B2C Kasual/Gen-Z),
mengatur Keyword Density, menyuntikkan transisi organik, dan menyesuaikan
Readability Score khusus untuk Bahasa Indonesia agar lolos AI Content Detectors.

Features:
- Audience Detection (B2B, B2C, Gen-Z, General)
- Keyword Density Optimization
- Organic Indonesian Transition Injection
- Flesch Reading Ease untuk Bahasa Indonesia
- AI Content Detector Bypass
- Readability Optimization

SUPREME ARCHITECT: ILMA v5.0 — PERFECTION & OPTIMIZATION UPDATE
"""

from __future__ import annotations
import asyncio
import hashlib
import json
import logging
import re
import math
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Any, Optional, Set, Tuple
from collections import Counter, defaultdict
import random

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ID-NLP")


# ═══════════════════════════════════════════════════════════════════════════════
# AUDIENCE TYPE & CONTENT ENUMS
# ═══════════════════════════════════════════════════════════════════════════════

class AudienceType(Enum):
    B2B_PROFESIONAL = "b2b_profesional"
    B2C_KASUAL = "b2c_kasual"
    GEN_Z = "gen_z"
    GENERAL = "general"
    ACADEMIC = "academic"


class ContentType(Enum):
    SEO_ARTICLE = "seo_article"
    BLOG_POST = "blog_post"
    SOCIAL_MEDIA = "social_media"
    PRODUCT_DESCRIPTION = "product_description"
    TECHNICAL_DOC = "technical_doc"
    ACADEMIC_PAPER = "academic_paper"


@dataclass
class AudienceProfile:
    """Profile untuk target audience tertentu."""
    audience_type: AudienceType
    formal_level: float  # 0.0 (santai) - 1.0 (formal)
    avg_sentence_length: Tuple[int, int]  # (min, max)
    avg_word_length: Tuple[int, int]  # (min, max)
    transition_style: List[str]
    banned_words: Set[str]
    required_elements: List[str]
    target_flesch_score: float
    emoji_allowed: bool
    slang_tolerance: float  # 0.0-1.0


# ═══════════════════════════════════════════════════════════════════════════════
# AUDIENCE PROFILES — TARGET PERSONA CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════

AUDIENCE_PROFILES: Dict[AudienceType, AudienceProfile] = {
    AudienceType.B2B_PROFESIONAL: AudienceProfile(
        audience_type=AudienceType.B2B_PROFESIONAL,
        formal_level=0.9,
        avg_sentence_length=(15, 25),
        avg_word_length=(4, 6),
        transition_style=[
            "Oleh karena itu,", "Dengan demikian,", "Berdasarkan hal tersebut,",
            "Lebih lanjut,", "Selanjutnya,", "Dalam konteks ini,",
            "Dari perspektif bisnis,", "Secara strategis,"
        ],
        banned_words={"gak", "nggak", "udah", "belom", "kalo", "dgn", "btw", "lol"},
        required_elements=[
            "data pendukung", "tren industri", "analisis komparatif",
            "stakeholder perspective", "ROI consideration"
        ],
        target_flesch_score=45.0,
        emoji_allowed=False,
        slang_tolerance=0.05
    ),
    
    AudienceType.B2C_KASUAL: AudienceProfile(
        audience_type=AudienceType.B2C_KASUAL,
        formal_level=0.5,
        avg_sentence_length=(10, 18),
        avg_word_length=(3, 5),
        transition_style=[
            "Selain itu,", "Menariknya lagi,", "Puncaknya,",
            "Yang lebih seru,", "Oh ya,", "Jadi intinya,"
        ],
        banned_words={"ndak", "kalo", "dgn"},
        required_elements=[
            "benefits konkret", "testimoni", "call-to-action"
        ],
        target_flesch_score=60.0,
        emoji_allowed=True,
        slang_tolerance=0.3
    ),
    
    AudienceType.GEN_Z: AudienceProfile(
        audience_type=AudienceType.GEN_Z,
        formal_level=0.2,
        avg_sentence_length=(8, 15),
        avg_word_length=(3, 5),
        transition_style=[
            "Terus", "Jadi gitu", "Nah ini dia", "Gokil",
            "Auto", "Ngopi", "Stay", "Sipp"
        ],
        banned_words={"oleh karena itu", "dengan demikian", "sehubungan dengan"},
        required_elements=[
            "viral hooks", "relatable content", "FOMO elements"
        ],
        target_flesch_score=75.0,
        emoji_allowed=True,
        slang_tolerance=0.7
    ),
    
    AudienceType.GENERAL: AudienceProfile(
        audience_type=AudienceType.GENERAL,
        formal_level=0.6,
        avg_sentence_length=(12, 20),
        avg_word_length=(4, 6),
        transition_style=[
            "Oleh karena itu,", "Selain itu,", "Menariknya lagi,",
            "Puncaknya,", "Dengan demikian,", "Hal ini menunjukkan,"
        ],
        banned_words={"gak", "nggak", "kalo"},
        required_elements=[
            "clear explanation", "practical examples"
        ],
        target_flesch_score=55.0,
        emoji_allowed=False,
        slang_tolerance=0.15
    ),
    
    AudienceType.ACADEMIC: AudienceProfile(
        audience_type=AudienceType.ACADEMIC,
        formal_level=0.95,
        avg_sentence_length=(20, 35),
        avg_word_length=(5, 8),
        transition_style=[
            "Sehubungan dengan hal tersebut,", "Dalam kerangka pemikiran ini,",
            "Berdasarkan analisis komprehensif,", "Secara epistemologis,",
            "Dari perspektif teoretis,", "Lebih lanjut dipandang dari sudut"
        ],
        banned_words={"gak", "nggak", "udah", "btw", "lol", "omg"},
        required_elements=[
            "citations", "methodology", "theoretical framework"
        ],
        target_flesch_score=35.0,
        emoji_allowed=False,
        slang_tolerance=0.0
    ),
}


# ═══════════════════════════════════════════════════════════════════════════════
# KEYWORD DENSITY OPTIMIZER
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class KeywordConfig:
    """Konfigurasi untuk satu keyword."""
    keyword: str
    target_density: float  # 0.01 - 0.03 (1-3%)
    min_density: float = 0.005
    max_density: float = 0.05
    priority: str = "medium"  # high, medium, low
    variations: List[str] = field(default_factory=list)


class KeywordDensityOptimizer:
    """
    Mengatur keyword density agar optimal untuk SEO tanpa over-optimization.
    
    Target: 1-3% density (Google's sweet spot)
    Over-optimization: >3% = potential penalty
    Under-optimization: <1% = not ranking
    """
    
    def __init__(self):
        self.keywords: List[KeywordConfig] = []
        self.primary_keyword: Optional[str] = None
    
    def set_primary_keyword(self, keyword: str, target_density: float = 0.02):
        """Set keyword utama yang paling penting."""
        self.primary_keyword = keyword
        self.keywords.insert(0, KeywordConfig(
            keyword=keyword,
            target_density=target_density,
            priority="high",
            variations=self._generate_variations(keyword)
        ))
    
    def add_secondary_keyword(self, keyword: str, target_density: float = 0.015):
        """Tambah keyword sekunder."""
        self.keywords.append(KeywordConfig(
            keyword=keyword,
            target_density=target_density,
            priority="medium",
            variations=self._generate_variations(keyword)
        ))
    
    def add_lsi_keyword(self, keyword: str):
        """Tambah LSI keyword (semantic related)."""
        self.keywords.append(KeywordConfig(
            keyword=keyword,
            target_density=0.008,
            priority="low",
            variations=[]
        ))
    
    def _generate_variations(self, keyword: str) -> List[str]:
        """Generate keyword variations untuk natural insertion."""
        variations = [keyword]
        
        # Singular/plural
        if keyword.endswith('s'):
            variations.append(keyword[:-1])
        else:
            variations.append(keyword + 's')
        
        # Dengan prefix
        prefixes = ["memahami ", "tentang ", "untuk ", "dengan "]
        for p in prefixes:
            if not keyword.startswith(p):
                variations.append(p + keyword)
        
        # Dengan suffix
        suffixes = [" untuk bisnis", " Indonesia", " terbaru"]
        for s in suffixes:
            variations.append(keyword + s)
        
        return list(set(variations))
    
    def calculate_current_density(self, text: str, keyword: str) -> float:
        """Hitung keyword density saat ini."""
        text_lower = text.lower()
        keyword_lower = keyword.lower()
        
        words = re.findall(r'\b\w+\b', text_lower)
        total_words = len(words)
        
        if total_words == 0:
            return 0.0
        
        keyword_count = text_lower.count(keyword_lower)
        
        # Also count in compound words
        for word in words:
            if keyword_lower in word:
                keyword_count += 0.5
        
        return keyword_count / total_words
    
    def optimize_text(
        self,
        text: str,
        min_word_count: int = 300,
        max_keyword_insertions: int = 8
    ) -> str:
        """
        Optimize text dengan keyword placement yang natural.
        
        Returns text dengan keyword yang sudah dioptimasi.
        """
        if not self.keywords:
            return text
        
        optimized = text
        insertions_made = 0
        
        primary = self.keywords[0]
        
        # First paragraph - harus ada keyword di awal
        first_100_words = ' '.join(optimized.split()[:100])
        if primary.keyword.lower() not in first_100_words.lower():
            optimized = self._insert_keyword_naturally(
                optimized,
                primary.keyword,
                position="first",
                max_insertions=1
            )
            insertions_made += 1
        
        # Headings - tambahkan keyword di H2/H3
        if insertions_made < max_keyword_insertions:
            optimized = self._optimize_headings(optimized, primary.keyword)
        
        # Throughout text - natural distribution
        if insertions_made < max_keyword_insertions:
            remaining = max_keyword_insertions - insertions_made
            optimized = self._distribute_keywords(optimized, remaining)
        
        # Secondary keywords - subtle placement
        for kw_config in self.keywords[1:]:
            if kw_config.priority == "high":
                optimized = self._inject_keyword_variation(
                    optimized,
                    kw_config.keyword,
                    count=3
                )
        
        return optimized
    
    def _insert_keyword_naturally(
        self,
        text: str,
        keyword: str,
        position: str = "first",
        max_insertions: int = 1
    ) -> str:
        """Insert keyword secara natural di posisi yang tepat."""
        
        if position == "first":
            sentences = re.split(r'(?<=[.!?])\s+', text)
            if sentences:
                first_sentence = sentences[0]
                
                # Check if keyword already in first sentence
                if keyword.lower() not in first_sentence.lower():
                    # Insert setelah subjek pertama
                    words = first_sentence.split()
                    if len(words) > 3:
                        # Insert setelah kata ke-2 atau ke-3
                        insert_pos = min(3, len(words) - 1)
                        words.insert(insert_pos, keyword)
                        sentences[0] = ' '.join(words)
                
                return ' '.join(sentences)
        
        return text
    
    def _optimize_headings(self, text: str, keyword: str) -> str:
        """Tambahkan keyword di headings jika belum ada."""
        
        headings = re.findall(r'^(#{1,6}\s+.+)$', text, re.MULTILINE)
        
        keyword_in_heading = any(keyword.lower() in h.lower() for h in headings)
        
        if not keyword_in_heading and headings:
            # Add keyword ke H2 atau H3 yang kedua (setelah title)
            for i, heading in enumerate(headings[1:3], 1):
                if keyword.lower() not in heading.lower():
                    # Append keyword ke heading
                    new_heading = heading.rstrip() + f" - {keyword}"
                    text = text.replace(heading, new_heading, 1)
                    break
        
        return text
    
    def _distribute_keywords(self, text: str, count: int) -> str:
        """Distribute keyword secara merata di seluruh text."""
        
        if not self.keywords:
            return text
        
        sentences = re.split(r'(?<=[.!?])\s+', text)
        primary = self.keywords[0]
        
        # Split text jadi bagian dan distribusikan
        segment_size = len(sentences) / max(count, 1)
        
        for i in range(min(count, len(sentences))):
            segment_start = int(i * segment_size)
            segment_end = int((i + 1) * segment_size)
            
            if segment_start >= len(sentences):
                break
            
            segment = ' '.join(sentences[segment_start:segment_end])
            
            if primary.keyword.lower() not in segment.lower():
                # Insert secara natural
                words = segment.split()
                if len(words) > 5:
                    insert_pos = len(words) // 2
                    words.insert(insert_pos, primary.keyword)
                    sentences[segment_start] = ' '.join(words)
        
        return ' '.join(sentences)
    
    def _inject_keyword_variation(self, text: str, keyword: str, count: int) -> str:
        """Inject keyword variation secara subtle."""
        
        for _ in range(count):
            # Cari tempat yang appropriate untuk inject
            patterns = [
                (r'(untuk\s+)(\w+)', r'\1' + keyword + r' \2'),
                (r'(dengan\s+)(\w+)', r'\1' + keyword + r' \2'),
                (r'(tentang\s+)(\w+)', r'\1' + keyword + r' \2'),
            ]
            
            for pattern, replacement in patterns:
                if re.search(pattern, text, re.IGNORECASE):
                    text = re.sub(pattern, replacement, text, count=1, flags=re.IGNORECASE)
                    break
        
        return text


# ═══════════════════════════════════════════════════════════════════════════════
# INDONESIAN TRANSITION ENGINE — ORGANIC FLOW
# ═══════════════════════════════════════════════════════════════════════════════

class IndonesianTransitionEngine:
    """
    Menyuntikkan transisi kalimat yang sangat organik dalam Bahasa Indonesia.
    
    Transisi yang terlalu robotic (Pertama-tama, Kedua, Ketiga) langsung
    terdeteksi sebagai AI-generated. Engine ini menggunakan transisi yang
    lebih natural dan varied.
    """
    
    # Transisi formal (untuk B2B, Academic)
    FORMAL_TRANSITIONS = [
        "Oleh karena itu,",
        "Dengan demikian,",
        "Berdasarkan hal tersebut,",
        "Lebih lanjut,",
        "Selanjutnya,",
        "Dalam konteks ini,",
        "Dari perspektif yang lebih luas,",
        "Sejalan dengan perkembangan,",
        "Merujuk pada fenomena tersebut,",
        "Menjawab pertanyaan tersebut,",
        "Menariknya lagi,",
        "Puncaknya,",
        "Secara tidak langsung,",
        "Dapat disimpulkan bahwa,",
        "Hal ini menunjukkan bahwa,",
    ]
    
    # Transisi semi-formal (untuk B2C)
    SEMIFORMAL_TRANSITIONS = [
        "Selain itu,",
        "Menariknya lagi,",
        "Puncaknya,",
        "Yang lebih menarik,",
        "Tak hanya itu,",
        "Yang lebih penting,",
        "Hal lain yang perlu diperhatikan,",
        "Berikutnya,",
        "Kemudian,",
        "Setelah dipahami,",
        "Dalam situasi ini,",
        "Ketika berbicara tentang,",
        "Dari sudut pandang ini,",
        "Dengan kata lain,",
    ]
    
    # Transisi kasual (untuk Gen-Z)
    CASUAL_TRANSITIONS = [
        "Terus yang bikin kaget,",
        "Gokilnya lagi,",
        "Nah ini yang seru,",
        "Jadi gitu guys,",
        "Auto gitu lho,",
        "Sipp banget sih,",
        "Nah loose,",
        "Anyway,",
        "Oh iya,",
        "Jadiintinya nih,",
        "Gitu loh sebenernya,",
        "Stay tuned ya,",
        "Ngopi dulu,",
    ]
    
    # Transisi untuk intro
    INTRO_TRANSITIONS = [
        "Perhatikan bahwa,",
        "Perlu diketahui bahwa,",
        "Penting untuk dipahami bahwa,",
        "Hal mendasar yang perlu dicatat adalah,",
        "Dalam pembahasan kali ini,",
        "Menarik untuk disimak bahwa,",
    ]
    
    # Transisi untuk kesimpulan
    CONCLUSION_TRANSITIONS = [
        "Dari uraian di atas, dapat disimpulkan bahwa,",
        "Berdasarkan pembahasan tersebut,",
        "Sebagai penutup,",
        "Untuk meresume,",
        "Sebagai akhir kata,",
        "Подвести итоги,",
    ]
    
    def __init__(self):
        self.last_transition_used: Optional[str] = None
        self.transition_history: List[str] = []
    
    def get_transitions_for_audience(
        self,
        audience: AudienceType,
        context: str = "body"  # intro, body, conclusion
    ) -> List[str]:
        """Get transisi yang sesuai untuk audience dan konteks."""
        
        if audience == AudienceType.B2B_PROFESIONAL or audience == AudienceType.ACADEMIC:
            base = self.FORMAL_TRANSITIONS
        elif audience == AudienceType.GEN_Z:
            base = self.CASUAL_TRANSITIONS
        else:
            base = self.SEMIFORMAL_TRANSITIONS
        
        if context == "intro":
            return self.INTRO_TRANSITIONS
        elif context == "conclusion":
            return self.CONCLUSION_TRANSITIONS
        
        return base
    
    def inject_transitions(
        self,
        text: str,
        audience: AudienceType,
        injection_rate: float = 0.3  # 30% of sentences get transitions
    ) -> str:
        """
        Inject transisi secara natural ke text.
        
        Proses:
        1. Split text jadi sentences
        2. Identifikasi sentence yang perlu transisi
        3. Pilih transisi yang sesuai (avoid repetition)
        4. Inject dengan formatting yang natural
        """
        
        sentences = re.split(r'(?<=[.!?])\s+', text)
        transitions = self.get_transitions_for_audience(audience)
        
        optimized_sentences = []
        
        for i, sentence in enumerate(sentences):
            # Skip if sentence terlalu pendek
            if len(sentence.split()) < 5:
                optimized_sentences.append(sentence)
                continue
            
            # Skip if sudah ada transisi
            if self._has_existing_transition(sentence):
                optimized_sentences.append(sentence)
                continue
            
            # Decide apakah perlu transisi
            should_inject = random.random() < injection_rate
            
            if should_inject and i > 0:  # Jangan kasih transisi di sentence pertama
                # Select transition yang berbeda dari sebelumnya
                available = [t for t in transitions if t != self.last_transition_used]
                transition = random.choice(available)
                
                # Combine dengan natural punctuation
                sentence = self._combine_transition(sentence, transition, audience)
                self.last_transition_used = transition
                self.transition_history.append(transition)
            
            optimized_sentences.append(sentence)
        
        return ' '.join(optimized_sentences)
    
    def _has_existing_transition(self, sentence: str) -> bool:
        """Check apakah sentence sudah punya transisi."""
        all_transitions = (
            self.FORMAL_TRANSITIONS +
            self.SEMIFORMAL_TRANSITIONS +
            self.CASUAL_TRANSITIONS
        )
        
        sentence_lower = sentence.lower()
        for t in all_transitions:
            if t.rstrip(',').lower() in sentence_lower:
                return True
        
        return False
    
    def _combine_transition(
        self,
        sentence: str,
        transition: str,
        audience: AudienceType
    ) -> str:
        """Gabungkan transisi dengan sentence secara natural."""
        
        # Capitalize first letter of transition
        transition = transition.capitalize()
        
        # Check first word of sentence
        first_word = sentence.split()[0] if sentence.split() else ""
        
        # Patterns untuk natural combination
        if audience in [AudienceType.B2B_PROFESIONAL, AudienceType.ACADEMIC]:
            # Formal: "Berdasarkan data, terlihat bahwa..."
            return f"{transition} {sentence}"
        
        elif audience == AudienceType.GEN_Z:
            # Kasual: "Terus yang bikin kaget tuh..."
            return f"{transition} {sentence.lower()}"
        
        else:
            # Semi-formal: "Selain itu, penting untuk..."
            if first_word[0].isupper():
                return f"{transition} {sentence}"
            else:
                return f"{transition} {sentence}"
    
    def create_paragraph_transitions(
        self,
        paragraphs: List[str],
        audience: AudienceType
    ) -> List[str]:
        """
        Create natural transitions antar paragraph.
        
        Returns paragraphs dengan transisi yang menghubungkan.
        """
        
        if len(paragraphs) < 2:
            return paragraphs
        
        transitions = self.get_transitions_for_audience(audience)
        optimized = [paragraphs[0]]  # First paragraph stays as-is
        
        for i in range(1, len(paragraphs)):
            prev_para = paragraphs[i - 1]
            current_para = paragraphs[i]
            
            # Extract last sentence dari paragraph sebelumnya
            prev_sentences = re.split(r'(?<=[.!?])\s+', prev_para)
            if prev_sentences:
                last_sentence = prev_sentences[-1].strip()
                
                # Generate connection based on content
                connection = self._generate_paragraph_connection(
                    last_sentence,
                    current_para,
                    transitions,
                    audience
                )
                
                if connection:
                    current_para = f"{connection} {current_para}"
            
            optimized.append(current_para)
        
        return optimized
    
    def _generate_paragraph_connection(
        self,
        prev_sentence: str,
        current_para: str,
        transitions: List[str],
        audience: AudienceType
    ) -> str:
        """Generate paragraph connection yang natural."""
        
        available = [t for t in transitions if t != self.last_transition_used]
        
        if not available:
            return ""
        
        # Pilih transisi berdasarkan content analysis
        transition = random.choice(available)
        
        # Untuk Gen-Z, bisa use hook phrases
        if audience == AudienceType.GEN_Z:
            hooks = ["Lanjut ke yang ini:", "Nih yang gak kalah keren:", "Nah sekarang:"]
            if random.random() > 0.5:
                return f"{random.choice(hooks)}"
        
        return f"{transition}"


# ═══════════════════════════════════════════════════════════════════════════════
# INDONESIAN READABILITY SCORER — FLESCH ADAPTATION
# ═══════════════════════════════════════════════════════════════════════════════

class IndonesianReadabilityScorer:
    """
    Menghitung Readability Score dengan Flesch Reading Ease yang
    diadaptasi untuk Bahasa Indonesia.
    
    Formula:
    Flesch Reading Ease = 206.835 - 1.015(sentence_length) - 84.6(syllables_per_word)
    
    Untuk Bahasa Indonesia:
    - Sentence length cenderung lebih panjang untuk formal
    - Word complexity berbeda (affixation patterns)
    - Cultural context mempengaruhi readability
    """
    
    # Indonesian syllables estimation based on vowel clusters
    VOWELS = set('aiueoAIUEO')
    
    # Common Indonesian affixes untuk syllable estimation
    AFFIXES = {
        'me', 'mem', 'men', 'meng', 'meny', 'mem', 'memp',
        'pe', 'pem', 'pen', 'peng', 'peny', 'pem', 'pep',
        'ber', 'bel', 'be', 'per', 'pel', 'pe',
        'ter', 'tel', 'te',
        'di', 'dik', 'din', 'dig', 'dii',
        'ke', 'ket', 'kem', 'ken',
        'se', 'sem', 'sen', 'sung',
        'kan', 'an', 'wan', 'i', 'ti',
        'lah', 'kah', 'tah', 'pun',
    }
    
    # Readability thresholds by audience
    AUDIENCE_TARGETS = {
        AudienceType.B2B_PROFESIONAL: {"min": 35, "max": 50, "ideal": 45},
        AudienceType.B2C_KASUAL: {"min": 55, "max": 70, "ideal": 62},
        AudienceType.GEN_Z: {"min": 68, "max": 85, "ideal": 75},
        AudienceType.GENERAL: {"min": 50, "max": 65, "ideal": 58},
        AudienceType.ACADEMIC: {"min": 25, "max": 40, "ideal": 32},
    }
    
    def count_syllables_indonesian(self, word: str) -> int:
        """
        Estimate syllables dalam word Indonesia.
        
        Uses vowel cluster counting dengan affix handling.
        """
        if not word:
            return 0
        
        word = word.lower()
        
        # Remove non-alphabetic
        word = re.sub(r'[^a-z]', '', word)
        
        if not word:
            return 0
        
        # Count vowel groups (approximate syllables)
        syllable_count = 0
        prev_was_vowel = False
        
        for char in word:
            is_vowel = char in self.VOWELS
            
            if is_vowel and not prev_was_vowel:
                syllable_count += 1
            
            prev_was_vowel = is_vowel
        
        # Handle common affixes (reduce syllable count)
        for affix in self.AFFIXES:
            if word.startswith(affix) and len(word) > len(affix) + 3:
                syllable_count = max(1, syllable_count - 1)
        
        return max(1, syllable_count)
    
    def calculate_flesch_score(self, text: str) -> float:
        """
        Calculate Flesch Reading Ease score untuk Indonesian text.
        
        Returns score dari 0-100:
        - 90-100: Very Easy (Pelajar SD)
        - 60-70: Standard (Pelajar SMA)
        - 30-50: Difficult (Mahasiswa)
        - 0-30: Very Difficult (Akademisi)
        """
        
        if not text or not text.strip():
            return 50.0
        
        # Clean text
        text = re.sub(r'\s+', ' ', text.strip())
        
        # Split into sentences
        sentences = re.split(r'[.!?]+', text)
        sentences = [s.strip() for s in sentences if s.strip() and len(s.split()) > 1]
        
        if not sentences:
            return 50.0
        
        # Split into words
        words = re.findall(r'\b[\w\']+\b', text.lower())
        words = [w for w in words if len(w) > 1]
        
        if not words:
            return 50.0
        
        # Calculate metrics
        total_sentences = len(sentences)
        total_words = len(words)
        total_syllables = sum(self.count_syllables_indonesian(w) for w in words)
        
        # Average sentence length
        avg_sentence_length = total_words / total_sentences
        
        # Average syllables per word
        avg_syllables_per_word = total_syllables / total_words
        
        # Flesch Reading Ease formula (Indonesian adaptation)
        flesch_score = (
            206.835
            - (1.015 * avg_sentence_length)
            - (84.6 * avg_syllables_per_word)
        )
        
        # Clamp to valid range
        return max(0.0, min(100.0, flesch_score))
    
    def get_readability_grade(self, flesch_score: float) -> str:
        """Convert Flesch score ke education level."""
        
        if flesch_score >= 90:
            return "Sangat Mudah (Sekolah Dasar)"
        elif flesch_score >= 75:
            return "Mudah (Sekolah Menengah Pertama)"
        elif flesch_score >= 60:
            return "Standar (Sekolah Menengah Atas)"
        elif flesch_score >= 45:
            return "Cukup Sulit (Mahasiswa)"
        elif flesch_score >= 30:
            return "Sulit (Akademisi)"
        else:
            return "Sangat Sulit (Pakar)"
    
    def analyze_text(self, text: str) -> Dict[str, Any]:
        """Full readability analysis untuk text."""
        
        sentences = re.split(r'[.!?]+', text)
        sentences = [s.strip() for s in sentences if s.strip()]
        
        words = re.findall(r'\b[\w\']+\b', text.lower())
        
        flesch = self.calculate_flesch_score(text)
        
        # Word length distribution
        word_lengths = [len(w) for w in words]
        
        # Sentence length distribution
        sentence_lengths = [len(s.split()) for s in sentences]
        
        return {
            "flesch_score": round(flesch, 2),
            "grade_level": self.get_readability_grade(flesch),
            "total_words": len(words),
            "total_sentences": len(sentences),
            "avg_sentence_length": round(sum(sentence_lengths) / max(len(sentence_lengths), 1), 2),
            "avg_word_length": round(sum(word_lengths) / max(len(word_lengths), 1), 2),
            "long_sentences": sum(1 for sl in sentence_lengths if sl > 25),
            "short_sentences": sum(1 for sl in sentence_lengths if sl < 8),
        }
    
    def suggest_improvements(self, text: str, target_audience: AudienceType) -> List[str]:
        """Generate suggestions untuk meningkatkan readability."""
        
        analysis = self.analyze_text(text)
        target = self.AUDIENCE_TARGETS.get(target_audience, self.AUDIENCE_TARGETS[AudienceType.GENERAL])
        
        suggestions = []
        
        current_score = analysis['flesch_score']
        ideal = target['ideal']
        
        if current_score < target['min']:
            # Too difficult - simplify
            if analysis['avg_sentence_length'] > 20:
                suggestions.append("Ringkas kalimat panjang (>20 kata) jadi lebih pendek")
            if analysis['long_sentences'] > 3:
                suggestions.append(f"Ada {analysis['long_sentences']} kalimat yang terlalu panjang - pecah jadi 2")
            suggestions.append("Gunakan kata-kata yang lebih sederhana dan umum")
            suggestions.append("Kurangi penggunaan istilah teknis yang tidak perlu")
        
        elif current_score > target['max']:
            # Too simple - add substance
            if analysis['short_sentences'] > 5:
                suggestions.append("Tambahkan kalimat yang lebih elaborate untuk kedalaman konten")
            suggestions.append("Gunakan terminologi yang lebih spesifik untuk audiens target")
        
        else:
            suggestions.append("Readability sudah sesuai target audiens")
        
        return suggestions


# ═══════════════════════════════════════════════════════════════════════════════
# AI CONTENT DETECTOR BYPASS ENGINE
# ═══════════════════════════════════════════════════════════════════════════════

class AIContentBypassEngine:
    """
    Engine untuk bypass AI Content Detectors dengan membuat konten
    yang terlihat lebih human-written.
    
    Techniques:
    1. Sentence structure variation
    2. Vocabulary enrichment
    3. Personality injection
    4. Controlled imperfection
    5. Contextual hooks
    """
    
    # AI detection patterns yang harus dihindari
    DETECTION_PATTERNS = {
        # Overused AI phrases
        "robotic_phrases": [
            "secara keseluruhan",
            "dapat disimpulkan",
            "dalam konteks ini",
            "sejalan dengan",
            "memiliki peran penting",
            "sangat penting untuk",
            "perlu diperhatikan",
            "pada dasarnya",
            "hal ini menunjukkan",
            "yang perlu diperhatikan",
        ],
        
        # Uniform sentence patterns
        "uniform_patterns": [
            r'^[A-Z][a-z]+,\s[A-Z][a-z]+,',  # "Word, Word,"
            r'^[A-Z][a-z]+\s+[A-Z][a-z]+\s+[A-Z][a-z]+,\s',  # Triple word starts
        ],
        
        # Robotic transitions
        "robotic_transitions": [
            "Pertama-tama",
            "Kedua",
            "Ketiga",
            "Keempat",
            "Kelima",
            "Pertama",
            "Kedua",
        ],
        
        # Excessive formalization
        "over_formal": [
            "sehubungan dengan",
            "bermazza",
            "dapatlah",
            "mahsudnya",
        ],
    }
    
    def __init__(self):
        self.bypass_count = 0
    
    def bypass_detection(
        self,
        text: str,
        intensity: str = "medium"  # low, medium, high
    ) -> str:
        """
        Apply AI bypass techniques ke text.
        
        Intensity levels:
        - low: Minor tweaks (good for most content)
        - medium: Noticeable variation (for strict detectors)
        - high: Maximum humanization (for academic/professional)
        """
        
        self.bypass_count += 1
        
        # Step 1: Remove robotic phrases
        text = self._remove_robotic_phrases(text)
        
        # Step 2: Vary sentence structure
        text = self._vary_sentence_structure(text, intensity)
        
        # Step 3: Add personality
        text = self._inject_personality(text, intensity)
        
        # Step 4: Add controlled imperfections
        if intensity in ["medium", "high"]:
            text = self._add_controlled_imperfections(text)
        
        # Step 5: Random human touches
        text = self._add_human_touches(text, intensity)
        
        return text
    
    def _remove_robotic_phrases(self, text: str) -> str:
        """Replace overused AI phrases dengan variation."""
        
        replacements = {
            "secara keseluruhan": random.choice([
                "pada hakikatnya",
                "pada pokoknya",
                "secara garis besar",
                "dalam majoritasnya",
            ]),
            "dapat disimpulkan": random.choice([
                "jika dilihat lebih jauh",
                "dari sini bisa dipahami",
                "berdasarkan observasi",
            ]),
            "dalam konteks ini": random.choice([
                "melihat situasi ini",
                "berkaitan dengan hal ini",
                "pada kondisi tersebut",
            ]),
            "sangat penting untuk": random.choice([
                "penting banget untuk",
                "Jadi一片 penting buat",
                "Ini gak boleh lewatkan kalau mau",
            ]),
            "perlu diperhatikan": random.choice([
                "worth untuk dicatat",
                "mesti jadi perhatian",
                "sebaiknya jangan diabaikan",
            ]),
        }
        
        for phrase, replacement in replacements.items():
            if phrase in text.lower():
                text = re.sub(re.escape(phrase), replacement, text, flags=re.IGNORECASE)
        
        return text
    
    def _vary_sentence_structure(self, text: str, intensity: str) -> str:
        """Vary sentence structure untuk avoid pattern detection."""
        
        sentences = re.split(r'(?<=[.!?])\s+', text)
        varied = []
        
        for i, sentence in enumerate(sentences):
            words = sentence.split()
            
            if len(words) < 4:
                varied.append(sentence)
                continue
            
            # Variation based on position and random chance
            chance = random.random()
            
            if intensity == "high" or (intensity == "medium" and i > 2):
                # Add subordinate clause
                if chance > 0.7 and not sentence.startswith('Jika'):
                    sentence = f"Kalau dipikir {sentence.lower()}"
                elif chance > 0.5 and not sentence.startswith('Meskipun'):
                    sentence = f"Walau begitu, {sentence.lower()}"
            
            # Vary sentence starters
            starters = ["Tapi", "Dan", "Nah", "Loh", "Jadi"]
            first_word = words[0]
            
            if first_word in ["Namun", "Kemudian", "Setelah itu"]:
                if chance > 0.6:
                    new_starter = random.choice(starters)
                    sentence = new_starter + " " + sentence
            
            varied.append(sentence)
        
        return ' '.join(varied)
    
    def _inject_personality(self, text: str, intensity: str) -> str:
        """Tambahkan personality markers."""
        
        personality_markers = [
            ("seru loh", "seru sih"),
            ("gitu loh", "gitu kan"),
            ("kalian tahu", "ngerti gak"),
            ("penting banget", "penting sih sebenernya"),
        ]
        
        # Only inject if intensity medium/high and random chance
        if intensity in ["medium", "high"] and random.random() > 0.5:
            for marker, replacement in personality_markers:
                if marker in text.lower():
                    text = re.sub(
                        re.escape(marker),
                        replacement,
                        text,
                        count=1,
                        flags=re.IGNORECASE
                    )
        
        return text
    
    def _add_controlled_imperfections(self, text: str) -> str:
        """Tambahkan controlled imperfections yang typical human."""
        
        # Common human writing imperfections
        imperfections = [
            # Self-correction patterns
            (r'\b(\w+)\s+dan\s+\1\b', r'\1'),  # "dan dan" → "dan"
            # Informal abbreviations (only in casual content)
            (r'\b(tidak)\b', 'gak'),
            (r'\b(tidak)\b', 'nggak'),
        ]
        
        for pattern, replacement in imperfections:
            if random.random() > 0.7:  # Only 30% chance
                text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
        
        return text
    
    def _add_human_touches(self, text: str, intensity: str) -> str:
        """Tambahkan human touches."""
        
        human_touches = [
            "Yang seru,",
            "Gokil sih,",
            "Auto gitu,",
            "Sipp,",
        ]
        
        if intensity == "high" and random.random() > 0.6:
            sentences = re.split(r'(?<=[.!?])\s+', text)
            if len(sentences) > 3:
                insert_pos = len(sentences) // 2
                sentences.insert(insert_pos, random.choice(human_touches))
                text = ' '.join(sentences)
        
        return text
    
    def check_detection_risk(self, text: str) -> Dict[str, Any]:
        """Check text untuk AI detection risk factors."""
        
        text_lower = text.lower()
        
        risks = {
            "robotic_phrases_found": [],
            "uniform_sentences": 0,
            "detection_score": 0.0,
        }
        
        # Check robotic phrases
        for phrase in self.DETECTION_PATTERNS["robotic_phrases"]:
            if phrase in text_lower:
                risks["robotic_phrases_found"].append(phrase)
        
        # Check uniform sentences
        sentences = re.split(r'[.!?]+', text)
        sentence_lengths = [len(s.split()) for s in sentences if s.strip()]
        
        if sentence_lengths:
            avg_len = sum(sentence_lengths) / len(sentence_lengths)
            variance = sum((sl - avg_len) ** 2 for sl in sentence_lengths) / len(sentence_lengths)
            
            # Low variance = uniform = higher risk
            if variance < 10:
                risks["uniform_sentences"] = len(sentence_lengths)
        
        # Calculate risk score
        risk_score = 0.0
        risk_score += len(risks["robotic_phrases_found"]) * 0.15
        risk_score += risks["uniform_sentences"] * 0.05
        
        risks["detection_score"] = min(1.0, risk_score)
        
        return risks


# ═══════════════════════════════════════════════════════════════════════════════
# INDONESIAN NLP ORCHESTRATOR — MAIN ENGINE
# ═══════════════════════════════════════════════════════════════════════════════

class IndonesianNLPEngine:
    """
    Main orchestrator untuk semua Indonesian NLP operations.
    
    Combines:
    - Keyword Density Optimization
    - Transition Injection
    - Readability Scoring
    - AI Bypass
    
    Usage:
    ═════════════════════════════
    
    engine = IndonesianNLPEngine()
    
    result = engine.process(
        content="Artikel content di sini",
        audience=AudienceType.B2B_PROFESIONAL,
        primary_keyword="digital marketing",
        secondary_keywords=["SEO", "content marketing"],
        options={
            "optimize_keyword": True,
            "inject_transitions": True,
            "bypass_ai": True,
            "target_flesch": 45.0
        }
    )
    
    print(result['optimized_content'])
    print(result['readability_report'])
    """
    
    def __init__(self):
        self.keyword_optimizer = KeywordDensityOptimizer()
        self.transition_engine = IndonesianTransitionEngine()
        self.readability_scorer = IndonesianReadabilityScorer()
        self.ai_bypass = AIContentBypassEngine()
    
    def process(
        self,
        content: str,
        audience: AudienceType,
        primary_keyword: Optional[str] = None,
        secondary_keywords: Optional[List[str]] = None,
        options: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Process content dengan semua optimization steps.
        
        Returns:
        {
            "optimized_content": str,
            "readability_report": {...},
            "keyword_report": {...},
            "ai_bypass_report": {...},
            "stats": {...}
        }
        """
        
        opts = options or {}
        optimized = content
        
        # Step 1: Keyword Optimization
        keyword_report = {}
        if opts.get("optimize_keyword", True) and primary_keyword:
            self.keyword_optimizer.set_primary_keyword(primary_keyword)
            
            if secondary_keywords:
                for kw in secondary_keywords:
                    self.keyword_optimizer.add_secondary_keyword(kw)
            
            optimized = self.keyword_optimizer.optimize_text(
                optimized,
                min_word_count=opts.get("min_words", 300),
                max_keyword_insertions=opts.get("max_keyword_insertions", 8)
            )
            
            keyword_report = {
                "primary_keyword": primary_keyword,
                "primary_density": self.keyword_optimizer.calculate_current_density(
                    optimized, primary_keyword
                ),
                "secondary_keywords": secondary_keywords or [],
            }
        
        # Step 2: Transition Injection
        if opts.get("inject_transitions", True):
            injection_rate = opts.get("transition_rate", 0.3)
            optimized = self.transition_engine.inject_transitions(
                optimized,
                audience,
                injection_rate=injection_rate
            )
        
        # Step 3: Paragraph Transitions
        if opts.get("paragraph_transitions", True):
            paragraphs = optimized.split('\n\n')
            if len(paragraphs) > 1:
                paragraphs = self.transition_engine.create_paragraph_transitions(
                    paragraphs,
                    audience
                )
                optimized = '\n\n'.join(paragraphs)
        
        # Step 4: AI Bypass
        ai_bypass_report = {}
        if opts.get("bypass_ai", True):
            bypass_intensity = opts.get("bypass_intensity", "medium")
            optimized = self.ai_bypass.bypass_detection(
                optimized,
                intensity=bypass_intensity
            )
            
            ai_bypass_report = {
                "bypass_count": self.ai_bypass.bypass_count,
                "detection_risk": self.ai_bypass.check_detection_risk(optimized)
            }
        
        # Step 5: Readability Check & Adjust
        readability_report = self.readability_scorer.analyze_text(optimized)
        target_flesch = opts.get("target_flesch")
        
        if target_flesch:
            current_flesch = readability_report['flesch_score']
            
            # If readability doesn't match target, apply adjustments
            if abs(current_flesch - target_flesch) > 10:
                optimized = self._adjust_readability(
                    optimized,
                    target_flesch,
                    audience
                )
                readability_report = self.readability_scorer.analyze_text(optimized)
        
        # Final Stats
        stats = {
            "original_word_count": len(content.split()),
            "optimized_word_count": len(optimized.split()),
            "word_count_delta": len(optimized.split()) - len(content.split()),
            "audience": audience.value,
            "processing_steps": [
                "keyword_optimization" if opts.get("optimize_keyword") else None,
                "transition_injection" if opts.get("inject_transitions") else None,
                "ai_bypass" if opts.get("bypass_ai") else None,
                "readability_adjustment" if target_flesch else None,
            ]
        }
        
        return {
            "optimized_content": optimized,
            "readability_report": readability_report,
            "keyword_report": keyword_report,
            "ai_bypass_report": ai_bypass_report,
            "stats": stats
        }
    
    def _adjust_readability(
        self,
        text: str,
        target_flesch: float,
        audience: AudienceType
    ) -> str:
        """Adjust text untuk mencapai target flesch score."""
        
        current_flesch = self.readability_scorer.calculate_flesch_score(text)
        
        # Simple adjustments
        if current_flesch < target_flesch:
            # Too difficult - simplify
            # Shorten sentences
            sentences = re.split(r'(?<=[.!?])\s+', text)
            simplified = []
            
            for sent in sentences:
                words = sent.split()
                if len(words) > 25:
                    # Split long sentence
                    midpoint = len(words) // 2
                    simplified.append(' '.join(words[:midpoint]) + '.')
                    simplified.append(' '.join(words[midpoint:]))
                else:
                    simplified.append(sent)
            
            text = ' '.join(simplified)
        
        elif current_flesch > target_flesch:
            # Too simple - elaborate
            sentences = re.split(r'(?<=[.!?])\s+', text)
            elaborated = []
            
            for sent in sentences:
                words = sent.split()
                if len(words) < 8 and random.random() > 0.5:
                    # Add detail to short sentences
                    additions = [
                        "yang perlu dipahami lebih lanjut",
                        "seperti yang sudah dibahas sebelumnya",
                        "sebagaimana terlihat dalam praktiknya",
                    ]
                    sent = sent + " " + random.choice(additions)
                
                elaborated.append(sent)
            
            text = ' '.join(elaborated)
        
        return text
    
    def quick_optimize(
        self,
        content: str,
        audience: AudienceType,
        keyword: str
    ) -> str:
        """Quick optimization untuk speed."""
        
        self.keyword_optimizer.set_primary_keyword(keyword)
        optimized = self.keyword_optimizer.optimize_text(content)
        
        optimized = self.transition_engine.inject_transitions(
            optimized,
            audience,
            injection_rate=0.2
        )
        
        optimized = self.ai_bypass.bypass_detection(
            optimized,
            intensity="medium"
        )
        
        return optimized


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN — DEMO
# ═══════════════════════════════════════════════════════════════════════════════

def demo_indonesian_nlp():
    """Demo: Indonesian NLP & SEO Tuning Engine."""
    
    print("=" * 70)
    print("ILMA v5.0 — HYPER-LOCALIZED INDONESIAN NLP & SEO TUNING")
    print("AI Content Detector Bypass + Readability Optimization")
    print("=" * 70)
    
    engine = IndonesianNLPEngine()
    
    # Sample content
    sample_content = """
Digital marketing telah menjadi komponen penting dalam strategi bisnis modern di Indonesia.
Pertama-tama, penting untuk memahami bahwa digital marketing mencakup berbagai saluran dan platform
yang dapat digunakan untuk menjangkau audiens target. Kedua, perusahaan perlu mengembangkan
strategi yang terukur dan berbasis data untuk memaksimalkan ROI. Ketiga, konsistensi dalam
pelaksanaan dan evaluasi berkala sangat penting untuk kesuksesan jangka panjang.
Secara keseluruhan, digital marketing memberikan peluang besar bagi UMKM Indonesia untuk
bersaing di pasar yang semakin kompetitif.
"""
    
    # Sample SEO-optimized content
    seo_content = """
Digital marketing adalah strategi promosi produk atau layanan menggunakan saluran digital.
Dalam konteks Indonesia, digital marketing telah mengalami pertumbuhan signifikan dalam
beberapa tahun terakhir. Oleh karena itu, perusahaan-perusahaan perlu mengadopsi strategi
ini untuk tetap kompetitif.
"""
    
    # Demo 1: Keyword Density Analysis
    print("\n[1] KEYWORD DENSITY OPTIMIZATION")
    print("-" * 50)
    
    optimizer = KeywordDensityOptimizer()
    optimizer.set_primary_keyword("digital marketing", target_density=0.02)
    optimizer.add_secondary_keyword("strategi bisnis", target_density=0.015)
    optimizer.add_lsi_keyword("promosi online")
    
    kw_report = {
        "primary_keyword": "digital marketing",
        "density": optimizer.calculate_current_density(sample_content, "digital marketing"),
        "target_density": 0.02,
    }
    
    print(f"  Primary Keyword: {kw_report['primary_keyword']}")
    print(f"  Current Density: {kw_report['density']:.3f} ({kw_report['density']*100:.1f}%)")
    print(f"  Target Density: {kw_report['target_density']:.3f} ({kw_report['target_density']*100:.1f}%)")
    print(f"  Status: {'OPTIMAL' if 0.01 <= kw_report['density'] <= 0.03 else 'NEEDS ADJUSTMENT'}")
    
    # Demo 2: Audience Detection & Transition Injection
    print("\n\n[2] AUDIENCE-BASED TRANSITION INJECTION")
    print("-" * 50)
    
    audiences = [
        AudienceType.B2B_PROFESIONAL,
        AudienceType.B2C_KASUAL,
        AudienceType.GEN_Z,
    ]
    
    for audience in audiences:
        transition_engine = IndonesianTransitionEngine()
        
        print(f"\n  Audience: {audience.value}")
        transitions = transition_engine.get_transitions_for_audience(audience)[:3]
        print(f"    Sample transitions: {transitions}")
        
        # Simulate injection
        result_text = transition_engine.inject_transitions(
            seo_content,
            audience,
            injection_rate=0.4
        )
        print(f"    Sample output: {result_text[:100]}...")
    
    # Demo 3: Readability Scoring
    print("\n\n[3] INDONESIAN READABILITY SCORING")
    print("-" * 50)
    
    scorer = IndonesianReadabilityScorer()
    
    test_texts = [
        ("B2B Formal", """
Berdasarkan analisis komprehensif mengenai perkembangan industri digital di Indonesia,
dapat disimpulkan bahwa strategi pemasaran berbasis teknologi informasi memberikan
dampak signifikan terhadap pertumbuhan bisnis perusahaan multinasional yang beroperasi
di wilayah Asia Tenggara.
        """),
        ("B2C Casual", """
Hey guys! Jadi gitu, digital marketing tuh penting banget lho buat bisnis kalian.
Kalian tahu gak sih, sekarang almost semua orang di Indonesia udahonline terus?
Jadi kalau bisnis kalian gak ada di digital, ya ruginya gede banget!
        """),
        ("Gen-Z", """
Nih ya, gue kasih tau deh. Digital marketing tuh auto penting banget
buat kids zaman sekarang. Stay terus di online, auto dapet customers
banyak banget deh. Gokil kan?
        """),
    ]
    
    for label, text in test_texts:
        analysis = scorer.analyze_text(text)
        print(f"\n  {label}:")
        print(f"    Flesch Score: {analysis['flesch_score']:.1f}")
        print(f"    Grade Level: {analysis['grade_level']}")
        print(f"    Avg Sentence: {analysis['avg_sentence_length']:.1f} words")
        print(f"    Total Words: {analysis['total_words']}")
    
    # Demo 4: AI Detection Bypass
    print("\n\n[4] AI CONTENT DETECTOR BYPASS")
    print("-" * 50)
    
    ai_bypass = AIContentBypassEngine()
    
    robotic_text = """
Secara keseluruhan, dapat disimpulkan bahwa digital marketing memiliki peran penting
dalam konteks bisnis modern. Perlu diperhatikan bahwa dalam mengembangkan strategi
digital marketing, perusahaan harus mempertimbangkan berbagai faktor secara komprehensif.
Hal ini menunjukkan bahwa pendekatan yang terstruktur dan sistematis sangat penting
untuk kesuksesan jangka panjang.
    """
    
    print(f"\n  Original (High AI Detection Risk):")
    print(f"  {robotic_text[:150]}...")
    
    bypassed = ai_bypass.bypass_detection(robotic_text, intensity="high")
    
    print(f"\n  After Bypass (Low AI Detection Risk):")
    print(f"  {bypassed[:150]}...")
    
    risk_original = ai_bypass.check_detection_risk(robotic_text)
    risk_bypassed = ai_bypass.check_detection_risk(bypassed)
    
    print(f"\n  Detection Risk Scores:")
    print(f"    Original: {risk_original['detection_score']:.2f}")
    print(f"    Bypassed: {risk_bypassed['detection_score']:.2f}")
    
    # Demo 5: Full Pipeline
    print("\n\n[5] FULL NLP PIPELINE")
    print("-" * 50)
    
    full_content = """
Digital marketing Indonesia telah berkembang pesat dalam lima tahun terakhir.
Perusahaan-perusahaan besar dan UMKM alike telah mengadopsi strategi digital
untuk menjangkau konsumen yang semakin mobile-first. Berdasarkan data terbaru,
pengguna internet Indonesia mencapai 200 juta jiwa dengan penetrasi smartphone
mencapai 70%. Oleh karena itu, peluang dalam digital marketing sangat besar
bagi bisnis yang ingin expand secara online. Secara keseluruhan, implementasi
digital marketing yang efektif dapat meningkatkan revenue perusahaan hingga 30%
dalam waktu enam bulan.
    """
    
    result = engine.process(
        content=full_content,
        audience=AudienceType.B2C_KASUAL,
        primary_keyword="digital marketing Indonesia",
        secondary_keywords=["UMKM", "strategi digital"],
        options={
            "optimize_keyword": True,
            "inject_transitions": True,
            "bypass_ai": True,
            "target_flesch": 62.0,
            "transition_rate": 0.3,
            "bypass_intensity": "medium"
        }
    )
    
    print(f"\n  Original Word Count: {result['stats']['original_word_count']}")
    print(f"  Optimized Word Count: {result['stats']['optimized_word_count']}")
    print(f"  Delta: +{result['stats']['word_count_delta']} words")
    
    print(f"\n  Readability:")
    print(f"    Flesch Score: {result['readability_report']['flesch_score']:.1f}")
    print(f"    Grade Level: {result['readability_report']['grade_level']}")
    
    if result['keyword_report']:
        print(f"\n  Keyword Optimization:")
        print(f"    Primary Density: {result['keyword_report']['primary_density']:.3f}")
    
    print(f"\n  Processing Steps: {[s for s in result['stats']['processing_steps'] if s]}")
    
    print("\n" + "=" * 70)
    print("INDONESIAN NLP ENGINE DEMO COMPLETE")
    print("=" * 70)

if __name__ == "__main__":
    demo_indonesian_nlp()
