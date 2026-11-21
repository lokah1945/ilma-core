# SQL Probes for Schema Drift Analysis

Copy-paste ready queries for common drift detection patterns. Parameterize `<db>`, `<pattern>`, `<table>` as needed.

---

## 1. Column Inventory Across All Databases

```sql
-- Find all columns matching pattern across all databases
SELECT TABLE_SCHEMA, TABLE_NAME, COLUMN_NAME, DATA_TYPE, 
       CHARACTER_MAXIMUM_LENGTH, NUMERIC_PRECISION, COLUMN_DEFAULT,
       IS_NULLABLE, COLUMN_KEY, EXTRA
FROM INFORMATION_SCHEMA.COLUMNS
WHERE COLUMN_NAME LIKE '%<pattern>%'
ORDER BY TABLE_SCHEMA, TABLE_NAME, ORDINAL_POSITION;
```

**Patterns to try:** `token`, `face`, `vector`, `embedding`, `feature`, `model`, `version`

---

## 2. Live Schema for Specific Table

```sql
-- Full CREATE TABLE statement
SHOW CREATE TABLE `<db>`.`<table>`;

-- Column details only
SELECT COLUMN_NAME, DATA_TYPE, CHARACTER_MAXIMUM_LENGTH, NUMERIC_PRECISION,
       COLUMN_DEFAULT, IS_NULLABLE, COLUMN_KEY, EXTRA, COLUMN_COMMENT
FROM INFORMATION_SCHEMA.COLUMNS
WHERE TABLE_SCHEMA = '<db>' AND TABLE_NAME = '<table>'
ORDER BY ORDINAL_POSITION;
```

---

## 3. Vector/Embedding Dimension Check

```sql
-- For comma-separated float vectors stored as TEXT/VARCHAR
SELECT id, 
       (LENGTH(<vector_col>) - LENGTH(REPLACE(<vector_col>, ',', '')) + 1) as dimension,
       LEFT(<vector_col>, 200) as sample
FROM `<db>`.`<table>`
LIMIT 10;

-- Dimension distribution (if mixed)
SELECT 
    (LENGTH(<vector_col>) - LENGTH(REPLACE(<vector_col>, ',', '')) + 1) as dimension,
    COUNT(*) as count
FROM `<db>`.`<table>`
GROUP BY dimension
ORDER BY count DESC;
```

---

## 4. Token/ID Length Analysis

```sql
-- Max actual length per token column
SELECT 
    TABLE_SCHEMA, TABLE_NAME, COLUMN_NAME,
    CHARACTER_MAXIMUM_LENGTH as defined_max,
    MAX(LENGTH(COLUMN_NAME)) as actual_max
FROM INFORMATION_SCHEMA.COLUMNS
JOIN `<db>`.`<table>` -- manual per table or use dynamic SQL
WHERE COLUMN_NAME LIKE '%token%'
GROUP BY TABLE_SCHEMA, TABLE_NAME, COLUMN_NAME, CHARACTER_MAXIMUM_LENGTH
HAVING actual_max > defined_max OR defined_max < 50;
```

**Per-table version:**
```sql
SELECT MAX(LENGTH(token)) as max_token_len, 
       MAX(LENGTH(facetoken_in)) as max_facetoken_in_len,
       MAX(LENGTH(facetoken_out)) as max_facetoken_out_len
FROM `<db>`.`<table>`;
```

---

## 5. Cross-Database Foreign Keys

```sql
-- All FKs with referenced schema (catches cross-DB refs)
SELECT 
    TABLE_SCHEMA, TABLE_NAME, COLUMN_NAME,
    REFERENCED_TABLE_SCHEMA, REFERENCED_TABLE_NAME, REFERENCED_COLUMN_NAME,
    CONSTRAINT_NAME
FROM INFORMATION_SCHEMA.KEY_COLUMN_USAGE
WHERE TABLE_SCHEMA IN ('<db1>', '<db2>', '<db3>')
  AND REFERENCED_TABLE_SCHEMA IS NOT NULL
ORDER BY TABLE_SCHEMA, TABLE_NAME;
```

---

## 6. Missing Columns (Live vs Reference)

```sql
-- Columns in reference but missing in live (requires reference data in temp table)
-- Or manually compare:
-- Reference columns:
SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA='<ref_db>' AND TABLE_NAME='<table>';

-- Live columns:
SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA='<live_db>' AND TABLE_NAME='<table>';
```

---

## 7. Character Set / Collation Drift

```sql
-- Table-level
SELECT TABLE_SCHEMA, TABLE_NAME, TABLE_COLLATION
FROM INFORMATION_SCHEMA.TABLES
WHERE TABLE_SCHEMA IN ('<db1>', '<db2>');

-- Column-level
SELECT TABLE_SCHEMA, TABLE_NAME, COLUMN_NAME, CHARACTER_SET_NAME, COLLATION_NAME
FROM INFORMATION_SCHEMA.COLUMNS
WHERE TABLE_SCHEMA IN ('<db1>', '<db2>')
  AND CHARACTER_SET_NAME IS NOT NULL
ORDER BY TABLE_SCHEMA, TABLE_NAME;
```

