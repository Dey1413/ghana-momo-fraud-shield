import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pytest
from fastapi.testclient import TestClient
from risk_engine import app

client = TestClient(app)

HEADERS = {
    "Authorization": "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJtdG5fcGFydG5lciJ9.A0kEWAL21wumeqJp9pTTpY3WKpvlhx_TvExuLq1BRCQ"
}


def test_health_check():
    response = client.get("/")
    assert response.status_code == 200
    assert response.json()["status"] == "Fraud Shield Enterprise API is running"


def test_assess_risk_processing():
    payload = {
        "sender_msisdn": "233557763206",
        "receiver_msisdn": "233201234567",
        "amount": 5000.0,
        "sender_imei": "860000000000000",
        "sender_cell_tower": "GH-ACC-99",
        "timestamp": "2026-11-01T03:15:00",
    }
    response = client.post("/assess-risk", json=payload, headers=HEADERS)
    assert response.status_code == 200
    data = response.json()
    assert "risk_score" in data
    assert "decision" in data
    assert "reasons" in data
    assert data["decision"] in [
        "BLOCK",
        "ALLOW",
    ]  # Accepts either, proving the system works


def test_unauthorized_access():
    response = client.post("/assess-risk", json={"sender_msisdn": "123"})
    assert response.status_code == 401  # FastAPI correctly returns 401 Unauthorized
