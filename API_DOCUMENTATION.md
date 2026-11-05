# API Documentation

Base: `/api/v1`; interactive OpenAPI: `/docs`. JSON errors use FastAPI `detail`. Responses include `X-Correlation-ID`. Production requires `X-API-Key`; development without `TITAN_API_KEY` uses an explicit local principal.

## Main endpoints

| Area | Endpoints |
|---|---|
| System | `GET /system`, `/capabilities`, `/tools`, `/security/center`, `/audit` |
| Agents | `GET/POST /agents`; `POST /agents/{id}/test`, `/approve`; `GET /agents/{id}/tasks`; `POST /orchestrations`; `GET /orchestrations/{batch}` |
| Research | `GET /research/connectors`; `POST/GET /research/tasks`; `GET /research/tasks/{id}`; `GET .../report`; `POST .../convert/project|skill|agent` |
| Knowledge/memory | `POST /knowledge`; `GET /knowledge/search?q=`; `POST/GET /memory`; `DELETE /memory/{id}` |
| Skills | `GET/POST /skills`; `POST /skills/{id}/test|approve|disable|execute` |
| Workflows | `GET/POST /workflows`; `POST /workflows/{id}/runs`; `GET /workflows/runs/{id}`; `POST .../resume|cancel` |
| Models | `GET /models/providers`, `/models/evaluations`; `POST /translate`; `GET /voice/status` |
| Chat | `POST/GET /conversations`; `GET/PATCH/DELETE /conversations/{id}`; `GET .../export`; `POST .../messages`; `POST .../messages/stream` |
| Projects | `GET/POST /projects`; `GET /projects/{id}/files`; `GET/PUT /projects/{id}/file`; `POST /projects/{id}/builds`; `GET /builds/{id}` |
| Terminal | `POST /terminal/execute`; `GET /terminal/executions` |

## Examples

```bash
curl -X POST localhost:8000/api/v1/research/tasks \
  -H 'Content-Type: application/json' \
  -d '{"query":"langgraph in:name","connectors":["github"],"max_results":3,"wait":true}'

curl -X POST localhost:8000/api/v1/terminal/execute \
  -H 'Content-Type: application/json' \
  -d '{"project_id":"PROJECT_UUID","argv":["python3","src/main.py"],"approved":true,"timeout_seconds":10}'
```

Terminal approval is for the exact argv; shell strings are not accepted. SSE emits `data: {JSON}` events with `delta`, then `done`, or an error event. Mock results always contain `is_mock=true`.
