#!/usr/bin/env python3
# diff-schemas.py — Compare live vs reference schema, output drift table
# Usage: python3 diff-schemas.py <live_schema_dir> <reference_schema_dir> [output_file]

import os
import sys
import csv
from pathlib import Path
from collections import defaultdict

def load_live_schema(live_dir):
    """Load live schema from extract-live-schema.sh output."""
    schema = {}
    live_path = Path(live_dir)
    
    for db_dir in live_path.iterdir():
        if not db_dir.is_dir():
            continue
        db_name = db_dir.name
        schema[db_name] = {'tables': {}, 'columns': {}}
        
        # Load columns.tsv
        cols_file = db_dir / 'columns.tsv'
        if cols_file.exists():
            with open(cols_file) as f:
                reader = csv.DictReader(f, delimiter='\t')
                for row in reader:
                    table = row['TABLE_NAME']
                    col = row['COLUMN_NAME']
                    key = (table, col)
                    schema[db_name]['columns'][key] = {
                        'data_type': row['DATA_TYPE'],
                        'char_max_len': row['CHARACTER_MAXIMUM_LENGTH'],
                        'num_precision': row['NUMERIC_PRECISION'],
                        'col_default': row['COLUMN_DEFAULT'],
                        'is_nullable': row['IS_NULLABLE'],
                        'col_key': row['COLUMN_KEY'],
                        'extra': row['EXTRA'],
                    }
        
        # Load table list
        tables_file = db_dir / 'tables.txt'
        if tables_file.exists():
            with open(tables_file) as f:
                for line in f:
                    table = line.strip()
                    if table:
                        schema[db_name]['tables'][table] = True
        
        # Load indexes
        idx_file = db_dir / 'indexes.tsv'
        if idx_file.exists():
            schema[db_name]['indexes'] = defaultdict(list)
            with open(idx_file) as f:
                reader = csv.DictReader(f, delimiter='\t')
                for row in reader:
                    schema[db_name]['indexes'][(row['TABLE_NAME'], row['INDEX_NAME'])].append(row)
        
        # Load foreign keys
        fk_file = db_dir / 'foreign_keys.tsv'
        if fk_file.exists():
            schema[db_name]['foreign_keys'] = []
            with open(fk_file) as f:
                reader = csv.DictReader(f, delimiter='\t')
                for row in reader:
                    schema[db_name]['foreign_keys'].append(row)
    
    return schema

def load_reference_schema(ref_dir):
    """Load reference schema from parse-dump-sections.py output."""
    schema = {}
    ref_path = Path(ref_dir)
    
    for tables_file in ref_path.glob('*_tables.txt'):
        db_name = tables_file.stem.replace('_tables', '')
        schema[db_name] = {'tables': {}, 'columns': {}}
        
        with open(tables_file) as f:
            for line in f:
                table = line.strip()
                if table:
                    schema[db_name]['tables'][table] = True
        
        # Load column info from individual .sql files
        schema[db_name]['columns'] = {}
        for sql_file in ref_path.glob(f"{db_name}_*.sql"):
            if sql_file.stem.endswith('_tables'):
                continue
            table_name = sql_file.stem.replace(f"{db_name}_", "")
            with open(sql_file) as f:
                content = f.read()
            
            # Parse columns from CREATE TABLE (simplified)
            # This is a basic parser - for production use a proper SQL parser
            col_pattern = r'`([^`]+)`\s+(\w+(?:\(\d+\))?)\s*(?:CHARACTER SET \w+)?\s*(?:COLLATE \w+)?\s*(?:NOT NULL|NULL)?\s*(?:DEFAULT [^,\n]+)?\s*(?:AUTO_INCREMENT)?\s*(?:COMMENT [^,\n]+)?'
            # Actually, let's do a simpler approach - extract column lines between parentheses
            lines = content.split('\n')
            in_columns = False
            for line in lines:
                line = line.strip().rstrip(',')
                if line.startswith('CREATE TABLE'):
                    in_columns = True
                    continue
                if in_columns:
                    if line.startswith(')') or line.startswith('PRIMARY KEY') or line.startswith('KEY ') or line.startswith('CONSTRAINT '):
                        continue
                    if not line or line.startswith('--'):
                        continue
                    # Parse column definition
                    parts = line.split()
                    if len(parts) >= 2:
                        col_name = parts[0].strip('`')
                        col_type = parts[1]
                        schema[db_name]['columns'][(table_name, col_name)] = {
                            'data_type': col_type,
                            'raw_line': line
                        }
    
    return schema

