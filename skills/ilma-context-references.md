---
name: ilma-context-references
description: Hermes @-syntax for inline file/folder/diff/git/url injection. Inject specific file sections, directory trees, git changes, and web content directly into messages. SSS Tier — Core Hermes feature.
version: 1.0.0
category: core
platforms:
  - linux
  - macos
  - windows
metadata:
  hermes:
    tags: [context, files, git, injection, references]
    category: core
    config:
      context_refs_enabled:
        key: context_refs_enabled
        description: Enable/disable @-syntax context references
        default: true
---

# ILMA Context References — @-syntax Inline Injection

## Overview

Context References adalah fitur Hermes untuk injecting content secara inline menggunakan `@` syntax. Ini memungkinkan ILMA membaca file, folder, git diff, commits, dan web content tanpa harus memanggil tool terpisah.

## Supported Syntax

| Syntax | Description | Example |
|--------|-------------|---------|
| `@file:path/to/file.py` | Inject file contents | `@file:src/main.py` |
| `@file:path/to/file.py:10-25` | Inject specific line range (1-indexed, inclusive) | `@file:src/main.py:42` atau `10-25` |
| `@folder:path/to/dir` | Directory tree listing with metadata | `@folder:src/components` |
| `@diff` | Git unstaged working tree changes | `@diff` |
| `@staged` | Git staged changes (`git diff --staged`) | `@staged` |
| `@git:5` | Last N commits with patches (max 10) | `@git:5` |
| `@url:https://example.com` | Fetch and inject web page content | `@url:https://arxiv.org/abs/2301.00001` |

## Usage Examples

```text
Review @file:src/main.py and suggest improvements

What changed? @diff

Compare @file:old_config.yaml and @file:new_config.yaml

What's in @folder:src/components?

Summarize this article @url:https://arxiv.org/abs/2301.00001

Check @file:main.py, and also @file:test.py.

Show me lines 50-80 of @file:src/auth.py:50-80
```

## Implementation (ILMA Native)

Since ILMA doesn't have native Hermes @-syntax, implement as a reasoning pattern:

### Pattern 1 — File Reference
```
When user says "@file:path/to/file", do:
1. read_file(path, offset, limit) for ranges
2. Return content in structured format
3. If no range specified, read full file (up to context limit)
```

### Pattern 2 — Folder Reference
```
When user says "@folder:path/to/dir", do:
1. terminal(f"find {dir} -type f -maxdepth 3 | sort")
2. terminal(f"ls -la {dir}")
3. Return directory tree with file sizes and modification dates
```

### Pattern 3 — Git Diff
```
When user says "@diff", do:
1. terminal("git diff --stat")
2. terminal("git diff")
3. Return diff output

When user says "@staged", do:
1. terminal("git diff --staged --stat")
2. terminal("git diff --staged")
3. Return staged diff output
```

### Pattern 4 — Git Commits
```
When user says "@git:N", do:
1. terminal(f"git log -n {N} --patch")
2. Clamp N to range [1, 10]
3. Return commit history with patches
```

### Pattern 5 — URL Fetch
```
When user says "@url:https://...", do:
1. web_extract(url) — returns markdown
2. If PDF URL, use PDF extraction
3. Return summarized content (LLM-summarize if >5000 chars)
```

## Size Limits

| Threshold | Value | Behavior |
|-----------|-------|----------|
| Soft limit | 25% of context length | Warning appended, expansion proceeds |
| Hard limit | 50% of context length | Expansion refused, original message returned |
| Folder entries | 200 files max | Excess entries replaced with `- ...` |
| Git commits | 10 max | @git:N clamped to [1, 10] |

## Security — Sensitive Path Blocking

These paths are ALWAYS blocked from @file references:

```text
~/.ssh/id_rsa, ~/.ssh/id_ed25519, ~/.ssh/authorized_keys, ~/.ssh/config
~/.bashrc, ~/.zshrc, ~/.profile, ~/.bash_profile, ~/.zprofile
~/.netrc, ~/.pgpass, ~/.npmrc, ~/.pypirc
$HERMES_HOME/.env
~/.ssh/, ~/.aws/, ~/.gnupg/, ~/.kube/
$HERMES_HOME/skills/.hub/
```

## Path Traversal Protection

- All paths resolved relative to working directory
- Paths resolving outside workspace root → rejected
- Only text files processed (binary → rejected with warning)
- Known text extensions bypass MIME detection: .py, .md, .json, .yaml, .toml, .js, .ts

## CLI Tab Completion (for future reference)

When ILMA has CLI mode:
- `@` shows all reference types
- `@file:` and `@folder:` trigger filesystem path completion
- Bare `@` + partial text → matching files/folders

## Interaction with Context Compression

- Large file contents via @file: contribute to context usage
- If conversation compressed, file content is summarized (not preserved verbatim)
- For large files, use line ranges: `@file:main.py:100-200`

## Common Workflows

### Code Review Workflow
```
User: "Review @diff and check for security issues"
ILMA: 
  1. terminal("git diff") 
  2. Analyze diff for security issues
  3. Report findings
```

### Debug with Context
```
User: "This test is failing. Here's the test @file:tests/test_auth.py
and the implementation @file:src/auth.py:50-80"
ILMA:
  1. read_file("tests/test_auth.py")
  2. read_file("src/auth.py", offset=50, limit=31)
  3. Analyze and debug
```

### Project Exploration
```
User: "What does this project do? @folder:src @file:README.md"
ILMA:
  1. terminal("find src -type f | head -50")
  2. read_file("README.md")
  3. Summarize project
```

### Research
```
User: "Compare the approaches in @url:https://arxiv.org/abs/2301.00001
and @url:https://arxiv.org/abs/2301.00002"
ILMA:
  1. web_extract both URLs
  2. Compare and synthesize
```

## Error Handling

| Condition | Behavior |
|-----------|----------|
| File not found | Warning: "file not found" |
| Binary file | Warning: "binary files are not supported" |
| Folder not found | Warning: "folder not found" |
| Git command fails | Warning with git stderr |
| URL returns no content | Warning: "no content extracted" |
| Sensitive path | Warning: "path is a sensitive credential file" |
| Path outside workspace | Warning: "path is outside the allowed workspace" |

## Auto-Trigger

Load this skill when:
- User mentions `@file:`, `@folder:`, `@diff`, `@staged`, `@git:`, `@url:`
- User asks to "compare files", "review git changes", "show project structure"
- User references specific line numbers in a file

## Future Integration

When ILMA has native @-syntax support:
1. Register context reference parser in tool registry
2. Implement priority: file > folder > git > url
3. Add security scanning for each reference
4. Respect size limits and context compression

---

*Hermes v0.13.0 — Context References feature*
*Integrated into ILMA v3.3*