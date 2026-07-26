# Reference — `vps_project.json` (and similar SOT-infra JSON) Surgical Update Recipe

Last validated: 2026-06-20.
Used to refresh `/root/credential/vps_project.json` from v1.1 → v1.2 with port corrections (3000→3201, 1337→3200, 3001→3100) and `pm2_name` rename (`yapsi-website` → `nextjs`) on the FullStack VPS section.

## The recipe — 5 steps, no skip

### 1. Backup (timestamped, mode-preserving)
```bash
cd /root/credential
TS=$(date +%Y%m%d_%H%M%S)
cp vps_project.json "vps_project.json.backup_${TS}_pre-<description>"
ls -la vps_project.json.backup_*
```
Keep at least one backup per `last_modified_week`. Do NOT gzip — diff-debugging needs plaintext.

### 2. Read the WHOLE file before any patch
`cat <file>` — not `head`/`tail`. You must see the full scope to avoid unique-string collisions in patch old_string matching. JSON files with deeply nested keys (`projects.yapsi-website.services...`) often have repeated block shapes.

### 3. Plan: list every field as a row in your head before editing
| Field | Old | New | Evidence |
|---|---|---|---|
| `projects.yapsi-website.services.main_website.port` | 3000 | 3201 | `pm2 list nextjs` + curl HTTP 200 |
| `...main_website.pm2_name` | yapsi-website | nextjs | `pm2 list` shows `id=1 name=nextjs` |
| `_meta.version` | 1.1 | 1.2 | minor bump for port-update |
| `_meta.last_updated` | 2026-04-15 | today | reflect audit |

Skip any field lacking **direct runtime evidence** — "I think this is the same value" is a fabrication risk.

### 4. Apply patches one nested block at a time
Each `{"services": {...}}` block should be one patch operation. Do not use `replace_all` on JSON — it will catch unintended siblings. Use `replace` with enough surrounding context for uniqueness.

### 5. Verify
```bash
python3 -m json.tool <file> > /tmp/parsed.json && echo "valid JSON"
diff <backup> <file> | grep "^<\|^>" | wc -l   # rough diff size
git diff --stat <file>                          # if in a tracked repo
```

## What NOT to do

- **Don't overwrite `vps_project.json` from memory.** I almost did this on first attempt; the `vps_project.json` had been silently updated for FullStack VPS (`pm2_name` rename, port reassignments) and my memory was stale by 2 months.
- **Don't `json.dump` from a Python rewrite of the whole file** unless you've diffed the new JSON line-by-line against the backup. Even trivial rewrites change key ordering and lose original comments — losing git-blame provenance.
- **Don't `git commit` infra JSON alongside `auth.json` token rotations unless the user explicitly batched them.** Mixed commits force a "all 4 together or none" decision that is hard to reverse if one file needs to revert. Today Bos explicitly chose to batch, so this is a permission-set exception, not a default.
- **Don't push the local file directly; mirror the structure under `/root/.hermes/profiles/ilma/` (or the relevant tracked repo) and push from there.** The credential dir (`/root/credential/`) is outside the git repo profile but its files host references like `private_key_file` paths that are safe to track. Mirror = copy, not symlink (git doesn't track symlinks usefully across clones).

## The mandatory-sync consideration

`vps_project.json` lives in `/root/credential/` (outside the repo), but is referenced as SOT throughout ILMA. When updating, mirror the JSON into the profile repo (`/root/.hermes/profiles/ilma/`) so the next session that does `git pull` sees the latest. After commit, the local canonical remains `/root/credential/` — the profile mirror is for git-tracked provenance only.

## When to treat the file as untrusted

The `vps_project.json` file is hand-edited in casual contexts (Bos updates it 1-2× per quarter). Before any operational runtime assumption fetched from it (port, key, user), the ssh-server-discovery-and-recon matrix-scan should re-verify. Concretely: every read of `vps_project.json` is a *starting hypothesis*, not a fact.

## Joins with other skills

- `ssh-server-discovery-and-recon` (the umbrella): defines how to verify each service is actually up after the JSON gets corrected
- `claude-code`: when the fix involves writing a deploy/audit script to update a half-dozen similar projects, treat it as a Claude Code remote-project task (per claude-code "Remote Project Workflow" section)
- `system-administration` (unread stub): relevant when this JSON gets loaded into a systemd unit or ENV overlay

## Audit trail — 2026-06-20

| Commit | Author | What |
|---|---|---|
| `77a1993` 2026-06-20 08:38 WIB | ILMA Agent (Bos: Huda Choirul Anam) | Initial v1.2 with port corrections + 4-file batched commit per Bos authorization |
| `ada3cfb` (prior) | security re-init | Clean baseline |

Why this reference exists: I almost edited `vps_project.json` from memory, would have shipped stale ports (3000/1337/3001), and only the actual SSH + curl evidence-based audit surfaced the disagreement. Without that pattern, future ILMA sessions will reintroduce the same drift.
