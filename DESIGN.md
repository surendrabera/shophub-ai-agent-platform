# ShopHub AI Agent Platform — Technical Design

## 1. Overview

ShopHub is a multi-tenant e-commerce support platform built with Python, FastAPI, and LangGraph. It demonstrates order lookup, inter-agent communication, merchant-level authorization, and approval-controlled refunds and cancellations.

The implementation uses a deterministic fake LLM/router so it runs locally without an external model API key. Docker Compose runs the three services.

## 2. Architecture and Request Flow

**Store API — port 8001**

- Authenticates demonstration bearer tokens and maps them to merchant identities.
- Maintains mock merchant and order data.
- Enforces merchant-level access restrictions and exposes order operations.

**Orders Sub-Agent — port 8002**

- Publishes agent metadata at `/.well-known/agent.json`.
- Exposes a JSON-RPC 2.0 endpoint at `/rpc`.
- Forwards the caller's authorization header to the Store API.

**Orchestrator — host port 8004**

- Uses LangGraph to coordinate request processing.
- Discovers the Orders Sub-Agent using its agent card.
- Calls the sub-agent over HTTP and JSON-RPC.
- Provides chat, SSE streaming, and approval endpoints.
- Persists approval proposals in SQLite.

### Typical order lookup

1. The client sends a chat request and bearer token to the Orchestrator.
2. LangGraph routes the request using deterministic logic.
3. The Orchestrator discovers and calls the Orders Sub-Agent over HTTP using JSON-RPC.
4. The sub-agent forwards the authorization token to the Store API.
5. The Store API authenticates the caller and checks merchant ownership.
6. The result returns through the sub-agent to the Orchestrator and then to the client.

The sub-agent is called over HTTP rather than imported directly into the Orchestrator. This demonstrates service separation and a structured inter-agent interface. It should not be described as a complete implementation of every formal A2A protocol feature.

## 3. Security and Approval Workflow

The Store API is responsible for enforcing merchant-level access. A caller must not be able to retrieve another merchant's order by changing an order identifier. Tokens without an associated merchant must not access merchant orders.

Customer-provided text is treated as untrusted input. Security-related sanitization helps reduce prompt-injection risk, and sensitive customer information should be redacted before model-facing processing.

Refunds and cancellations require an explicit approval decision:

1. The client submits an approval proposal.
2. The system records the proposed action and relevant order information.
3. The proposal can be approved or rejected.
4. Rejected proposals must not execute the requested operation.
5. Approved actions are revalidated before execution.

The current implementation uses demonstration credentials and mock data. Before production use, approval transitions and financial operations would need stronger transaction guarantees, concurrency controls, idempotency, and audit logging.

## 4. Persistence and Deployment

SQLite stores approval proposals. The approval database path is configurable through `APPROVAL_DB_PATH`, and Docker Compose configures a named volume for persistent approval data.

SQLite is appropriate for a small local demonstration because it is simple to configure and requires no separate database service. A production system with concurrent requests may need a managed database and explicit transaction and locking strategies.

Start the application:

```
docker compose up --build -d
docker compose ps
```

Run the automated tests:

```
python -m pytest -v
```

Run the five-scenario evaluation harness with the services running:

```
python scripts/run_evaluation.py
```

The evaluation scenarios cover order lookup, unknown orders, cross-merchant access, approval requirements, and rejected refunds. The harness uses the local Orchestrator API and does not require an external LLM API key.

The `/chat/stream` endpoint uses Server-Sent Events to return processing updates and a final response. The precise event types depend on the implementation.

## 5. Design Trade-offs and Limitations

**Deterministic routing instead of a live LLM:** This makes behavior reproducible, offline, and easy to test. It does not demonstrate the full uncertainty or flexibility of a production language model.

**Separate Orders Sub-Agent:** HTTP and JSON-RPC provide a clear service boundary, at the cost of network latency and additional failure modes.

**SQLite instead of a managed database:** This reduces local setup and operational overhead but limits the design's suitability for high-concurrency production workloads.

**Mock Store API:** This enables repeatable tests without external systems, but does not represent real payment processing or a production commerce backend.

**Demonstration authentication:** Hardcoded tokens simplify testing but are not suitable for production identity management.

The project demonstrates HTTP/JSON-RPC agent communication; MCP integration should not be claimed unless implemented separately. Likewise, streaming should not be described as emitting tool-started and tool-finished events unless those events are implemented and tested.

### Rough cost and latency estimates

These are planning estimates, not measured benchmark results.

- **Local demonstration:** No external LLM API cost. Runtime costs are limited to the developer's machine and Docker resources.
- **Order lookup latency:** A simple local request may take tens to hundreds of milliseconds, depending on startup state, database access, and HTTP overhead. Measure actual latency before making performance claims.
- **Production LLM cost:** Depends on the chosen model, token volume, request rate, and model pricing. No reliable estimate can be made until these inputs are defined.
- **Production infrastructure:** Costs would depend on service replicas, database choice, observability, hosting region, and traffic.

## 6. Next-Week Plan

1. **Reliability:** Add tests for Store API outages, timeouts, invalid downstream responses, and failed approval execution.
2. **Approval safety:** Implement and test atomic state transitions, idempotency, and safe handling of duplicate or concurrent decisions.
3. **Streaming:** Emit and test explicit tool-started and tool-finished events if required by the interface.
4. **Persistence:** Verify conversation-state persistence across container recreation, separately from approval persistence.
5. **Observability:** Add structured logs, request correlation IDs, and basic latency/error measurements.
6. **Evaluation:** Expand scripted scenarios and assert actual order state as well as proposal state.
7. **Production planning:** Evaluate identity management, secrets handling, a managed database, and an optional real-LLM integration.

## 7. AI Coding Assistant Disclosure

An AI coding assistant was used during development to help explain technical concepts, review design choices, troubleshoot implementation issues, and support test and documentation development. The author remains responsible for reviewing the code, validating behavior, and understanding the final implementation.