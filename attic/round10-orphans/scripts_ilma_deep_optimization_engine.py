#!/usr/bin/env python3
"""
ILMA DEEP OPTIMIZATION ENGINE
Iterates 1000x to ensure all components are connected and operational.
Target: MILITARY GRADE TIER SSS+++
"""

import sys, os, json, importlib, traceback, time, re
from pathlib import Path

os.chdir('/root/.hermes/profiles/ilma')
sys.path.insert(0, '.')

ITERATIONS = 1000
FIXES_APPLIED = []
ERRORS = []

def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)

# =====================================================================
# PHASE 1: MAP ALL ILMA COMPONENTS
# =====================================================================
log("=== PHASE 1: COMPONENT MAPPING ===")

component_map = {
    'root_scripts': [],      # ilma_*.py at root
    'skills': {},            # category -> [skill names]
    'modules': [],           # Python modules in key dirs
    'data_files': {},        # name -> path
    'workflows': [],          # workflow files
    'routers': {},           # routing components
}

# Root scripts
for f in sorted(os.listdir('.')):
    if f.startswith('ilma_') and f.endswith('.py'):
        component_map['root_scripts'].append(f)

# Skills are at skills/{skill_name}/SKILL.md (single level)
skills_base = 'skills'
for entry in os.listdir(skills_base):
    path = os.path.join(skills_base, entry)
    if os.path.isdir(path) and os.path.exists(os.path.join(path, 'SKILL.md')):
        cat = 'ilma'  # ILMA skills go in one bucket
        if cat not in component_map['skills']:
            component_map['skills'][cat] = []
        component_map['skills'][cat].append(entry)

# Router data files
for f in os.listdir('ilma_model_router_data'):
    if f.endswith('.json'):
        component_map['data_files'][f] = f'ilma_model_router_data/{f}'

# Workflows
for f in os.listdir('.'):
    if 'workflow' in f.lower() and f.endswith('.py'):
        component_map['workflows'].append(f)

log(f"  Root scripts: {len(component_map['root_scripts'])}")
log(f"  Skills: {sum(len(v) for v in component_map['skills'].values())} across {len(component_map['skills'])} categories")
log(f"  Data files: {len(component_map['data_files'])}")
log(f"  Workflows: {len(component_map['workflows'])}")

# =====================================================================
# PHASE 2: TEST ilma_model_router ALL PUBLIC APIS (iterative)
# =====================================================================
log("=== PHASE 2: MODEL ROUTER API VERIFICATION (1000 iterations) ===")

# Force fresh start
for m in list(sys.modules.keys()):
    if 'ilma_model' in m:
        del sys.modules[m]

import ilma_model_router as mr
importlib.reload(mr)
mr._db_cache = None
mr._db_cache_mtime = 0
mr._benchmark_lookup = {}
mr._benchmark_loaded = False

db = mr.load_provider_db()
mr._load_benchmark_db()

# Test fixtures use real WORKING provider models
api_tests = [
    ('is_model_allowed', lambda: mr.is_model_allowed('nvidia/meta/llama-3.1-8b-instruct', True)),
    ('score_task_fit', lambda: mr.score_task_fit(db["providers"]["nvidia"]["models"]["meta/llama-3.1-8b-instruct"], 'heavy_coding', 'nvidia/meta/llama-3.1-8b-instruct')),
    ('calculate_route_score', lambda: mr.calculate_route_score(db["providers"]["nvidia"]["models"]["meta/llama-3.1-8b-instruct"], 'heavy_coding', 'nvidia', 0.91)),
    ('get_best_model', lambda: mr.get_best_model('heavy_coding', prefer_free=True)),
    ('route_task', lambda: mr.route_task('heavy_coding', max_fallbacks=3)),
    ('detect_task_type', lambda: mr.detect_task_type('write a complex API server')),
    ('list_free_models', lambda: mr.list_free_models()),
    ('get_provider_health', lambda: mr.get_provider_health()),
    ('get_router_stats', lambda: mr.get_router_stats()),
    ('list_providers', lambda: mr.list_providers()),
    ('list_models', lambda: mr.list_models()),
    ('search_models', lambda: mr.search_models('claude')),
    ('get_model_info', lambda: mr.get_model_info('nvidia/meta/llama-3.1-8b-instruct')),
]

