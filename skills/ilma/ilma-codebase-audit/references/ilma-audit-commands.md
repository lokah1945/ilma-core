# ILMA Audit Command Bank

Verified-working commands from the 2026-07-09 full audit. Run from `/root/.hermes/profiles/ilma`.

## Boot & Wiring
```bash
python3 ilma.py --status
python3 ilma_runtime_wiring.py --verify
python3 ilma_orphan_wiring.py --verify
git status --short
```

## Syntax sweep (all root modules)
```bash
python3 -m py_compile ilma_*.py && echo "SYNTAX OK"
python3 -c "import py_compile,glob; errs=[f for f in glob.glob('ilma_*.py') if (lambda: (__import__('io'),False)[1])() or _bad(f)][0] if False else None"
# simpler robust version:
python3 - <<'PY'
import py_compile, glob
bad=[f for f in glob.glob('ilma_*.py') if (lambda f: (py_compile.compile(f,doraise=True),False)[1] if False else False)(f)]
errs=[]
for f in glob.glob('ilma_*.py'):
    try: py_compile.compile(f, doraise=True)
    except py_compile.PyCompileError as e: errs.append((f,str(e)[:80]))
print('modules:',len(glob.glob('ilma_*.py')),'| syntax errors:',len(errs))
for e in errs: print(e)
PY
```

## Bug-class greps (run per layer)
```bash
# Duplicate dict key (manual review of flagged dicts)
grep -n '"is_free"' ilma_model_router.py
# Missing module imports
grep -rn "from ilma_learning_memory import" --include=*.py .
# JSON trailing comma / validity
python3 -c "import json; json.load(open('ilma_integration_manifest.json'))"
# Bare except
grep -rn "except Exception:" ilma_two_way_sync.py ilma_subagent_router.py ilma_health_manager.py
grep -rn "except:" ilma_autonomous_loop_engine.py
```

## E2E proofs
```bash
# Router + execution
python3 -c "from ilma_subagent_router import SubAgentRouter; r=SubAgentRouter(); d=r.route_and_execute('Write exactly 5 words','writing task',thinking='off',allow_paid=False,stateless=True); print('success:',d.get('success'),'| content:',repr(d.get('content'))[:60])"
# Workflow 8-step
python3 ilma_workflow_ecc.py --task "audit probe"
# Autonomous loop (correct class name: AutonomousLoopEngine, NOT ILMAAutonomousLoopEngine)
python3 -c "import ilma_autonomous_loop_engine as A; print(A.AutonomousLoopEngine().run_cycle(task='x').get('state'))"
# Capability registry (correct API: reg.get(name), NOT get_capability)
python3 -c "import ilma_capability_registry as C; r=C.CapabilityRegistry(); r.initialize(); print('caps:',len(r.get_all()))"
# Mongo/SOT live
python3 scripts/ilma_two_way_sync.py --status
# Browser CDP
curl -s http://127.0.0.1:9222/json/version | head
systemctl --user is-active ilma-chrome@lokah2150.service
```

## Cron state
```bash
cat cron/jobs.json | python3 -c "import json,sys; d=json.load(sys.stdin); [print(j.get('id'),j.get('name'),'| state=',j.get('state'),'| err=',(j.get('error') or '')[:60]) for j in (d if isinstance(d,list) else d.get('jobs',[]))]"
```
