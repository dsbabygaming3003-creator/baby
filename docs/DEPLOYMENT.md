# DEPLOYMENT

---

## 1. Topology

```
                       ┌──────────────────────────┐
   Android client ────▶│  reverse proxy (TLS)     │
   (HTTPS + SSE + WS)  │  nginx / Caddy / Cloudflare│
                       └────────────┬─────────────┘
                                    │
                       ┌────────────▼─────────────┐
                       │  uvicorn titan.main:app   │
                       │  0.0.0.0:8000             │
                       └──────┬───────────┬────────┘
                              │           │
                   ┌──────────▼───┐   ┌───▼──────────────┐
                   │ PostgreSQL   │   │ filesystem / S3  │
                   │ (or SQLite)  │   │ reports, artifacts│
                   └──────────────┘   └──────────────────┘
```

The app itself serves CORS for all origins by default; **restrict `cors_origins`** in any
real deployment.

---

## 2. Environment variables

| Variable | Required | Default | Notes |
|---|---|---|---|
| `TITAN_JWT_SECRET` | **yes in production** | dev default | rotates all sessions |
| `TITAN_DATABASE_URL` | for Postgres | SQLite file | `postgresql+asyncpg://…` |
| `TITAN_DATA_DIR` | no | `<repo>/data` | reports, artifacts |
| `TITAN_SANDBOX_ROOT` | no | `/tmp/titan-sandbox` | isolated per project |
| `TITAN_TOOLCHAIN_DIR` | no | `/opt/titan/toolchain` | Android build tools |
| `TITAN_EGRESS_ALLOWLIST` | recommended | empty (public hosts only) | comma-separated hosts |
| `OPENAI_API_KEY` / `ANTHROPIC_API_KEY` / `GEMINI_API_KEY` / `GROQ_API_KEY` / `HUGGINGFACE_API_KEY` | to use real models | unset | server-side only |
| `TITAN_RATE_LIMIT_PER_MINUTE` | no | 120 | see `config.py` |

---

## 3. Running

```bash
cd backend
/opt/titan/venv/bin/python -m uvicorn titan.main:app --host 0.0.0.0 --port 8000 --workers 1
```

> Use **one worker** with the SQLite profile: the in-process rate limiter, the WebSocket
> broker and the sandbox supervisor are per-process. For multiple workers, switch to
> Postgres and move the rate limiter and broker to Redis (documented as a scale-out step,
> not implemented here).

Behind a reverse proxy, the SSE and WebSocket routes need buffering disabled:

```nginx
location /api/v1/chat/stream { proxy_buffering off; proxy_read_timeout 3600s; }
location /ws/              { proxy_http_version 1.1; proxy_set_header Upgrade $http_upgrade;
                            proxy_set_header Connection "upgrade"; }
```

---

## 4. Cloudflare target stack

The brief named Cloudflare Workers / D1 / R2 / Queues / Durable Objects. That is a
**deployment target**, not what this build runs:

| Cloudflare service | TITAN equivalent | Migration note |
|---|---|---|
| D1 | SQLite now, Postgres target | **D1 is not PostgreSQL** — no server-side enums, no `asyncpg` dialect, limited index support. The SQLAlchemy models are portable, but the D1 dialect needs an adapter layer. |
| R2 | local `data/` directory | object storage for attachments and build artifacts |
| Queues | `agent_tasks` / `workflow_runs` tables | queue semantics over the existing task tables |
| Durable Objects | in-process WebSocket broker | move the broker into a Durable Object for multi-region fan-out |
| Workers | the FastAPI app | not a drop-in: Workers run V8 isolates, FastAPI needs a Python runtime — an external origin (or a Python Workers runtime) is required |
| AI Gateway | the native gateway in `services/gateway.py` | the native gateway already does routing, retries, fallback and cost accounting |

---

## 5. Production checklist

- [ ] set `TITAN_JWT_SECRET` to a strong random value
- [ ] move to Postgres and set `TITAN_DATABASE_URL`
- [ ] restrict `cors_origins` to the client origins
- [ ] set `TITAN_EGRESS_ALLOWLIST`
- [ ] provision provider keys **on the server only**
- [ ] put the app behind TLS termination
- [ ] schedule database backups
- [ ] keep `command_allowlist` minimal for the workload
- [ ] run `verification/run_acceptance.py` against the deployment before promotion
