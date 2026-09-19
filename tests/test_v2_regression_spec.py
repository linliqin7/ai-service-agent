"""Desired-behavior regression specifications from the V1 audit.

These tests intentionally describe the target product behavior. A failure is
useful evidence for the next fix phase; this file does not patch production
behavior.
"""

from datetime import date

from fastapi.testclient import TestClient

from app.api import app
from app.rag.retriever import records
from app.runtime.engine import Engine
from app.runtime.router import route
from app.schemas import SessionState


class OrderAndKnowledgePlanner:
    """Deterministic planner that deliberately requests both evidence sources."""

    def plan(self, query, observations, allowed):
        names = [item["name"] for item in observations]
        if "get_order_detail" not in names:
            return {"action": "tool", "name": "get_order_detail", "args": {"order_id": "ORD1001"}}
        if "search_knowledge" not in names:
            return {
                "action": "tool",
                "name": "search_knowledge",
                "args": {"query": "订单专用测试规则"},
            }
        return {"action": "answer"}


def test_public_unfilled_definition_does_not_enter_private_order_flow():
    """A public definition and a personal order diagnosis are different tasks."""
    public = Engine().handle(SessionState(session_id="public-definition"), "未成交是什么意思？")
    private = Engine().handle(
        SessionState(session_id="private-order"), "我的订单为什么没成交？"
    )

    assert route("未成交是什么意思？")["intent"] == "rules"
    assert public.intent == "rules"
    assert public.status == "answered"
    assert public.citations
    assert not public.handoff
    assert not public.trace or not any(event.type == "auth" for event in public.trace)

    assert route("我的订单为什么没成交？")["intent"] == "order"
    assert private.intent == "order"
    assert private.status == "clarify"
    assert private.handoff is None
    assert "order_id" not in private.citations
    assert "订单号" in private.answer


def test_successful_answer_resets_stale_clarification_context():
    session = SessionState(session_id="clarification-lifecycle")

    first = Engine().handle(session, "这是一个完全未知的业务问题")
    assert first.status == "clarify"
    assert session.pending_slots.get("clarifications") == 1

    answered = Engine().handle(session, "开户需要什么材料")
    assert answered.status == "answered"
    assert session.pending_slots == {}

    next_task = Engine().handle(session, "另一个完全未知的业务问题")
    assert next_task.status == "clarify"
    assert session.pending_slots.get("clarifications") == 1


def test_agent_search_knowledge_observation_reaches_final_evidence(monkeypatch):
    """Knowledge requested inside the agent loop must be linked to the answer."""
    special = {
        **records()[2],
        "id": "K-REGRESSION-ORDER-RULE",
        "title": "订单专用测试规则",
        "text": "只有本条测试知识包含的专用条件：撤单后不得再次提交同一委托。",
        "keywords": ["订单专用测试规则"],
    }
    monkeypatch.setattr("app.runtime.tools.search", lambda query: [special])

    response = Engine(OrderAndKnowledgePlanner()).handle(
        SessionState(session_id="agent-evidence", user_id="U1001", authenticated=True),
        "查 ORD1001 为什么没成交",
    )

    assert any(item["name"] == "search_knowledge" for item in response.observations)
    assert (
        special["id"] in {item["id"] for item in response.citations}
        or special["text"] in response.answer
        or "撤单后不得再次提交同一委托" in response.answer
    )


def test_public_knowledge_api_filters_non_public_records(monkeypatch):
    """The public browsing endpoint must apply the same governance boundary."""
    base = records()[0]
    public = {**base, "id": "K-PUBLIC-REGRESSION"}
    staff = {**base, "id": "K-STAFF-REGRESSION", "audience": "staff"}
    draft = {**base, "id": "K-DRAFT-REGRESSION", "review_status": "draft"}
    inactive = {**base, "id": "K-INACTIVE-REGRESSION", "direct_answer": False}
    expired = {
        **base,
        "id": "K-EXPIRED-REGRESSION",
        "effective_at": "2020-01-01",
        "expires_at": "2021-01-01",
    }
    monkeypatch.setattr("app.api.records", lambda: [public, staff, draft, inactive, expired])

    response = TestClient(app).get("/api/knowledge")
    assert response.status_code == 200
    ids = {item["id"] for item in response.json()}
    assert public["id"] in ids
    assert not ids.intersection(
        {staff["id"], draft["id"], inactive["id"], expired["id"]}
    )
