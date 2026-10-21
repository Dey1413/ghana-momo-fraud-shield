import pandas as pd
from neo4j import GraphDatabase

# Connect to local Neo4j
URI = "neo4j://localhost:7687"
AUTH = ("neo4j", "password123")

print("Connecting to Neo4j...")
driver = GraphDatabase.driver(URI, auth=AUTH)

def clear_db(tx):
    tx.run("MATCH (n) DETACH DELETE n")

def ingest_transaction(tx, row):
    tx.run("""
        MERGE (s:User {msisdn: $sender_msisdn})
        MERGE (r:User {msisdn: $receiver_msisdn})
        
        MERGE (s_dev:Device {imei: $sender_imei})
        MERGE (r_dev:Device {imei: $receiver_imei})
        MERGE (s)-[:USES_DEVICE]->(s_dev)
        MERGE (r)-[:USES_DEVICE]->(r_dev)
        
        MERGE (s_tow:CellTower {tower_id: $sender_cell_tower})
        MERGE (r_tow:CellTower {tower_id: $receiver_cell_tower})
        MERGE (s)-[:PINGED_TOWER]->(s_tow)
        MERGE (r)-[:PINGED_TOWER]->(r_tow)
        
        CREATE (s)-[:SENT_MONEY {
            tx_id: $tx_id, 
            amount: $amount, 
            timestamp: $timestamp,
            is_sim_swap: $is_sim_swap,
            fraud_type: $fraud_type
        }]->(r)
    """, 
    sender_msisdn=str(row['sender_msisdn']),
    receiver_msisdn=str(row['receiver_msisdn']),
    sender_imei=str(row['sender_imei']),
    receiver_imei=str(row['receiver_imei']),
    sender_cell_tower=str(row['sender_cell_tower']),
    receiver_cell_tower=str(row['receiver_cell_tower']),
    tx_id=str(row['tx_id']),
    amount=float(row['amount']),
    timestamp=str(row['timestamp']),
    is_sim_swap=bool(row['is_sim_swap']),
    fraud_type=str(row['fraud_type'])
    )

print("Clearing any existing data in the database...")
with driver.session() as session:
    session.execute_write(clear_db)

print("Loading CSV and ingesting into Neo4j (this takes about 30-60 seconds)...")
df = pd.read_csv('synthetic_momo_transactions.csv')

with driver.session() as session:
    for index, row in df.iterrows():
        session.execute_write(ingest_transaction, row)
        if index % 2000 == 0 and index > 0:
            print(f"Ingested {index} transactions...")

print("✅ Ingestion complete! Open http://localhost:7474 in your browser to view the graph.")
driver.close()