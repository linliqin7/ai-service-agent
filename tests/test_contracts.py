from datetime import datetime
import pytest
from app.schemas import SessionState, TraceEvent, AgentResponse
from app.config import Settings

def test_session_state_requires_session_id():
    with pytest.raises(Exception):
        SessionState(user_id=None)

def test_trace_event_and_response_round_trip():
    event = TraceEvent(type="route", data={"pipeline": "FAQ"}, timestamp=datetime.now())
    response = AgentResponse(answer="ok", status="answered", trace=[event], citations=[])
    assert response.trace[0].data["pipeline"] == "FAQ"

def test_settings_reads_environment(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "secret")
    s = Settings()
    assert s.deepseek_api_key == "secret"

def test_session_starts_with_empty_trace():
    assert SessionState(session_id="s").traces == []
