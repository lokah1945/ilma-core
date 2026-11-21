---
name: database-schema-drift-analysis
category: devops
description: Detect and remediate schema drift between live databases and reference schemas (installer dumps, migration files, ORM models) that cause application errors.
triggers:
  - "Data too long for column"
  - "Unknown column"
  - "Incompatible feature column type"
  - "Foreign key constraint fails"
  - Schema version mismatch between environments
---

# Database Schema Drift Analysis

**Class-level skill for detecting and remediating schema drift between live databases and reference schemas (installer dumps, migration files, ORM models) that cause application errors.**

---

## When to Use

- Application errors that hint at schema mismatch: "Data too long for column", "Unknown column", "Incompatible type", "Foreign key constraint fails"
- Legacy PHP/MySQL applications (JIBAS, WordPress, Drupal, custom) where DB evolved outside migrations
- Comparing live production DB against clean installer dump or migration baseline
- Pre-upgrade verification: will the new app version work with current DB?
- Post-migration validation: did all schema changes apply correctly?

---

## Triggers

- Error messages referencing column size, type, or missing columns
- Application behavior divergence between environments (dev/staging/prod)
- Suspected manual DB changes (hotfixes, emergency ALTERs)
- Version upgrade of application without corresponding migration run

---

## Methodology

### 1. Establish Connection & Inventory
```bash
# SSH to target
ssh <alias> "mysql -h <host> -P <port> -u <user> -p'<pass>' -e 'SHOW DATABASES;'"

# List all tables per database
for db in <db_list>; do mysql ... $db -e 'SHOW TABLES;'; done
```

### 2. Identify Target Database & Tables
- Use application config (e.g., `database.config.php`) to find which DB/connection the app uses
- Search codebase for keywords (face, wajah, token, vector) to find relevant tables
- Query `INFORMATION_SCHEMA.COLUMNS` for columns matching error context

### 3. Extract Live Schema
```sql
-- Full CREATE TABLE for target tables
SHOW CREATE TABLE `table_name`;

-- Column details for specific patterns
SELECT TABLE_NAME, COLUMN_NAME, DATA_TYPE, CHARACTER_MAXIMUM_LENGTH, NUMERIC_PRECISION
FROM INFORMATION_SCHEMA.COLUMNS
WHERE TABLE_SCHEMA='<db>' AND (COLUMN_NAME LIKE '%token%' OR COLUMN_NAME LIKE '%vector%' OR COLUMN_NAME LIKE '%face%');
```

### 4. Extract Reference Schema
- Parse installer SQL dump (`grep 'CREATE TABLE' dump.sql | sed ...`)
- Or parse migration files
- Or dump from clean install environment

### 5. Diff & Classify Drift
| Drift Type | Detection | Remediation |
|------------|-----------|-------------|
| Column size too small | `CHARACTER_MAXIMUM_LENGTH` in live < reference OR app sends longer data | `ALTER TABLE ... MODIFY column VARCHAR(N)` |
| Missing column | Column in reference, not in live | `ALTER TABLE ... ADD COLUMN ...` |
| Extra column | Column in live, not in reference | Document; may be app enhancement |
| Type mismatch | `DATA_TYPE` differs (e.g., `text` vs `varchar`, `int` vs `smallint`) | `ALTER TABLE ... MODIFY column NEW_TYPE` |
| Constraint diff | FK/PK/INDEX present in one but not other | Add/drop constraints to match reference |
| Default value drift | `COLUMN_DEFAULT` differs | Align to reference or app expectation |

### 6. Map Drift to Application Errors
- "Data too long for column 'X'" → Column size drift (live too small)
- "Unknown column 'X'" → Missing column in live
- "Incompatible feature column type" → Type/dimension mismatch (e.g., vector 128 vs 512)
- "Foreign key constraint fails" → Missing FK or referenced data missing

### 7. Generate Remediation Plan
- Prioritize: blocking errors first, then consistency
- Write `ALTER` statements in dependency order (parents before children for FK)
- Test on staging clone first
- Backup before production apply

---

## Key SQL Probes (Reusable)

```sql
-- All columns matching pattern across all DBs
SELECT TABLE_SCHEMA, TABLE_NAME, COLUMN_NAME, DATA_TYPE, CHARACTER_MAXIMUM_LENGTH, NUMERIC_PRECISION
FROM INFORMATION_SCHEMA.COLUMNS
WHERE COLUMN_NAME LIKE '%<pattern>%';

-- Table row count + sample data for embedding/vector columns
SELECT id, (LENGTH(embedding) - LENGTH(REPLACE(embedding, ',', '')) + 1) as dimension FROM table LIMIT 10;

-- Check specific column constraints
SHOW CREATE TABLE table_name;

-- Find tables with column name
SELECT TABLE_SCHEMA, TABLE_NAME FROM INFORMATION_SCHEMA.COLUMNS WHERE COLUMN_NAME = 'token';
```

---

## Pitfalls & Gotchas

1. **Cross-database FKs** — JIBAS uses FKs across `jbsakad`, `jbssdm`, `jbssat`. Reference dump may split by DB; live has all. Check `REFERENCED_TABLE_SCHEMA` in `INFORMATION_SCHEMA.KEY_COLUMN_USAGE`.

2. **Character set drift** — Reference: `utf8`/`utf8_general_ci` per table. Live: may be `latin1`/`latin1_swedish_ci` default with per-column overrides. Causes silent truncation on 4-byte chars.

3. **Auto-increment gaps** — Live `AUTO_INCREMENT=43` vs reference `AUTO_INCREMENT=1`. Not an error, but indicates data volume.

4. **Version columns not in installer** — Live `fcface.facemodel` column exists (v2) but absent from JIBAS 37.0 installer dump. App may depend on it.

5. **Token/ID size assumptions** — `VARCHAR(5)` for tokens assumes numeric 5-digit codes. .NET Face Server may send GUIDs (36 chars) or JWTs (100+). Always verify with app team or inspect actual data.

6. **Vector/embedding storage** — Stored as `TEXT` with comma-separated floats. Dimension = `LENGTH(embedding) - LENGTH(REPLACE(embedding, ',', '')) + 1`. No native vector type in MariaDB 10.4.

7. **Dump section boundaries** — Multi-DB dump uses `-- Current Database: \`name\`` comments. Use line numbers (`grep -n`) to extract per-DB sections.

---

## Deliverables

- **Drift Report**: Table with columns [Table, Column, Live Spec, Reference Spec, Drift Type, Severity, Remediation SQL]
- **Remediation Script**: Ordered `ALTER` statements ready for review/execution
- **Verification Queries**: Post-apply checks to confirm fix

---

## References

- `references/jibas-face-server-case-study.md` — Full JIBAS Face Server drift analysis (token size + vector dimension)
- `references/sql-probes.md` — Copy-paste probe queries for common drift patterns

---

## Scripts

- `scripts/extract-live-schema.sh` — Parameterized live schema extractor
- `scripts/parse-dump-sections.py` — Split multi-DB dump into per-DB CREATE TABLE lists
- `scripts/diff-schemas.py` — Compare live vs reference, output drift table