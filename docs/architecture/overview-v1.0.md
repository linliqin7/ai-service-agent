# AI Service Agent v1.0 Architecture Overview

This is the current architecture overview for the public v1.0 release. Securities brokerage customer service is the first validation scenario; it does not limit the product to a brokerage-only system.

## Product loop

```text
User Goal
  → Task State
  → Router / Workflow
  → Knowledge / Controlled Tools
  → Evidence
  → Answerability Gate
  → Answer / Clarify / Reject / Handoff
```

## Runtime responsibilities

| Layer | Responsibility |
|---|---|
| Task State | Holds one active task, its entities, required and missing slots, lifecycle status, clarification count, task-local evidence, and the final decision. |
| Router / workflow | Selects a public knowledge path, controlled private task, clarification, risk rejection, or local handoff. Stable paths stay deterministic; the optional local controlled loop is bounded by tool and policy rules. |
| Knowledge | Uses governed, current, public records from the curated JSON corpus. Retrieval is lightweight lexical matching and returns candidates, not facts by itself. |
| Controlled tools | Provide simulated business facts through a whitelist with parameter validation, authentication, and ownership checks. No tool executes a real transaction. |
| Evidence | Promotes only governed knowledge and verified controlled-tool results into knowledge evidence or business fact evidence, bound to the active task. |
| Answerability Gate | Checks required support coverage, task binding, validity, audience, ownership, conflicts, missing user information, unsafe requests, and scope before an answer can be completed. |
| Response / trace | Produces an answer, clarification, rejection, retrieval path, or local handoff with citations and trace events where applicable. |

## Current decision boundary

`TaskStatus` describes the task lifecycle. `AnswerabilityDecision` separately explains whether the evidence can complete that task. A task is not answered merely because retrieval found relevant material.

For example, an order tool may verify an order status, while a public knowledge record explains the general meaning of “unfilled.” Without a verified, task-bound order reason, the system cannot present that definition as the cause of that user’s order.

## Technology implementation

The v1.0 local prototype uses FastAPI, Pydantic, HTTPX, SQLite session storage, a curated JSON knowledge corpus, lexical retrieval, controlled tools, native web assets, pytest/TestClient, and offline evaluation. These are implementation choices, not product claims.

## Scope boundary

Current evidence and tools use controlled fixtures and simulated brokerage data. The system has no real broker APIs, identity provider, customer accounts, trading execution, production handoff, or production compliance approval. Vector databases, rerankers, Multi-Agent orchestration, LangGraph, MCP, long-term memory, and omnichannel service are future candidates rather than v1.0 capabilities.

## Related documents

- [Current PRD](../../PRD.md)
- [Historical V2 task-state design](v2-task-state-answerability.md)
- [Evidence and Answerability implementation audit](../audit/evidence-answerability-report.md)
