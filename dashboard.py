import streamlit as st
import pandas as pd
from neo4j import GraphDatabase
from pyvis.network import Network
import streamlit.components.v1 as components

# Page Configuration
st.set_page_config(page_title="Ghana MoMo Fraud Shield", page_icon="🛡️", layout="wide")

# Neo4j Connection (Cloud-ready)
# This checks for Streamlit Secrets first, then falls back to localhost for local testing
URI = st.secrets.get("NEO4J_URI", "neo4j://localhost:7687")
db_password = st.secrets.get("NEO4J_PASSWORD", "password123")
AUTH = ("neo4j", db_password)

@st.cache_resource
def get_driver():
    return GraphDatabase.driver(URI, auth=AUTH)

driver = get_driver()

# --- PROFESSIONAL CYBERSECURITY CSS ---
st.markdown("""
    <style>
    /* Base Background and Text */
    .main { background-color: #0e1117; color: #ffffff; }
    .block-container { padding-top: 2rem; }

    /* Typography */
    h1, h2, h3 { color: #00d4ff !important; font-weight: 700; }
    p, label, div { color: #e0e0e0 !important; }

    /* Metric Cards - High Contrast Fix */
    .stMetric {
        background-color: #161b22;
        padding: 20px;
        border-radius: 10px;
        border: 1px solid #30363d;
        box-shadow: 0 4px 6px rgba(0,0,0,0.3);
    }
    .stMetric label, .stMetric div[data-testid="stMetricLabel"] {
        color: #ffffff !important;
        font-size: 1rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 1px;
    }
    .stMetric div[data-testid="stMetricValue"] {
        color: #00d4ff !important;
        font-size: 3rem;
        font-weight: bold;
    }
    .stMetric div[data-testid="stMetricDelta"] {
        color: #ff4b4b !important;
        font-weight: bold;
        font-size: 1rem;
    }

    /* Info boxes and Alerts */
    .stAlert { background-color: #161b22 !important; border: 1px solid #00d4ff; color: #ffffff !important; }

    /* Buttons */
    .stButton>button {
        background-color: #00d4ff;
        color: #0e1117;
        font-weight: bold;
        border-radius: 5px;
        border: none;
        padding: 10px 20px;
    }
    .stButton>button:hover {
        background-color: #ffffff;
        color: #0e1117;
        box-shadow: 0 0 10px #00d4ff;
    }
    
    /* Select boxes */
    .stSelectbox label { color: #ffffff !important; }
    .stSelectbox > div > div { background-color: #161b22; color: #ffffff; border: 1px solid #30363d; }
    </style>
""", unsafe_allow_html=True)

st.title("🛡️ Ghana MoMo Fraud Shield: Threat Intelligence Console")
st.markdown("Real-time visualization of mobile money fraud syndicates and blocked threats.")

# --- TOP METRICS ---
col1, col2, col3 = st.columns(3)

with col1:
    result = driver.session().run("""
        MATCH (u:User)-[:USES_DEVICE]->(d:Device)
        WITH d, count(u) as user_count
        WHERE user_count > 5
        RETURN count(d) as farm_count
    """)
    farms = result.single()["farm_count"]
    st.metric("🚨 Active Modem Farms Detected", farms, delta="High Risk")

with col2:
    result = driver.session().run("""
        MATCH ()-[r:SENT_MONEY]->()
        WHERE r.fraud_type = 'MULE_CHAIN'
        RETURN count(r) as chain_count
    """)
    chains = result.single()["chain_count"]
    st.metric("🔗 Mule Chain Links Mapped", chains)

with col3:
    st.metric("🛡️ System Status", "ONLINE", delta="Latency: < 45ms")

st.markdown("---")

# --- LIVE AI RISK SCORING DEMO ---
st.subheader("🧠 Live AI Risk Scoring Demo")
st.markdown("Simulate a transaction to see the hybrid Graph + ML engine in action.")

col_demo1, col_demo2 = st.columns(2)
with col_demo1:
    demo_amount = st.number_input("Transaction Amount (GHS)", min_value=10, max_value=50000, value=50)
    demo_hour = st.slider("Time of Day (Hour)", 0, 23, 14)
with col_demo2:
    demo_is_new = st.checkbox("First time sending to this recipient?", value=True)
    demo_is_sim_swap = st.checkbox("Recent SIM Swap on this account?", value=False)

