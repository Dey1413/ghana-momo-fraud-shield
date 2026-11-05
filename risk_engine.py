import os
import time
import jwt
from collections import deque
from datetime import datetime

from dotenv import load_dotenv
from fastapi import FastAPI, BackgroundTasks, Depends, HTTPException, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from pydantic import BaseModel
from neo4j import GraphDatabase
import joblib
import pandas as pd
import requests
import redis
import logging
import sys

# Configure Structured Logger
logging.basicConfig(
    level=logging.INFO,
    format='{"time": "%(asctime)s", "level": "%(levelname)s", "message": "%(message)s"}',
    stream=sys.stdout,
)
logger = logging.getLogger("fraud_shield_api")

# Load environment variables from .env file
load_dotenv()

app = FastAPI(title="Ghana MoMo Fraud Shield - Risk Engine v4 (Secure & Rate-Limited)")

# --- DATABASE & CACHE CONNECTIONS (Docker-Aware) ---
neo4j_uri = os.getenv("NEO4J_URI", "neo4j://127.0.0.1:7687")
neo4j_user = os.getenv("NEO4J_USER", "neo4j")
neo4j_password = os.getenv("NEO4J_PASSWORD", "password123")
driver = GraphDatabase.driver(neo4j_uri, auth=(neo4j_user, neo4j_password))

# Redis: Use environment variable for Docker (redis://redis:6379), fallback to local
redis_url = os.getenv("REDIS_URL", "redis://127.0.0.1:6379")
redis_client = redis.from_url(redis_url, decode_responses=True)

# --- SECURITY CONFIGURATION ---
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "fallback-super-secret-key")
ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")

limiter = Limiter(key_func=get_remote_address, storage_uri=redis_url)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
security = HTTPBearer()

# --- TELEGRAM ALERT CONFIGURATION ---
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# --- LOAD ML MODEL ---
print("Loading ML Model...")
ml_model = joblib.load("fraud_ml_model.pkl")
print("✅ ML Model, Redis Cache, and Security Layers loaded successfully!")

