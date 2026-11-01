# 🛡️ Ghana MoMo Fraud Shield

[![Streamlit](https://img.shields.io/badge/Dashboard-Streamlit-FF4B4B?logo=streamlit)](https://share.streamlit.io/)
[![FastAPI](https://img.shields.io/badge/API-FastAPI-009688?logo=fastapi)](https://fastapi.tiangolo.com/)
[![Neo4j](https://img.shields.io/badge/Graph-Neo4j-008CC1?logo=neo4j)](https://neo4j.com/)
[![Python](https://img.shields.io/badge/ML-XGBoost-336791?logo=python)](https://xgboost.readthedocs.io/)

A real-time, hybrid **Graph + Machine Learning** fraud detection engine designed to combat mobile money (MoMo) fraud in Ghana. 

## 🌐 Live Demo
🔗 **[Try the Live Dashboard Here](https://dey1413-ghana-momo-fraud-shield.streamlit.app)

## 🚨 The Problem
Mobile money has driven massive financial inclusion in Ghana, but fraud is a critical barrier. Traditional rule-based systems fail because:
1. **Social Engineering**: Users willingly hand over PINs, bypassing basic security.
2. **Mule Networks**: Stolen funds are rapidly moved through 3-4 accounts ("hot potato") to hide the trail.
3. **Modem Farms**: Fraudsters use SIM boxes to manage dozens of accounts from a single physical device.

## 💡 The Solution
Instead of just checking PINs, this system analyzes the **entire context** of a transaction in < 50ms using a hybrid approach:
- **Graph Database (Neo4j)**: Maps relationships to catch organized syndicates, modem farms, and mule chains.
- **Machine Learning (XGBoost)**: Detects behavioral anomalies (e.g., unusual time, abnormal amounts, new recipients) even for brand-new accounts with no history.

## 🏗️ System Architecture

```mermaid
graph TD
    A[MoMo Transaction Request] --> B(FastAPI Risk Engine)
    B --> C{Hybrid Analysis}
    C -->|Graph Query| D[(Neo4j AuraDB)]
    C -->|Behavioral Score| E[XGBoost ML Model]
    D --> F[Syndicate / Mule Chain Detection]
    E --> G[Anomaly Detection]
    F --> H{Risk Scoring Engine}
    G --> H
    H -->|Score < 40| I[✅ ALLOW]
    H -->|Score 40-69| J[⚠️ STEP_UP_AUTH]
    H -->|Score >= 70| K[🚫 BLOCK]
    L[Streamlit Dashboard] -.->|Live Visualization| D