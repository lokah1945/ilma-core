# Subagent Lifecycle Management (2026-05-13)

## Timeout Handling

When a subagent times out (600s default), it has usually produced partial work. Handle gracefully:

```python
result = delegate_task(goal, role="leaf", toolsets=[...])
# result may be None, partial, or complete
if result is None or not result.get("summary"):
    # Subagent timed out — check what was produced anyway
    # File system is still the ground truth
    pass
```

**Pattern:** Always check the file system for work product even if the subagent result is empty/timed-out. The subagent may have created files before timing out.

---

## Partial Completion Recovery

1. **Check file system first** — files created by timed-out subagent are the real output
2. **Check last modified timestamps** — identify which files the subagent was working on
3. **Verify file sizes** — meaningful work produces non-trivial files (500+ bytes)
4. **Count compilation errors** — TypeScript errors and Python tracebacks are visible in build output

---

## Subagent Work Quality Verification

```bash
# Verify subagent output quality
find /path/to/workspace -name "*.tsx" -newer /tmp/start_time -exec wc -l {} \; | sort -n

# Check for meaningful content (not stubs)
find /path/to/workspace -name "*.tsx" -size +500c | wc -l

# Count TypeScript build errors
cd /path/to/frontend && npm run build 2>&1 | grep "error TS" | wc -l
```

---

## When Subagent Produces Bad Output

Common subagent failures:
- **Duplicate imports at end of file** — check for imports placed after component function body
- **Missing `style` prop support on Lucide icons** — use `className` text color utilities instead
- **Badge variant type strictness** — cast dynamic string values to union type
- **Incomplete component implementation** — empty array returns, stub data, missing handlers

**Recovery pattern:**
1. Identify the specific error pattern
2. Write a targeted fix (patch/replace)
3. Verify build passes
4. Document the pattern in the relevant skill

---

## Background Process Management

Subagent may start background processes that outlive the subagent:

```python
# Start background process
terminal(background=true, command="cd /path && npm run dev")

# Check if it's running
sleep 3 && curl -s http://localhost:3000 > /dev/null && echo "UP" || echo "DOWN"

# Kill if needed
terminal(command="pkill -f 'vite'")
```

---

## Related Fixes

### TypeScript Build Fixes for React Frontend

When Badge component rejects `style={{ color: ... }}` prop:
```typescript
// BAD
<Badge label="Active" variant="success" style={{ color: 'var(--accent-green)' }} />

// GOOD
<Badge label="Active" variant="success" />
```

When Badge variant type doesn't match union:
```typescript
// BAD - string not assignable
variant={statusColors[c.status] || 'default'}

// GOOD - cast to union type
variant={(statusColors[c.status] || 'default') as 'success' | 'warning' | 'danger' | 'info' | 'purple' | 'default'}
```

When duplicate React imports appear at end of file:
```typescript
// Remove line at end of file like:
// import { useEffect, useState, useMemo } from 'react';
```