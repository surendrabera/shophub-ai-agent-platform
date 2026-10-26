# ShopHub AI Agent Platform — Technical Design

## 1. Purpose

ShopHub AI Agent Platform demonstrates a multi-tenant e-commerce support system. It allows authenticated support agents to retrieve order information through a central orchestrator and a separate Orders Sub-Agent. It also demonstrates approval-controlled refunds and cancellations.

The initial implementation uses a deterministic fake LLM/router, allowing the application to run without an external LLM API key.

## 2. Architecture Overview

The application consists of three services.

### 2.1 Store API

**Port:** 8001

Responsibilities:
- Authenticate demo bearer tokens.
- Associate callers with merchant identities.
- Provide order lookup and listing operations.
- Support eligible refund and cancellation operations.
- Enforce merchant-level order access restrictions.

### 2.2 Orders Sub-Agent

**Port:** 8002

Responsibilities:
- Expose agent metadata through `/.well-known/agent.json`.
- Accept requests through the `/rpc` JSON-RPC endpoint.
- Forward authorized requests to the Store API.
- Pass the caller's authorization header to the Store API.

### 2.3 Orchestrator

**Host port:** 8004  
**Container port:** 8000

Responsibilities:
- Accept user requests through the chat API.
- Use LangGraph to coordinate request processing.
- Route requests using deterministic fake LLM/router logic.
- Communicate with the Orders Sub-Agent over HTTP and JSON-RPC.
- Provide Server-Sent Events (SSE) streaming.
- Create and process approval proposals.
- Persist approval records in SQLite.

## 3. Request Flow

A typical order-status request follows this sequence:

1. The client submits a request to the Orchestrator with a bearer token.
2. The Orchestrator processes the request through its LangGraph workflow.
3. The request is routed to the Orders Sub-Agent.
4. The Orders Sub-Agent forwards the request and authorization header to the Store API.
5. The Store API authenticates the caller and checks merchant-level access.
6. The result travels back through the Orders Sub-Agent to the Orchestrator.
7. The Orchestrator returns a customer-facing answer.

The Orchestrator communicates with the Sub-Agent through HTTP requests rather than directly importing its application code.

## 4. LangGraph Orchestration

LangGraph is used to represent request processing as a graph-based workflow.

The workflow maintains request state and coordinates the processing steps. The Orchestrator uses deterministic routing logic rather than a live LLM in this implementation.

This approach makes the demo reproducible and testable without requiring an external model service.

The exact nodes, edges, state fields, and routing conditions are defined in `app/orchestrator.py`.

## 5. Inter-Agent Communication

The Orders Sub-Agent exposes a JSON-RPC 2.0 endpoint at `/rpc`.

JSON-RPC provides a structured request-and-response format for invoking methods on the Sub-Agent.

The agent metadata is available at:

`GET http://localhost:8002/.well-known/agent.json`

The Orchestrator uses the configured agent-card URL to discover the Sub-Agent metadata.

**Protocol scope:** The project demonstrates agent-to-agent communication using HTTP and JSON-RPC with an agent card. This should not automatically be described as a complete implementation of every feature in a formal A2A protocol specification. MCP integration should likewise not be claimed unless implemented separately.

## 6. Authentication and Tenant Isolation

The demo uses bearer tokens to identify the calling support agent and associated merchant.

Example tokens:

| Token | Merchant |
|---|---|
| `token-merchant-a-demo` | `merchant_a` |
| `token-merchant-b-demo` | `merchant_b` |
| `token-no-merchant-demo` | No merchant assigned |

The Orders Sub-Agent forwards the caller's authorization header to the Store API so the Store API can enforce access restrictions.

A caller should not be able to access another merchant's orders by changing an order identifier.

The demo uses hardcoded tokens and mock data. Production deployment would require a proper identity provider, managed secrets, and stronger authorization controls.

## 7. Approval-Controlled Actions

Refunds and cancellations are sensitive operations. The application provides an approval proposal workflow.

### 7.1 Proposal creation

The client submits a proposal to the Orchestrator. The proposal records information such as the order, merchant, action, amount where applicable, and current proposal status.

### 7.2 Decision

An authorized decision is submitted through the approval decision endpoint.

