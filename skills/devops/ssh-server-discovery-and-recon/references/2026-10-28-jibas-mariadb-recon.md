# JIBAS MariaDB Recon — 172.16.103.253 (YAPSIDarussalam)
**Date:** 2026-10-28
**Host alias:** `yapsi` (172.16.103.253)
**SSH Key:** `/root/credential/lokah1945.pem` (OpenSSH format, works ONLY on this host)
**DB:** MariaDB 10.4.32 on port **33445** (non-standard)
**Credentials from:** `/var/www/siakad/include/database.config.php`
- User: `root`
- Pass: `MalangKotaBunga1945`
- Default DB: `jbsakad`

---

## Live Databases on Port 33445
| Database | Tables | Notes |
|---|---|---|
| **jbsakad** | **63** | Main academic DB (config.php default) |
| jbsfina | 99 | Keuangan |
| jbscbe | 60 | CBE (Computer Based Exam) |
| jbsvcr | 44 | VCR |
| jbssat | 36 | Satuan Pendidikan |
| jbssdm | 23 | SDM/HR |
| jbsjs | 25 | Sync/JS |
| jbsletter | 20 | Surat |
| jbsumum | 22 | Umum/Shared |
| jbsuser | 10 | User Management |
| jbsclient | 12 | Client/App |
| jbsperpus | 13 | Perpustakaan |
| jbssms | 16 | SMS Gateway |
| jbsegw | 9 | Gateway |
| jbsel | 11 | E-Learning |
| jbstgram | 9 | Telegram Bot |
| **Others** | - | nextcloud, rdm_mi/mts/ra, wagw, wp-multisite, keuangan.ulfasanda.my.id |

---

## Schema Comparison: jbsakad (Live) vs Installer Dump

**Dump file:** `/root/backups/jibas_db.sql` (JIBAS 37.0, 28 Oct 2026)
**Dump section for jbsakad:** 61 tables (lines 22-3118)

| Aspect | Live Server | Installer Dump | Delta |
|---|---|---|---|
| Tables in jbsakad | **63** | **61** | +2 in live |
| Extra tables in live | `appconfig`, `notiftemplate` | — | Likely added by v37 update |
| Missing in live | — | 0 | All dump tables present |
| Foreign Keys | Present | Defined in dump | Compare per table |
| Triggers | Need to verify | **Present** (e.g., `jssync_angkatan_*`) | Dump has sync triggers to `jbsjs.syncdata2` |
| Charset/Engine | Need to verify | `utf8`/`utf8_general_ci`, InnoDB | Per-table in dump |

### Extra Tables in Live (not in installer dump)
1. **`appconfig`** — likely application configuration storage
2. **`notiftemplate`** — notification templates

### Trigger Alert (Critical)
Dump installer defines triggers on multiple tables that write to `jbsjs.syncdata2`:
```sql
CREATE TRIGGER jbsakad.jssync_angkatan_ains2 AFTER INSERT ON jbsakad.angkatan
FOR EACH ROW BEGIN
  IF @DISABLE_TRIGGER IS NULL THEN
    INSERT INTO jbsjs.syncdata2 SET tablename = 'jbsakad.angkatan', iddata = NEW.replid, state = 'I', dataload = 1
    ON DUPLICATE KEY UPDATE state = CONCAT(state, 'I');
  END IF;
END
```
Similar triggers for UPDATE (`_aupd2`) and DELETE (`_adel2`).
**Risk:** If `jbsjs` database or `syncdata2` table is missing/corrupt, ANY write to `jbsakad` tables with triggers will fail.

---

## Recommended Follow-up Commands
```bash
# Check triggers in live jbsakad
ssh yapsi "mysql -h localhost -P 33445 -u root -p'MalangKotaBunga1945' jbsakad -e 'SHOW TRIGGERS;'"

# Check jbsjs.syncdata2 exists
ssh yapsi "mysql -h localhost -P 33445 -u root -p'MalangKotaBunga1945' jbsjs -e 'SHOW TABLES; DESCRIBE syncdata2;'"

# Deep compare specific table (e.g., siswa)
ssh yapsi "mysql -h localhost -P 33445 -u root -p'MalangKotaBunga1945' jbsakad -e 'SHOW CREATE TABLE siswa\\G'"

# Foreign key check
ssh yapsi "mysql -h localhost -P 33445 -u root -p'MalangKotaBunga1945' jbsakad -e 'SELECT TABLE_NAME, CONSTRAINT_NAME, REFERENCED_TABLE_NAME FROM INFORMATION_SCHEMA.KEY_COLUMN_USAGE WHERE REFERENCED_TABLE_NAME IS NOT NULL AND TABLE_SCHEMA = \"jbsakad\";'"
```

---

## Key Lessons for Future Recon
1. **Non-standard port 33445** — always check config file, don't assume 3306
2. **JIBAS = multi-database** — 16+ databases, not just jbsakad. Config.php only points to one.
3. **Installer dump ≠ live schema** — dump is baseline (61 tables), live has evolved (+2 tables, possibly more FK/data drift)
4. **Triggers cross databases** — jbsakad triggers write to jbsjs. Both must be healthy.
5. **Charset mismatch possible** — dump uses `utf8` per table but DB default `latin1`. Check live.
6. **Password in plaintext PHP config** — standard for JIBAS, locate via `database.config.php`