---
name: ilma-memory-providers
description: Hermes Memory Providers — 8 external memory backends (Honcho, OpenViking, Mem0, Hindsight, Holographic, RetainDB, ByteRover, Supermemory) via plugin architecture. SSS Tier.
version: 1.0.0
category: core
platforms:
  - linux
  - macos
metadata:
  hermes:
    tags: [memory, providers, plugins, persistent, external]
    category: core
---

# ILMA Memory Providers — External Memory Backends

## Overview

Hermes supports 8 external memory providers via a plugin architecture, beyond the built-in two-file memory system (MEMORY.md + USER.md).

| Provider | Type | Description |
|----------|------|-------------|
| Honcho | Session-based | Session-bound conversation memory |
| OpenViking | Open-source | Open-source memory solution |
| Mem0 | Managed | Production-grade memory infrastructure |
| Hindsight | Session-based | Session-based chat history |
| Holographic | Experimental | Distributed memory patterns |
| RetainDB | Database | SQL-backed persistent memory |
| ByteRover | Cloud | Cloud-native memory sync |
| Supermarket | Open | Community memory marketplace |

---

## Why External Providers?

Built-in memory is simple but limited:
- **2KB limits** — can't store large context
- **Single-file** — no search, no structured queries
- **Manual** — no automatic learning from conversations

External providers offer:
- **Unlimited storage** — no character limits
- **Semantic search** — find relevant past context
- **Automatic learning** — extract patterns from conversations
- **Multi-device sync** — access memory from anywhere
- **Structured data** — query memory like a database

---

## Plugin Architecture

Memory providers are loaded as plugins:

```
~/.hermes/plugins/
└── memory/
    ├── honcho/
    │   ├── __init__.py
    │   ├── honcho.py
    │   └── requirements.txt
    ├── mem0/
    │   └── ...
    └── ...
```

### Installing a Provider

```bash
# Via hermes setup
hermes memory add honcho

# Or manually
pip install hermes-memory-honcho
```

### Configuration

Each provider has its own configuration in `config.yaml`:

```yaml
# Honcho
memory:
  provider: honcho
  honcho:
    api_key: ${HONCHO_API_KEY}
    endpoint: https://api.honcho.ai

# Mem0
memory:
  provider: mem0
  mem0:
    api_key: ${MEM0_API_KEY}
    user_id: ${USER_ID}

# OpenViking (self-hosted)
memory:
  provider: openviking
  openviking:
    base_url: http://localhost:8080
    api_key: ${OPENViking_API_KEY}
```

---

## Usage Patterns

### Semantic Search

```python
# With external memory provider
result = await memory.search("what did we discuss about authentication?")
# Returns relevant past conversations with similarity scores
```

### Structured Queries

```python
# Query memory like a database
results = await memory.query({
    "topic": "security",
    "date_range": "2026-01-01 to 2026-05-01",
    "limit": 10
})
```

### Memory Learning

```python
# Provider automatically extracts and stores important facts
await memory.learn_from(conversation)
# Extracts entities, patterns, preferences
```

### Context Injection

```python
# Inject relevant memory before agent processing
context = await memory.get_relevant_context(current_task)
# context = "User prefers Python. Last project was Flask API..."
```

---

## Comparison with Built-in Memory

| Feature | Built-in | Honcho | Mem0 | OpenViking |
|---------|----------|--------|------|------------|
| Storage | 2KB file | Cloud | Cloud | Self-hosted |
| Search | Manual | Semantic | Semantic | Semantic |
| Cost | Free | Paid | Paid | Free |
| Setup | None | API key | API key | Self-host |
| Latency | Instant | API call | API call | Local |
| Privacy | 100% local | Cloud | Cloud | 100% local |

---

## Recommended Providers for ILMA

| Use Case | Provider | Reason |
|----------|----------|--------|
| Maximum privacy | OpenViking | Self-hosted, 100% local |
| Production | Mem0 | Managed, reliable, scalable |
| Budget | Honcho | Good free tier |
| Experimentation | Holographic | Novel patterns |

---

## Integration with ILMA

For ILMA to use external providers:

```python
# ilma_memory_manager.py
from typing import Optional

class MemoryManager:
    def __init__(self, provider: str = "builtin"):
        self.provider = provider
        self.client = self._init_client()
    
    async def store(self, key: str, value: dict):
        """Store memory entry."""
        if self.provider == "builtin":
            # Use built-in memory tool
            pass
        else:
            # Use external provider API
            await self.client.store(key, value)
    
    async def search(self, query: str, limit: int = 5):
        """Semantic search over memory."""
        if self.provider == "builtin":
            # Fall back to session_search
            pass
        else:
            return await self.client.search(query, limit)
    
    async def get_context(self, task: str):
        """Get relevant context for current task."""
        # Search memory for relevant past context
        results = await self.search(task)
        return self._format_context(results)
```

---

## Auto-Trigger

Load this skill when:
- User mentions "memory providers", "external memory", "semantic search"
- User wants to "search past conversations", "find previous work"
- User asks about "mem0", "honcho", "openviking", "hindsight"
- Current memory is insufficient (2KB limit reached)

---

*Hermes v0.13.0 — Memory Providers feature*
*Integrated into ILMA v3.3*