# --- REAL-TIME METRICS TRACKER ---
request_latencies = deque(maxlen=100)  # Keep last 100 requests
total_requests = 0


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
    alert_message = f"🚨 *FRAUD BLOCKED* 🚨\n**Risk Score:** {risk}/100\n**Sender:** `{sender}`\n**Receiver:** `{receiver}`\n**Amount:** GHS {amount}\n**Reason:** {reason}"
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
    global total_requests
    start_time = time.time()

    logger.info(f"Secure request received from user: {current_user}")
    risk_score, reasons, fraud_indicators = 0, [], {}

    # --- 1. Check Whitelist via Redis first (Sub-millisecond) ---
    whitelist_cache_key = f"whitelist:{tx.sender_msisdn}"
    is_whitelisted = redis_client.get(whitelist_cache_key)

    if is_whitelisted == "true":
        logger.info(f"User {tx.sender_msisdn} is WHITELISTED (Cache Hit). Allowing.")
        return RiskResponse(
            risk_score=0,
            decision="ALLOW",
            reasons=["Analyst Whitelist Override"],
            fraud_indicators={},
            ml_anomaly_score=0,
        )

    # --- 2. Calculate ML Score FIRST (so it's available for the rest of the function) ---
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
    ml_anomaly_score = round(ml_model.predict_proba(ml_data)[0][1] * 100, 2)

    # --- 3. Single Session for all Graph Queries ---
    with driver.session() as session:
        # 3a. Check DB for whitelist (only if Redis missed)
        whitelist_check = session.run(
            "MATCH (u:User {msisdn: $msisdn}) RETURN u.is_whitelisted AS is_white",
            msisdn=tx.sender_msisdn,
        ).single()

        if whitelist_check and whitelist_check.get("is_white") is True:
            redis_client.set(whitelist_cache_key, "true", ex=3600)  # Cache for 1 hour
            logger.info(
                f"User {tx.sender_msisdn} is WHITELISTED (DB Hit). Allowing and caching."
            )
            return RiskResponse(
                risk_score=0,
                decision="ALLOW",
                reasons=["Analyst Whitelist Override"],
                fraud_indicators={},
                ml_anomaly_score=0,
            )

        # 3b. Modem Farm Check (with Redis Cache)
        cache_key = f"device_users:{tx.sender_imei}"
        cached_count = redis_client.get(cache_key)

        if cached_count:
            device_user_count = int(cached_count)
            logger.info(f"CACHE HIT: IMEI {tx.sender_imei} count retrieved.")
        else:
            logger.info(f"CACHE MISS: Querying Neo4j for IMEI {tx.sender_imei}...")
            result = session.run(
                "MATCH (u:User {msisdn: $msisdn})-[:USES_DEVICE]->(d:Device) MATCH (other:User)-[:USES_DEVICE]->(d) RETURN count(other) as device_user_count",
                msisdn=tx.sender_msisdn,
            )
            record = result.single()
            device_user_count = record["device_user_count"] if record else 0
            redis_client.set(cache_key, device_user_count, ex=300)  # Cache for 5 mins

        fraud_indicators["device_user_count"] = device_user_count
        if device_user_count > 5:
            risk_score += 50
            reasons.append(
                f"CRITICAL: Device used by {device_user_count} different accounts (Modem Farm)"
            )

        # 3c. SIM Swap Check
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

        # 3d. Mule Chain Check
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

        # 3e. Transaction History Check
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

    # --- 4. Add ML Score to Total Risk ---
    if ml_anomaly_score > 80:
        risk_score += 30
        reasons.append(f"AI ALERT: Behavioral anomaly score is {ml_anomaly_score}%")
    elif ml_anomaly_score > 50:
        risk_score += 15
        reasons.append(
            f"AI WARNING: Mild behavioral anomaly detected ({ml_anomaly_score}%)"
        )

    # --- 5. Make Decision ---
    decision = (
        "BLOCK"
        if risk_score >= 70
        else ("STEP_UP_AUTH" if risk_score >= 40 else "ALLOW")
    )

    # --- 6. Handle Blocking (Alert + Log to Graph) ---
    if decision == "BLOCK":
        background_tasks.add_task(
            send_telegram_alert_async,
            tx.sender_msisdn,
            tx.receiver_msisdn,
            tx.amount,
            min(risk_score, 100),
            reasons[0] if reasons else "High Risk",
        )

        with driver.session() as session:
            session.run(
                """
                MERGE (sender:User {msisdn: $sender})
                MERGE (receiver:User {msisdn: $receiver})
                CREATE (sender)-[:SENT_MONEY {
                    amount: $amount, 
                    timestamp: $timestamp, 
                    status: 'BLOCKED', 
                    risk_score: $risk,
                    reason: $reason
                }]->(receiver)
            """,
                sender=tx.sender_msisdn,
                receiver=tx.receiver_msisdn,
                amount=tx.amount,
                timestamp=tx.timestamp,
                risk=min(risk_score, 100),
                reason=reasons[0] if reasons else "Unknown",
            )
            logger.info("BLOCKED transaction logged to Neo4j for Analyst Review.")

    # --- 7. Track Metrics ---
    total_requests += 1
    latency = (time.time() - start_time) * 1000  # in ms
    request_latencies.append(latency)

    # --- 8. Return Response ---
    return RiskResponse(
        risk_score=min(risk_score, 100),
        decision=decision,
        reasons=reasons,
        fraud_indicators=fraud_indicators,
        ml_anomaly_score=ml_anomaly_score,
    )


@app.get("/stats")
def get_api_stats():
    avg_latency = (
        sum(request_latencies) / len(request_latencies) if request_latencies else 0
    )
    return {
        "total_requests": total_requests,
        "avg_latency_ms": round(avg_latency, 2),
        "status": "healthy",
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