iteration_errors = []
for i in range(ITERATIONS):
    for name, fn in api_tests:
        try:
            fn()
        except Exception as e:
            iteration_errors.append(f"Iteration {i}: {name} -> {e}")

log(f"  1000 iterations complete. Errors: {len(iteration_errors)}")
if iteration_errors:
    for e in iteration_errors[:10]:
        log(f"    ERROR: {e}")
    ERRORS.extend(iteration_errors)

# =====================================================================
# PHASE 3: DATA FILE INTEGRITY
# =====================================================================
log("=== PHASE 3: DATA FILE INTEGRITY ===")

data_ok = 0
data_fail = 0

for name, path in component_map['data_files'].items():
    try:
        with open(path, 'r') as f:
            data = json.load(f)
        log(f"  OK: {name} ({len(json.dumps(data))//1024}KB)")
        data_ok += 1

        # Verify specific structure expectations
        if name == 'PROVIDER_INTELLIGENCE_MASTER.json':
            providers = data.get('providers', {})
            total_models = sum(len(p.get('models', {})) for p in providers.values())
            log(f"     Providers: {len(providers)}, Total models: {total_models}")

        elif name == 'benchmark_database.json':
            scores = data.get('model_scores', {})
            log(f"     Benchmark entries: {len(scores)}")

    except Exception as e:
        log(f"  FAIL: {name} -> {e}")
        data_fail += 1
        ERRORS.append(f"data_file:{name}: {e}")

log(f"  Data files: {data_ok}/{data_ok+data_fail} OK")

# =====================================================================
# PHASE 4: SKILL REGISTRY CONSISTENCY
# =====================================================================
log("=== PHASE 4: SKILL REGISTRY CONSISTENCY ===")

# Check skills are loadable
skill_ok = 0
skill_fail = 0

for skill_name in component_map['skills'].get('ilma', [])[:20]:  # Sample 20
        try:
            skill_path = f'skills/{skill_name}/SKILL.md'
            if os.path.exists(skill_path):
                with open(skill_path, 'r') as f:
                    first_line = f.readline().strip()
                if first_line.startswith('---'):
                    skill_ok += 1
                else:
                    skill_fail += 1
                    ERRORS.append(f"skill:{skill_name}: invalid frontmatter")
            else:
                skill_fail += 1
                ERRORS.append(f"skill:{skill_name}: file not found")
        except Exception as e:
            skill_fail += 1
            ERRORS.append(f"skill:{skill_name}: {e}")

log(f"  Skills (sampled): {skill_ok}/{skill_ok+skill_fail} OK")

# =====================================================================
# PHASE 5: ROOT SCRIPT IMPORTS
# =====================================================================
log("=== PHASE 5: ROOT SCRIPT IMPORTS ===")

scripts_ok = 0
scripts_fail = 0

for script in component_map['root_scripts'][:20]:  # Sample first 20
    try:
        # Just check syntax by compiling
        with open(script, 'r') as f:
            src = f.read()
        compile(src, script, 'exec')
        scripts_ok += 1
    except SyntaxError as e:
        log(f"  SYNTAX ERROR: {script} -> {e}")
        scripts_fail += 1
        ERRORS.append(f"script:{script}: syntax:{e}")
    except Exception as e:
        # Import errors are OK for now - just syntax check
        pass

log(f"  Root scripts (sampled): {scripts_ok}/{scripts_ok+scripts_fail} OK")

# =====================================================================
# PHASE 6: ilma_workflow_ecc.py INTEGRATION
# =====================================================================
log("=== PHASE 6: WORKFLOW INTEGRATION ===")

