# Freelance Platform Research — 2026-11-25 Session

## Executive Summary

Conducted live browser-based research across 12 major freelance platforms using ILMA's custom CDP browser runtime. Identified 6 platforms directly accessible via CDP, 6 blocked by Cloudflare/PX challenges.

## Platform Access Matrix

| Platform | URL | Cloudflare | CDP Status | Jobs Found | Notes |
|----------|-----|------------|------------|------------|-------|
| Freelancer.com | freelancer.com/jobs/python/ | No | ✅ Full | 144 (30 automation) | Best volume, verified clients |
| Guru.com | guru.com/d/jobs/skill/python | No | ✅ Full | 9 | Less competition, flexible pricing |
| PeoplePerHour | peopleperhour.com/freelance-jobs/python | No | ✅ Full | 300+ | UK/EU focused, "Opportunity" tags |
| RemoteOK | remoteok.com/remote-dev+python-jobs | No | ✅ Full | 91 | Remote-first, salary transparent |
| Python.org Jobs | python.org/jobs/ | No | ✅ Full | 22 | Official board, quality curated |
| Sribu | sribu.com/id (search: python developer) | No | ✅ Full | 8 services | Indonesian, service-model not job-board |
| Upwork | upwork.com/nx/search/jobs/?q=python | Yes | ❌ Blocked | — | Requires login + session cookies |
| Fiverr | fiverr.com/search/gigs?query=python | Yes | ❌ Blocked | — | PX challenge (press & hold) |
| Toptal | toptal.com/developers | Yes | ❌ Blocked | — | Screening + Cloudflare |
| WeWorkRemotely | weworkremotely.com/remote-jobs/search?term=python | Yes | ❌ Blocked | — | Cloudflare challenge |
| Projects.co.id | projects.co.id/ | Yes | ❌ Blocked | — | Cloudflare challenge |
| PythonJobs.github.io | pythonjobs.github.io/ | No | ✅ Full | ~6 | Static, outdated (2021-2022) |

## ILMA Capability → Job Mapping

### Tier 1: Direct Capability Match (Can Execute Independently)

| Capability Cluster | Platform | Sample Jobs | Est. Rate |
|-------------------|----------|-------------|-----------|
| AI Automation (n8n/Make/Python) | Freelancer | AI Automation Developer Partner ($151 avg), Sales Lead Automation ($418) | $150-500/project |
| Web Scraping & Data Extraction | Freelancer | LinkedIn Lead Gen ($404), Amazon Repricing ($217) | $200-500/project |
| Async Backend APIs (FastAPI/httpx) | Guru | Async API Client & Monitor (86 quotes) | $50-150/hr |
| ML Model Deployment | RemoteOK, Python.org | Senior Applied AI Engineer, Data/ML Engineer | $80-180k/yr |
| Browser Automation & Testing | Freelancer, Sribu | AI Chatbot testing, Custom automation | $10-50/hr |

### Tier 2: Partial Match (Need Some Setup)

| Capability | Platform | Gap |
|------------|----------|-----|
| Odoo/ERP Python | Sribu | Need Odoo-specific knowledge |
| Desktop Apps (PyQt/Tkinter) | Sribu | Packaging/distribution setup |
| Custom GPT/AI Bot | Sribu | Need OpenAI API keys |

## Recommended Strategy for ILMA

### Phase 1: Establish Presence (Week 1-2)
1. Create profiles on **Freelancer.com**, **Guru.com**, **PeoplePerHour** (accessible)
2. Build portfolio: 3-5 live demos (scraper, API, automation workflow)
3. Set up monitoring cron for new job posts

### Phase 2: Targeted Applications (Week 2-4)
1. Focus on **AI Automation** and **Web Scraping** categories (highest ILMA fit)
2. Use proposal templates customized per category
3. Track applications in local DB

### Phase 3: Scale (Month 2+)
1. Add RemoteOK for full-time remote if desired
2. Consider Upwork/Fiverr after manual account setup
3. Build reputation → higher rates, repeat clients

## Technical Notes for Future Sessions

### Browser Automation Commands Used
```python
# Start browser service
systemctl --user restart ilma-chrome.service
curl -s http://127.0.0.1:9222/json/version

# Navigate and extract
browser_navigate(url="https://freelancer.com/jobs/python/")
browser_snapshot(full=True)
browser_type(ref="@searchbox", text="python automation")
browser_press(key="Enter")
```

### Chrome Binary Version Fix (Encountered)
Playwright updated Chromium from v1228 to v1255. Systemd service path was stale.
```bash
sed -i 's|chromium_headless_shell-1228|chromium_headless_shell-1255|' /root/.config/systemd/user/ilma-chrome.service
systemctl --user daemon-reload && systemctl --user restart ilma-chrome.service
```

### Cloudflare Bypass Patterns
- **Not feasible** via headless CDP alone
- **Workaround**: Manual login in headed browser → export cookies → reuse in CDP session
- **Alternative**: Use accessible platforms (Freelancer, Guru, RemoteOK) as primary

## Evidence IDs
- ILMA-EVID-20261125-FREELANCE-RESEARCH-001 — Platform access matrix
- ILMA-EVID-20261125-BROWSER-FIX-001 — Chrome version mismatch fix
- ILMA-EVID-20261125-CAPABILITY-MAP-001 — ILMA capability to job mapping

## Next Research Triggers
- User asks: "apply to freelance jobs", "create proposal", "monitor new postings"
- New platform to evaluate
- Rate card analysis for specific category