# ShopHub AI Agent Platform

## Overview

ShopHub AI Agent Platform is a multi-tenant e-commerce support system built with Python, FastAPI, and LangGraph.

The system allows an authenticated merchant's support agent to retrieve order information through an orchestrator and a separate Orders Sub-Agent. It also supports approval-controlled refund and cancellation workflows.

The project uses a deterministic fake LLM/router so the application can run locally without an external LLM API key.

## Architecture

The application consists of three services:

1. **Store API** — authenticates demo bearer tokens, maintains mock merchant and order data, enforces tenant isolation, and provides order operations.
2. **Orders Sub-Agent** — exposes an agent card and a JSON-RPC 2.0 endpoint. It forwards the caller's authorization token to the Store API.
3. **Orchestrator** — uses LangGraph to route requests, communicate with the Orders Sub-Agent over HTTP, manage approval workflows, and stream responses using Server-Sent Events (SSE).

SQLite stores approval proposals. Docker Compose mounts persistent storage for the orchestrator database.

## Requirements

- Python 3.12
- Docker Desktop with Docker Compose
- PowerShell on Windows, or a compatible terminal

## Run with Docker Compose

Build and start the services:

```powershell
docker compose up --build -d
```

Check service status:

```powershell
docker compose ps
```

Expected service ports:

| Service | Host port |
|---|---:|
| Store API | 8001 |
| Orders Sub-Agent | 8002 |
| Orchestrator | 8004 |

Check health endpoints:

```powershell
Invoke-RestMethod http://localhost:8001/health
Invoke-RestMethod http://localhost:8002/health
Invoke-RestMethod http://localhost:8004/health
```

Stop the services:

```powershell
docker compose down
```

The approval database is stored in the `approval-data` Docker volume. Do not remove that volume if you want to retain the stored proposals.

## Demo authentication tokens

The mock Store API provides these demo tokens:

| Token | Merchant association |
|---|---|
| `token-merchant-a-demo` | `merchant_a` |
| `token-merchant-b-demo` | `merchant_b` |
| `token-no-merchant-demo` | No merchant association |

These tokens are for local development and testing only.

## Example: Query an order

Create a request body:

```powershell
@'
{"message":"What is the status of order 1002?"}
'@ | Set-Content -Path body.json -Encoding ascii
```

Call the orchestrator:

```powershell
Invoke-RestMethod `
  -Uri "http://localhost:8004/chat" `
  -Method Post `
  -Headers @{ Authorization = "Bearer token-merchant-a-demo" } `
  -ContentType "application/json" `
  -InFile "body.json"
```

Order `1002` belongs to Merchant A in the mock dataset.

## Approval-controlled operations

Refunds and cancellations use an approval workflow:

1. Submit a request to `/approvals/propose`.
2. Inspect the returned proposal.
3. Submit an explicit `approved` or `rejected` decision to `/approvals/{proposal_id}/decision`.
4. Verify the resulting proposal and order status.

Creating a proposal does not execute the requested operation. The system executes the action only after approval and rechecks the order before execution.

Example proposal request body:

```json
{
  "message": "Please refund order 1001"
}
```

Example decision request body:

```json
{
  "decision": "approved"
}
```

Use Merchant A's demo token for Merchant A's order and proposal.

## Streaming

The `/chat/stream` endpoint returns Server-Sent Events (SSE).

Example:

```powershell
@'
{"message":"What is the status of order 1002?"}
'@ | Set-Content -Path body.json -Encoding ascii

curl.exe -N `
  -X POST `
  "http://localhost:8004/chat/stream" `
  -H "Authorization: Bearer token-merchant-a-demo" `
  -H "Content-Type: application/json" `
  --data-binary "@body.json"
```

The stream includes status events and a final answer event.

## Run tests locally

Activate the virtual environment and install dependencies:

```powershell
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Run the complete test suite:

```powershell
python -m pytest -v
```

## Security considerations

- Order access is scoped to the authenticated merchant.
- Tokens without a merchant association must not access merchant orders.
- The Orders Sub-Agent forwards the caller's authorization token.
- Refunds and cancellations require explicit approval.
- Customer-provided notes are treated as untrusted input.
- Sensitive customer information should be redacted before being passed to model-facing components.

The demo tokens and in-memory mock order data are intended for a take-home assignment, not production deployment.

## Limitations

- The LLM/router is deterministic and does not call an external language model.
- Merchant and order data are mock data held in memory by the Store API.
- The system is intended for local demonstration and testing rather than production use.