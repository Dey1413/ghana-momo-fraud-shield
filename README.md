# 🛡️ Ghana MoMo Fraud Shield: Enterprise Real-Time Fraud Detection Engine

[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-green.svg)](https://fastapi.tiangolo.com/)
[![Neo4j](https://img.shields.io/badge/Neo4j-Graph%20Database-008CC1.svg)](https://neo4j.com/)
[![Docker](https://img.shields.io/badge/Docker-Compose-2496ED.svg)](https://www.docker.com/)
[![Tests](https://img.shields.io/badge/Tests-PyTest-brightgreen.svg)](https://docs.pytest.org/)

A production-grade, microservices-based fraud detection platform designed for mobile money ecosystems. It combines **Graph AI (Neo4j)**, **Machine Learning (XGBoost)**, and **Human-in-the-Loop (HITL)** analytics to detect and block sophisticated fraud syndicates in real-time.

---

## 🏗️ System Architecture

```mermaid
graph TD
    Client[📱 Streamlit SOC Dashboard] -->|HTTPS / JWT| API[⚡ FastAPI Risk Engine]
    
    subgraph "Core Detection Engine"
        API -->|1. Check Cache| Redis[(🔴 Redis Cache)]
        API -->|2. Graph Queries| Neo4j[(🔵 Neo4j Graph DB)]
        API -->|3. Behavioral Scoring| ML[🧠 XGBoost Model]
    end
    
    API -->|4. Async Alert| Telegram[📱 Telegram Bot API]
    API -->|5. Generate Report| PDF[📄 PDF Compliance Engine]
    
    Analyst[👨‍💼 SOC Analyst] -->|Override / Whitelist| Client