- **Rejected:** The proposal is marked rejected and the proposed order action is not executed.
- **Approved:** The application revalidates the order and relevant conditions before attempting the action.

### 7.3 Execution

When the action is approved and validation succeeds, the Orchestrator requests the corresponding operation through the agent and Store API layers.

The proposal status records the workflow outcome.

The implementation details and status transitions are defined in `app/orchestrator.py` and `app/approval_store.py`.

## 8. SQLite Persistence

Approval proposals are stored in SQLite.

The database location is configurable through `APPROVAL_DB_PATH`. Docker Compose configures persistent storage under `/app/data` using a named volume.

The named volume allows stored approval records to survive container replacement, provided the volume is retained.

SQLite is appropriate for a small, self-contained demonstration. A production deployment with concurrent workloads may require a managed database and explicit concurrency and transaction strategies.

## 9. Security Considerations

The project demonstrates several security-oriented controls:
- Bearer-token authentication.
- Merchant-level authorization.
- Authorization propagation across service boundaries.
- Output sanitization and handling of potentially malicious prompt-injection content.
- Approval before sensitive operations.
- Revalidation before approved actions are executed.

These controls should not be interpreted as a complete production security assessment.

Further work should include:
- Strong identity and access management.
- Secret management and credential rotation.
- Input validation and request-size limits.
- Idempotency for financial operations.
- Concurrency-safe approval transitions.
- Audit logging and monitoring.
- Careful handling and redaction of customer personal information.
- Tests for duplicate, stale, and conflicting approval requests.

## 10. Error Handling and Reliability

The services communicate over HTTP. Network failures, authorization failures, invalid requests, and downstream errors should be handled without incorrectly reporting successful business operations.

The current behavior is implemented in the service endpoint handlers and request-processing logic.

Production readiness would require clearly defined timeout and retry policies, structured logs, service-level metrics, distributed tracing, and tests for downstream outages.

Retries for refunds and cancellations should be designed carefully to avoid duplicate operations.

## 11. Streaming

The Orchestrator exposes `POST /chat/stream`.

The endpoint uses Server-Sent Events to send progress updates and a final response to the client.

This allows clients to receive processing status before the final answer.

## 12. Deployment

Docker Compose runs the three services:
- Store API on host port 8001.
- Orders Sub-Agent on host port 8002.
- Orchestrator on host port 8004.

The service configuration uses container-network addresses for communication between containers.

Start the application:

```powershell
docker compose up --build -d
```

Check service status:

```powershell
docker compose ps
```

Stop the application:

```powershell
docker compose down
```

Avoid `docker compose down -v` when you need to preserve the named approval-data volume.

## 13. Testing

Run the automated tests from the repository root:

```powershell
python -m pytest -v
```

The test suite includes tests for orchestration, Store API behavior, security, approval persistence, and evaluation scenarios.

Automated tests should be supplemented with integration tests against the running Docker services.

## 14. Known Limitations

- The LLM/router is deterministic and does not invoke a live language model.
- The Store API uses mock data.
- Authentication uses hardcoded demonstration tokens.
- SQLite is used for approval persistence.
- The system demonstrates HTTP and JSON-RPC communication between agents, but should not be presented as a complete A2A implementation without further verification.
- MCP support should not be claimed unless an MCP server or client integration is implemented.
- Production-grade observability, identity management, and concurrency controls require further work.

## 15. Future Improvements

Potential improvements include:
- Integrating a real LLM with constrained tool calling.
- Adding robust observability and distributed tracing.
- Improving identity management and secrets handling.
- Adding idempotency and concurrency-safe approval execution.
- Expanding integration and failure-injection testing.
- Adding continuous integration and deployment automation.
- Evaluating a production database for approval persistence.

## 16. Key Source Files

| File | Responsibility |
|---|---|
| `app/orchestrator.py` | LangGraph orchestration, chat endpoints, streaming, and approval workflow |
| `app/orders_agent.py` | Orders Sub-Agent and JSON-RPC interface |
| `app/store_api.py` | Mock Store API and merchant authorization |
| `app/approval_store.py` | SQLite approval persistence |
| `app/security.py` | Security-related sanitization functions |
| `docker-compose.yml` | Multi-service configuration |
| `Dockerfile` | Container image build |
| `requirements.txt` | Python dependencies |
| `tests/` | Automated tests |