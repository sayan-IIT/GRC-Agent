# AI-Powered GRC Risk Intelligence Platform
https://www.loom.com/share/82e828a2431c4e87af55e88623fb8167


Production-grade demo system for a GRC risk workflow with real CrustData ingestion, Kafka/Redpanda streaming, LangGraph agents, Postgres persistence, and a Next.js investor demo UI.

## What It Demonstrates

- Real async CrustData API call using `CRUSTDATA_API_KEY`
- Explicit API headers, request URL logging, parsed response handling, and success/failure logs
- Fallback mock path with the required log line: `Fallback to mock due to API failure`
- Kafka topic `risk_signals` via Redpanda, with `/events` webhook fallback
- Four-agent LangGraph workflow: Signal, Scoring, Explanation, Audit
- Human-in-the-loop approve/reject APIs that never overwrite `current_score` until approval
- Audit logs citing CrustData API signals

## Run

1. Create an environment file:

```bash
cp .env.example .env
```

2. Edit `.env` and set:

```bash
CRUSTDATA_API_KEY=your_real_key
```

The default CrustData URL is:

```bash
CRUSTDATA_BASE_URL=https://api.crustdata.com/screener/company
```

3. Start the full system:

```bash
docker-compose up --build
```

4. Open:

- Frontend: http://localhost:3000
- Backend: http://localhost:8000/health

## Demo Flow

1. Open the dashboard.
2. Confirm the live source badge: `Source: CrustData API`.
3. Click `Fetch External Signals`.
4. Backend calls CrustData with:

```python
headers = {
    "Authorization": f"Bearer {self.api_key}",
    "Content-Type": "application/json"
}
```

5. Normalized signals are persisted and published to Kafka topic `risk_signals`.
6. LangGraph agents produce a proposed score, explanation, and audit record.
7. UI updates with `Proposed Risk Increase` or decrease.
8. Open a risk detail page and click `Approve`.
9. The audit log records: `Based on CrustData API signal`.

## Backend API

- `GET /risks`
- `GET /risks/{id}`
- `POST /risks/{id}/fetch-external-signals`
- `POST /risks/{id}/approve`
- `POST /risks/{id}/reject`
- `POST /events`

## Database Tables

- `risks`: `id`, `name`, `current_score`, `proposed_score`, `confidence`, `status`
- `signals`: `id`, `risk_id`, `source`, `value`, `confidence`, `timestamp`
- `audit_logs`: `id`, `risk_id`, `previous_score`, `new_score`, `explanation`, `source`, `timestamp`

## Important Files

- `backend/app/adapters/crustdata.py`: CrustData MCP-style adapter
- `backend/app/agents/workflow.py`: LangGraph multi-agent workflow
- `backend/app/streaming.py`: Redpanda/Kafka producer and consumer
- `backend/app/main.py`: FastAPI endpoints and human approval workflow
- `frontend/app/page.tsx`: Investor dashboard
- `frontend/app/risks/[id]/page.tsx`: Risk detail and approval screen

## Fallback Behavior

If `CRUSTDATA_API_KEY` is missing, CrustData returns an error, or network access is unavailable, the backend logs:

```text
Fallback to mock due to API failure
```

The demo still proceeds with clearly marked mock metadata so the investor flow remains testable.

