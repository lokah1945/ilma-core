#!/usr/bin/env python3
"""ILMA Knowledge Ingestion Engine v1.0

Ingestion pipeline for knowledge sources:
- Document parsing (markdown, txt, json, html)
- Source classification
- Metadata extraction
- Chunking strategies
- Integration with KnowledgeGraphOS

This module handles the ETL (Extract-Transform-Load) of external knowledge
into ILMA's knowledge graph.
"""

from __future__ import annotations

import hashlib
import logging
import re
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

ILMA_ROOT = Path("/root/.hermes/profiles/ilma")


class SourceType(Enum):
    MARKDOWN = "markdown"
    TEXT = "text"
    JSON = "json"
    HTML = "html"
    URL = "url"
    CODE = "code"
    UNKNOWN = "unknown"


class ChunkStrategy(Enum):
    FIXED_SIZE = "fixed_size"
    PARAGRAPH = "paragraph"
    SENTENCE = "sentence"
    SEMANTIC = "semantic"


@dataclass
class IngestedChunk:
    chunk_id: str
    content: str
    source_type: SourceType
    source_path: str
    chunk_index: int
    total_chunks: int
    metadata: Dict[str, Any] = field(default_factory=dict)
    ingested_at: datetime = field(default_factory=datetime.now)


@dataclass
class IngestionResult:
    source_path: str
    source_type: SourceType
    total_chunks: int
    chunks: List[IngestedChunk]
    duration_ms: float
    success: bool
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class KnowledgeIngestionEngine:
    """Ingestion pipeline for external knowledge sources."""

    def __init__(
        self,
        chunk_size: int = 512,
        chunk_overlap: int = 64,
        chunk_strategy: ChunkStrategy = ChunkStrategy.PARAGRAPH,
    ):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.chunk_strategy = chunk_strategy
        self._stats = {"documents_processed": 0, "chunks_created": 0}

    def ingest_file(self, file_path: str) -> IngestionResult:
        """Ingest a single file."""
        start = time.time()
        path = Path(file_path)

        if not path.exists():
            return IngestionResult(
                source_path=str(path),
                source_type=SourceType.UNKNOWN,
                total_chunks=0,
                chunks=[],
                duration_ms=0,
                success=False,
                error="File not found",
            )

        source_type = self._detect_source_type(path)
        content = self._extract_content(path, source_type)

        if content is None:
            return IngestionResult(
                source_path=str(path),
                source_type=source_type,
                total_chunks=0,
                chunks=[],
                duration_ms=0,
                success=False,
                error="Failed to extract content",
            )

        chunks = self._chunk_content(content, str(path), source_type)
        self._stats["documents_processed"] += 1
        self._stats["chunks_created"] += len(chunks)

        return IngestionResult(
            source_path=str(path),
            source_type=source_type,
            total_chunks=len(chunks),
            chunks=chunks,
            duration_ms=(time.time() - start) * 1000,
            success=True,
        )

    def ingest_url(self, url: str) -> IngestionResult:
        """Ingest content from a URL."""
        # Placeholder - requires httpx or similar
        return IngestionResult(
            source_path=url,
            source_type=SourceType.URL,
            total_chunks=0,
            chunks=[],
            duration_ms=0,
            success=False,
            error="URL ingestion not yet implemented",
        )

    def _detect_source_type(self, path: Path) -> SourceType:
        ext = path.suffix.lower()
        mapping = {
            ".md": SourceType.MARKDOWN,
            ".markdown": SourceType.MARKDOWN,
            ".txt": SourceType.TEXT,
            ".json": SourceType.JSON,
            ".html": SourceType.HTML,
            ".htm": SourceType.HTML,
            ".py": SourceType.CODE,
            ".js": SourceType.CODE,
            ".sh": SourceType.CODE,
            ".yaml": SourceType.CODE,
            ".yml": SourceType.CODE,
        }
        return mapping.get(ext, SourceType.UNKNOWN)

    def _extract_content(self, path: Path, source_type: SourceType) -> Optional[str]:
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                return f.read()
        except Exception as e:
            logger.error(f"Failed to extract content from {path}: {e}")
            return None

    def _chunk_content(
        self, content: str, source_path: str, source_type: SourceType
    ) -> List[IngestedChunk]:
        if self.chunk_strategy == ChunkStrategy.PARAGRAPH:
            # Split by double newlines (paragraphs)
            paragraphs = re.split(r"\n\s*\n", content.strip())
        elif self.chunk_strategy == ChunkStrategy.SENTENCE:
            # Split by sentence boundaries
            sentences = re.split(r"(?<=[.!?])\s+", content)
            paragraphs = [" ".join(sentences[i:i+5]) for i in range(0, len(sentences), 5)]
        else:
            # Fixed size chunking
            paragraphs = [content[i:i+self.chunk_size] for i in range(0, len(content), self.chunk_size - self.chunk_overlap)]

        paragraphs = [p.strip() for p in paragraphs if p.strip()]
        chunks = []
        for i, text in enumerate(paragraphs):
            chunk_id = hashlib.md5(f"{source_path}:{i}:{text[:50]}".encode()).hexdigest()[:16]
            chunk = IngestedChunk(
                chunk_id=chunk_id,
                content=text,
                source_type=source_type,
                source_path=source_path,
                chunk_index=i,
                total_chunks=len(paragraphs),
                metadata={"strategy": self.chunk_strategy.value},
            )
            chunks.append(chunk)

        return chunks

    def get_stats(self) -> Dict[str, Any]:
        """Get ingestion statistics."""
        return dict(self._stats)


# === SINGLETON ACCESSOR ===
_global_kie_instance = None

def get_knowledge_ingestion_engine(**kwargs) -> KnowledgeIngestionEngine:
    """Get singleton KnowledgeIngestionEngine instance."""
    global _global_kie_instance
    if _global_kie_instance is None:
        _global_kie_instance = KnowledgeIngestionEngine(**kwargs)
    return _global_kie_instance
