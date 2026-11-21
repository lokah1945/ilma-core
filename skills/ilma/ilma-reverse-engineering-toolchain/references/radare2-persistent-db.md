# radare2 Persistent Database Workflow

## Why Persistent DB?

By default, radare2 analysis runs in memory and is lost when the session ends. The `-d` flag saves analysis to a SQLite database, allowing resume across sessions.

## Basic Commands

```bash
# Create new analysis DB (analyzes all: -A = aaa)
r2 -d analysis.r2db -A /path/to/binary

# Resume existing analysis
r2 -d analysis.r2db -

# Quick commands inside r2:
# Pd @ main      # disassemble main function
# afl            # list all functions
# aflq           # list functions (quiet, just names)
# pdf @ sym.main # disassemble specific function
# V              # visual mode (interactive)
# q              # quit
```

## Automation (Non-Interactive)

```bash
# Run commands non-interactively
r2 -d analysis.r2db -c "aaa; aflj" /path/to/binary > functions.json

# Export specific analysis
r2 -d analysis.r2db -c "pdfj @ main" /path/to/binary > main_func.json

# Search for strings
r2 -d analysis.r2db -c "izj" /path/to/binary > strings.json
```

## JSON Output for Agent Consumption

```bash
# All functions with metadata
r2 -d analysis.r2db -c "aflj" binary

# Imports
r2 -d analysis.r2db -c "ij" binary

# Sections
r2 -d analysis.r2db -c "iSj" binary

# Relocations
r2 -d analysis.r2db -c "irj" binary
```

## Python Wrapper

```python
import subprocess, json

def r2_analyze(binary, db_path=None):
    if not db_path:
        db_path = f"/tmp/{os.path.basename(binary)}.r2db"
    
    # Ensure DB exists with full analysis
    subprocess.run(["r2", "-d", db_path, "-A", binary], capture_output=True)
    
    # Extract functions
    result = subprocess.run(
        ["r2", "-d", db_path, "-c", "aflj", binary],
        capture_output=True, text=True
    )
    return json.loads(result.stdout)

def r2_decompile_func(binary, func_name, db_path=None):
    if not db_path:
        db_path = f"/tmp/{os.path.basename(binary)}.r2db"
    result = subprocess.run(
        ["r2", "-d", db_path, "-c", f"pdfj @ {func_name}", binary],
        capture_output=True, text=True
    )
    return json.loads(result.stdout)
```

## Version Compatibility Note

Database format may change between radare2 major versions. Current: v6.1.5.

```bash
# Check version
radare2 -v

# If upgrading, export critical findings first:
r2 -d old.r2db -c "aflj" binary > functions_backup.json
```

## Common Flags

| Flag | Meaning |
|------|---------|
| `-d` | Use database (persistent) |
| `-A` | Run `aaa` (analyze all) on load |
| `-c` | Run commands non-interactively |
| `-q` | Quiet mode |
| `-`  | Open database without binary (resume) |

---

*Reference for ilma-reverse-engineering-toolchain skill*