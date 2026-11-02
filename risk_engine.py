import jwt
from fastapi import FastAPI, BackgroundTasks, Depends, HTTPException, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from pydantic import BaseModel
from neo4j import GraphDatabase
import joblib
import pandas as pd
from datetime import datetime
import requests
import redis

app = FastAPI(title="Ghana MoMo Fraud Shield - Risk Engine v4 (Secure & Rate-Limited)")

# --- DATABASE & CACHE CONNECTIONS ---
URI = "neo4j://localhost:7687"
AUTH = ("neo4j", "password123")
driver = GraphDatabase.driver(URI, auth=AUTH)

# Redis Cache (In-memory, sub-millisecond lookups)
# Explicitly using 127.0.0.1 to avoid Windows IPv6 localhost resolution issues
redis_url = "redis://127.0.0.1:6379"
redis_client = redis.Redis(host="127.0.0.1", port=6379, db=0, decode_responses=True)

# --- SECURITY CONFIGURATION ---
SECRET_KEY = "super-secret-fraud-shield-key-2026"
ALGORITHM = "HS256"

# Rate Limiter: 100 requests per minute per IP address
limiter = Limiter(key_func=get_remote_address, storage_uri=redis_url)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

security = HTTPBearer()

# --- TELEGRAM ALERT CONFIGURATION ---
TELEGRAM_BOT_TOKEN = "9102941463:AAE1cxUoggw-2sDDUXVnyb7tm7_tw8L4WPY"
TELEGRAM_CHAT_ID = "7271712492"

# --- LOAD ML MODEL ---
print("Loading ML Model...")
ml_model = joblib.load("fraud_ml_model.pkl")
print("✅ ML Model, Redis Cache, and Security Layers loaded successfully!")


# --- MODELS ---
class TransactionRequest(BaseModel):
    sender_msisdn: str
    receiver_msisdn: str
    amount: float
    sender_imei: str
    sender_cell_tower: str
    timestamp: str = None


class RiskResponse(BaseModel):
    risk_score: int
    decision: str
    reasons: list
    fraud_indicators: dict
    ml_anomaly_score: float


# --- BACKGROUND TASK FOR ASYNC ALERTING ---
def send_telegram_alert_async(
    sender: str, receiver: str, amount: float, risk: int, reason: str
):
    alert_message = f"""
🚨 *FRAUD BLOCKED* 🚨
**Risk Score:** {risk}/100
**Sender:** `{sender}`
**Receiver:** `{receiver}`
**Amount:** GHS {amount}
**Reason:** {reason}
    """
    telegram_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": alert_message,
        "parse_mode": "Markdown",
    }

    try:
        requests.post(telegram_url, json=payload, timeout=3)
        print(f"✅ Async Telegram alert sent for {sender}.")
    except Exception as e:
        print(f"⚠️ Failed to send async alert: {e}")


# --- AUTHENTICATION HELPER ---
def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise HTTPException(
                status_code=401, detail="Invalid authentication credentials"
            )
        return username
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")


@app.get("/")
def health_check():
    return {"status": "Fraud Shield Enterprise API is running", "version": "4.0.0"}


@app.post("/login")
def login(username: str, password: str):
    if password != "admin123":
        raise HTTPException(status_code=400, detail="Incorrect password")

    token_data = {"sub": username}
    token = jwt.encode(token_data, SECRET_KEY, algorithm=ALGORITHM)
    return {"access_token": token, "token_type": "bearer"}