def compare_schemas(live, reference):
    """Compare live vs reference and return drift records."""
    drifts = []
    
    all_dbs = set(live.keys()) | set(reference.keys())
    
    for db in sorted(all_dbs):
        live_db = live.get(db, {'tables': {}, 'columns': {}})
        ref_db = reference.get(db, {'tables': {}, 'columns': {}})
        
        live_tables = set(live_db['tables'].keys())
        ref_tables = set(ref_db['tables'].keys())
        
        # Table-level drift
        for table in sorted(live_tables - ref_tables):
            drifts.append({
                'database': db,
                'table': table,
                'column': '',
                'drift_type': 'EXTRA_TABLE_IN_LIVE',
                'live_spec': 'EXISTS',
                'ref_spec': 'MISSING',
                'severity': 'INFO',
                'remediation': f'Document purpose; may be app enhancement'
            })
        
        for table in sorted(ref_tables - live_tables):
            drifts.append({
                'database': db,
                'table': table,
                'column': '',
                'drift_type': 'MISSING_TABLE_IN_LIVE',
                'live_spec': 'MISSING',
                'ref_spec': 'EXISTS',
                'severity': 'HIGH',
                'remediation': f'CREATE TABLE from reference or investigate why missing'
            })
        
        # Column-level drift for common tables
        common_tables = live_tables & ref_tables
        for table in sorted(common_tables):
            live_cols = {col for (t, col) in live_db['columns'].keys() if t == table}
            ref_cols = {col for (t, col) in ref_db['columns'].keys() if t == table}
            
            all_cols = live_cols | ref_cols
            
            for col in sorted(all_cols):
                live_key = (table, col)
                ref_key = (table, col)
                
                live_col = live_db['columns'].get(live_key)
                ref_col = ref_db['columns'].get(ref_key)
                
                if live_col and not ref_col:
                    drifts.append({
                        'database': db,
                        'table': table,
                        'column': col,
                        'drift_type': 'EXTRA_COLUMN_IN_LIVE',
                        'live_spec': f"{live_col['data_type']}({live_col['char_max_len'] or live_col['num_precision'] or ''})",
                        'ref_spec': 'MISSING',
                        'severity': 'INFO',
                        'remediation': 'Document; may be app enhancement'
                    })
                elif ref_col and not live_col:
                    drifts.append({
                        'database': db,
                        'table': table,
                        'column': col,
                        'drift_type': 'MISSING_COLUMN_IN_LIVE',
                        'live_spec': 'MISSING',
                        'ref_spec': f"{ref_col['data_type']}({ref_col.get('raw_line', '')})",
                        'severity': 'HIGH',
                        'remediation': f"ALTER TABLE `{db}`.`{table}` ADD COLUMN `{col}` {ref_col['data_type']} ..."
                    })
                elif live_col and ref_col:
                    # Compare specs
                    live_type = live_col['data_type'].lower()
                    ref_type = ref_col['data_type'].lower()
                    
                    live_len = live_col['char_max_len'] or live_col['num_precision'] or ''
                    ref_len = ref_col.get('char_max_len') or ref_col.get('num_precision') or ''
                    
                    # Normalize type names
                    type_map = {
                        'varchar': 'varchar', 'char': 'char', 'text': 'text',
                        'mediumtext': 'text', 'longtext': 'text', 'tinytext': 'text',
                        'int': 'int', 'tinyint': 'tinyint', 'smallint': 'smallint',
                        'bigint': 'bigint', 'datetime': 'datetime', 'date': 'date',
                        'blob': 'blob', 'mediumblob': 'blob', 'longblob': 'blob',
                    }
                    live_norm = type_map.get(live_type, live_type)
                    ref_norm = type_map.get(ref_type, ref_type)
                    
                    drift_type = None
                    severity = 'LOW'
                    
                    if live_norm != ref_norm:
                        drift_type = 'TYPE_MISMATCH'
                        severity = 'HIGH'
                    elif live_len and ref_len and live_len != ref_len:
                        # For varchar/char, compare lengths
                        if live_norm in ('varchar', 'char') and int(live_len) < int(ref_len):
                            drift_type = 'COLUMN_TOO_SMALL'
                            severity = 'HIGH'
                        elif live_norm in ('varchar', 'char') and int(live_len) > int(ref_len):
                            drift_type = 'COLUMN_LARGER_THAN_REF'
                            severity = 'LOW'
                    
                    if drift_type:
                        drifts.append({
                            'database': db,
                            'table': table,
                            'column': col,
                            'drift_type': drift_type,
                            'live_spec': f"{live_norm}({live_len})" if live_len else live_norm,
                            'ref_spec': f"{ref_norm}({ref_len})" if ref_len else ref_norm,
                            'severity': severity,
                            'remediation': generate_remediation(db, table, col, drift_type, live_norm, live_len, ref_norm, ref_len)
                        })
    
    return drifts

