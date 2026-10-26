## Request Flow

1. The client sends a request to the Orchestrator with a bearer token.
2. The Orchestrator uses LangGraph to route the request.
3. The Orchestrator discovers the Orders Sub-Agent using its agent card at `/.well-known/agent.json`.
4. The Orchestrator calls the Orders Sub-Agent over HTTP using JSON-RPC 2.0.
5. The Orders Sub-Agent forwards the caller's authorization token to the Store API.
6. The Store API authenticates the token and enforces merchant-level access.
7. The result is returned through the sub-agent to the Orchestrator, which responds to the client.

Refund and cancellation requests use a separate approval workflow. A proposal must be explicitly approved before the requested operation is executed.

## Run the Evaluation Harness

With the Docker Compose services running, execute:

```
python scripts/run_evaluation.py
```

The evaluation runner checks five scenarios:

- Order status lookup.
- Unknown order handling.
- Cross-merchant access denial.
- Refund proposal requires approval.
- Rejected refund is not executed.

The runner sends requests to the local Orchestrator API at `http://127.0.0.1:8004` by default. It uses the deterministic implementation and does not require an external LLM API key.

## AI Coding Assistant Disclosure

An AI coding assistant was used during development to help explain concepts, review implementation choices, troubleshoot errors, and support test and documentation development. The final repository and its behavior should be reviewed and validated by the author.