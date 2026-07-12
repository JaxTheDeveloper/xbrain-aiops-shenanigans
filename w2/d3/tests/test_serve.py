import sys
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from serve import app


client = TestClient(app)


def test_healthz():
    response = client.get('/healthz')
    assert response.status_code == 200
    assert response.json() == {'status': 'ok'}


def test_readyz():
    response = client.get('/readyz')
    assert response.status_code == 200
    assert 'status' in response.json()


def test_incident_endpoint_returns_rich_payload():
    payload = {
        'alerts': [
            {
                'id': 'a-test-1',
                'ts': '2026-06-12T09:45:10Z',
                'service': 'checkout-svc',
                'metric': 'latency_p99_ms',
                'severity': 'crit',
                'value': 250.0,
                'threshold': 200.0,
                'labels': {'region': 'us-east-1'}
            }
        ]
    }
    response = client.post('/incident', json=payload)
    assert response.status_code == 200
    body = response.json()
    assert 'clusters' in body
    assert 'root_cause' in body
    assert 'recommended_actions' in body
    assert 'similar_incidents' in body


def test_invalid_input_rejected():
    response = client.post('/incident', json={'alerts': []})
    assert response.status_code == 422
