# 🛡️ Ghana MoMo Fraud Shield: AI-Powered Fraud Detection System

**Live Demo:** [https://dey1413-ghana-momo-fraud-shield-dashboard-0se13q.streamlit.app](https://dey1413-ghana-momo-fraud-shield-dashboard-0se13q.streamlit.app)

---

## 🌍 Overview
A real-time, AI-powered fraud detection system designed to combat mobile money fraud in Ghana. This hybrid system combines **Graph Database analysis** with **Machine Learning** to detect sophisticated fraud patterns including modem farms, mule chains, and SIM swap attacks.

## 🎯 Problem Statement
Mobile money fraud is a critical issue in Ghana, with the Bank of Ghana recording **16,733 fraud cases** in 2024 alone. Traditional rule-based systems fail to detect sophisticated, organized fraud syndicates that use:
- **Modem Farms (SIM Boxes):** Single devices controlling 5+ fraudulent accounts simultaneously.
- **Mule Money Chains:** Rapid fund transfers through 3-4 accounts to hide the money trail.
- **SIM Swap Attacks:** Hijacking accounts and draining funds immediately after a SIM change.

## 💡 Solution
A hybrid detection engine that combines:
1. **Graph Database (Neo4j):** Maps relationships between users, devices, and transactions to identify organized fraud networks.
2. **Machine Learning (XGBoost):** Analyzes behavioral patterns (time, amount, frequency) to detect anomalies.
3. **Real-Time API (FastAPI):** Processes transactions in <50ms with instant BLOCK/ALLOW decisions.
4. **Interactive Dashboard (Streamlit):** Visualizes fraud syndicates and provides threat intelligence for security analysts.

## 🏗️ Architecture
```text
┌─────────────────┐     ┌──────────────┐     ┌─────────────────┐
│   Transaction   │────▶│  FastAPI     │────▶│   Neo4j Graph   │
│   Request       │     │  Risk Engine │     │   Database      │
└─────────────────┘     └──────────────┘     └─────────────────┘
                               │
                               ▼
                        ┌──────────────┐
                        │  XGBoost ML  │
                        │   Model      │
                        └──────────────┘
                               │
                               ▼
                        ┌──────────────┐
                        │   Decision   │
                        │ BLOCK/ALLOW  │
                        └──────────────┘