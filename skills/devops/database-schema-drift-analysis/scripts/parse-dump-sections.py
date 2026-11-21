#!/usr/bin/env python3
# parse-dump-sections.py — Split multi-DB dump into per-DB CREATE TABLE lists
# Usage: python3 parse-dump-sections.py /path/to/dump.sql [output_dir]

import re
import sys
import os
from pathlib import Path

def parse_dump(dump_path, output_dir=None):
    with open(dump_path, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()

    # Split by "Current Database" comments
    # Pattern: --\n-- Current Database: `db_name`
    sections = re.split(r'--\s*\n--\s*Current Database:\s*`([^`]+)`', content)
    
    # sections[0] = preamble (before first DB)
    # Then alternating: db_name, content, db_name, content...
    
    results = {}
    
    if output_dir:
        Path(output_dir).mkdir(parents=True, exist_ok=True)
    
    for i in range(1, len(sections), 2):
        db_name = sections[i].strip()
        sql_content = sections[i+1] if i+1 < len(sections) else ''
        
        # Extract CREATE TABLE statements
        tables = re.findall(r'CREATE TABLE `([^`]+)`', sql_content)
        
        # Also extract full CREATE TABLE blocks for each table
        table_blocks = {}
        for match in re.finditer(r'(CREATE TABLE `[^`]+` \(.*?\n\) ENGINE=\w+)', sql_content, re.DOTALL):
            block = match.group(1)
            table_name = re.search(r'CREATE TABLE `([^`]+)`', block).group(1)
            table_blocks[table_name] = block
        
        results[db_name] = {
            'table_count': len(tables),
            'tables': sorted(tables),
            'blocks': table_blocks
        }
        
        print(f"{db_name}: {len(tables)} tables")
        for t in sorted(tables):
            print(f"  {t}")
        
        if output_dir:
            # Write table list
            with open(Path(output_dir) / f"{db_name}_tables.txt", 'w') as f:
                f.write('\n'.join(sorted(tables)))
            
            # Write full CREATE TABLE blocks
            for table_name, block in table_blocks.items():
                safe_name = table_name.replace('/', '_')
                with open(Path(output_dir) / f"{db_name}_{safe_name}.sql", 'w') as f:
                    f.write(block)
    
    return results

def compare_dbs(results, db1, db2):
    """Compare two databases from parsed results."""
    t1 = set(results.get(db1, {}).get('tables', []))
    t2 = set(results.get(db2, {}).get('tables', []))
    
    print(f"\n=== {db1} vs {db2} ===")
    print(f"Only in {db1}: {sorted(t1 - t2)}")
    print(f"Only in {db2}: {sorted(t2 - t1)}")
    print(f"Common: {sorted(t1 & t2)}")

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python3 parse-dump-sections.py <dump.sql> [output_dir]")
        sys.exit(1)
    
    dump_path = sys.argv[1]
    output_dir = sys.argv[2] if len(sys.argv) > 2 else None
    
    results = parse_dump(dump_path, output_dir)
    
    # If we have both live DB names from JIBAS, offer comparison
    if 'jbsakad' in results and 'jbssat' in results:
        compare_dbs(results, 'jbsakad', 'jbssat')