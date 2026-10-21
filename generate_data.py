import pandas as pd
import numpy as np
import random
from faker import Faker
from datetime import datetime, timedelta

fake = Faker() 
np.random.seed(42)

# --- 1. Define the Base Population ---
NUM_NORMAL_USERS = 2000
NUM_TRANSACTIONS = 10000

# Generate normal users (MSISDNs and IMEIs)
normal_users = {f"233{random.randint(200000000, 299999999)}": f"35{random.randint(100000000000, 999999999999)}" for _ in range(NUM_NORMAL_USERS)}
normal_msisdns = list(normal_users.keys())

# --- 2. Generate Normal Transactions ---
transactions = []
start_time = datetime.now() - timedelta(days=7)

for _ in range(NUM_TRANSACTIONS):
    sender = random.choice(normal_msisdns)
    receiver = random.choice(normal_msisdns)
    while receiver == sender:
        receiver = random.choice(normal_msisdns)
        
    transactions.append({
        "tx_id": fake.uuid4(),
        "timestamp": start_time + timedelta(seconds=random.randint(0, 604800)),
        "sender_msisdn": sender,
        "receiver_msisdn": receiver,
        "amount": round(random.uniform(1.0, 500.0), 2), # Normal amounts: 1 to 500 GHS
        "sender_imei": normal_users[sender],
        "receiver_imei": normal_users[receiver],
        "sender_cell_tower": f"GH-ACC-{random.randint(1, 50)}",
        "receiver_cell_tower": f"GH-ACC-{random.randint(1, 50)}",
        "is_sim_swap": False,
        "fraud_type": "NONE"
    })

# --- 3. Inject Fraud Pattern 1: The "Hot Potato" Mule Chain ---
# A victim sends money to Mule 1 -> Mule 2 -> Mule 3 -> Cashout Agent
print("Injecting Mule Chains...")
for i in range(50):
    victim = random.choice(normal_msisdns)
    mules = [f"2335{random.randint(40000000, 49999999)}" for _ in range(3)] # New numbers
    cashout = f"2332{random.randint(00000000, 19999999)}" # Cashout agent
    
    chain = [victim] + mules + [cashout]
    base_time = start_time + timedelta(seconds=random.randint(0, 604800))
    stolen_amount = round(random.uniform(2000.0, 10000.0), 2) # High amount
    
    for j in range(len(chain) - 1):
        transactions.append({
            "tx_id": fake.uuid4(),
            "timestamp": base_time + timedelta(seconds=j * 15), # Moves every 15 seconds!
            "sender_msisdn": chain[j],
            "receiver_msisdn": chain[j+1],
            "amount": stolen_amount - (j * 10), # Slight drop due to fees
            "sender_imei": f"35{random.randint(100000000000, 999999999999)}",
            "receiver_imei": f"35{random.randint(100000000000, 999999999999)}",
            "sender_cell_tower": f"GH-KUM-{random.randint(1, 10)}",
            "receiver_cell_tower": f"GH-KUM-{random.randint(1, 10)}",
            "is_sim_swap": False,
            "fraud_type": "MULE_CHAIN"
        })

# --- 4. Inject Fraud Pattern 2: Modem Farm (SIM Box) ---
# 1 Physical Device (IMEI) used by 20 different fraudster numbers
print("Injecting Modem Farms...")
farm_imei = "860000000000000" # The physical SIM box
farm_numbers = [f"2335{random.randint(50000000, 59999999)}" for _ in range(20)]

for number in farm_numbers:
    for _ in range(10): # Each number does 10 rapid transactions
        transactions.append({
            "tx_id": fake.uuid4(),
            "timestamp": start_time + timedelta(seconds=random.randint(0, 604800)),
            "sender_msisdn": number,
            "receiver_msisdn": random.choice(normal_msisdns),
            "amount": round(random.uniform(50.0, 150.0), 2),
            "sender_imei": farm_imei, # SAME IMEI!
            "receiver_imei": normal_users[random.choice(normal_msisdns)],
            "sender_cell_tower": "GH-ACC-99", # Same cell tower!
            "receiver_cell_tower": f"GH-ACC-{random.randint(1, 50)}",
            "is_sim_swap": False,
            "fraud_type": "MODEM_FARM"
        })

# --- 5. Inject Fraud Pattern 3: SIM Swap ---
# A normal user suddenly gets a new IMEI and drains their account
print("Injecting SIM Swaps...")
for _ in range(30):
    victim = random.choice(normal_msisdns)
    original_imei = normal_users[victim]
    new_imei = f"35{random.randint(100000000000, 999999999999)}"
    fraudster_receiver = f"2335{random.randint(60000000, 69999999)}"
    
    # Normal transaction before the swap
    transactions.append({
        "tx_id": fake.uuid4(),
        "timestamp": start_time + timedelta(days=1),
        "sender_msisdn": victim,
        "receiver_msisdn": random.choice(normal_msisdns),
        "amount": 50.0,
        "sender_imei": original_imei,
        "receiver_imei": normal_users[random.choice(normal_msisdns)],
        "sender_cell_tower": "GH-ACC-10",
        "receiver_cell_tower": "GH-ACC-10",
        "is_sim_swap": False,
        "fraud_type": "NONE"
    })
    
    # The SIM Swap Drain (Happens days later)
    transactions.append({
        "tx_id": fake.uuid4(),
        "timestamp": start_time + timedelta(days=5, hours=2), # 2 AM!
        "sender_msisdn": victim,
        "receiver_msisdn": fraudster_receiver,
        "amount": 15000.0, # Draining the account
        "sender_imei": new_imei, # NEW IMEI!
        "receiver_imei": f"35{random.randint(100000000000, 999999999999)}",
        "sender_cell_tower": "GH-ACC-10",
        "receiver_cell_tower": "GH-KUM-5",
        "is_sim_swap": True, # Flagged by Telco API
        "fraud_type": "SIM_SWAP"
    })

# --- 6. Save to CSV ---
df = pd.DataFrame(transactions)
df = df.sort_values(by='timestamp').reset_index(drop=True)
df.to_csv('synthetic_momo_transactions.csv', index=False)
print(f"Successfully generated {len(df)} transactions and saved to synthetic_momo_transactions.csv")