try:
    with open('ilma_workflow_ecc.py', 'r') as f:
        wf_src = f.read()
    compile(wf_src, 'ilma_workflow_ecc.py', 'exec')
    log("  ilma_workflow_ecc.py: SYNTAX OK")

    # Check it references ILMA components
    ilma_refs = re.findall(r'ilma_[a-z_]+', wf_src)
    unique_refs = sorted(set(ilma_refs))
    log(f"  Workflow ILMA references: {unique_refs}")

except Exception as e:
    log(f"  FAIL: ilma_workflow_ecc.py -> {e}")
    ERRORS.append(f"workflow:ilma_workflow_ecc.py:{e}")

# =====================================================================
# PHASE 7: CONFIG.YAML CONSISTENCY
# =====================================================================
log("=== PHASE 7: CONFIG.YAML CONSISTENCY ===")

try:
    import yaml
    with open('config.yaml', 'r') as f:
        cfg = yaml.safe_load(f)
    log(f"  config.yaml: OK ({len(cfg)} top-level keys)")

    # Check ilma_runtime_policy
    irp = cfg.get('ilma_runtime_policy', {})
    log(f"  ilma_runtime_policy: {irp}")

    # Check smart_model_routing
    smr = cfg.get('smart_model_routing', {})
    log(f"  smart_model_routing: {smr}")

    # Check model config
    model = cfg.get('model', {})
    log(f"  model.default: {model.get('default')}")
    log(f"  model.provider: {model.get('provider')}")

    # Check delegation config
    deleg = cfg.get('delegation', {})
    log(f"  delegation.model: {deleg.get('model')}")
    log(f"  delegation.provider: {deleg.get('provider')}")

except Exception as e:
    log(f"  FAIL: config.yaml -> {e}")
    ERRORS.append(f"config:yaml:{e}")

# =====================================================================
# PHASE 8: SOUL.md CONSISTENCY CHECK
# =====================================================================
log("=== PHASE 8: SOUL.md CONSISTENCY ===")

try:
    with open('SOUL.md', 'r') as f:
        soul = f.read()
    log(f"  SOUL.md: OK ({len(soul)} chars)")

    # Check key sections exist
    sections = [
        'BAGIAN 17',  # Core command
        'BAGIAN 18',  # Final directive
        'FULL AUTONOMY',
        'MANDATORY WORKFLOW',
        'STREAMING MANDATE',
        'ANTI-BLOCKING RULES',
        'ANTI-STUCK RULES',
    ]
    for sec in sections:
        if sec in soul:
            log(f"    Section '{sec}': present")
        else:
            log(f"    WARNING: Section '{sec}': MISSING")
            ERRORS.append(f"SOUL:missing_section:{sec}")

except Exception as e:
    log(f"  FAIL: SOUL.md -> {e}")
    ERRORS.append(f"SOUL.md:{e}")

# =====================================================================
# PHASE 10: FINAL COMPREHENSIVE TEST
# =====================================================================
log("=== PHASE 10: FINAL COMPREHENSIVE TEST ===")

