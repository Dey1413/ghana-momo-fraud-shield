from fastapi import FastAPI, BackgroundTasks
from pydantic import BaseModel
from neo4j import GraphDatabase
import joblib
import pandas as pd
from datetime import datetime
import requests
import redis

app = FastAPI(title="Ghana MoMo Fraud Shield - Risk Engine v3 (Enterprise)")

# --- DATABASE & CACHE CONNECTIONS ---
URI = "neo4j://localhost:7687"
AUTH = ("neo4j", "password123")
driver = GraphDatabase.driver(URI, auth=AUTH)

# Redis Cache (In-memory, sub-millisecond lookups)
redis_client = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)

# --- TELEGRAM ALERT CONFIGURATION ---
TELEGRAM_BOT_TOKEN = "9102941463:AAE1cxUoggw-2sDDUXVnyb7tm7_tw8L4WPY"
TELEGRAM_CHAT_ID = "7271712492"

# --- LOAD ML MODEL ---
print("Loading ML Model...")
ml_model = joblib.load('fraud_ml_model.pkl')
print("✅ ML Model and Redis Cache loaded successfully!")

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
def send_telegram_alert_async(sender: str, receiver: str, amount: float, risk: int, reason: str):
    """Runs in the background so it doesn't block the API response."""
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
        "parse_mode": "Markdown"
    }
    
    try:
        requests.post(telegram_url, json=payload, timeout=3)
        print(f"✅ Async Telegram alert sent for {sender}.")
    except Exception as e:
        print(f"⚠️ Failed to send async alert: {e}")

@app.get("/")
def health_check():
    return {"status": "Fraud Shield Enterprise API is running", "version": "3.0.0"}

@app.post("/assess-risk", response_model=RiskResponse)
def assess_transaction_risk(tx: TransactionRequest, background_tasks: BackgroundTasks):
    risk_score = 0
    reasons = []
    fraud_indicators = {}
    
    # --- 1. PREPARE ML FEATURES ---
    tx_time = datetime.fromisoformat(tx.timestamp) if tx.timestamp else datetime.now()
    hour = tx_time.hour
    is_night = 1 if (hour >= 22 or hour <= 5) else 0
    is_high_value = 1 if tx.amount > 1000 else 0
    
    ml_data = pd.DataFrame([{
        'amount': tx.amount,
        'hour_of_day': hour,
        'is_night_transaction': is_night,
        'is_high_value': is_high_value
    }])
    
    ml_fraud_prob = ml_model.predict_proba(ml_data)[0][1]
    ml_anomaly_score = round(ml_fraud_prob * 100, 2)
    
    with driver.session() as session:
        # --- 2. CHECK 1: Modem Farm (WITH REDIS CACHING) ---
        cache_key = f"device_users:{tx.sender_imei}"
        cached_count = redis_client.get(cache_key)
        
        if cached_count:
            device_user_count = int(cached_count)
            print(f"⚡ CACHE HIT: Retrieved IMEI {tx.sender_imei} count from Redis in <2ms")
        else:
            print(f"💾 CACHE MISS: Querying Neo4j for IMEI {tx.sender_imei}...")
            result = session.run("""
                MATCH (u:User {msisdn: $msisdn})-[:USES_DEVICE]->(d:Device)
                MATCH (other:User)-[:USES_DEVICE]->(d)
                RETURN count(other) as device_user_count
            """, msisdn=tx.sender_msisdn)
            record = result.single()
            device_user_count = record["device_user_count"] if record else 0
            
            # Save to Redis for 5 minutes (300 seconds)
        redis_client.set(cache_key, device_user_count, ex=300)
        fraud_indicators["device_user_count"] = device_user_count
        if device_user_count > 5:
            risk_score += 50
            reasons.append(f"CRITICAL: Device used by {device_user_count} different accounts (Modem Farm)")
        
        # --- 3. CHECK 2: SIM Swap History ---
        result = session.run("""
            MATCH (u:User {msisdn: $msisdn})-[r:SENT_MONEY]->(dest:User)
            WHERE r.is_sim_swap = true
            RETURN count(r) as sim_swap_count
        """, msisdn=tx.sender_msisdn)
        record = result.single()
        if record and record["sim_swap_count"] > 0:
            risk_score += 40
            reasons.append(f"CRITICAL: Account has {record['sim_swap_count']} SIM swap fraud incidents")

        # --- 4. CHECK 3: Mule Chain Link ---
        result = session.run("""
            MATCH path = (u:User {msisdn: $msisdn})<-[:SENT_MONEY*1..3]-(mule:User)
            WHERE ANY(rel IN relationships(path) WHERE rel.fraud_type = 'MULE_CHAIN')
            RETURN count(path) as mule_chain_involvement
        """, msisdn=tx.receiver_msisdn)
        record = result.single()
        if record and record["mule_chain_involvement"] > 0:
            risk_score += 35
            reasons.append(f"CRITICAL: Receiver linked to {record['mule_chain_involvement']} mule chains")

        # --- 5. CHECK 4: High Value to New Recipient ---
        result = session.run("""
            MATCH (sender:User {msisdn: $sender})-[r:SENT_MONEY]->(receiver:User {msisdn: $receiver})
            RETURN count(r) as transaction_history
        """, sender=tx.sender_msisdn, receiver=tx.receiver_msisdn)
        record = result.single()
        if record and record["transaction_history"] == 0:
            if tx.amount > 1000:
                risk_score += 25
                reasons.append(f"WARNING: First-time high-value transaction (GHS {tx.amount})")
            fraud_indicators["new_recipient"] = True

    # --- 6. CHECK 5: AI BEHAVIORAL ANOMALY ---
    if ml_anomaly_score > 80:
        risk_score += 30
        reasons.append(f"AI ALERT: Behavioral anomaly score is {ml_anomaly_score}% (Unusual time/amount pattern)")
    elif ml_anomaly_score > 50:
        risk_score += 15
        reasons.append(f"AI WARNING: Mild behavioral anomaly detected ({ml_anomaly_score}%)")

    # --- 7. FINAL DECISION ---
    if risk_score >= 70:
        decision = "BLOCK"
    elif risk_score >= 40:
        decision = "STEP_UP_AUTH"
    else:
        decision = "ALLOW"
    
    # --- 8. ASYNC ALERTING ---
    if decision == "BLOCK":
        background_tasks.add_task(
            send_telegram_alert_async, 
            tx.sender_msisdn, tx.receiver_msisdn, tx.amount, min(risk_score, 100), reasons[0] if reasons else "High Risk"
        )

    return RiskResponse(
        risk_score=min(risk_score, 100),
        decision=decision,
        reasons=reasons,
        fraud_indicators=fraud_indicators,
        ml_anomaly_score=ml_anomaly_score
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)