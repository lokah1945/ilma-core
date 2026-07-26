# Reference: 2026-06-21 yapsidarussalam.or.id Asset-Existence Audit

## What happened

Bos asked after the 2026-06-20 FullStackVPS audit: "adakah website yg saya build untuk yapsidarussalam.or.id?"

ILMA ran the new Step 4b asset-existence check and confirmed:

- Public DNS: **NXDOMAIN** for 4 candidate domains (`yapsidarussalam.or.id`, `yapsidarussalam.com`, `yapsidarussalam.id`, plus the unlikely TLD variants)
- Source code: ZERO matches across `/root/multisite-blog/web-nextjs/sites/`, `web-nextjs/src/`, `cms-strapi/config/`, `cms-strapi/src/` for `yapsi|darussalam|\.or\.id`
- PM2 processes: none mentioning `yapsi` or `darussalam` (only `nextjs`/`prelanding-ads`/`strapi`)
- Listening ports on `fullstack` (172.16.103.200): 3100 / 3200 / 3201 — none mapped to the target domain

Conclusion: **website belum dibentuk**. Bos acknowledged: "kalau begitu website nya belum di bentuk."

## Sibling signal — what is active nearby

The `yapsi.or.id` (no `darussalam`) domain DOES resolve and points to `103.164.173.46` — but that host serves WordPress + LiteSpeed, NOT Next.js+Strapi. The internal blog on `172.16.103.200:3201` has not yet been public-proxied at this domain.

This is a classic public-IP vs internal-port trap (Pitfall #5 / new Step 4c in skill).

## Probe sequence (verbatim, executable)

```bash
# Step B1 — Domain public DNS check
getent hosts yapsidarussalam.or.id      # → NXDOMAIN
getent hosts yapsi.or.id                # → 103.164.173.46 (WordPress)
getent hosts yapsidarussalam.com        # → NXDOMAIN
getent hosts yapsidarussalam.id         # → NXDOMAIN

# Step B2 — Local SSH to FullStackVPS to inspect source + runtime
ssh fullstack '
  ls -la /root/ | grep -iE "(yapsi|darussalam|blog|next|strapi)"
  # → only `/root/multisite-blog` exists

  ls /root/multisite-blog/web-nextjs/sites/
  # → Cryptonice, GlimpseIt, "Health & Beauty" — NO yapsidarussalam

  grep -rliE "(yapsi|darussalam|\.or\.id)" \
    /root/multisite-blog/web-nextjs/sites/ \
    /root/multisite-blog/web-nextjs/src/ \
    /root/multisite-blog/cms-strapi/config/ \
    /root/multisite-blog/cms-strapi/src/ 2>/dev/null
  # → empty (silent match found only system locales in node_modules, irrelevant)
'

# Step B3 — Live process check
ssh fullstack 'pm2 list'  # → only strapi / nextjs / prelanding-ads
ssh fullstack 'ss -tlnp'  # → only 3100/3200/3201
```

## Lesson

The user's question "is X built yet" looks like a yes/no but actually requires **four independent negative signals** before the answer is safe to give. The Step 4b block was written after this audit (2026-06-21) — see the updated SKILL.md.

## Memory state captured 2026-06-21

- `[mem_004]` updated to include YAPSIDARUSSALAM status with timestamp `2026-06-21 02:00 WIB`
- Skill `ilma-self-improvement/ilma-memory-crisis-recovery` patched with new pitfall about `remove`/`replace` intermittent failure that surfaced during the memory update step of this session
- Skill `devops/ssh-server-discovery-and-recon` patched with new Step 4b (asset existence) and Step 4c (public IP trap)
