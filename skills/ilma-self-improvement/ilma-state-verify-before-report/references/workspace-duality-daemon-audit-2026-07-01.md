# Workspace Duality in Daemon Repos — wrapper-nvidia forensic (2026-07-01)

When auditing a Node daemon backed by `src/index.js` whose repo root also
contains `index.js`/`key_pool.js` of older dates, this is the minimum
audit that prevented ~30 minutes of confusion in the original session.

## 1. Find what runtime actually loads (NOT what `ls` shows)

```bash
PID=$(pgrep -f "node.*src/index.js" | head -1)
echo "pid=$PID"
cat /proc/$PID/cmdline | tr '\0' ' '; echo
echo "cwd=$(readlink -f /proc/$PID/cwd)"
echo "port=$(grep -E '^(LISTEN_)?PORT=' /proc/$PID/environ | head -1)"
```

The daemon's CWD and argv are ground truth. The repo file tree can lie if
older files exist alongside canonical ones.

## 2. Detect root-shadow artifacts

```bash
for f in index.js key_pool.js package.json; do
  if [ -f "$f" ] && [ -f "src/$f" ]; then
    echo "$f:"
    ls -la "$f" "src/$f"
    md5sum "$f" "src/$f"
    echo
  fi
done

git ls-files | grep -E "^(index|key_pool)\.js$" \
  || echo "ROOT LEVEL FILES UNTRACKED → likely legacy/backup copies"
```

If `git ls-files` shows them as untracked and their mtime/hash differs from
canonical `src/`, treat them as **decorative archaeology**, NOT as files
to be edited.

## 3. Establish canonical commit BEFORE any patch

```bash
git log --oneline -5
git status -s
git diff --stat
```

Take the HEAD commit hash as `BASELINE_COMMIT` and store it. Every future
`git checkout` for rollback uses this hash.

## 4. Safe rollback recipe (paranoia-grade)

```bash
mkdir -p .pre-phaseN-backups
cp src/index.js src/key_pool.js .pre-phaseN-backups/
md5sum src/index.js src/key_pool.js > .pre-phaseN-backups/MD5.PRE

# Later, collapse to baseline:
git checkout <BASELINE_COMMIT> -- src/index.js src/key_pool.js
node -c src/index.js && node -c src/key_pool.js

# Move (not delete) untracked root artifacts out of the way so they
# don't get confused with canonical again:
mkdir -p .archive/root-artifacts
mv index.js key_pool.js .archive/root-artifacts/   # only if you're sure
```

## 5. Working-app lookup pattern (when you only know behavior)

For any number of node processes on a busy box:

```bash
for pid in $(pgrep -f node 2>/dev/null); do
  port=$(grep -E '^(LISTEN_)?PORT=' /proc/$pid/environ 2>/dev/null | head -1)
  cwd=$(readlink -f /proc/$pid/cwd 2>/dev/null)
  cmd=$(cat /proc/$pid/cmdline 2>/dev/null | tr '\0' ' ')
  echo "$pid    cwd=$cwd    port=$port    cmd=$cmd"
done
```

This bypasses both install-dir guessing and port guessing and systemd-unit
guessing — all three of which failed in the original audit.

## What this caught in the original session

| Wrong assumption | Actual value |
|------------------|--------------|
| cwd = `/opt/wrapper-nvidia` | `/root/wrapper/nvidia` |
| port = `8080` | `9100` |
| systemd unit = `wrapper.service` | none (orphan, PPID=1) |
| tracking = `./index.js` | `src/index.js` |

After this audit ran (took ~60s), every subsequent read/write to the
right files succeeded on first try. The cost of skipping this audit was
multiple "file not found" and "connect refused" errors, each followed by
2-3 minutes of backtracking.
