#!/usr/bin/env bash
# extract-live-schema.sh — Parameterized live schema extractor
# Usage: ./extract-live-schema.sh <ssh_alias> <db_user> <db_pass> <db_port> <output_dir> [db_list]

set -euo pipefail

SSH_ALIAS="${1:-yapsi}"
DB_USER="${2:-root}"
DB_PASS="${3}"
DB_PORT="${4:-33445}"
OUTPUT_DIR="${5:-./schema_output}"
DB_LIST="${6:-}"

if [[ -z "$DB_PASS" ]]; then
    echo "Usage: $0 <ssh_alias> <db_user> <db_pass> <db_port> <output_dir> [db_list]"
    echo "Example: $0 yapsi root 'MalangKotaBunga1945' 33445 ./schema_output 'jbsakad jbssat jbssdm'"
    exit 1
fi

mkdir -p "$OUTPUT_DIR"

# Build database list
if [[ -z "$DB_LIST" ]]; then
    # Auto-discover all databases
    DBS=$(ssh "$SSH_ALIAS" "mysql -h localhost -P $DB_PORT -u $DB_USER -p'$DB_PASS' -e 'SHOW DATABASES;' -s -N" | grep -v -E '^(information_schema|performance_schema|mysql|sys)$')
else
    DBS="$DB_LIST"
fi

echo "Extracting schema for databases: $DBS"
echo "Output directory: $OUTPUT_DIR"

for DB in $DBS; do
    echo "Processing $DB..."
    DB_DIR="$OUTPUT_DIR/$DB"
    mkdir -p "$DB_DIR"

    # 1. List tables
    ssh "$SSH_ALIAS" "mysql -h localhost -P $DB_PORT -u $DB_USER -p'$DB_PASS' $DB -e 'SHOW TABLES;' -s -N" > "$DB_DIR/tables.txt"

    # 2. Full CREATE TABLE for each table
    while IFS= read -r TABLE; do
        [[ -z "$TABLE" ]] && continue
        ssh "$SSH_ALIAS" "mysql -h localhost -P $DB_PORT -u $DB_USER -p'$DB_PASS' $DB -e \"SHOW CREATE TABLE \\\`$TABLE\\\`;\" --raw" \
            | sed '1d' > "$DB_DIR/${TABLE}.sql"
    done < "$DB_DIR/tables.txt"

    # 3. Column details (CSV for diffing)
    ssh "$SSH_ALIAS" "mysql -h localhost -P $DB_PORT -u $DB_USER -p'$DB_PASS' $DB -e '
        SELECT TABLE_NAME, COLUMN_NAME, ORDINAL_POSITION, DATA_TYPE, 
               CHARACTER_MAXIMUM_LENGTH, NUMERIC_PRECISION, NUMERIC_SCALE,
               COLUMN_DEFAULT, IS_NULLABLE, COLUMN_KEY, EXTRA, COLUMN_COMMENT
        FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_SCHEMA = \"$DB\"
        ORDER BY TABLE_NAME, ORDINAL_POSITION;' --batch --raw" \
        | sed '1d' > "$DB_DIR/columns.tsv"

    # 4. Indexes
    ssh "$SSH_ALIAS" "mysql -h localhost -P $DB_PORT -u $DB_USER -p'$DB_PASS' $DB -e '
        SELECT TABLE_NAME, INDEX_NAME, COLUMN_NAME, NON_UNIQUE, INDEX_TYPE
        FROM INFORMATION_SCHEMA.STATISTICS
        WHERE TABLE_SCHEMA = \"$DB\"
        ORDER BY TABLE_NAME, INDEX_NAME, SEQ_IN_INDEX;' --batch --raw" \
        | sed '1d' > "$DB_DIR/indexes.tsv"

    # 5. Foreign Keys
    ssh "$SSH_ALIAS" "mysql -h localhost -P $DB_PORT -u $DB_USER -p'$DB_PASS' $DB -e '
        SELECT TABLE_NAME, CONSTRAINT_NAME, COLUMN_NAME,
               REFERENCED_TABLE_SCHEMA, REFERENCED_TABLE_NAME, REFERENCED_COLUMN_NAME,
               UPDATE_RULE, DELETE_RULE
        FROM INFORMATION_SCHEMA.KEY_COLUMN_USAGE
        WHERE TABLE_SCHEMA = \"$DB\" AND REFERENCED_TABLE_SCHEMA IS NOT NULL
        ORDER BY TABLE_NAME, CONSTRAINT_NAME;' --batch --raw" \
        | sed '1d' > "$DB_DIR/foreign_keys.tsv"

    # 6. Table metadata (row count, engine, collation, auto_inc)
    ssh "$SSH_ALIAS" "mysql -h localhost -P $DB_PORT -u $DB_USER -p'$DB_PASS' $DB -e '
        SELECT TABLE_NAME, ENGINE, TABLE_COLLATION, TABLE_ROWS, AUTO_INCREMENT
        FROM INFORMATION_SCHEMA.TABLES
        WHERE TABLE_SCHEMA = \"$DB\";' --batch --raw" \
        | sed '1d' > "$DB_DIR/table_meta.tsv"

    echo "  Done: $DB"
done

echo "Schema extraction complete. Output in $OUTPUT_DIR"
echo ""
echo "Structure:"
find "$OUTPUT_DIR" -type f | head -30