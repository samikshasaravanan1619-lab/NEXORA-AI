import sqlite3
from datetime import datetime, date, time
from pathlib import Path

import pandas as pd
import streamlit as st
import os

# Optional ML dependency; install with: pip install scikit-learn
try:
    from sklearn.ensemble import RandomForestRegressor
    SKLEARN_AVAILABLE = True
except ImportError:
    RandomForestRegressor = None
    SKLEARN_AVAILABLE = False

# ============================================================
# BIZPILOT-AI: NEXORA — student prototype
# Data entered in this app is saved locally in nexora.db.
# Forecasts are estimates based on available historical records.
# ============================================================

APP_DIR = Path(__file__).resolve().parent
DB_PATH = APP_DIR / "nexora.db"

st.set_page_config(page_title="NEXORA | BIZPILOT-AI", page_icon="🧠", layout="wide")

# ---------- THEME ----------
st.markdown("""
<style>
.stApp { background: radial-gradient(circle at 10% 10%, rgba(0,170,255,.16), transparent 32%), radial-gradient(circle at 90% 85%, rgba(0,90,255,.13), transparent 35%), linear-gradient(135deg,#030712,#081629 55%,#050b18); color:#eaf6ff; }
[data-testid="stMain"] { background-image:linear-gradient(rgba(50,150,220,.045) 1px,transparent 1px),linear-gradient(90deg,rgba(50,150,220,.045) 1px,transparent 1px); background-size:32px 32px; }
[data-testid="stSidebar"] { background:linear-gradient(180deg,#081426,#030914); border-right:1px solid #16466b; }
.block-container { padding-top:2rem; padding-bottom:2rem; }
h1 { color:#67e8ff !important; } h2,h3 { color:#d7efff; }
.hero { padding:28px; border:1px solid #087eae; border-radius:18px; background:linear-gradient(120deg,#082d4e,#071122); box-shadow:0 0 28px rgba(0,183,255,.12); margin-bottom:24px; }
.hero h1 { font-size:34px; font-weight:800; letter-spacing:1px; } .hero p { color:#b6d9f5; }
.metric-card,.module-card { background:linear-gradient(145deg,#102541,#091426); border:1px solid #20557a; border-radius:15px; padding:18px; box-shadow:0 4px 18px rgba(0,0,0,.2); }
.metric-label { color:#a8c7e3; font-size:12px; letter-spacing:1px; } .metric-value { color:#69e4ff; font-size:24px; font-weight:800; margin-top:10px; }
.stButton>button { background:linear-gradient(90deg,#087ea4,#1557b0); color:white; border:1px solid #48d7ff; border-radius:9px; font-weight:600; }
.stButton>button:hover { border-color:#a4f2ff; box-shadow:0 0 15px rgba(0,200,255,.3); color:white; }
.stTextInput input,.stNumberInput input,.stDateInput input,.stTimeInput input { background-color:#0b192c; color:#eaf6ff; border:1px solid #28577a; border-radius:8px; }
</style>
""", unsafe_allow_html=True)

# ---------- DATABASE ----------
def get_connection():
    return sqlite3.connect(DB_PATH, check_same_thread=False)


def init_db():
    with get_connection() as con:
        con.execute("""CREATE TABLE IF NOT EXISTS business_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT, business_name TEXT NOT NULL,
            record_month TEXT NOT NULL, revenue REAL NOT NULL, costs REAL NOT NULL,
            created_at TEXT NOT NULL)""")
        con.execute("""CREATE TABLE IF NOT EXISTS product_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT, product_name TEXT NOT NULL,
            record_date TEXT NOT NULL, selling_price REAL NOT NULL, unit_cost REAL NOT NULL,
            quantity INTEGER NOT NULL, other_costs REAL NOT NULL, revenue REAL NOT NULL,
            total_cost REAL NOT NULL, profit REAL NOT NULL, created_at TEXT NOT NULL)""")
        con.execute("""CREATE TABLE IF NOT EXISTS inventory_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT, product_name TEXT NOT NULL,
            stock INTEGER NOT NULL, minimum_stock INTEGER NOT NULL,
            reorder_quantity INTEGER NOT NULL, owner_decision TEXT NOT NULL,
            created_at TEXT NOT NULL)""")
        con.execute("""CREATE TABLE IF NOT EXISTS security_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT NOT NULL,
            event_date TEXT NOT NULL, event_time TEXT NOT NULL, failed_attempts INTEGER NOT NULL,
            unfamiliar_location INTEGER NOT NULL, unusual_time INTEGER NOT NULL,
            mfa_enabled INTEGER NOT NULL, alert TEXT NOT NULL, created_at TEXT NOT NULL)""")
        con.execute("""CREATE TABLE IF NOT EXISTS ad_creatives (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_name TEXT NOT NULL, target_audience TEXT NOT NULL,
            objective TEXT NOT NULL, platform TEXT NOT NULL, tone TEXT NOT NULL,
            language TEXT NOT NULL, variation_number INTEGER NOT NULL,
            headline TEXT NOT NULL, description TEXT NOT NULL,
            caption TEXT NOT NULL, call_to_action TEXT NOT NULL,
            hashtags TEXT NOT NULL, model_name TEXT NOT NULL, created_at TEXT NOT NULL)""")
        con.execute("""CREATE TABLE IF NOT EXISTS sales_leads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            person_name TEXT NOT NULL, company TEXT NOT NULL, email TEXT NOT NULL,
            phone TEXT NOT NULL DEFAULT '', source TEXT NOT NULL, fit_score INTEGER NOT NULL,
            engagement_score INTEGER NOT NULL, intent_score INTEGER NOT NULL,
            lead_score INTEGER NOT NULL, consent INTEGER NOT NULL DEFAULT 0,
            opted_out INTEGER NOT NULL DEFAULT 0, stage TEXT NOT NULL DEFAULT 'New',
            followup_date TEXT NOT NULL DEFAULT '', last_reply TEXT NOT NULL DEFAULT '',
            notes TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL, updated_at TEXT NOT NULL)""")


