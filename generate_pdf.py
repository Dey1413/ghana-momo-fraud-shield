from fpdf import FPDF


class PDF(FPDF):
    def header(self):
        self.set_font("helvetica", "B", 14)
        self.cell(
            0,
            10,
            "Ghana MoMo Fraud Shield - Project Report",
            align="C",
            new_x="LMARGIN",
            new_y="NEXT",
        )
        self.ln(5)

    def footer(self):
        self.set_y(-15)
        self.set_font("helvetica", "I", 8)
        self.cell(0, 10, f"Page {self.page_no()}", align="C")


pdf = PDF()
pdf.add_page()
pdf.set_font("helvetica", "", 11)

text = """
PROJECT: Ghana MoMo Fraud Shield
AUTHOR: Kofi Dey

1. THE PROBLEM
Mobile money has revolutionized financial inclusion in Ghana, but fraud is a massive barrier. Traditional rule-based systems fail against organized syndicates using SIM boxes and mule chains.

2. THE SOLUTION: HYBRID AI + GRAPH
I built a real-time risk engine scoring transactions in <50ms using:
- Neo4j Graph Database: Maps 10,000+ transactions to expose hidden relationships.
- Graph AI (Risk Propagation): Auto-discovers fraud clusters without hardcoded rules.
- XGBoost ML Model: Catches behavioral anomalies (unusual times, amounts, new recipients).
- FastAPI: Sub-50ms real-time risk scoring.
- Telegram Webhooks: Instant real-time alerting for blocked transactions.

3. LIVE LINKS
Dashboard: https://dey1413-ghana-momo-fraud-shield-dashboard-0se13q.streamlit.app/
GitHub: https://github.com/Dey1413/ghana-momo-fraud-shield
"""

# Note: fpdf2 handles basic text well. Emojis are omitted in this script for maximum compatibility.
pdf.multi_cell(0, 6, text)
pdf.output("Ghana_MoMo_Fraud_Shield_Report.pdf")
print("✅ PDF generated successfully: Ghana_MoMo_Fraud_Shield_Report.pdf")