@app.post("/assess-risk", response_model=RiskResponse)
@limiter.limit("100/minute")
def assess_transaction_risk(
    request: Request,
    tx: TransactionRequest,
    background_tasks: BackgroundTasks,
    current_user: str = Depends(verify_token),
):
    print(f"🔒 Secure request received from user: {current_user}")

    risk_score = 0
    reasons = []
    fraud_indicators = {}

    tx_time = datetime.fromisoformat(tx.timestamp) if tx.timestamp else datetime.now()
    hour = tx_time.hour
    is_night = 1 if (hour >= 22 or hour <= 5) else 0
    is_high_value = 1 if tx.amount > 1000 else 0

    ml_data = pd.DataFrame(
        [
            {
                "amount": tx.amount,
                "hour_of_day": hour,
                "is_night_transaction": is_night,
                "is_high_value": is_high_value,
            }
        ]
    )
    ml_fraud_prob = ml_model.predict_proba(ml_data)[0][1]
    ml_anomaly_score = round(ml_fraud_prob * 100, 2)

    with driver.session() as session:
        cache_key = f"device_users:{tx.sender_imei}"
        cached_count = redis_client.get(cache_key)

        if cached_count:
            device_user_count = int(cached_count)
            print(
                f"⚡ CACHE HIT: Retrieved IMEI {tx.sender_imei} count from Redis in <2ms"
            )
        else:
            print(f"💾 CACHE MISS: Querying Neo4j for IMEI {tx.sender_imei}...")
            result = session.run(
                "MATCH (u:User {msisdn: $msisdn})-[:USES_DEVICE]->(d:Device) MATCH (other:User)-[:USES_DEVICE]->(d) RETURN count(other) as device_user_count",
                msisdn=tx.sender_msisdn,
            )
            record = result.single()
            device_user_count = record["device_user_count"] if record else 0
            redis_client.set(cache_key, device_user_count, ex=300)

        fraud_indicators["device_user_count"] = device_user_count
        if device_user_count > 5:
            risk_score += 50
            reasons.append(
                f"CRITICAL: Device used by {device_user_count} different accounts (Modem Farm)"
            )

        result = session.run(
            "MATCH (u:User {msisdn: $msisdn})-[r:SENT_MONEY]->(dest:User) WHERE r.is_sim_swap = true RETURN count(r) as sim_swap_count",
            msisdn=tx.sender_msisdn,
        )
        record = result.single()
        if record and record["sim_swap_count"] > 0:
            risk_score += 40
            reasons.append(
                f"CRITICAL: Account has {record['sim_swap_count']} SIM swap fraud incidents"
            )

        result = session.run(
            "MATCH path = (u:User {msisdn: $msisdn})<-[:SENT_MONEY*1..3]-(mule:User) WHERE ANY(rel IN relationships(path) WHERE rel.fraud_type = 'MULE_CHAIN') RETURN count(path) as mule_chain_involvement",
            msisdn=tx.receiver_msisdn,
        )
        record = result.single()
        if record and record["mule_chain_involvement"] > 0:
            risk_score += 35
            reasons.append(
                f"CRITICAL: Receiver linked to {record['mule_chain_involvement']} mule chains"
            )

        result = session.run(
            "MATCH (sender:User {msisdn: $sender})-[r:SENT_MONEY]->(receiver:User {msisdn: $receiver}) RETURN count(r) as transaction_history",
            sender=tx.sender_msisdn,
            receiver=tx.receiver_msisdn,
        )
        record = result.single()
        if record and record["transaction_history"] == 0:
            if tx.amount > 1000:
                risk_score += 25
                reasons.append(
                    f"WARNING: First-time high-value transaction (GHS {tx.amount})"
                )
            fraud_indicators["new_recipient"] = True

    if ml_anomaly_score > 80:
        risk_score += 30
        reasons.append(f"AI ALERT: Behavioral anomaly score is {ml_anomaly_score}%")
    elif ml_anomaly_score > 50:
        risk_score += 15
        reasons.append(
            f"AI WARNING: Mild behavioral anomaly detected ({ml_anomaly_score}%)"
        )

    if risk_score >= 70:
        decision = "BLOCK"
    elif risk_score >= 40:
        decision = "STEP_UP_AUTH"
    else:
        decision = "ALLOW"

    if decision == "BLOCK":
        background_tasks.add_task(
            send_telegram_alert_async,
            tx.sender_msisdn,
            tx.receiver_msisdn,
            tx.amount,
            min(risk_score, 100),
            reasons[0] if reasons else "High Risk",
        )

    return RiskResponse(
        risk_score=min(risk_score, 100),
        decision=decision,
        reasons=reasons,
        fraud_indicators=fraud_indicators,
        ml_anomaly_score=ml_anomaly_score,
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