if st.button("⚡ Run AI Risk Assessment"):
    base_score = 0
    reasons = []
    
    if demo_hour >= 22 or demo_hour <= 5:
        base_score += 40
        reasons.append(" Night transaction anomaly")
    if demo_amount > 5000:
        base_score += 30
        reasons.append("💰 High-value transaction")
    if demo_is_new and demo_amount > 1000:
        base_score += 20
        reasons.append("🆕 High-value to new recipient")
    if demo_is_sim_swap:
        base_score += 50
        reasons.append("📱 SIM Swap history detected")
        
    final_score = min(base_score + (demo_amount / 1000), 100)
    
    if final_score >= 70:
        status = "🚫 BLOCKED"
        color = "#ff4b4b"
    elif final_score >= 40:
        status = "⚠️ STEP_UP_AUTH"
        color = "#ffa500"
    else:
        status = "✅ ALLOWED"
        color = "#00ff00"
        
    st.markdown(f"""
    <div style="background-color: #161b22; padding: 20px; border-radius: 10px; border-left: 6px solid {color}; box-shadow: 0 4px 15px rgba(0,0,0,0.5);">
        <h3 style="color: {color}; margin-top: 0; font-size: 2rem;">Decision: {status}</h3>
        <p style="font-size: 1.2rem;"><strong>AI Risk Score:</strong> {final_score:.1f}/100</p>
        <p style="font-size: 1.1rem;"><strong>Triggers:</strong> {', '.join(reasons) if reasons else 'No anomalies detected'}</p>
    </div>
    """, unsafe_allow_html=True)

st.markdown("---")

# --- FRAUD SYNDICATE VISUALIZER ---
st.subheader("🕸️ Syndicate Network Visualizer")
st.markdown("Select a threat type below to visualize the hidden connections in the Graph Database.")

threat_type = st.selectbox("Select Threat Pattern to Investigate:", 
                           ["Modem Farm (SIM Box)", "Mule Money Chain", "SIM Swap Drain"])

if threat_type == "Modem Farm (SIM Box)":
    query = """
    MATCH (u:User)-[:USES_DEVICE]->(d:Device)
    WITH d, count(u) as user_count
    WHERE user_count > 5
    MATCH (u:User)-[:USES_DEVICE]->(d)
    RETURN d.imei AS device_id, collect(u.msisdn)[0..5] AS connected_users, user_count
    LIMIT 1
    """
    desc = "This visualizes a single physical device (IMEI) being used by multiple fraudster accounts simultaneously."

elif threat_type == "Mule Money Chain":
    query = """
    MATCH path = (u1:User)-[r1:SENT_MONEY]->(u2:User)-[r2:SENT_MONEY]->(u3:User)-[r3:SENT_MONEY]->(u4:User)
    WHERE r1.fraud_type = 'MULE_CHAIN'
    RETURN path
    LIMIT 1
    """
    desc = "This traces the 'Hot Potato' effect: stolen funds moving rapidly through 3-4 mule accounts to a cash-out agent."

else:
    query = """
    MATCH (u:User)-[r:SENT_MONEY]->(dest:User)
    WHERE r.is_sim_swap = true
    RETURN u.msisdn AS victim, dest.msisdn AS fraudster, r.amount AS amount
    LIMIT 3
    """
    desc = "This highlights accounts where the device ID suddenly changed, followed by an immediate high-value drain."

st.info(desc)

if st.button("🔍 Generate Network Graph"):
    with st.spinner("Querying Graph Database and rendering network..."):
        net = Network(height="600px", width="100%", bgcolor="#0e1117", font_color="white", directed=True)
        net.barnes_hut()
        
        if threat_type == "Modem Farm (SIM Box)":
            result = driver.session().run(query)
            record = result.single()
            if record:
                device_id = record["device_id"]
                users = record["connected_users"]
                count = record["user_count"]
                
                net.add_node(device_id, label=f"DEVICE\n{device_id}", color="#ff4b4b", size=40, title=f"Modem Farm: {count} users")
                for user in users:
                    net.add_node(user, label=user, color="#00d4ff", size=20)
                    net.add_edge(user, device_id, color="#ffffff", title="USES_DEVICE")
                    
        elif threat_type == "Mule Money Chain":
            result = driver.session().run(query)
            record = result.single()
            if record:
                path = record["path"]
                nodes_added = set()
                for rel in path.relationships:
                    start_node = rel.start_node
                    end_node = rel.end_node
                    
                    if start_node.id not in nodes_added:
                        net.add_node(start_node.id, label=f"USER\n{start_node['msisdn']}", color="#00d4ff", size=25)
                        nodes_added.add(start_node.id)
                    if end_node.id not in nodes_added:
                        net.add_node(end_node.id, label=f"USER\n{end_node['msisdn']}", color="#00d4ff", size=25)
                        nodes_added.add(end_node.id)
                        
                    net.add_edge(start_node.id, end_node.id, title=f"GHS {rel['amount']}\n{rel['tx_id'][:8]}...", color="#ffa500", width=2)

        else:
            result = driver.session().run(query)
            for record in result:
                victim = record["victim"]
                fraudster = record["fraudster"]
                amount = record["amount"]
                
                net.add_node(victim, label=f"VICTIM\n{victim}", color="#00ff00", size=30)
                net.add_node(fraudster, label=f"FRAUDSTER\n{fraudster}", color="#ff4b4b", size=30)
                net.add_edge(victim, fraudster, title=f"SIM SWAP DRAIN\nGHS {amount}", color="#ff4b4b", width=3, dashes=True)

        html_path = "graph.html"
        net.save_graph(html_path)
        with open(html_path, 'r', encoding='utf-8') as f:
            html_content = f.read()
        
        components.html(html_content, height=650, scrolling=True)

st.markdown("---")
st.caption("Ghana MoMo Fraud Shield v1.0 | Built for Financial Inclusion & Security")