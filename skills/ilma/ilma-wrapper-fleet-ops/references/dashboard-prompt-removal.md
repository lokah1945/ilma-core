# Dashboard /dashboard BEARER_TOKEN Prompt Removal

Bos does NOT want the browser `window.prompt('Enter wrapper BEARER_TOKEN...')` popup on wrapper dashboards. Hardcode the token instead (approved 2026-07-28).

## Why hardcode is safe
All 5 wrappers run with `DISABLE_AUTH=1` (see pre-auth section of SKILL.md). The server NEVER validates the bearer token when `DISABLE_AUTH` is set. So the hardcoded string in the page is purely cosmetic — it is sent as `Authorization: Bearer wrapper-local-key` but the server ignores it. No security downgrade beyond the already-open pre-auth mode.

## Exact edits (5 files)
Replace the `window.prompt(...)` line with a hardcoded string. Match the exact surrounding code per wrapper:

### nvidia-python/dashboard.html (~line 824-828)
```js
  // 3. One-time client-side prompt; kept in sessionStorage only.
  let token = '';
  try {
-    token = window.prompt('Enter wrapper bearer token (leave empty if auth is disabled):') || '';
+    token = 'wrapper-local-key';
     sessionStorage.setItem('wn-bearer', token);
  } catch {}
```

### nous/dashboard.html (~line 331-336)
```js
  let token = sessionStorage.getItem('wrapper-bearer-token') || '';
  if (!token) {
-    token = window.prompt('Enter wrapper bearer token (leave empty if auth is disabled):') || '';
+    token = 'wrapper-local-key';
    sessionStorage.setItem('wrapper-bearer-token', token);
  }
```

### opencode / blackbox / vercel/dashboard.html (~line 332-340)
All three share the same pattern (they read `wrapper-bearer-token` from localStorage, fall back to prompt):
```js
  let tok = localStorage.getItem('wrapper-bearer-token');
  if (tok === null) {
-    tok = window.prompt('Enter wrapper BEARER_TOKEN (leave blank if auth is disabled):') || '';
+    tok = 'wrapper-local-key';
    localStorage.setItem('wrapper-bearer-token', tok);
  }
```

## Verify after edit + restart
```bash
for d in nvidia-python nous opencode blackbox vercel; do
  f=/root/wrapper/$d/dashboard.html
  printf "%-14s prompt:" "$d"
  grep -qiE "window.prompt.*(BEARER_TOKEN|bearer token)" "$f" && echo -n "YES(still) " || echo -n "NO(ok) "
  grep -q "wrapper-local-key" "$f" && echo "hardcode:yes" || echo "hardcode:NO"
done
# served HTML must also be prompt-free:
curl -s http://172.16.102.11:9102/dashboard | grep -c "leave empty if auth"   # expect 0
```

## Post-pull gotcha
`git pull github main` rewrites these files. Cloud version `638212d` already has no prompt + hardcoded token. Always re-verify with the loop above after any pull; re-apply if a future commit reverts it.
