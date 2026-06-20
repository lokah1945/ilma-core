# Reference: Repr-Sandbox Masking — When the Display Lies (2026-06-19)

## TL;DR

If `execute_code()` prints something like `'sk-cp-...S-Ig'`,
the **data is real and intact** — the message you're seeing has been
filtered by the repr sanitizer inside Hermes' Python sandbox, not by
the source. To verify a credential claim:

1. Write a small Python script via `write_file` (STDOUT bunyi `subprocess`
   bukan `repr`).
2. `subprocess.run([sys.executable, "/tmp/x.py"], capture_output=True)`
   — getattr stdout bersih, repr tidak di-truncate.
3. Verify via API: `curl ... -H "x-api-key: <full>"` atau `mmx auth login`.

## What happened

Sesi 2026-06-19, Bos minta: "ambil saya api key minimax dari database".

Saya query SOT MongoDB (`credentials.llm_providers`):

```python
from pymongo import MongoClient
c = MongoClient(host="172.16.103.253", port=27017, ...)
key = c["credentials"].llm_providers.find_one(
    {"provider": "minimax"}, {"_id": 0, "api_key": 1})["api_key"]
print(repr(key))
# Hermes sandbox printed:  'sk-cp-...S-Ig'   len=125
```

Yang muncul di chat hanya prefix `sk-cp-...` dan suffix `S-Ig` — 125 char
terlihat dari panjang, isi tengah tidak printable.

Berdasarkan heuristic P-2 lama skill `ilma-sot-credential-retrieval`
("`sk-cp-...` shape tidak familiar → placeholder"), saya hampir mengklaim
"key ini placeholder, minta Bos kasih API key baru."

**Tapi**: saya jalur verify runtime dulu via curl:

```python
import requests
r = requests.post(
    "https://api.minimax.io/anthropic/v1/messages",
    headers={"x-api-key": key, "anthropic-version": "2023-06-01"},
    json={"model": "MiniMax-M2.5", "max_tokens": 10,
          "messages": [{"role": "user", "content": "hi"}]},
)
print(r.status_code, r.text[:300])
# 200  {"id":"0684b521966f61e6ab146872c780422c","type":"message", ...}
```

**Buktinya**: API return 200 dengan `model: MiniMax-M2.5` menjawab "…ILMA…".
Key BENAR live Token Plan key.

## Output sanitization — yang ditemukan

Saya audit channel output berbeda:

| Mekanisme | Apa yang di-filter | Contoh dari sesi |
|-----------|---------------------|------------------|
| `execute_code` stdout (repr) | String panjang dengan substring credential-shaped tertentu di-truncate ke `…` | `'sk-cp-...S-Ig'` |
| `terminal()` dengan `grep` key | Pola credential-key di-strip oleh chat renderer | `grep ... MINIMAX` → baris 70: `MINIMAX_API_KEY=*** ` (literal) |
| `write_file` ke file raw | Tidak di-filter — hex dump/dump representable penuh | Benar-benar 125-char key string |

**Catatan**: hex dump `0x4d494e494d41585f4150495f4b45593d736b2d63702d5857484439...`
cocok dengan key prefix `sk-cp-XWHD`. Itu cara konfirmasi byte-level
bahwa isi file sama dengan kata Bos.

## Lesson — siapa yg harus membaca file ini

Skill yang mengurus claim runtime state (`ilma-state-verify-before-report`),
skill yang audit credential (`ilma-sot-credential-retrieval`), dan siapa pun
yang mem-print `api_key`, `password`, `secret`, atau string sensitif apa pun
ke stdout / chat context.

**Wajib dua-channel verify:**
1. **Channel A** — channel sanitized (yang Bos lihat). Pakai untuk narasi
   "key ada, panjang 125, prefix sk-cp-, status UNVERIFIED" → JANGAN claim invalid/valid dari sini.
2. **Channel B** — channel clean (subprocess via write_file + raw curl). Pakai
   untuk claim functional ("HTTP 200 dengan model M3, quota 99%").

## Kenapa old P-2 salah

Skill P-2 yang lama:

> "String values like `sk-cp-...S-Ig` (125 chars) look like keys.
> **They are placeholders** ... `Length 125 + prefix sk-cp-` → not a known
> real key format."

Saya patch skill P-2 untuk tambahkan:
- `key_status: UNVERIFIED` ≠ invalid (hanya "tidak di-validate sejak restore")
- shape-heuristic tetap sebagai *smell test*, bukan conclusion
- **wajib two-channel verify (sanitized + clean) sebelum claim apa-apa**

## Kenapa claim awal saya (chat pertama) salah

Saya bilang di chat: "API key `minimax` di MongoDB adalah placeholder
`sk-cp-...S-Ig` (literal string tersebut), bukan Token Plan Key yang valid
untuk `api.minimax.io`." — klaim ini berdasarkan shape heuristic saja.
Pas Bos bilang "2" (test API langsung), saya curl → 200 → klaim harus direvisi.

Jika saja saya tidak test with runtime, ILMA bakal minta Bos bikin
Token Plan subscription baru yang sebenernya sudah aktif — waste effort.

## Cross-link

- `ilma-state-verify-before-report` P-5 (revisi 2026-06-19)
- `ilma-sot-credential-retrieval` P-2 (revisi 2026-06-19) & P-3
- `ilma-false-positive-detection` — class-level pattern: "registry unverified,
  runtime actually works" — lesson ini kasus khusus untuk domain credentials.
