# execute_code Tool Pitfalls

## execute_code truncates to 1 line (CRITICAL)

**Symptom:** Multi-line Python scripts in `execute_code` produce single-line or empty output with no error shown.

**Root cause:** `execute_code` tool silently truncates output. Any code with multi-line blocks, list comprehensions, or complex formatting gets truncated to 1 line.

**Affected patterns:**
```python
# This works (single line)
import json; print(json.dumps({'a':1}))

# This FAILS (multi-line)
import json
data = json.load(open('file.json'))
print(len(data))

# This FAILS (complex inline)
results = [x for x in items if x.get('count', 0) > 5]
print(len(results))
```

**Workaround:** Use `terminal` tool with Python scripts instead.

```bash
# WRONG: execute_code with multi-line Python
python3 -c "
import json
print('test')
"

# CORRECT: terminal with heredoc
cat << 'EOF' | python3
import json
print('test')
EOF
```

## execute_code with import chains

**Symptom:** `import module; import module2; x = module.func()` sometimes works but complex chains fail silently.

**Fix:** Split into separate `terminal` calls, or use script file.

## always use terminal for database operations

For SQLite/Python database work, always use terminal:
```bash
python3 << 'EOF'
import sqlite3
# database operations
EOF
```

Not execute_code for anything beyond trivial one-liners.