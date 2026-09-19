from fastapi.testclient import TestClient
from app.api import app

client = TestClient(app)

def test_web_entry_and_static_assets_are_served():
    assert client.get('/').status_code == 200
    assert '经纪业务智能客服' in client.get('/').text
    assert client.get('/static/app.js').status_code == 200

def test_api_session_auth_and_trace_flow():
    sid=client.post('/api/sessions').json()['session_id']
    assert client.post(f'/api/sessions/{sid}/auth',json={'user_id':'U1002'}).status_code == 200
    response=client.post(f'/api/sessions/{sid}/messages',json={'content':'我能不能开创业板'})
    assert response.json()['status']=='answered'
    trace=client.get(f'/api/sessions/{sid}/trace').json()
    assert any(event['type']=='tool' for event in trace)