---

## 8. Auto-Increment Status

```sql
SELECT TABLE_SCHEMA, TABLE_NAME, AUTO_INCREMENT
FROM INFORMATION_SCHEMA.TABLES
WHERE TABLE_SCHEMA = '<db>' AND AUTO_INCREMENT IS NOT NULL
ORDER BY AUTO_INCREMENT DESC;
```

---

## 9. Index & Constraint Comparison

```sql
-- Indexes
SELECT TABLE_SCHEMA, TABLE_NAME, INDEX_NAME, COLUMN_NAME, NON_UNIQUE, INDEX_TYPE
FROM INFORMATION_SCHEMA.STATISTICS
WHERE TABLE_SCHEMA = '<db>'
ORDER BY TABLE_NAME, INDEX_NAME, SEQ_IN_INDEX;

-- Foreign Keys
SELECT TABLE_SCHEMA, TABLE_NAME, CONSTRAINT_NAME, COLUMN_NAME,
       REFERENCED_TABLE_SCHEMA, REFERENCED_TABLE_NAME, REFERENCED_COLUMN_NAME,
       UPDATE_RULE, DELETE_RULE
FROM INFORMATION_SCHEMA.KEY_COLUMN_USAGE
WHERE TABLE_SCHEMA = '<db>' AND REFERENCED_TABLE_SCHEMA IS NOT NULL;
```

---

## 10. Extract Dump Sections (Bash + SQL)

```bash
# Find DB section boundaries in multi-DB dump
grep -n 'Current Database' /path/to/dump.sql

# Extract specific DB section (line ranges from above)
sed -n '<start_line>,<end_line>p' /path/to/dump.sql | grep 'CREATE TABLE' | sed 's/.*`\([^`]*\)`.*/\1/'
```

```python
# Python: parse dump into per-DB table lists
import re
with open('dump.sql') as f:
    content = f.read()

# Split by "Current Database" comments
sections = re.split(r'--\s*Current Database:\s*`([^`]+)`', content)
# sections[0] = preamble, then alternating: db_name, content, db_name, content...
for i in range(1, len(sections), 2):
    db_name = sections[i]
    sql = sections[i+1]
    tables = re.findall(r'CREATE TABLE `([^`]+)`', sql)
    print(f"{db_name}: {len(tables)} tables")
    for t in sorted(tables):
        print(f"  {t}")
```

---

## 11. Generate ALTER Statements for Column Expansion

```sql
-- Template: expand VARCHAR columns that are too small
-- Run this query to generate ALTERs, then review & execute
SELECT CONCAT(
    'ALTER TABLE `', TABLE_SCHEMA, '`.`', TABLE_NAME, 
    '` MODIFY `', COLUMN_NAME, '` VARCHAR(100)', 
    CASE WHEN IS_NULLABLE = 'NO' THEN ' NOT NULL' ELSE ' NULL' END, ';'
) as alter_sql
FROM INFORMATION_SCHEMA.COLUMNS
WHERE TABLE_SCHEMA IN ('<db1>', '<db2>')
  AND COLUMN_NAME LIKE '%token%'
  AND DATA_TYPE = 'varchar'
  AND CHARACTER_MAXIMUM_LENGTH < 50;
```

---

## 12. Quick Health Check for Face/Vector Tables

```sql
-- Run against suspected face/vector database
SELECT 
    t.TABLE_NAME,
    t.TABLE_ROWS,
    c.COLUMN_NAME,
    c.DATA_TYPE,
    c.CHARACTER_MAXIMUM_LENGTH,
    -- For embedding columns
    CASE 
        WHEN c.COLUMN_NAME = 'embedding' AND c.DATA_TYPE IN ('text', 'mediumtext', 'longtext')
        THEN (SELECT CONCAT(MIN(dim), '-', MAX(dim)) FROM (
            SELECT (LENGTH(embedding) - LENGTH(REPLACE(embedding, ',', '')) + 1) as dim 
            FROM `<db>`.`<table>` LIMIT 100
        ) sub)
    END as vector_dim_range
FROM INFORMATION_SCHEMA.TABLES t
JOIN INFORMATION_SCHEMA.COLUMNS c ON c.TABLE_SCHEMA = t.TABLE_SCHEMA AND c.TABLE_NAME = t.TABLE_NAME
WHERE t.TABLE_SCHEMA = '<db>'
  AND (t.TABLE_NAME LIKE 'fc%' OR t.TABLE_NAME LIKE 'fr%' OR t.TABLE_NAME LIKE '%face%')
  AND c.COLUMN_NAME IN ('token', 'facetoken_in', 'facetoken_out', 'embedding', 'facemodel', 'idface', 'facebmp')
ORDER BY t.TABLE_NAME, c.ORDINAL_POSITION;
```