init_db()


def read_table(table):
    allowed = {"business_records", "product_records", "inventory_records", "security_events", "ad_creatives", "sales_leads"}
    if table not in allowed:
        raise ValueError("Unsupported table")
    with get_connection() as con:
        return pd.read_sql_query(f"SELECT * FROM {table} ORDER BY id DESC", con)


def money(value):
    return f"₹{float(value):,.2f}"


def save_business(name, month, revenue, costs):
    with get_connection() as con:
        con.execute("INSERT INTO business_records (business_name,record_month,revenue,costs,created_at) VALUES (?,?,?,?,?)",
                    (name.strip() or "Unnamed business", month, float(revenue), float(costs), datetime.now().isoformat(timespec="seconds")))


def save_product(name, record_date, price, unit_cost, quantity, other_costs):
    revenue = float(price) * int(quantity)
    total_cost = float(unit_cost) * int(quantity) + float(other_costs)
    profit = revenue - total_cost
    with get_connection() as con:
        con.execute("""INSERT INTO product_records
            (product_name,record_date,selling_price,unit_cost,quantity,other_costs,revenue,total_cost,profit,created_at)
            VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (name.strip(), record_date.isoformat(), float(price), float(unit_cost), int(quantity), float(other_costs),
             revenue, total_cost, profit, datetime.now().isoformat(timespec="seconds")))
    return revenue, total_cost, profit


def simple_forecast(values, steps=3):
    """Linear-trend forecast using standard Python; returns None if data is insufficient."""
    vals = [float(v) for v in values]
    if len(vals) < 3:
        return None
    n = len(vals)
    x_mean = (n - 1) / 2
    y_mean = sum(vals) / n
    denom = sum((i - x_mean) ** 2 for i in range(n))
    if denom == 0:
        return [y_mean] * steps
    slope = sum((i - x_mean) * (v - y_mean) for i, v in enumerate(vals)) / denom
    intercept = y_mean - slope * x_mean
    return [intercept + slope * i for i in range(n, n + steps)]

# ---------- SIDEBAR ----------
st.sidebar.markdown("# ◈ NEXORA")
st.sidebar.caption("INTELLIGENT BUSINESS SYSTEM")
page = st.sidebar.radio("NAVIGATION", [
    "Command Center", "Business Intelligence", "Product Profit Predictor",
    "Business Autopilot", "Cybersecurity Center", "Saved Records", "AI Advertisement Studio",
    "Sales Pipeline Autopilot"
])
st.sidebar.markdown("---")
st.sidebar.markdown("### SYSTEM STATUS")
st.sidebar.success("Prototype Online")
st.sidebar.caption("Local database: nexora.db")
st.sidebar.caption("Demo only — not connected to live business or security systems.")

st.markdown("""
<div class="hero"><h1>◈ BIZPILOT-AI: NEXORA</h1>
<p>Predictive Intelligence · Smart Automation · Cybersecurity</p><p>ONE PLATFORM. THREE POWERS.</p></div>
""", unsafe_allow_html=True)

# Load saved data
business_df = read_table("business_records")
product_df = read_table("product_records")
inventory_df = read_table("inventory_records")
security_df = read_table("security_events")

# ============================================================
# COMMAND CENTER
# ============================================================
if page == "Command Center":
    st.subheader("◈ COMMAND CENTER")
    total_revenue = float(business_df["revenue"].sum()) if not business_df.empty else 0.0
    total_costs = float(business_df["costs"].sum()) if not business_df.empty else 0.0
    total_product_profit = float(product_df["profit"].sum()) if not product_df.empty else 0.0
    low_stock = int((inventory_df["stock"] <= inventory_df["minimum_stock"]).sum()) if not inventory_df.empty else 0
    cols = st.columns(4)
    metrics = [("SAVED BUSINESS REVENUE", money(total_revenue)), ("SAVED BUSINESS COSTS", money(total_costs)),
               ("PRODUCT PROFIT / LOSS", money(total_product_profit)), ("LOW-STOCK RECORDS", str(low_stock))]
    for col, (label, value) in zip(cols, metrics):
        with col:
            st.markdown(f'<div class="metric-card"><div class="metric-label">{label}</div><div class="metric-value">{value}</div></div>', unsafe_allow_html=True)
    st.markdown("### ◈ MODULES")
    a, b, c = st.columns(3)
    with a:
        st.markdown('<div class="module-card"><h3>🧠 Predictive BI</h3>Save business figures, review trends, and estimate future results from past records.</div>', unsafe_allow_html=True)
    with b:
        st.markdown('<div class="module-card"><h3>⚙️ Business Autopilot</h3>Record stock levels and request owner approval for reorder recommendations.</div>', unsafe_allow_html=True)
    with c:
        st.markdown('<div class="module-card"><h3>🛡️ Cybersecurity</h3>Review manually entered login events with simple demo rules.</div>', unsafe_allow_html=True)
    if not business_df.empty:
        st.markdown("### SAVED BUSINESS REVENUE VS COSTS")
        chart_df = business_df.sort_values("record_month").groupby("record_month", as_index=False)[["revenue", "costs"]].sum().set_index("record_month")
        st.line_chart(chart_df)
    else:
        st.info("Start by saving a record in Business Intelligence or Product Profit Predictor. The dashboard will update from saved data.")

# ============================================================
# BUSINESS INTELLIGENCE
# ============================================================
elif page == "Business Intelligence":
    st.subheader("🧠 PREDICTIVE BUSINESS INTELLIGENCE")
    st.write("Enter business figures for a month and save them to the local SQLite database.")
    with st.form("business_form"):
        name = st.text_input("Business name", "NEXORA Demo Store")
        month = st.date_input("Record month (choose any date in that month)", value=date.today()).replace(day=1).isoformat()
        revenue = st.number_input("Total sales revenue (₹)", min_value=0.0, value=50000.0, step=1000.0)
        costs = st.number_input("Total business costs (₹)", min_value=0.0, value=30000.0, step=1000.0)
        save_bi = st.form_submit_button("SAVE BUSINESS RECORD")
    if save_bi:
        save_business(name, month, revenue, costs)
        st.success("Business record saved in nexora.db.")
        st.rerun()
    profit = revenue - costs
    margin = (profit / revenue * 100) if revenue else 0.0
    c1, c2, c3 = st.columns(3)
    c1.metric("Revenue", money(revenue))
    c2.metric("Profit / Loss", money(profit))
    c3.metric("Profit Margin", f"{margin:.2f}%")
    st.bar_chart(pd.DataFrame({"Amount (₹)": [revenue, costs]}, index=["Revenue", "Costs"]))
    if profit > 0:
        st.success("The entered figures show a profit.")
    elif profit < 0:
        st.warning("The entered figures show a loss.")
    else:
        st.info("Revenue and costs are equal.")
    st.markdown("### SAVED MONTHLY HISTORY")
    if business_df.empty:
        st.info("No saved monthly records yet. Save at least three months to create a basic forecast.")
    else:
        monthly = business_df.groupby("record_month", as_index=False)[["revenue", "costs"]].sum().sort_values("record_month")
        monthly["profit"] = monthly["revenue"] - monthly["costs"]
        st.dataframe(monthly, use_container_width=True, hide_index=True)
        st.line_chart(monthly.set_index("record_month")[["revenue", "costs", "profit"]])
        forecasts = simple_forecast(monthly["profit"].tolist(), 3)
        if forecasts is not None:
            future = pd.DataFrame({"Forecast step": ["Next period 1", "Next period 2", "Next period 3"], "Estimated profit (₹)": forecasts}).set_index("Forecast step")
            st.markdown("### ESTIMATED PROFIT TREND")
            st.line_chart(future)
            st.caption("Estimate only: simple linear trend based on saved records, not a guarantee. Enter comparable monthly data for more useful estimates.")
        else:
            st.info("Add records for at least three different months before a trend estimate can be shown.")

    # Optional ML forecast: trained only when enough distinct monthly history exists.
    st.markdown("### 🤖 MACHINE-LEARNING SALES FORECAST")
    st.caption("Experimental Random Forest model. It uses saved monthly revenue history; results are estimates, not guarantees.")
    if not SKLEARN_AVAILABLE:
        st.warning("Scikit-learn is not installed. In your terminal run: python -m pip install scikit-learn")
    else:
        ml_monthly = business_df.groupby("record_month", as_index=False)[["revenue"]].sum().sort_values("record_month")
        # Need enough history to create lag features and still have multiple training rows.
        if len(ml_monthly) < 6:
            st.info(f"Save at least 6 distinct months of business records to enable this ML demo. Current months: {len(ml_monthly)}.")
        else:
            revenues = ml_monthly["revenue"].astype(float).tolist()
            X, y = [], []
            for i in range(2, len(revenues)):
                X.append([i, revenues[i-1], revenues[i-2]])
                y.append(revenues[i])
            if len(X) >= 4:
                model = RandomForestRegressor(n_estimators=100, random_state=42, min_samples_leaf=1)
                model.fit(X, y)
                history = revenues[:]
                predictions = []
                for step in range(3):
                    i = len(history)
                    predicted = max(0.0, float(model.predict([[i, history[-1], history[-2]]])[0]))
                    predictions.append(predicted)
                    history.append(predicted)
                forecast_months = ["Next month", "Month +2", "Month +3"]
                ml_df = pd.DataFrame({"Period": forecast_months, "ML estimated revenue (₹)": predictions}).set_index("Period")
                st.line_chart(ml_df)
                st.dataframe(ml_df, use_container_width=True)
                st.caption("Model: Random Forest regression with month index and the previous two months' revenue. With small or changing datasets, predictions may be unreliable. Use this as a prototype, not financial advice.")
            else:
                st.info("More distinct monthly records are needed to train this model.")

# ============================================================
# PRODUCT PROFIT PREDICTOR
# ============================================================
elif page == "Product Profit Predictor":
    st.subheader("📦 PRODUCT PROFIT PREDICTOR")
    st.write("Calculate product revenue, costs, profit/loss and margin. Save each record to build a history for future estimates.")
    with st.form("product_form"):
        p_name = st.text_input("Product name", "Notebook")
        p_date = st.date_input("Sales record date", value=date.today())
        price = st.number_input("Selling price per unit (₹)", min_value=0.0, value=80.0, step=1.0)
        unit_cost = st.number_input("Cost to make/buy one unit (₹)", min_value=0.0, value=45.0, step=1.0)
        quantity = st.number_input("Expected / actual units sold", min_value=0, value=100, step=1)
        other_costs = st.number_input("Other total costs for this record (₹)", min_value=0.0, value=500.0, step=50.0)
        save_product_button = st.form_submit_button("CALCULATE & SAVE PRODUCT RECORD")
    revenue = price * quantity
    total_cost = unit_cost * quantity + other_costs
    profit = revenue - total_cost
    margin = (profit / revenue * 100) if revenue > 0 else 0.0
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Revenue", money(revenue))
    m2.metric("Total Cost", money(total_cost))
    m3.metric("Profit / Loss", money(profit))
    m4.metric("Profit Margin", f"{margin:.2f}%")
    st.markdown("### PROFIT CALCULATION")
    st.write(f"Revenue = selling price × quantity = {money(price)} × {quantity:,} = **{money(revenue)}**")
    st.write(f"Total cost = unit cost × quantity + other costs = {money(unit_cost)} × {quantity:,} + {money(other_costs)} = **{money(total_cost)}**")
    st.write(f"Profit / loss = revenue − total cost = **{money(profit)}**")
    if profit > 0:
        st.success("This set of inputs estimates a profit.")
    elif profit < 0:
        st.warning("This set of inputs estimates a loss. Consider reviewing price, costs or expected sales.")
    else:
        st.info("This product breaks even with the current inputs.")
    if save_product_button:
        if not p_name.strip():
            st.error("Please enter a product name before saving.")
        else:
            save_product(p_name, p_date, price, unit_cost, quantity, other_costs)
            st.success("Product calculation saved to the local database.")
            st.rerun()
    st.markdown("### PRODUCT HISTORY")
    if product_df.empty:
        st.info("No saved product records yet. Save several records over time to estimate a future trend.")
    else:
        hist = product_df.copy()
        hist["record_date"] = pd.to_datetime(hist["record_date"], errors="coerce")
        st.dataframe(hist[["record_date", "product_name", "selling_price", "unit_cost", "quantity", "revenue", "total_cost", "profit"]], use_container_width=True, hide_index=True)
        selected = st.selectbox("Choose a product to review its saved profit trend", sorted(product_df["product_name"].dropna().unique().tolist()))
        ph = product_df[product_df["product_name"] == selected].copy()
        ph = ph.groupby("record_date", as_index=False)[["revenue", "total_cost", "profit", "quantity"]].sum().sort_values("record_date")
        st.line_chart(ph.set_index("record_date")[["revenue", "total_cost", "profit"]])
        forecast = simple_forecast(ph["profit"].tolist(), 3)
        if forecast is not None:
            forecast_df = pd.DataFrame({"Future estimate": ["Period 1", "Period 2", "Period 3"], "Estimated profit (₹)": forecast}).set_index("Future estimate")
            st.markdown("### FUTURE PROFIT ESTIMATE")
            st.bar_chart(forecast_df)
            st.caption("This is a basic linear-trend estimate from saved records for the selected product. It is not a trained advanced ML model and may be inaccurate if prices, costs or demand change.")
        else:
            st.info("Save at least three records for this product on different dates to show a basic profit trend estimate.")

# ============================================================
# BUSINESS AUTOPILOT
# ============================================================
elif page == "Business Autopilot":
    st.subheader("⚙️ BUSINESS AUTOPILOT")
    st.write("Track inventory and save owner decisions. This prototype does not place orders automatically.")
    with st.form("inventory_form"):
        product = st.text_input("Product name", "Notebook")
        stock = st.number_input("Current stock", min_value=0, value=5, step=1)
        minimum = st.number_input("Minimum stock level", min_value=0, value=10, step=1)
        reorder_qty = st.number_input("Suggested reorder quantity", min_value=0, value=20, step=1)
        decision = st.selectbox("Owner decision", ["Pending", "Approve recommendation", "Reject recommendation"])
        save_inventory = st.form_submit_button("CHECK & SAVE STOCK RECORD")
    if stock <= minimum:
        st.warning(f"Low stock detected for {product}. Suggested reorder: {reorder_qty} units.")
        if decision == "Approve recommendation":
            st.success("Owner approved the recommendation. No order has been placed by this prototype.")
        elif decision == "Reject recommendation":
            st.info("Owner rejected the recommendation.")
        else:
            st.info("Waiting for owner approval.")
    else:
        st.success(f"{product}: stock is currently above the minimum level.")
    if save_inventory:
        if not product.strip():
            st.error("Please enter a product name.")
        else:
            with get_connection() as con:
                con.execute("INSERT INTO inventory_records (product_name,stock,minimum_stock,reorder_quantity,owner_decision,created_at) VALUES (?,?,?,?,?,?)",
                            (product.strip(), int(stock), int(minimum), int(reorder_qty), decision, datetime.now().isoformat(timespec="seconds")))
            st.success("Stock record saved.")
            st.rerun()
    st.markdown("### RECENT STOCK RECORDS")
    if inventory_df.empty:
        st.info("No inventory records saved yet.")
    else:
        st.dataframe(inventory_df[["created_at", "product_name", "stock", "minimum_stock", "reorder_quantity", "owner_decision"]], use_container_width=True, hide_index=True)

# ============================================================
# CYBERSECURITY CENTER
# ============================================================
elif page == "Cybersecurity Center":
    st.subheader("🛡️ CYBERSECURITY CENTER")
    st.caption("Manual event analysis using simple rules. This is not live monitoring, an intrusion detection system, or a replacement for professional security tools.")
    with st.form("security_form"):
        username = st.text_input("Sample username", "demo_user")
        event_date = st.date_input("Event date", value=date.today())
        event_time = st.time_input("Event time", value=time(12, 0))
        attempts = st.number_input("Failed login attempts in this event", min_value=0, value=1, step=1)
        unfamiliar = st.checkbox("Login from an unfamiliar location")
        unusual_time = st.checkbox("Login at an unusual time")
        mfa_enabled = st.checkbox("Multi-factor authentication (MFA) enabled", value=True)
        analyze = st.form_submit_button("ANALYZE & SAVE LOGIN EVENT")
    if analyze:
        reasons = []
        if attempts >= 5:
            reasons.append("5 or more failed login attempts")
        if unfamiliar:
            reasons.append("unfamiliar location")
        if unusual_time:
            reasons.append("unusual login time")
        if not mfa_enabled:
            reasons.append("MFA is not enabled")
        alert = "Suspicious" if reasons else "No alert from these basic rules"
        with get_connection() as con:
            con.execute("INSERT INTO security_events (username,event_date,event_time,failed_attempts,unfamiliar_location,unusual_time,mfa_enabled,alert,created_at) VALUES (?,?,?,?,?,?,?,?,?)",
                        (username.strip() or "unknown", event_date.isoformat(), event_time.strftime("%H:%M"), int(attempts), int(unfamiliar), int(unusual_time), int(mfa_enabled), alert, datetime.now().isoformat(timespec="seconds")))
        if reasons:
            st.error("ALERT: Suspicious login event based on entered details.")
            st.write("Reasons: " + "; ".join(reasons))
            st.write("Suggested next step: verify the event and follow your organization's security process.")
        else:
            st.success("No alert triggered by the selected demo rules.")
        st.rerun()
    st.markdown("### SAVED LOGIN EVENT HISTORY")
    if security_df.empty:
        st.info("No login events saved yet.")
    else:
        st.dataframe(security_df[["created_at", "username", "event_date", "event_time", "failed_attempts", "unfamiliar_location", "unusual_time", "mfa_enabled", "alert"]], use_container_width=True, hide_index=True)

# ============================================================
# SAVED RECORDS
# ============================================================
elif page == "Saved Records":
    st.subheader("🗄️ SAVED RECORDS")
    st.write("These records are stored in the local SQLite file `nexora.db` next to `app.py`.")
    tabs = st.tabs(["Business", "Products", "Inventory", "Security"])
    frames = [business_df, product_df, inventory_df, security_df]
    empty_messages = ["No business records saved.", "No product records saved.", "No inventory records saved.", "No security events saved."]
    for tab, frame, empty_message in zip(tabs, frames, empty_messages):
        with tab:
            if frame.empty:
                st.info(empty_message)
            else:
                st.dataframe(frame, use_container_width=True, hide_index=True)
    st.markdown("---")
    st.caption("Database is local to this computer. Keep a backup of nexora.db if you want to preserve your saved records.")


# ============================================================
# SALES PIPELINE AUTOPILOT — SYNESIS 26 problem statement module
# ============================================================
elif page == "Sales Pipeline Autopilot":
    st.subheader("🚀 SALES PIPELINE AUTOPILOT")
    st.write("Manage consent-aware leads, prioritize opportunities, prepare personalized outreach, and track follow-ups. This prototype does not scrape leads or send messages automatically.")
    stages = ["New", "Qualified", "Contacted", "Interested", "Needs Human Review", "Won", "Lost", "Opted Out"]
    with get_connection() as con:
        leads = pd.read_sql_query("SELECT * FROM sales_leads ORDER BY lead_score DESC, updated_at DESC", con)

    # 1. Lead discovery / enrichment: user-entered or authorized-source leads only.
    with st.expander("1 · Add / enrich a lead", expanded=leads.empty):
        with st.form("lead_add_form"):
            c1, c2 = st.columns(2)
            person = c1.text_input("Contact name *")
            company = c2.text_input("Company / organization *")
            email = c1.text_input("Email address")
            phone = c2.text_input("Phone (optional)")
            source = st.selectbox("Lead source", ["Authorized directory", "Customer referral", "Website enquiry", "Event / networking", "Existing CRM", "Manual demo entry"])
            notes = st.text_area("Verified context / needs (do not enter sensitive personal data)")
            consent = st.checkbox("I have permission/appropriate consent to contact this lead")
            opted_out = st.checkbox("This lead has opted out of contact")
            add_lead = st.form_submit_button("SAVE LEAD")
        if add_lead:
            if not person.strip() or not company.strip():
                st.error("Contact name and company are required.")
            elif email.strip() and "@" not in email:
                st.error("Enter a valid-looking email address or leave it blank.")
            else:
                with get_connection() as con:
                    existing = con.execute("SELECT id FROM sales_leads WHERE (email<>'' AND lower(email)=lower(?)) OR (lower(person_name)=lower(?) AND lower(company)=lower(?))", (email.strip(), person.strip(), company.strip())).fetchone()
                    if existing:
                        st.warning(f"Possible duplicate lead found (record #{existing[0]}). No duplicate was added.")
                    else:
                        now = datetime.now().isoformat(timespec="seconds")
                        con.execute("INSERT INTO sales_leads (person_name,company,email,phone,source,fit_score,engagement_score,intent_score,lead_score,consent,opted_out,stage,followup_date,last_reply,notes,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                            (person.strip(), company.strip(), email.strip(), phone.strip(), source, 0, 0, 0, 0, int(consent), int(opted_out), "Opted Out" if opted_out else "New", "", "", notes.strip(), now, now))
                st.rerun()

    # Refresh data after adding records.
    with get_connection() as con:
        leads = pd.read_sql_query("SELECT * FROM sales_leads ORDER BY lead_score DESC, updated_at DESC", con)

    if not leads.empty:
        total = len(leads)
        qualified = int(leads["stage"].isin(["Qualified", "Contacted", "Interested", "Needs Human Review", "Won"]).sum())
        due = int(((leads["followup_date"] != "") & (leads["followup_date"] <= date.today().isoformat()) & (~leads["stage"].isin(["Won", "Lost", "Opted Out"]))).sum())
        m1, m2, m3 = st.columns(3)
        m1.metric("TOTAL LEADS", total)
        m2.metric("ACTIVE / QUALIFIED", qualified)
        m3.metric("FOLLOW-UPS DUE", due)

    # 2. Lead scoring: explainable weighted score.
    st.markdown("### 2 · Lead scoring")
    if leads.empty:
        st.info("Add a lead first to start the pipeline.")
    else:
        lead_labels = {int(r.id): f"{r.person_name} — {r.company} (score {r.lead_score})" for r in leads.itertuples()}
        selected_id = st.selectbox("Choose lead", list(lead_labels.keys()), format_func=lambda x: lead_labels[x], key="lead_select")
        selected = leads[leads["id"] == selected_id].iloc[0]
        with st.form("score_form"):
            fit = st.slider("Customer / business fit (0–40)", 0, 40, int(selected.fit_score), help="How closely the lead matches your target customer profile.")
            engagement = st.slider("Engagement (0–30)", 0, 30, int(selected.engagement_score), help="Use evidence such as a requested demo or a meaningful enquiry.")
            intent = st.slider("Buying intent (0–30)", 0, 30, int(selected.intent_score), help="Use verified buying signals, not assumptions about personal traits.")
            score_save = st.form_submit_button("SAVE LEAD SCORE")
        if score_save:
            score = int(fit + engagement + intent)
            with get_connection() as con:
                con.execute("UPDATE sales_leads SET fit_score=?, engagement_score=?, intent_score=?, lead_score=?, updated_at=? WHERE id=?", (fit, engagement, intent, score, datetime.now().isoformat(timespec="seconds"), int(selected_id)))
            st.success(f"Score saved: {score}/100. This is a transparent prioritization aid, not a guaranteed conversion prediction.")
            st.rerun()
        current_score = int(selected.lead_score)
        st.progress(max(0, min(100, current_score)))
        st.caption(f"Current score: {current_score}/100 · " + ("High priority" if current_score >= 70 else "Medium priority" if current_score >= 40 else "Needs more qualification"))

        # 3. Personalized outreach draft. Consent is required; never auto-send.
        st.markdown("### 3 · Personalized outreach draft")
        if not bool(selected.consent) or bool(selected.opted_out) or selected.stage == "Opted Out":
            st.warning("Outreach drafting is disabled for this lead until permission/consent is confirmed and the lead has not opted out.")
        else:
            product_or_service = st.text_input("Your product / service", "NEXORA business solution", key="outreach_product")
            value_prop = st.text_area("Relevant value proposition", "helps organize business workflows and improve visibility", key="outreach_value")
            if st.button("GENERATE PERSONALIZED DRAFT", key="draft_outreach"):
                draft = f"Subject: A possible fit for {selected.company}\n\nHi {selected.person_name},\n\nI’m reaching out because {selected.company} may be interested in {product_or_service}. Based on the context we have, {value_prop}.\n\nWould a short conversation be useful? If this is not relevant, please let me know and I will not follow up.\n\nBest regards,\n[Your name]"
                st.text_area("Review and edit before sending", draft, height=230, key="outreach_draft_text")
                st.caption("Draft only: no email or message is sent by this app. Confirm accuracy and obtain human approval before sending.")

        # 4. Follow-up scheduling and 5. reply intelligence.
        st.markdown("### 4 · Follow-up manager and 5 · Reply intelligence")
        with st.form("lead_activity_form"):
            followup = st.date_input("Next follow-up date", value=date.today(), key="lead_followup_date")
            reply = st.text_area("Paste a reply received through your normal channel (optional)", key="lead_reply")
            activity_save = st.form_submit_button("SAVE FOLLOW-UP / CLASSIFY REPLY")
        if activity_save:
            reply_text = reply.strip().lower()
            if any(k in reply_text for k in ["unsubscribe", "stop emailing", "do not contact", "don't contact", "remove me", "opt out"]):
                reply_class, new_stage, optout = "Opt-out request", "Opted Out", 1
            elif any(k in reply_text for k in ["not interested", "no thanks", "not a fit", "please stop"]):
                reply_class, new_stage, optout = "Not interested", "Lost", 0
            elif any(k in reply_text for k in ["demo", "pricing", "interested", "let's talk", "lets talk", "schedule", "meeting"]):
                reply_class, new_stage, optout = "Interested / buying signal", "Interested", 0
            elif any(k in reply_text for k in ["more information", "more info", "details", "question", "how does"]):
                reply_class, new_stage, optout = "Needs more information", "Needs Human Review", 0
            elif reply_text:
                reply_class, new_stage, optout = "Unclear — human review required", "Needs Human Review", 0
            else:
                reply_class, new_stage, optout = "No reply supplied", str(selected.stage), int(selected.opted_out)
            with get_connection() as con:
                con.execute("UPDATE sales_leads SET followup_date=?, last_reply=?, stage=?, opted_out=?, consent=CASE WHEN ?=1 THEN 0 ELSE consent END, updated_at=? WHERE id=?", (followup.isoformat(), reply.strip(), new_stage, optout, optout, datetime.now().isoformat(timespec="seconds"), int(selected_id)))
            st.info(f"Reply classification: **{reply_class}** · Suggested stage: **{new_stage}**. This rule-based result must be reviewed by a person.")
            st.rerun()

        # 6. CRM pipeline, stage changes are explicit and human-controlled.
        st.markdown("### 6 · CRM pipeline")
        with st.form("stage_form"):
            new_stage = st.selectbox("Update lead stage", stages, index=stages.index(selected.stage) if selected.stage in stages else 0)
            new_notes = st.text_area("Update notes", str(selected.notes or ""))
            stage_save = st.form_submit_button("SAVE CRM UPDATE")
        if stage_save:
            with get_connection() as con:
                con.execute("UPDATE sales_leads SET stage=?, notes=?, updated_at=? WHERE id=?", (new_stage, new_notes.strip(), datetime.now().isoformat(timespec="seconds"), int(selected_id)))
                if new_stage == "Opted Out":
                    con.execute("UPDATE sales_leads SET opted_out=1, consent=0 WHERE id=?", (int(selected_id),))
            st.success("CRM record updated.")
            st.rerun()

        # 7. Consent, duplicate and human approval safeguards.
        st.markdown("### 7 · Consent and human-approval safeguards")
        st.write("Before any outreach, a person must confirm the lead source, contact permission, message accuracy, and recipient. Opt-outs disable outreach drafts. Duplicate email/contact-company records are blocked at entry.")
        st.warning("This prototype only prepares drafts and records follow-up dates. It does not send email, scrape websites, connect to an external CRM, or execute purchases/actions automatically.")
        st.markdown("### Pipeline overview")
        view_cols = ["id", "person_name", "company", "email", "source", "lead_score", "stage", "followup_date", "consent", "opted_out", "updated_at"]
        st.dataframe(leads[view_cols], use_container_width=True, hide_index=True)
        csv_data = leads.drop(columns=["notes"], errors="ignore").to_csv(index=False).encode("utf-8-sig")
        st.download_button("Export leads as CSV", data=csv_data, file_name="nexora_sales_leads.csv", mime="text/csv")
        if st.button("DELETE SELECTED LEAD", type="secondary"):
            with get_connection() as con:
                con.execute("DELETE FROM sales_leads WHERE id=?", (int(selected_id),))
            st.success("Lead deleted.")
            st.rerun()

# ============================================================
# AI ADVERTISEMENT STUDIO — added to the original NEXORA app
# ============================================================
elif page == "AI Advertisement Studio":
    st.subheader("✨ AI ADVERTISEMENT STUDIO")
    st.write("Create platform-ready advertisement copy with generative AI. Review all claims before publishing.")
    with st.form("ai_ad_form"):
        product_name = st.text_input("Product or service name", "NEXORA Smart Bottle")
        product_details = st.text_area("Product details and verified benefits", "Reusable water bottle with an insulated design. Avoid claims not included here.")
        target_audience = st.text_input("Target audience", "College students and young professionals")
        objective = st.selectbox("Campaign objective", ["Brand awareness", "Website traffic", "Product sales", "Lead generation", "App installs"])
        platform = st.selectbox("Advertising platform", ["Instagram", "Facebook", "Google Ads", "LinkedIn", "TikTok", "Email"])
        tone = st.selectbox("Writing tone", ["Friendly", "Professional", "Bold", "Playful", "Premium", "Informative"])
        language = st.selectbox("Language", ["English", "Tamil", "Hindi", "Malayalam", "Telugu"])
        variations = st.slider("Number of ad variations", min_value=1, max_value=5, value=3)
        submitted = st.form_submit_button("GENERATE ADVERTISEMENTS")
    if submitted:
        if not product_name.strip() or not product_details.strip() or not target_audience.strip():
            st.error("Please provide the product name, details, and target audience.")
        else:
            # Local template-based generator: no OpenAI API key or internet API needed.
            # This is a free rule-based fallback, not a large-language-model response.
            product = product_name.strip()
            details = product_details.strip().rstrip(".!? ")
            audience = target_audience.strip()
            tone_openers = {
                "Friendly": ["Meet your new favourite", "A little upgrade for your day", "Made with you in mind", "Say hello to", "Bring more ease to your routine"],
                "Professional": ["Introducing", "A practical choice for", "Designed to support", "Discover a smarter approach with", "A solution built for"],
                "Bold": ["Make room for", "Ready to level up with", "Choose better with", "Put the spotlight on", "Make your next move with"],
                "Playful": ["Hey there, meet", "Your routine called—it wants", "Good things are here with", "Add a little fun with", "Psst… have you tried"],
                "Premium": ["Experience the appeal of", "Thoughtfully designed:", "Discover the difference with", "A refined choice:", "Elevate your everyday with"],
                "Informative": ["Get to know", "Here is", "Explore the benefits of", "Learn more about", "A closer look at"],
            }
            objective_cta = {
                "Brand awareness": ["Discover the brand", "Get to know us", "Follow for updates", "Explore what we offer", "Meet us today"],
                "Website traffic": ["Visit our website", "Explore the details", "Learn more online", "See how it works", "Visit us to learn more"],
                "Product sales": ["Explore the product", "Check the details", "Find out more", "Choose what suits you", "View the product"],
                "Lead generation": ["Contact us to learn more", "Ask us a question", "Request more information", "Start a conversation", "Connect with our team"],
                "App installs": ["Explore the app", "Learn about the app", "See what the app offers", "Find out more today", "Discover the app"],
            }
            hashtags_base = " ".join("#" + word for word in product.replace("-", " ").split() if word.isalnum())
            platform_tags = {
                "Instagram": "#Instagram #DiscoverMore",
                "Facebook": "#Facebook #SmallBusiness",
                "Google Ads": "#Search #LearnMore",
                "LinkedIn": "#LinkedIn #Business",
                "TikTok": "#TikTok #MadeForYou",
                "Email": "#Newsletter #Updates",
            }
            language_cta = {
                "English": objective_cta,
                "Tamil": {
                    "Brand awareness": ["எங்கள் பிராண்டை அறியுங்கள்", "மேலும் தெரிந்துகொள்ளுங்கள்", "புதுப்பிப்புகளைப் பின்தொடருங்கள்", "எங்கள் தயாரிப்புகளைப் பாருங்கள்", "இன்றே அறிந்துகொள்ளுங்கள்"],
                    "Website traffic": ["எங்கள் இணையதளத்தைப் பாருங்கள்", "விவரங்களை அறியுங்கள்", "மேலும் படியுங்கள்", "எப்படி செயல்படுகிறது எனப் பாருங்கள்", "மேலும் அறிய இணையதளத்தைப் பாருங்கள்"],
                    "Product sales": ["தயாரிப்பைப் பாருங்கள்", "விவரங்களைச் சரிபாருங்கள்", "மேலும் அறியுங்கள்", "உங்களுக்கு ஏற்றதைத் தேர்ந்தெடுங்கள்", "தயாரிப்பு விவரங்களைப் பாருங்கள்"],
                    "Lead generation": ["மேலும் அறிய எங்களைத் தொடர்புகொள்ளுங்கள்", "உங்கள் கேள்வியைக் கேளுங்கள்", "கூடுதல் தகவலைப் பெறுங்கள்", "உரையாடலைத் தொடங்குங்கள்", "எங்கள் குழுவுடன் இணையுங்கள்"],
                    "App installs": ["செயலியைப் பற்றி அறியுங்கள்", "செயலி விவரங்களைப் பாருங்கள்", "செயலியின் அம்சங்களை அறியுங்கள்", "மேலும் தெரிந்துகொள்ளுங்கள்", "செயலியை ஆராயுங்கள்"],
                },
            }
            ads = []
            openers = tone_openers.get(tone, tone_openers["Friendly"])
            ctas = language_cta.get(language, {}).get(objective, objective_cta.get(objective, ["Learn more"] * 5))
            for idx in range(variations):
                opener = openers[idx % len(openers)]
                cta = ctas[idx % len(ctas)]
                if language == "Tamil":
                    headline = f"{product} — உங்களுக்காக ஒரு சிறந்த தேர்வு"
                    description = f"{details}. {audience} அவர்களுக்காக இந்த தகவலைப் பகிர்கிறோம்."
                    caption = f"{product} பற்றி மேலும் அறியுங்கள். {details}. {cta}!"
                elif language == "Hindi":
                    headline = f"{product} — आपके लिए एक उपयोगी विकल्प"
                    description = f"{details}. यह जानकारी {audience} के लिए है।"
                    caption = f"{product} के बारे में जानें। {details}. {cta}!"
                elif language == "Telugu":
                    headline = f"{product} — మీ కోసం ఒక మంచి ఎంపిక"
                    description = f"{details}. ఈ సమాచారం {audience} కోసం."
                    caption = f"{product} గురించి మరింత తెలుసుకోండి. {details}. {cta}!"
                elif language == "Malayalam":
                    headline = f"{product} — നിങ്ങൾക്കായുള്ള ഒരു മികച്ച തിരഞ്ഞെടുപ്പ്"
                    description = f"{details}. ഈ വിവരം {audience} ലക്ഷ്യമിടുന്നു."
                    caption = f"{product}യെക്കുറിച്ച് കൂടുതൽ അറിയൂ. {details}. {cta}!"
                else:
                    headline = f"{opener} {product}"
                    description = f"{details}. Created for {audience}, with a focus on {objective.lower()}."
                    caption = f"Looking for something relevant to {audience.lower()}? {product}: {details}. {cta}!"
                ad = {
                    "headline": headline,
                    "description": description,
                    "caption": caption,
                    "call_to_action": cta,
                    "hashtags": f"{hashtags_base} {platform_tags.get(platform, '#DiscoverMore')}".strip(),
                }
                ads.append(ad)
            try:
                import json
                with get_connection() as con:
                    for idx, ad in enumerate(ads, start=1):
                        con.execute("""INSERT INTO ad_creatives
                            (product_name,target_audience,objective,platform,tone,language,variation_number,headline,description,caption,call_to_action,hashtags,model_name,created_at)
                            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                            (product, audience, objective, platform, tone, language, idx,
                             ad["headline"], ad["description"], ad["caption"], ad["call_to_action"], ad["hashtags"],
                             "Local template generator (free; no API)", datetime.now().isoformat(timespec="seconds")))
                st.success(f"Created and saved {len(ads)} advertisement variation(s) using the free local generator.")
                st.info("This version uses editable templates and your inputs. It does not call OpenAI or require an API key; a local template generator is less flexible than a full generative AI model.")
                for idx, ad in enumerate(ads, start=1):
                    with st.container(border=True):
                        st.markdown(f"#### Variation {idx}: {ad['headline']}")
                        st.write("**Description:**", ad["description"])
                        st.write("**Caption:**", ad["caption"])
                        st.write("**Call to action:**", ad["call_to_action"])
                        st.write("**Hashtags:**", ad["hashtags"])
                        ad_text = (
                            f"{ad['headline']}\n\n"
                            f"DESCRIPTION\n{ad['description']}\n\n"
                            f"CAPTION\n{ad['caption']}\n\n"
                            f"CALL TO ACTION\n{ad['call_to_action']}\n\n"
                            f"HASHTAGS\n{ad['hashtags']}\n"
                        )
                        st.download_button(
                            "Download advertisement (text)",
                            data=ad_text,
                            file_name=f"nexora_ad_{idx}.txt",
                            mime="text/plain",
                            key=f"ad_download_{idx}"
                        )
            except Exception as exc:
                st.error(f"Could not save advertisement history: {exc}")

    st.markdown("### SAVED ADVERTISEMENT HISTORY")
    ads_df = read_table("ad_creatives")
    if ads_df.empty:
        st.info("No generated ads saved yet.")
    else:
        st.dataframe(ads_df.drop(columns=["id"], errors="ignore"), use_container_width=True, hide_index=True)
        st.download_button("Export ad history as CSV", data=ads_df.to_csv(index=False).encode("utf-8-sig"), file_name="nexora_ad_history.csv", mime="text/csv")

# ---------- FOOTER ----------
st.markdown("---")
st.caption("BIZPILOT-AI: NEXORA | Student Prototype | Predictive BI • Product Profit • Inventory Autopilot • Cybersecurity • AI Advertisement Studio • Sales Pipeline Autopilot • SQLite")
