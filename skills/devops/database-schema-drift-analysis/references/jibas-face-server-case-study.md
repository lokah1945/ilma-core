# JIBAS Face Server Schema Drift Case Study

**Session:** 2026-10-28  
**Environment:** VPS 172.16.103.253 (alias: `yapsi`)  
**Database:** MariaDB 10.4.32 on port 33445  
**Application:** JIBAS v37.0 (PHP) + Face Server (.NET, external)

---

## Error Symptoms

1. **"Data too long for column 'token' at row 1"** — during face training
2. **"Incompatible feature column type: 'Vector<Single, 512>' vs 'Vector<Single, 128>'"** — during recognition

---

## Root Cause Analysis

### Error 1: Token Column Size Mismatch

| Table | Column | Live Spec | Max Data Seen | Required |
|-------|--------|-----------|---------------|----------|
| `fcface` | `token` | `VARCHAR(5)` | `72092` (5 digits) | `VARCHAR(100+)` |
| `fcanalyzeface` | `token` | `VARCHAR(5)` | — | `VARCHAR(100+)` |
| `frpresence` | `facetoken_in/out` | `VARCHAR(5)` | — | `VARCHAR(100+)` |
| `frpresensikegiatan` | `facetoken_in/out` | `VARCHAR(5)` | — | `VARCHAR(100+)` |
| `fcpresensibebasdata` | `facetoken_in/out` | `VARCHAR(5)` | — | `VARCHAR(100+)` |

**Cause:** .NET Face Server generates tokens longer than 5 chars (GUID/JWT/base64). DB assumes 5-digit numeric codes.

**Fix:**
```sql
ALTER TABLE fcface MODIFY token VARCHAR(100) NOT NULL;
ALTER TABLE fcanalyzeface MODIFY token VARCHAR(100) NOT NULL;
ALTER TABLE frpresence MODIFY facetoken_in VARCHAR(100), MODIFY facetoken_out VARCHAR(100);
ALTER TABLE frpresensikegiatan MODIFY facetoken_in VARCHAR(100), MODIFY facetoken_out VARCHAR(100);
ALTER TABLE fcpresensibebasdata MODIFY facetoken_in VARCHAR(100), MODIFY facetoken_out VARCHAR(100);
```

---

### Error 2: Vector Dimension Mismatch

| Table | Column | Live Dimension | Installer Spec | Face Server Expects |
|-------|--------|----------------|----------------|---------------------|
| `fcfacedata` | `embedding` | **512** (verified) | `TEXT` (no dim constraint) | **128 or 512** |

**Evidence:**
```sql
SELECT id, (LENGTH(embedding) - LENGTH(REPLACE(embedding, ',', '')) + 1) as dimension 
FROM fcfacedata LIMIT 10;
-- All return 512
```

**Cause:** Face Server .NET loads a model expecting 128-dim vectors (old: dlib/OpenFace) but DB contains 512-dim vectors (new: ArcFace/AdaFace/InsightFace). Or vice versa.

**Key Finding:** Live DB has `fcface.facemodel` column (`TINYINT(3) DEFAULT 1`) with value `2` for both records. **Installer dump (JIBAS 37.0) does NOT have this column.** This indicates:
- Server upgraded to model v2 (512-dim) after initial install
- Face Server .NET may still be configured for model v1 (128-dim)
- OR Face Server upgraded but DB not migrated properly

---

## Schema Comparison: Live vs Installer Dump

### `fcface` Table
| Column | Live (jbssat) | Installer (jibas_db.sql) | Drift |
|--------|---------------|--------------------------|-------|
| `id` | `int(10) unsigned` | `int(10) unsigned` | ✅ |
| `jenis` | `tinyint(3) unsigned` | `tinyint(3) unsigned` | ✅ |
| `nis` | `varchar(20)` | `varchar(20)` | ✅ |
| `nip` | `varchar(30)` | `varchar(30)` | ✅ |
| `nic` | `varchar(20)` | `varchar(20)` | ✅ |
| `departemen` | `varchar(50)` | `varchar(50)` | ✅ |
| `tanggal` | `datetime` | `datetime` | ✅ |
| `status` | `tinyint(4)` | `tinyint(4)` | ✅ |
| `useraktif` | `tinyint(4) unsigned` | `tinyint(4) unsigned` | ✅ |
| `petugas` | `varchar(30)` | `varchar(30)` | ✅ |
| `token` | `varchar(5)` | `varchar(5)` | ⚠️ **TOO SMALL** |
| `lastpresence` | `datetime` | `datetime` | ✅ |
| `istrained` | `tinyint(4)` | `tinyint(4)` | ✅ |
| `checkuserid` | `tinyint(4)` | `tinyint(4)` | ✅ |
| `facemodel` | `tinyint(3) DEFAULT 1` | **MISSING** | ⚠️ **EXTRA IN LIVE** |

### `fcfacedata` Table
| Column | Live | Installer | Drift |
|--------|------|-----------|-------|
| `id` | `int(10) unsigned` | `int(10) unsigned` | ✅ |
| `idface` | `int(10) unsigned` | `int(10) unsigned` | ✅ |
| `facebmp` | `mediumblob` | `mediumblob` | ✅ |
| `facepos` | `varchar(10)` | `varchar(10)` | ✅ |
| `embedding` | `text` | `text` | ✅ (but dim=512 vs unknown) |

---

## Face Recognition Database Schema (jbssat)

```
fcface (master)
  ├── fcfacedata (embeddings 512-d) ─── FK: idface → fcface.id
  ├── fcinputdataml (ML training input) ── FK: idface → fcface.id
  ├── fcanalyzeface (recognition logs) ── FK: idfacedata → fcfacedata.id
  ├── frpresence (daily presence) ────── FK: faceid_in/out → fcface.id
  ├── frpresensikegiatan (event presence) FK: faceid_in/out → fcface.id
  ├── fcpresensibebasdata (free presence) FK: faceid_in/out → fcface.id
  ├── fcrecoghistory (recognition history) FK: idface → fcface.id
  └── fcdelface (deleted faces) ──────── FK: idface → fcface.id
```

**Cross-DB FKs:**
- `fcface.nis` → `jbsakad.siswa.nis`
- `fcface.nip` → `jbssdm.pegawai.nip`
- `fcface.nic` → `jbsakad.calonsiswa.nopendaftaran`
- `fcface.departemen` → `jbsakad.departemen.departemen`

---

## Remediation Checklist

- [ ] **HIGH** — Expand all `token`/`facetoken_*` columns to `VARCHAR(100)`
- [ ] **HIGH** — Verify Face Server .NET config: model dimension (128 vs 512) matches DB
- [ ] **MEDIUM** — Document `facemodel` column purpose; add to installer or migration
- [ ] **MEDIUM** — Add vector dimension validation trigger or app-level check
- [ ] **LOW** — Character set alignment: live `latin1` vs installer `utf8` per table

---

## Files Referenced

- Live DB: `jbssat` on `yapsi:33445`
- Installer dump: `/root/backups/jibas_db.sql` (JIBAS 37.0, 28 Oct 2026)
- App config: `/var/www/siakad/include/database.config.php`
- Face tables located in `jbssat` (NOT `jbsakad` as assumed from config)