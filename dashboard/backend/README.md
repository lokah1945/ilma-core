# ILMA Web Observability Dashboard — Backend

## Stack
- **Python 3.11+** with FastAPI
- **SQLModel** (SQLAlchemy + Pydantic v2)
- **SQLite** (local-first, PostgreSQL-compatible schema)
- **Uvicorn** ASGI server

## Installation

```bash
cd /root/.hermes/profiles/ilma/dashboard/backend
pip install -r requirements.txt
```

## Run

```bash
# Start server
python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000

# Or use the script
bash ../../scripts/run_dashboard_backend.sh
```

## Database

- Location: `/root/.hermes/profiles/ilma/data/ilma_dashboard.db`
- Auto-created on first run
- Schema: 11 tables (providers, model_ids, benchmark_records, token_usage_events, etc.)

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/health` | Health check |
| GET | `/api/overview` | Dashboard summary stats |
| GET | `/api/providers` | List all providers |
| GET | `/api/providers/{id}` | Provider detail with models |
| GET | `/api/models` | List all models (filterable) |
| GET | `/api/models/{id}` | Model detail |
| GET | `/api/models/{id}/benchmarks` | Benchmarks for model |
| GET | `/api/models/{id}/usage` | Token usage for model |
| GET | `/api/benchmarks` | All benchmark records |
| GET | `/api/specializations` | Task category → route mapping |
| GET | `/api/routing/subagents` | Sub-agent route chains |
| GET | `/api/workflows` | Workflow definitions |
| GET | `/api/pipelines` | Pipeline definitions |
| GET | `/api/evidence` | Evidence ledger |
| GET | `/api/capabilities` | Capability registry |
| GET | `/api/refresh-jobs` | Refresh job status |
| POST | `/api/refresh/ingest` | Re-ingest all sources |
| POST | `/api/refresh/validate` | Run ilma.py validate + doctor |

## Docs

- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

## Security

- CORS restricted to localhost:3000
- No API keys or secrets exposed
- Read-only from data sources

## Data Sources Ingested

1. `model_specialization_database.json` (1088 models)
2. Bridge models (Qwen 19 + Arena 155 + Use.ai 22 = 196)
3. `ilma_benchmark.db` (live benchmark runs)
4. `ilma_capability_registry.py` (1169 capabilities)
5. `ILMA_EVIDENCE_LEDGER_2026-05-07.md` (evidence records)
6. `CAPABILITY_MODEL_PREFERENCE` (routing policy)
7. Workflow definitions from `ilma_workflow_ecc.py`