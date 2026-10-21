from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from neo4j import GraphDatabase
import joblib
import pandas as pd
from datetime import datetime

app = FastAPI(title="Ghana MoMo Fraud Shield - Risk Engine v2 (AI Powered)")

# Neo4j Connection
URI = "neo4j://localhost:7687"
AUTH = ("neo4j", "password123")
driver = GraphDatabase.driver(URI, auth=AUTH)

# Load ML Model at startup
print("Loading ML Model...")
ml_model = joblib.load('fraud_ml_model.pkl')
print("ML Model loaded successfully!")

class TransactionRequest(BaseModel):
    sender_msisdn: str
    receiver_msisdn: str
    amount: float
    sender_imei: str
    sender_cell_tower: str
    timestamp: str = None # Optional: defaults to now

class RiskResponse(BaseModel):
    risk_score: int
    decision: str
    reasons: list
    fraud_indicators: dict
    ml_anomaly_score: float

@app.get("/")
def health_check():
    return {"status": "Fraud Shield AI API is running", "version": "2.0.0"}

@app.post("/assess-risk", response_model=RiskResponse)
def assess_transaction_risk(tx: TransactionRequest):
    risk_score = 0
    reasons = []
    fraud_indicators = {}
    
    # --- PREPARE ML FEATURES ---
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
    
    # Get ML Probability of Fraud (Index 1 is the fraud class)
    ml_fraud_prob = ml_model.predict_proba(ml_data)[0][1]
    ml_anomaly_score = round(ml_fraud_prob * 100, 2)
    
    with driver.session() as session:
        # CHECK 1: Modem Farm
        result = session.run("""
            MATCH (u:User {msisdn: $msisdn})-[:USES_DEVICE]->(d:Device)
            MATCH (other:User)-[:USES_DEVICE]->(d)
            RETURN count(other) as device_user_count
        """, msisdn=tx.sender_msisdn)
        record = result.single()
        if record:
            device_user_count = record["device_user_count"]
            fraud_indicators["device_user_count"] = device_user_count
            if device_user_count > 5:
                risk_score += 50
                reasons.append(f"CRITICAL: Device used by {device_user_count} different accounts (Modem Farm)")
        
        # CHECK 2: SIM Swap History
        result = session.run("""
            MATCH (u:User {msisdn: $msisdn})-[r:SENT_MONEY]->(dest:User)
            WHERE r.is_sim_swap = true
            RETURN count(r) as sim_swap_count
        """, msisdn=tx.sender_msisdn)
        record = result.single()
        if record and record["sim_swap_count"] > 0:
            risk_score += 40
            reasons.append(f"CRITICAL: Account has {record['sim_swap_count']} SIM swap fraud incidents")

        # CHECK 3: Mule Chain Link
        result = session.run("""
            MATCH path = (u:User {msisdn: $msisdn})<-[:SENT_MONEY*1..3]-(mule:User)
            WHERE ANY(rel IN relationships(path) WHERE rel.fraud_type = 'MULE_CHAIN')
            RETURN count(path) as mule_chain_involvement
        """, msisdn=tx.receiver_msisdn)
        record = result.single()
        if record and record["mule_chain_involvement"] > 0:
            risk_score += 35
            reasons.append(f"CRITICAL: Receiver linked to {record['mule_chain_involvement']} mule chains")

        # CHECK 4: High Value to New Recipient
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

    # --- CHECK 5: AI BEHAVIORAL ANOMALY ---
    if ml_anomaly_score > 80:
        risk_score += 30
        reasons.append(f"AI ALERT: Behavioral anomaly score is {ml_anomaly_score}% (Unusual time/amount pattern)")
    elif ml_anomaly_score > 50:
        risk_score += 15
        reasons.append(f"AI WARNING: Mild behavioral anomaly detected ({ml_anomaly_score}%)")

    # Final Decision
    if risk_score >= 70:
        decision = "BLOCK"
    elif risk_score >= 40:
        decision = "STEP_UP_AUTH"
    else:
        decision = "ALLOW"
    
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