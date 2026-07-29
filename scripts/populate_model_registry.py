#!/usr/bin/env python3
"""Populate model_registry.db from PROVIDER_INTELLIGENCE_MASTER.json"""

import json
import sqlite3

with open('/root/.hermes/profiles/ilma/ilma_model_router_data/PROVIDER_INTELLIGENCE_MASTER.json') as f:
    data = json.load(f)

conn = sqlite3.connect('/root/.hermes/profiles/ilma/ilma_model_router_data/model_registry.db')
cur = conn.cursor()

# Clear existing - using DROP/CREATE to avoid DELETE without WHERE
cur.execute('DROP TABLE IF EXISTS providers')
cur.execute('DROP TABLE IF EXISTS model_ids')
cur.execute('DROP TABLE IF EXISTS subagent_routes')

# providers table
cur.execute('''
CREATE TABLE providers (
    provider_id TEXT PRIMARY KEY,
    display_name TEXT,
    source_type TEXT,
    trust_level INTEGER DEFAULT 5,
    health_score INTEGER DEFAULT 50,
    last_verified TEXT,
    stale_status TEXT,
    notes TEXT,
    api_key_present INTEGER DEFAULT 0,
    api_key_source TEXT
)
''')

# model_ids table
cur.execute('''
CREATE TABLE model_ids (
    canonical_model_id TEXT PRIMARY KEY,
    provider TEXT,
    provider_model_id TEXT,
    display_name TEXT,
    free_or_paid TEXT,
    availability_status TEXT,
    allowed_by_policy INTEGER DEFAULT 1,
    context_window INTEGER,
    max_output_tokens INTEGER,
    modality TEXT,
    supports_tools INTEGER DEFAULT 0,
    supports_json INTEGER DEFAULT 0,
    supports_vision INTEGER DEFAULT 0,
    supports_long_context INTEGER DEFAULT 0,
    quality_score REAL,
    coding_score REAL,
    reasoning_score REAL,
    tool_use_score REAL,
    specialization TEXT,
    last_verified TEXT,
    benchmark_coverage TEXT,
    caveat TEXT
)
''')

# subagent_routes table
cur.execute('''
CREATE TABLE subagent_routes (
    role TEXT,
    task_key TEXT,
    route TEXT
)
''')

cur.execute('CREATE INDEX IF NOT EXISTS idx_subagent_role_task ON subagent_routes(role, task_key)')

providers = data.get('providers', {})
total_models = 0

for pid, pdata in providers.items():
    # Insert provider
    cur.execute('''
    INSERT OR REPLACE INTO providers 
    (provider_id, display_name, source_type, trust_level, health_score, last_verified, stale_status, notes, api_key_present, api_key_source)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (pid, pdata.get('provider_info', {}).get('name', pid), 'NATIVE', 5, 
          50 if pdata.get('status') == 'active' else 0, None, 'unknown', '', 1, 'env'))
    
    models = pdata.get('models', {})
    for mid, mdata in models.items():
        if not isinstance(mdata, dict):
            continue
            
        cur.execute('''
        INSERT OR REPLACE INTO model_ids
        (canonical_model_id, provider, provider_model_id, display_name, free_or_paid, availability_status, allowed_by_policy, 
         context_window, max_output_tokens, modality, supports_tools, supports_json, supports_vision, supports_long_context,
         quality_score, coding_score, reasoning_score, tool_use_score, specialization, last_verified, benchmark_coverage, caveat)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (mid, pid, mdata.get('model_id', mid), mdata.get('name', mid),
              'FREE' if mdata.get('is_free', False) or mdata.get('free_tier', False) else 'PAID',
              'ACTIVE' if mdata.get('is_active', True) and not mdata.get('disabled', False) else 'INACTIVE',
              1 if not mdata.get('disabled', False) else 0,
              mdata.get('context_window', mdata.get('context_length', 4096)),
              mdata.get('max_tokens', 4096),
              'text',
              1 if mdata.get('capabilities') and 'tool' in str(mdata.get('capabilities', [])).lower() else 0,
              1, 0, 0,
              mdata.get('quality_score', 0.5),
              mdata.get('scores', {}).get('coding', 0.0) if isinstance(mdata.get('scores'), dict) else 0.0,
              mdata.get('scores', {}).get('reasoning', 0.0) if isinstance(mdata.get('scores'), dict) else 0.0,
              mdata.get('scores', {}).get('tool_use', 0.0) if isinstance(mdata.get('scores'), dict) else 0.0,
              mdata.get('specialization', 'general'),
              mdata.get('last_verified', mdata.get('refreshed_at', None)),
              'enriched', ''))
        total_models += 1

conn.commit()
print(f'Inserted {len(providers)} providers and {total_models} models')
conn.close()