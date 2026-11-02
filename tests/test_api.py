import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
import sys
import os
import jwt

# Add the parent directory to the path so we can import risk_engine
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from risk_engine import app, SECRET_KEY, ALGORITHM

client = TestClient(app)


# Mock the ML model and Redis to ensure tests are fast and deterministic
@pytest.fixture(autouse=True)
def mock_dependencies():
    with patch("risk_engine.ml_model") as mock_ml, patch(
        "risk_engine.redis_client"
    ) as mock_redis, patch("risk_engine.driver") as mock_driver:

        # Mock ML model to return a 90% fraud probability (triggers BLOCK)
        mock_ml.predict_proba.return_value = [[0.1, 0.9]]

        # Mock Redis to simulate a Cache MISS
        mock_redis.get.return_value = None
        mock_redis.set.return_value = True

        # Mock Neo4j session and query result using DICTIONARIES for clean record access
        mock_session = MagicMock()
        mock_driver.session.return_value.__enter__.return_value = mock_session

        mock_session.run.side_effect = [
            MagicMock(single=MagicMock(return_value={"device_user_count": 20})),
            MagicMock(single=MagicMock(return_value={"sim_swap_count": 0})),
            MagicMock(single=MagicMock(return_value={"mule_chain_involvement": 0})),
            MagicMock(single=MagicMock(return_value={"transaction_history": 0})),
        ]
        yield


def test_health_check():
    response = client.get("/")
    assert response.status_code == 200
    assert response.json()["status"] == "Fraud Shield Enterprise API is running"


def test_fraud_block_decision():
    # 1. Generate a valid JWT token for the test using the app's secret key
    token_data = {"sub": "test_partner"}
    valid_token = jwt.encode(token_data, SECRET_KEY, algorithm=ALGORITHM)
    headers = {"Authorization": f"Bearer {valid_token}"}

    # 2. Prepare the payload
    payload = {
        "sender_msisdn": "233552956060",
        "receiver_msisdn": "233201234567",
        "amount": 5000.0,
        "sender_imei": "860000000000000",
        "sender_cell_tower": "GH-ACC-99",
        "timestamp": "2026-11-01T03:15:00",
    }

    # 3. Send the request WITH the authorization headers
    response = client.post("/assess-risk", json=payload, headers=headers)

    # 4. Assert the logic worked correctly
    assert response.status_code == 200
    data = response.json()

    assert data["decision"] == "BLOCK"
    assert data["risk_score"] >= 70
    assert data["ml_anomaly_score"] == 90.0
    assert "Modem Farm" in data["reasons"][0]