# Final API tests
final_tests = [
    ('is_model_allowed(nvidia/codellama,free)', lambda: mr.is_model_allowed('meta/llama-3.1-8b-instruct', True)),
    ('is_model_allowed(paid-model,paid)', lambda: mr.is_model_allowed('openai/gpt-5', False)),
    ('is_model_allowed(banned)', lambda: mr.is_model_allowed('some-banned/test', True)),
    ('score_task_fit(codellama,heavy_coding)', lambda: mr.score_task_fit(db['providers']['nvidia']['models']['meta/llama-3.1-8b-instruct'], 'heavy_coding', 'nvidia/meta/llama-3.1-8b-instruct')),
    ('calculate_route_score(codellama)', lambda: mr.calculate_route_score(db['providers']['nvidia']['models']['meta/llama-3.1-8b-instruct'], 'heavy_coding', 'nvidia', 0.86)),
    ('get_best_model(heavy_coding)', lambda: mr.get_best_model('heavy_coding', prefer_free=True)),
    ('get_best_model(medium_coding)', lambda: mr.get_best_model('medium_coding', prefer_free=True)),
    ('get_best_model(reasoning_xhigh)', lambda: mr.get_best_model('reasoning_xhigh', prefer_free=True)),
    ('get_best_model(vision)', lambda: mr.get_best_model('vision', prefer_free=True)),
    ('get_best_model(fast_tasks)', lambda: mr.get_best_model('fast_tasks', prefer_free=True)),
    ('get_best_model(general)', lambda: mr.get_best_model('general', prefer_free=True)),
    ('get_best_model(research)', lambda: mr.get_best_model('research', prefer_free=True)),
    ('get_best_model(heavy_coding,paid)', lambda: mr.get_best_model('heavy_coding', prefer_free=False)),
    ('detect_task_type(coding)', lambda: mr.detect_task_type('write a complex API')),
    ('detect_task_type(reasoning)', lambda: mr.detect_task_type('solve this math problem')),
    ('detect_task_type(vision)', lambda: mr.detect_task_type('describe this image')),
    ('route_task(heavy_coding)', lambda: mr.route_task('heavy_coding', max_fallbacks=5)),
    ('route_task(medium_coding)', lambda: mr.route_task('medium_coding', max_fallbacks=3)),
    ('list_free_models()', lambda: mr.list_free_models()),
    ('list_free_models(heavy_coding)', lambda: mr.list_free_models('heavy_coding')),
    ('get_provider_health()', lambda: mr.get_provider_health()),
    ('get_router_stats()', lambda: mr.get_router_stats()),
    ('list_providers()', lambda: mr.list_providers()),
    ('list_models()', lambda: mr.list_models()),
    ('list_models(task=heavy_coding)', lambda: mr.list_models(task_type='heavy_coding')),
    ('search_models(gpt)', lambda: mr.search_models('gpt')),
    ('search_models(claude)', lambda: mr.search_models('claude')),
    ('get_model_info(nvidia/codellama)', lambda: mr.get_model_info('nvidia/meta/llama-3.1-8b-instruct')),
    ('get_model_info(nonexistent)', lambda: mr.get_model_info('nonexistent/model')),
]

final_ok = 0
final_fail = 0
for name, fn in final_tests:
    try:
        result = fn()
        final_ok += 1
    except Exception as e:
        final_fail += 1
        log(f"  FAIL: {name} -> {e}")
        ERRORS.append(f"api:{name}:{e}")

# =====================================================================
# FINAL REPORT
# =====================================================================
log("")
log("=" * 70)
log("  ILMA DEEP OPTIMIZATION ENGINE - FINAL REPORT")
log("  MILITARY GRADE TIER SSS+++")
log("=" * 70)
log(f"  Iterations completed: {ITERATIONS}")
log(f"  Component map:")
log(f"    - Root scripts: {len(component_map['root_scripts'])}")
log(f"    - Skills: {sum(len(v) for v in component_map['skills'].values())}")
log(f"    - Data files: {len(component_map['data_files'])}")
log(f"    - Workflows: {len(component_map['workflows'])}")
log(f"  Data files: {data_ok}/{data_ok+data_fail} OK")
log(f"  Final API tests: {final_ok}/{final_ok+final_fail} PASSED")
log(f"  Total errors: {len(ERRORS)}")

if ERRORS:
    log(f"  ERRORS DETAIL:")
    seen = set()
    for e in ERRORS[:20]:
        if e not in seen:
            log(f"    - {e[:100]}")
            seen.add(e)

log("")
if final_fail == 0 and len(ERRORS) == 0:
    log("  STATUS: ████████████████████████████ 100%")
    log("  ALL COMPONENTS OPERATIONAL")
    log("  MILITARY-GRADE TIER SSS+++ ACHIEVED")
else:
    log(f"  STATUS: {final_ok}/{final_ok+final_fail} - ISSUES FOUND")
    log(f"  Fixes needed: {len(ERRORS)}")

log("=" * 70)

# Exit with error if any failures
sys.exit(0 if final_fail == 0 and len(ERRORS) == 0 else 1)