def generate_remediation(db, table, col, drift_type, live_type, live_len, ref_type, ref_len):
    if drift_type == 'COLUMN_TOO_SMALL':
        return f"ALTER TABLE `{db}`.`{table}` MODIFY `{col}` {ref_type}({ref_len});"
    elif drift_type == 'TYPE_MISMATCH':
        return f"ALTER TABLE `{db}`.`{table}` MODIFY `{col}` {ref_type}({ref_len or ''}); -- REVIEW: type change may lose data"
    elif drift_type == 'MISSING_COLUMN_IN_LIVE':
        return f"ALTER TABLE `{db}`.`{table}` ADD COLUMN `{col}` {ref_type}({ref_len or ''});"
    return 'MANUAL REVIEW REQUIRED'

def write_report(drifts, output_file=None):
    """Write drift report as CSV and Markdown table."""
    if not drifts:
        print("No drifts found!")
        return
    
    # Sort by severity then database/table/column
    severity_order = {'HIGH': 0, 'MEDIUM': 1, 'LOW': 2, 'INFO': 3}
    drifts.sort(key=lambda d: (severity_order.get(d['severity'], 99), d['database'], d['table'], d['column']))
    
    # CSV output
    if output_file:
        with open(output_file, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=drifts[0].keys())
            writer.writeheader()
            writer.writerows(drifts)
        print(f"CSV report written to {output_file}")
    
    # Markdown table to stdout
    print("\n## Schema Drift Report\n")
    print("| Database | Table | Column | Drift Type | Live Spec | Ref Spec | Severity | Remediation |")
    print("|----------|-------|--------|------------|-----------|----------|----------|-------------|")
    for d in drifts:
        print(f"| {d['database']} | {d['table']} | {d['column']} | {d['drift_type']} | {d['live_spec']} | {d['ref_spec']} | {d['severity']} | {d['remediation']} |")
    
    # Summary
    print(f"\n**Total drifts: {len(drifts)}**")
    for sev in ['HIGH', 'MEDIUM', 'LOW', 'INFO']:
        count = sum(1 for d in drifts if d['severity'] == sev)
        if count:
            print(f"  {sev}: {count}")

if __name__ == '__main__':
    if len(sys.argv) < 3:
        print("Usage: python3 diff-schemas.py <live_schema_dir> <reference_schema_dir> [output.csv]")
        sys.exit(1)
    
    live_dir = sys.argv[1]
    ref_dir = sys.argv[2]
    output_file = sys.argv[3] if len(sys.argv) > 3 else None
    
    print(f"Loading live schema from {live_dir}...")
    live = load_live_schema(live_dir)
    
    print(f"Loading reference schema from {ref_dir}...")
    reference = load_reference_schema(ref_dir)
    
    print("Comparing...")
    drifts = compare_schemas(live, reference)
    
    write_report(drifts, output_file)