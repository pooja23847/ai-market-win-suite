import streamlit as st
import pandas as pd
import requests
import json
import mysql.connector
import os
from datetime import datetime
import io
import base64
from dotenv import load_dotenv
from memory_manager import MarketMemoryManager

load_dotenv()

# ==========================================
# DATABASE CONFIG
# ==========================================
DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "user": os.getenv("DB_USER", "root"),
    "password": os.getenv("DB_PASSWORD", ""),
    "database": os.getenv("DB_NAME", "marketwin_db")
}

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")


@st.cache_resource
def get_memory_manager():
    return MarketMemoryManager()

# ==========================================
# DEMO DATA (fallback when MySQL is offline)
# ==========================================
DEMO_INTEL = [
    {"competitor": "CloudVibe Corp",    "category": "Pricing",      "intel": "CloudVibe charges 40% more for their enterprise tier with no additional features. Customers frequently cite hidden overage fees.", "timestamp": "2025-06-01 09:00:00"},
    {"competitor": "CloudVibe Corp",    "category": "Technical",    "intel": "No native REST API — requires a third-party middleware layer. Integration projects average 3x longer than with our platform.", "timestamp": "2025-06-02 11:30:00"},
    {"competitor": "CloudVibe Corp",    "category": "Support",      "intel": "SLA response time is 48 hrs for P1 incidents. Multiple enterprise clients have publicly complained on G2.", "timestamp": "2025-06-03 14:15:00"},
    {"competitor": "NexaFlow AI",       "category": "Feature Gap",  "intel": "No offline mode. Loses all functionality in low-connectivity environments, a critical blocker for field sales teams.", "timestamp": "2025-06-04 08:45:00"},
    {"competitor": "NexaFlow AI",       "category": "Legal",        "intel": "Under GDPR investigation in Germany (Q1 2025). Data residency options limited to US-East only.", "timestamp": "2025-06-05 16:00:00"},
    {"competitor": "NexaFlow AI",       "category": "Pricing",      "intel": "Per-seat pricing with no team discounts. Scales poorly for orgs over 50 users.", "timestamp": "2025-06-06 10:20:00"},
    {"competitor": "DataPulse Inc",     "category": "Technical",    "intel": "Legacy architecture (PHP monolith). Average page load is 4.2s vs our 0.8s. Fails on 10k+ record datasets.", "timestamp": "2025-06-07 13:00:00"},
    {"competitor": "DataPulse Inc",     "category": "Feature Gap",  "intel": "No AI/ML capabilities. Roadmap shows nothing planned for 18 months. Cannot compete on intelligent automation.", "timestamp": "2025-06-08 09:30:00"},
    {"competitor": "SalesBridge Pro",   "category": "Support",      "intel": "Offshore support team with documented language barriers. NPS score dropped from 42 to 28 in last annual survey.", "timestamp": "2025-06-09 15:45:00"},
    {"competitor": "SalesBridge Pro",   "category": "Pricing",      "intel": "Mandatory 3-year lock-in contracts. Customers cannot scale down mid-contract — serious red flag for SMEs.", "timestamp": "2025-06-10 11:00:00"},
]

DEMO_USERS = {
    "demo@marketwin.ai": {"password": "demo123", "role": "Administrator"},
    "sales@marketwin.ai": {"password": "sales123", "role": "Sales"},
}

DEMO_AUDIT = [
    {"id": 1, "timestamp": "2025-06-10 08:00:00", "user": "demo@marketwin.ai",  "action": "User Authentication Successful"},
    {"id": 2, "timestamp": "2025-06-10 08:05:00", "user": "demo@marketwin.ai",  "action": "Extracted Sales Playbook vs 'CloudVibe Corp'"},
    {"id": 3, "timestamp": "2025-06-10 09:12:00", "user": "sales@marketwin.ai", "action": "User Authentication Successful"},
    {"id": 4, "timestamp": "2025-06-10 09:20:00", "user": "sales@marketwin.ai", "action": "Generated Context-Injected B2B Proposal Document"},
    {"id": 5, "timestamp": "2025-06-10 10:30:00", "user": "demo@marketwin.ai",  "action": "Executed Predictive Win Probability Engine"},
]

# ==========================================
# DB HELPERS WITH DEMO FALLBACK
# ==========================================
def check_db():
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        conn.close()
        return True
    except Exception:
        return False

def run_query(query, params=None, is_select=True):
    conn = mysql.connector.connect(**DB_CONFIG)
    cursor = conn.cursor()
    try:
        if is_select:
            cursor.execute(query, params or ())
            return cursor.fetchall()
        else:
            cursor.execute(query, params or ())
            conn.commit()
            return None
    finally:
        cursor.close()
        conn.close()

def log_system_activity(user, action):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if st.session_state.get("demo_mode"):
        st.session_state.demo_audit.append({"id": len(st.session_state.demo_audit)+1, "timestamp": now, "user": user, "action": action})
        return
    try:
        run_query("INSERT INTO audit_logs (timestamp, user, action) VALUES (%s, %s, %s)", (now, user, action), is_select=False)
    except Exception:
        pass

def get_intel_df():
    if st.session_state.get("demo_mode"):
        return pd.DataFrame(st.session_state.demo_intel)
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        df = pd.read_sql_query("SELECT * FROM competitor_intel", conn)
        conn.close()
        return df
    except Exception:
        return pd.DataFrame(columns=["competitor","category","intel","timestamp"])

def insert_intel(competitor, category, intel, timestamp):
    if st.session_state.get("demo_mode"):
        st.session_state.demo_intel.append({"competitor": competitor, "category": category, "intel": intel, "timestamp": timestamp})
        return
    run_query("INSERT INTO competitor_intel (competitor, category, intel, timestamp) VALUES (%s, %s, %s, %s)", (competitor, category, intel, timestamp), is_select=False)

def retain_hindsight_memory(competitor, category, intel, timestamp):
    try:
        update_text = f"{category}: {intel}"
        return get_memory_manager().store_competitor_intel(competitor, update_text, timestamp)
    except Exception:
        return None

def recall_hindsight_context(query):
    try:
        memories = get_memory_manager().recall_relevant_market_data(query)
        return "\n".join([f"- {m.text}" for m in memories]) if memories else "No relevant Hindsight memories recalled."
    except Exception:
        return "No relevant Hindsight memories recalled."

def authenticate(email, password):
    if st.session_state.get("demo_mode") or not st.session_state.get("db_online"):
        user = DEMO_USERS.get(email)
        if user and user["password"] == password:
            return user["role"]
        return None
    try:
        result = run_query("SELECT role FROM users WHERE email=%s AND password=%s", (email, password))
        return result[0][0] if result else None
    except Exception:
        return None

# ==========================================
# PAGE CONFIG
# ==========================================
st.set_page_config(
    page_title="AI Market-Win Suite",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ==========================================
# SESSION STATE INIT
# ==========================================
defaults = {
    "logged_in": False, "user_email": "", "role": "",
    "theme_preference": "Executive Dark", "demo_mode": False,
    "db_online": False, "toast_msg": None, "toast_type": "success",
    "demo_intel": list(DEMO_INTEL), "demo_audit": list(DEMO_AUDIT),
    "battlecard_output": "", "proposal_output": "",
    "show_search": False,
}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

# Check DB once per session
if "db_checked" not in st.session_state:
    st.session_state.db_online = check_db()
    st.session_state.db_checked = True
    if not st.session_state.db_online:
        st.session_state.demo_mode = True

# ==========================================
# TOAST NOTIFICATION HELPER
# ==========================================
def show_toast(msg, t="success"):
    st.session_state.toast_msg = msg
    st.session_state.toast_type = t

TOAST_CSS = ""
if st.session_state.toast_msg:
    color = {"success": "#10B981", "error": "#EF4444", "info": "#3B82F6"}.get(st.session_state.toast_type, "#3B82F6")
    icon  = {"success": "✓", "error": "✕", "info": "i"}.get(st.session_state.toast_type, "i")
    TOAST_CSS = f"""
    <style>
    .mw-toast {{
        position: fixed; bottom: 28px; right: 28px; z-index: 9999;
        background: #1A2235; border: 1px solid {color}55;
        border-left: 4px solid {color};
        padding: 14px 20px; border-radius: 10px;
        display: flex; align-items: center; gap: 12px;
        box-shadow: 0 8px 32px rgba(0,0,0,0.4);
        animation: slideIn 0.3s ease, fadeOut 0.5s ease 3.5s forwards;
        min-width: 280px; max-width: 420px;
    }}
    .mw-toast .t-icon {{
        width: 24px; height: 24px; border-radius: 50%;
        background: {color}22; color: {color};
        display: flex; align-items: center; justify-content: center;
        font-size: 0.8rem; font-weight: 700; flex-shrink: 0;
    }}
    .mw-toast .t-msg {{ font-size: 0.88rem; color: #F1F5F9; font-weight: 500; }}
    @keyframes slideIn {{ from {{ transform: translateX(120%); opacity:0; }} to {{ transform: translateX(0); opacity:1; }} }}
    @keyframes fadeOut {{ from {{ opacity:1; }} to {{ opacity:0; pointer-events:none; }} }}
    </style>
    <div class="mw-toast">
        <div class="t-icon">{icon}</div>
        <div class="t-msg">{st.session_state.toast_msg}</div>
    </div>
    """
    st.session_state.toast_msg = None

# ==========================================
# MASTER CSS
# ==========================================
def get_css(dark=True):
    if dark:
        return """
<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@300;400;500;600;700&family=Inter:wght@300;400;500;600&family=JetBrains+Mono:wght@400;500&display=swap');
:root {
    --bg-primary:#080C18; --bg-secondary:#0F1629; --bg-card:#131929;
    --bg-card-hover:#1A2235; --bg-input:#0A0F1E;
    --border-subtle:rgba(255,255,255,0.06); --border-active:rgba(59,130,246,0.5);
    --accent-blue:#3B82F6; --accent-blue-dim:rgba(59,130,246,0.15);
    --accent-emerald:#10B981; --accent-violet:#8B5CF6; --accent-amber:#F59E0B;
    --text-primary:#F1F5F9; --text-secondary:#94A3B8; --text-muted:#475569;
    --shadow-card:0 4px 24px rgba(0,0,0,0.4); --shadow-glow:0 0 40px rgba(59,130,246,0.12);
}
.stApp {
    background: var(--bg-primary) !important;
    background-image: radial-gradient(ellipse 80% 60% at 50% -20%,rgba(59,130,246,0.08) 0%,transparent 60%),
                      radial-gradient(ellipse 50% 40% at 85% 80%,rgba(139,92,246,0.06) 0%,transparent 50%) !important;
    font-family:'Inter',-apple-system,sans-serif !important; color:var(--text-primary) !important;
}
*,*::before,*::after{box-sizing:border-box}
h1,h2,h3,h4,h5,h6{font-family:'Space Grotesk',sans-serif !important;color:var(--text-primary) !important;letter-spacing:-0.02em}
p,span,div,label{font-family:'Inter',sans-serif !important;color:var(--text-primary) !important}
code,pre{font-family:'JetBrains Mono',monospace !important}
[data-testid="stSidebar"]{background:linear-gradient(180deg,#080C18 0%,#0A0F1E 100%) !important;border-right:1px solid var(--border-subtle) !important;padding-top:0 !important}
[data-testid="stSidebar"] *{color:var(--text-primary) !important}
[data-testid="stSidebar"] p,[data-testid="stSidebar"] .stSelectbox label{color:var(--text-secondary) !important;font-size:0.85rem !important}
.stButton>button{background:linear-gradient(135deg,#2563EB,#3B82F6) !important;color:#FFF !important;border:none !important;border-radius:8px !important;padding:0.6rem 1.5rem !important;font-family:'Space Grotesk',sans-serif !important;font-weight:600 !important;font-size:0.9rem !important;box-shadow:0 4px 14px rgba(59,130,246,0.3) !important;transition:all 0.2s ease !important;width:100% !important}
.stButton>button:hover{background:linear-gradient(135deg,#1D4ED8,#2563EB) !important;box-shadow:0 6px 20px rgba(59,130,246,0.45) !important;transform:translateY(-1px) !important}
div[data-baseweb="input"]>div,div[data-baseweb="textarea"]>div{background-color:var(--bg-input) !important;border:1px solid rgba(255,255,255,0.08) !important;border-radius:8px !important;transition:border-color 0.2s ease !important}
div[data-baseweb="input"]>div:focus-within,div[data-baseweb="textarea"]>div:focus-within{border-color:var(--accent-blue) !important;box-shadow:0 0 0 3px rgba(59,130,246,0.12) !important}
input,textarea{color:var(--text-primary) !important;font-family:'Inter',sans-serif !important;background:transparent !important}
input::placeholder,textarea::placeholder{color:var(--text-muted) !important}
div[data-baseweb="select"]>div{background-color:var(--bg-input) !important;border:1px solid rgba(255,255,255,0.08) !important;border-radius:8px !important;color:var(--text-primary) !important}
div[data-baseweb="select"] svg{color:var(--text-secondary) !important}
[data-baseweb="popover"]{background:var(--bg-card) !important;border:1px solid var(--border-subtle) !important;border-radius:8px !important}
[role="option"]{background:var(--bg-card) !important;color:var(--text-primary) !important}
[role="option"]:hover{background:var(--bg-card-hover) !important}
.stTabs [data-baseweb="tab-list"]{background:var(--bg-secondary) !important;border-radius:12px !important;padding:4px !important;gap:2px !important;border:1px solid var(--border-subtle) !important;flex-wrap:wrap !important}
.stTabs [data-baseweb="tab"]{background:transparent !important;color:var(--text-secondary) !important;border:none !important;border-radius:8px !important;padding:0.5rem 1.1rem !important;font-family:'Space Grotesk',sans-serif !important;font-weight:500 !important;font-size:0.85rem !important;transition:all 0.2s ease !important}
.stTabs [data-baseweb="tab"]:hover{color:var(--text-primary) !important;background:var(--bg-card) !important}
.stTabs [aria-selected="true"]{background:linear-gradient(135deg,#2563EB,#3B82F6) !important;color:#FFF !important;box-shadow:0 2px 12px rgba(59,130,246,0.35) !important}
.stTabs [data-baseweb="tab-panel"]{background:transparent !important;padding-top:1.5rem !important}
div[data-testid="stForm"]{background:var(--bg-card) !important;border:1px solid var(--border-subtle) !important;border-radius:16px !important;padding:2rem !important;box-shadow:var(--shadow-card) !important}
div[data-testid="stDataFrame"]{border:1px solid var(--border-subtle) !important;border-radius:12px !important;overflow:hidden !important}
div[data-testid="stDataFrame"] *{color:#1E293B !important;font-family:'Inter',sans-serif !important;font-size:0.85rem !important}
div[data-testid="stMetric"]{background:var(--bg-card) !important;border:1px solid var(--border-subtle) !important;border-radius:12px !important;padding:1.25rem !important;box-shadow:var(--shadow-card) !important}
div[data-testid="stMetric"] label{color:var(--text-secondary) !important;font-size:0.8rem !important;font-weight:500 !important;text-transform:uppercase !important;letter-spacing:0.08em !important}
div[data-testid="stMetric"] div[data-testid="stMetricValue"]{color:var(--text-primary) !important;font-family:'Space Grotesk',sans-serif !important;font-size:2rem !important;font-weight:700 !important}
.stInfo>div{background:rgba(59,130,246,0.1) !important;border-color:rgba(59,130,246,0.3) !important;color:#93C5FD !important;border-radius:10px !important}
.stSuccess>div{background:rgba(16,185,129,0.1) !important;border-color:rgba(16,185,129,0.3) !important;color:#6EE7B7 !important;border-radius:10px !important}
.stError>div{background:rgba(239,68,68,0.1) !important;border-color:rgba(239,68,68,0.3) !important;color:#FCA5A5 !important;border-radius:10px !important}
.stTextInput label,.stTextArea label,.stSelectbox label,.stSlider label{color:var(--text-secondary) !important;font-size:0.82rem !important;font-weight:500 !important;text-transform:uppercase !important;letter-spacing:0.06em !important}
.stCaption{color:var(--text-muted) !important;font-size:0.75rem !important}
[data-testid="stSidebar"] hr{border-color:var(--border-subtle) !important}
::-webkit-scrollbar{width:6px;height:6px}
::-webkit-scrollbar-track{background:var(--bg-secondary)}
::-webkit-scrollbar-thumb{background:rgba(255,255,255,0.1);border-radius:3px}
::-webkit-scrollbar-thumb:hover{background:rgba(255,255,255,0.2)}

/* FIXED: Sidebar collapse/expand toggle button */
button[data-testid="baseButton-header"],
button[data-testid="collapsedControl"] {
    background: rgba(59,130,246,0.1) !important;
    border: 1px solid rgba(59,130,246,0.25) !important;
    border-radius: 8px !important;
    color: #3B82F6 !important;
    width: 36px !important;
    height: 36px !important;
    padding: 0 !important;
    box-shadow: none !important;
    transform: none !important;
}
button[data-testid="baseButton-header"]:hover,
button[data-testid="collapsedControl"]:hover {
    background: rgba(59,130,246,0.2) !important;
    transform: none !important;
    box-shadow: none !important;
}
button[data-testid="baseButton-header"] svg,
button[data-testid="collapsedControl"] svg {
    color: #3B82F6 !important;
    width: 18px !important;
    height: 18px !important;
}
/* Hide any text nodes that leak into the toggle button */
button[data-testid="baseButton-header"] p,
button[data-testid="collapsedControl"] p {
    display: none !important;
    font-size: 0 !important;
    visibility: hidden !important;
}

/* ── CUSTOM COMPONENTS ── */
.mw-metric-card{background:var(--bg-card);border:1px solid var(--border-subtle);border-radius:14px;padding:1.25rem 1.5rem;text-align:center;position:relative;overflow:hidden;transition:transform 0.2s,box-shadow 0.2s}
.mw-metric-card::before{content:'';position:absolute;top:0;left:0;right:0;height:2px;background:linear-gradient(90deg,var(--accent-blue),var(--accent-violet))}
.mw-metric-value{font-family:'Space Grotesk',sans-serif;font-size:2rem;font-weight:700;color:var(--text-primary) !important;line-height:1;margin-bottom:0.35rem}
.mw-metric-label{font-size:0.78rem;font-weight:500;color:var(--text-secondary) !important;text-transform:uppercase;letter-spacing:0.06em}
.mw-badge{display:inline-flex;align-items:center;gap:6px;background:rgba(16,185,129,0.12);color:#34D399 !important;border:1px solid rgba(16,185,129,0.25);padding:4px 12px 4px 8px;border-radius:20px;font-size:0.78rem;font-weight:600;letter-spacing:0.04em;text-transform:uppercase}
.mw-badge-demo{display:inline-flex;align-items:center;gap:6px;background:rgba(245,158,11,0.12);color:#FCD34D !important;border:1px solid rgba(245,158,11,0.25);padding:4px 12px 4px 8px;border-radius:20px;font-size:0.78rem;font-weight:600;letter-spacing:0.04em;text-transform:uppercase}
.mw-badge .dot,.mw-badge-demo .dot{width:6px;height:6px;border-radius:50%;animation:pulse 2s infinite}
.mw-badge .dot{background:#10B981}
.mw-badge-demo .dot{background:#F59E0B}
@keyframes pulse{0%,100%{opacity:1;transform:scale(1)}50%{opacity:0.5;transform:scale(0.85)}}
.mw-hero-title{font-family:'Space Grotesk',sans-serif;font-size:3rem;font-weight:700;line-height:1.1;letter-spacing:-0.03em;color:var(--text-primary) !important;margin:0.75rem 0 1rem 0}
.mw-hero-title span{background:linear-gradient(135deg,#60A5FA,#818CF8);-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;color:transparent !important}
.mw-hero-sub{font-size:1rem;line-height:1.7;color:var(--text-secondary) !important;margin-bottom:0.75rem}
.mw-hero-stat{font-size:0.85rem;color:var(--accent-amber) !important;font-weight:600;margin-bottom:2rem;padding:0.6rem 1rem;background:rgba(245,158,11,0.08);border:1px solid rgba(245,158,11,0.2);border-radius:8px;display:inline-block}
.mw-login-card{background:var(--bg-card);border:1px solid var(--border-subtle);border-radius:20px;padding:2.5rem;box-shadow:var(--shadow-card),var(--shadow-glow);position:relative;overflow:hidden}
.mw-login-card::before{content:'';position:absolute;top:0;left:0;right:0;height:3px;background:linear-gradient(90deg,#3B82F6,#8B5CF6,#10B981)}
.mw-login-title{font-family:'Space Grotesk',sans-serif;font-size:1.4rem;font-weight:600;color:var(--text-primary) !important;margin:0 0 0.4rem 0}
.mw-login-sub{font-size:0.875rem;color:var(--text-secondary) !important;margin-bottom:1.75rem}
.mw-section-header{display:flex;align-items:center;gap:12px;margin-bottom:1.75rem;padding-bottom:1rem;border-bottom:1px solid var(--border-subtle)}
.mw-section-icon{width:38px;height:38px;background:var(--accent-blue-dim);border:1px solid rgba(59,130,246,0.2);border-radius:10px;display:flex;align-items:center;justify-content:center;font-size:1.1rem}
.mw-section-title{font-family:'Space Grotesk',sans-serif;font-size:1.3rem;font-weight:600;color:var(--text-primary) !important;margin:0;line-height:1}
.mw-section-desc{font-size:0.82rem;color:var(--text-secondary) !important;margin:0}
.mw-alert-success{background:rgba(16,185,129,0.1);border:1px solid rgba(16,185,129,0.25);border-radius:10px;padding:1rem 1.25rem;color:#6EE7B7 !important;font-size:0.9rem;display:flex;align-items:flex-start;gap:10px}
.mw-alert-error{background:rgba(239,68,68,0.1);border:1px solid rgba(239,68,68,0.25);border-radius:10px;padding:1rem 1.25rem;color:#FCA5A5 !important;font-size:0.9rem;display:flex;align-items:flex-start;gap:10px}
.mw-win-score{background:linear-gradient(135deg,var(--bg-card),var(--bg-card-hover));border:1px solid var(--border-active);border-radius:16px;padding:2rem;text-align:center;box-shadow:var(--shadow-card),0 0 30px rgba(59,130,246,0.1)}
.mw-win-score .score-number{font-family:'Space Grotesk',sans-serif;font-size:4.5rem;font-weight:700;background:linear-gradient(135deg,#60A5FA,#818CF8);-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;line-height:1;display:block}
.mw-win-score .score-label{font-size:0.85rem;font-weight:500;color:var(--text-secondary) !important;text-transform:uppercase;letter-spacing:0.08em;margin-top:0.5rem}
.mw-profile-card{background:rgba(255,255,255,0.03);border:1px solid var(--border-subtle);border-radius:12px;padding:1rem 1.1rem;margin-bottom:0.75rem}
.mw-profile-email{font-size:0.82rem;font-weight:600;color:var(--text-primary) !important;word-break:break-all}
.mw-profile-role{font-size:0.75rem;color:var(--accent-blue) !important;font-weight:500;margin-top:2px;text-transform:uppercase;letter-spacing:0.05em}
.mw-workspace-title{font-family:'Space Grotesk',sans-serif;font-size:1.7rem;font-weight:700;color:var(--text-primary) !important;margin:0;letter-spacing:-0.02em}
.mw-workspace-sub{font-size:0.82rem;color:var(--text-secondary) !important;margin:0}
.mw-ai-output{background:linear-gradient(135deg,rgba(59,130,246,0.06),rgba(139,92,246,0.06));border:1px solid rgba(59,130,246,0.2);border-radius:14px;padding:1.75rem;font-size:0.92rem;line-height:1.75;color:var(--text-primary) !important;white-space:pre-wrap;box-shadow:0 4px 20px rgba(59,130,246,0.06)}
.mw-divider{border:none;border-top:1px solid var(--border-subtle);margin:1.5rem 0}
.mw-wordmark{display:flex;align-items:center;gap:10px;padding:1.5rem 1rem 1.25rem 1rem;border-bottom:1px solid var(--border-subtle);margin-bottom:1.25rem}
.mw-wordmark-icon{width:32px;height:32px;background:linear-gradient(135deg,#3B82F6,#8B5CF6);border-radius:8px;display:flex;align-items:center;justify-content:center;font-size:1rem}
.mw-wordmark-text{font-family:'Space Grotesk',sans-serif;font-size:1rem;font-weight:700;color:var(--text-primary) !important;letter-spacing:-0.01em}
.mw-wordmark-ver{font-size:0.68rem;color:var(--text-muted) !important;margin-top:1px}

/* ROI card */
.mw-roi-card{background:linear-gradient(135deg,rgba(16,185,129,0.08),rgba(59,130,246,0.08));border:1px solid rgba(16,185,129,0.2);border-radius:14px;padding:1.5rem;position:relative;overflow:hidden}
.mw-roi-card::before{content:'ROI';position:absolute;top:-10px;right:16px;font-family:'Space Grotesk',sans-serif;font-size:4rem;font-weight:700;color:rgba(16,185,129,0.05);line-height:1}
.mw-roi-row{display:flex;gap:1rem;flex-wrap:wrap;margin-top:0.75rem}
.mw-roi-item{flex:1;min-width:100px;text-align:center}
.mw-roi-num{font-family:'Space Grotesk',sans-serif;font-size:1.6rem;font-weight:700;color:#10B981 !important}
.mw-roi-lbl{font-size:0.75rem;color:var(--text-secondary) !important;text-transform:uppercase;letter-spacing:0.06em}

/* Comparison matrix */
.mw-matrix-wrap{overflow-x:auto;border-radius:12px;border:1px solid var(--border-subtle)}
.mw-matrix{width:100%;border-collapse:collapse;font-size:0.85rem}
.mw-matrix th{background:var(--bg-secondary);padding:0.75rem 1rem;text-align:left;font-family:'Space Grotesk',sans-serif;font-weight:600;font-size:0.78rem;text-transform:uppercase;letter-spacing:0.06em;color:var(--text-secondary) !important;border-bottom:1px solid var(--border-subtle)}
.mw-matrix td{padding:0.75rem 1rem;border-bottom:1px solid var(--border-subtle);color:var(--text-primary) !important;vertical-align:middle}
.mw-matrix tr:last-child td{border-bottom:none}
.mw-matrix tr:hover td{background:var(--bg-card-hover)}
.mw-matrix .us{color:#10B981 !important;font-weight:600}
.mw-matrix .them{color:#EF4444 !important}
.mw-matrix .neutral{color:var(--text-secondary) !important}
.mw-check{color:#10B981;font-size:1rem}
.mw-cross{color:#EF4444;font-size:1rem}

/* Empty state */
.mw-empty-state{text-align:center;padding:3.5rem 2rem;color:var(--text-secondary) !important}
.mw-empty-icon{font-size:3rem;margin-bottom:1rem;display:block;opacity:0.5}
.mw-empty-title{font-family:'Space Grotesk',sans-serif;font-size:1.1rem;font-weight:600;color:var(--text-secondary) !important;margin-bottom:0.5rem}
.mw-empty-desc{font-size:0.85rem;color:var(--text-muted) !important}

/* Search bar */
.mw-search-row{display:flex;gap:0.75rem;margin-bottom:1.25rem;align-items:flex-end}

/* Export button variant */
.mw-export-btn{display:inline-flex;align-items:center;gap:8px;background:rgba(16,185,129,0.1);border:1px solid rgba(16,185,129,0.25);color:#34D399 !important;padding:0.5rem 1.1rem;border-radius:8px;font-size:0.85rem;font-weight:600;cursor:pointer;text-decoration:none;transition:all 0.2s}
.mw-export-btn:hover{background:rgba(16,185,129,0.18);transform:translateY(-1px)}

/* Footer */
.mw-footer{margin-top:3rem;padding:1.5rem 0 0.5rem 0;border-top:1px solid var(--border-subtle);display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:1rem}
.mw-footer-stack{display:flex;align-items:center;gap:0.75rem;flex-wrap:wrap}
.mw-footer-tag{background:var(--bg-card);border:1px solid var(--border-subtle);border-radius:6px;padding:3px 10px;font-size:0.75rem;font-weight:500;color:var(--text-secondary) !important}
.mw-footer-copy{font-size:0.75rem;color:var(--text-muted) !important}

/* Demo banner */
.mw-demo-banner{background:linear-gradient(90deg,rgba(245,158,11,0.1),rgba(245,158,11,0.05));border:1px solid rgba(245,158,11,0.25);border-radius:10px;padding:0.85rem 1.25rem;margin-bottom:1.5rem;display:flex;align-items:center;gap:12px;font-size:0.88rem;color:#FCD34D !important}

/* Streaming output wrapper */
.mw-stream-wrap{position:relative}
.mw-copy-btn{position:absolute;top:12px;right:12px;background:rgba(255,255,255,0.08);border:1px solid rgba(255,255,255,0.12);border-radius:6px;padding:4px 10px;font-size:0.75rem;color:var(--text-secondary) !important;cursor:pointer;transition:all 0.2s}
.mw-copy-btn:hover{background:rgba(255,255,255,0.14);color:var(--text-primary) !important}
</style>"""
    else:
        return """
<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@300;400;500;600;700&family=Inter:wght@300;400;500;600&family=JetBrains+Mono:wght@400;500&display=swap');
:root{--bg-primary:#F0F4FF;--bg-secondary:#FFFFFF;--bg-card:#FFFFFF;--bg-card-hover:#F8FAFF;--bg-input:#F8FAFF;--border-subtle:rgba(0,0,0,0.07);--border-active:rgba(37,99,235,0.4);--accent-blue:#2563EB;--accent-blue-dim:rgba(37,99,235,0.08);--accent-emerald:#059669;--accent-violet:#7C3AED;--accent-amber:#D97706;--text-primary:#0F172A;--text-secondary:#475569;--text-muted:#94A3B8;--shadow-card:0 2px 16px rgba(0,0,0,0.07);--shadow-glow:0 0 40px rgba(37,99,235,0.08)}
.stApp{background:var(--bg-primary) !important;background-image:radial-gradient(ellipse 80% 60% at 50% -20%,rgba(37,99,235,0.05) 0%,transparent 60%) !important;font-family:'Inter',-apple-system,sans-serif !important;color:var(--text-primary) !important}
*,*::before,*::after{box-sizing:border-box}
h1,h2,h3,h4,h5,h6{font-family:'Space Grotesk',sans-serif !important;color:var(--text-primary) !important;letter-spacing:-0.02em}
p,span,div,label{font-family:'Inter',sans-serif !important;color:var(--text-primary) !important}
code,pre{font-family:'JetBrains Mono',monospace !important}
[data-testid="stSidebar"]{background:linear-gradient(180deg,#0F172A 0%,#1E293B 100%) !important;border-right:1px solid rgba(255,255,255,0.06) !important}
[data-testid="stSidebar"] *{color:#F1F5F9 !important}
[data-testid="stSidebar"] p,[data-testid="stSidebar"] .stSelectbox label{color:#94A3B8 !important;font-size:0.85rem !important}
.stButton>button{background:linear-gradient(135deg,#1D4ED8,#2563EB) !important;color:#FFF !important;border:none !important;border-radius:8px !important;padding:0.6rem 1.5rem !important;font-family:'Space Grotesk',sans-serif !important;font-weight:600 !important;font-size:0.9rem !important;box-shadow:0 4px 14px rgba(37,99,235,0.25) !important;transition:all 0.2s ease !important;width:100% !important}
.stButton>button:hover{background:linear-gradient(135deg,#1E40AF,#1D4ED8) !important;box-shadow:0 6px 20px rgba(37,99,235,0.4) !important;transform:translateY(-1px) !important}
div[data-baseweb="input"]>div,div[data-baseweb="textarea"]>div{background-color:var(--bg-input) !important;border:1px solid rgba(0,0,0,0.1) !important;border-radius:8px !important}
div[data-baseweb="input"]>div:focus-within,div[data-baseweb="textarea"]>div:focus-within{border-color:var(--accent-blue) !important;box-shadow:0 0 0 3px rgba(37,99,235,0.1) !important}
input,textarea{color:var(--text-primary) !important;background:transparent !important}
input::placeholder,textarea::placeholder{color:var(--text-muted) !important}
div[data-baseweb="select"]>div{background-color:var(--bg-input) !important;border:1px solid rgba(0,0,0,0.1) !important;border-radius:8px !important;color:var(--text-primary) !important}
[data-baseweb="popover"]{background:#FFF !important;border:1px solid rgba(0,0,0,0.08) !important;border-radius:8px !important;box-shadow:0 8px 24px rgba(0,0,0,0.1) !important}
[role="option"]{background:#FFF !important;color:var(--text-primary) !important}
[role="option"]:hover{background:#F8FAFF !important}
.stTabs [data-baseweb="tab-list"]{background:#FFF !important;border-radius:12px !important;padding:4px !important;gap:2px !important;border:1px solid rgba(0,0,0,0.07) !important;box-shadow:0 2px 8px rgba(0,0,0,0.05) !important;flex-wrap:wrap !important}
.stTabs [data-baseweb="tab"]{background:transparent !important;color:#475569 !important;border:none !important;border-radius:8px !important;padding:0.5rem 1.1rem !important;font-family:'Space Grotesk',sans-serif !important;font-weight:500 !important;font-size:0.85rem !important;transition:all 0.2s ease !important}
.stTabs [data-baseweb="tab"]:hover{color:#0F172A !important;background:#F8FAFF !important}
.stTabs [aria-selected="true"]{background:linear-gradient(135deg,#1D4ED8,#2563EB) !important;color:#FFF !important;box-shadow:0 2px 10px rgba(37,99,235,0.3) !important}
.stTabs [data-baseweb="tab-panel"]{background:transparent !important;padding-top:1.5rem !important}
div[data-testid="stForm"]{background:var(--bg-card) !important;border:1px solid var(--border-subtle) !important;border-radius:16px !important;padding:2rem !important;box-shadow:var(--shadow-card) !important}
div[data-testid="stDataFrame"]{border:1px solid var(--border-subtle) !important;border-radius:12px !important;overflow:hidden !important;box-shadow:var(--shadow-card) !important}
div[data-testid="stDataFrame"] *{color:#0F172A !important;font-size:0.85rem !important}
div[data-testid="stMetric"]{background:var(--bg-card) !important;border:1px solid var(--border-subtle) !important;border-radius:12px !important;padding:1.25rem !important;box-shadow:var(--shadow-card) !important}
div[data-testid="stMetric"] label{color:var(--text-secondary) !important;font-size:0.8rem !important;font-weight:500 !important;text-transform:uppercase !important;letter-spacing:0.08em !important}
div[data-testid="stMetric"] div[data-testid="stMetricValue"]{color:var(--text-primary) !important;font-family:'Space Grotesk',sans-serif !important;font-size:2rem !important;font-weight:700 !important}
.stTextInput label,.stTextArea label,.stSelectbox label,.stSlider label{color:var(--text-secondary) !important;font-size:0.82rem !important;font-weight:500 !important;text-transform:uppercase !important;letter-spacing:0.06em !important}
.stCaption{color:#94A3B8 !important;font-size:0.75rem !important}
[data-testid="stSidebar"] hr{border-color:rgba(255,255,255,0.08) !important}
::-webkit-scrollbar{width:6px;height:6px}
::-webkit-scrollbar-track{background:rgba(0,0,0,0.03)}
::-webkit-scrollbar-thumb{background:rgba(0,0,0,0.12);border-radius:3px}

/* FIXED: Sidebar collapse/expand toggle button - light theme */
button[data-testid="baseButton-header"],
button[data-testid="collapsedControl"] {
    background: rgba(37,99,235,0.08) !important;
    border: 1px solid rgba(37,99,235,0.2) !important;
    border-radius: 8px !important;
    color: #2563EB !important;
    width: 36px !important;
    height: 36px !important;
    padding: 0 !important;
    box-shadow: none !important;
    transform: none !important;
}
button[data-testid="baseButton-header"]:hover,
button[data-testid="collapsedControl"]:hover {
    background: rgba(37,99,235,0.15) !important;
    transform: none !important;
    box-shadow: none !important;
}
button[data-testid="baseButton-header"] svg,
button[data-testid="collapsedControl"] svg {
    color: #2563EB !important;
    width: 18px !important;
    height: 18px !important;
}
button[data-testid="baseButton-header"] p,
button[data-testid="collapsedControl"] p {
    display: none !important;
    font-size: 0 !important;
    visibility: hidden !important;
}

.mw-metric-card{background:#FFF;border:1px solid rgba(0,0,0,0.07);border-radius:14px;padding:1.25rem 1.5rem;text-align:center;position:relative;overflow:hidden;box-shadow:0 2px 12px rgba(0,0,0,0.06)}
.mw-metric-card::before{content:'';position:absolute;top:0;left:0;right:0;height:2px;background:linear-gradient(90deg,#2563EB,#7C3AED)}
.mw-metric-value{font-family:'Space Grotesk',sans-serif;font-size:2rem;font-weight:700;color:#0F172A !important;line-height:1;margin-bottom:0.35rem}
.mw-metric-label{font-size:0.78rem;font-weight:500;color:#475569 !important;text-transform:uppercase;letter-spacing:0.06em}
.mw-badge{display:inline-flex;align-items:center;gap:6px;background:rgba(5,150,105,0.08);color:#059669 !important;border:1px solid rgba(5,150,105,0.2);padding:4px 12px 4px 8px;border-radius:20px;font-size:0.78rem;font-weight:600;letter-spacing:0.04em;text-transform:uppercase}
.mw-badge-demo{display:inline-flex;align-items:center;gap:6px;background:rgba(217,119,6,0.08);color:#92400E !important;border:1px solid rgba(217,119,6,0.2);padding:4px 12px 4px 8px;border-radius:20px;font-size:0.78rem;font-weight:600;letter-spacing:0.04em;text-transform:uppercase}
.mw-badge .dot{width:6px;height:6px;background:#059669;border-radius:50%;animation:pulse 2s infinite}
.mw-badge-demo .dot{width:6px;height:6px;background:#D97706;border-radius:50%;animation:pulse 2s infinite}
@keyframes pulse{0%,100%{opacity:1;transform:scale(1)}50%{opacity:0.5;transform:scale(0.85)}}
.mw-hero-title{font-family:'Space Grotesk',sans-serif;font-size:3rem;font-weight:700;line-height:1.1;letter-spacing:-0.03em;color:#0F172A !important;margin:0.75rem 0 1rem 0}
.mw-hero-title span{background:linear-gradient(135deg,#2563EB,#7C3AED);-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;color:transparent !important}
.mw-hero-sub{font-size:1rem;line-height:1.7;color:#475569 !important;margin-bottom:0.75rem}
.mw-hero-stat{font-size:0.85rem;color:#B45309 !important;font-weight:600;margin-bottom:2rem;padding:0.6rem 1rem;background:rgba(217,119,6,0.06);border:1px solid rgba(217,119,6,0.15);border-radius:8px;display:inline-block}
.mw-login-card{background:#FFF;border:1px solid rgba(0,0,0,0.07);border-radius:20px;padding:2.5rem;box-shadow:0 8px 40px rgba(0,0,0,0.1);position:relative;overflow:hidden}
.mw-login-card::before{content:'';position:absolute;top:0;left:0;right:0;height:3px;background:linear-gradient(90deg,#2563EB,#7C3AED,#059669)}
.mw-login-title{font-family:'Space Grotesk',sans-serif;font-size:1.4rem;font-weight:600;color:#0F172A !important;margin:0 0 0.4rem 0}
.mw-login-sub{font-size:0.875rem;color:#475569 !important;margin-bottom:1.75rem}
.mw-section-header{display:flex;align-items:center;gap:12px;margin-bottom:1.75rem;padding-bottom:1rem;border-bottom:1px solid rgba(0,0,0,0.07)}
.mw-section-icon{width:38px;height:38px;background:rgba(37,99,235,0.08);border:1px solid rgba(37,99,235,0.15);border-radius:10px;display:flex;align-items:center;justify-content:center;font-size:1.1rem}
.mw-section-title{font-family:'Space Grotesk',sans-serif;font-size:1.3rem;font-weight:600;color:#0F172A !important;margin:0;line-height:1}
.mw-section-desc{font-size:0.82rem;color:#475569 !important;margin:0}
.mw-alert-success{background:rgba(5,150,105,0.08);border:1px solid rgba(5,150,105,0.2);border-radius:10px;padding:1rem 1.25rem;color:#065F46 !important;font-size:0.9rem;display:flex;align-items:flex-start;gap:10px}
.mw-alert-error{background:rgba(220,38,38,0.06);border:1px solid rgba(220,38,38,0.2);border-radius:10px;padding:1rem 1.25rem;color:#7F1D1D !important;font-size:0.9rem;display:flex;align-items:flex-start;gap:10px}
.mw-win-score{background:linear-gradient(135deg,#F8FAFF,#EFF6FF);border:1px solid rgba(37,99,235,0.2);border-radius:16px;padding:2rem;text-align:center;box-shadow:0 4px 20px rgba(37,99,235,0.08)}
.mw-win-score .score-number{font-family:'Space Grotesk',sans-serif;font-size:4.5rem;font-weight:700;background:linear-gradient(135deg,#2563EB,#7C3AED);-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;line-height:1;display:block}
.mw-win-score .score-label{font-size:0.85rem;font-weight:500;color:#475569 !important;text-transform:uppercase;letter-spacing:0.08em;margin-top:0.5rem}
.mw-profile-card{background:rgba(255,255,255,0.08);border:1px solid rgba(255,255,255,0.1);border-radius:12px;padding:1rem 1.1rem;margin-bottom:0.75rem}
.mw-profile-email{font-size:0.82rem;font-weight:600;color:#F1F5F9 !important;word-break:break-all}
.mw-profile-role{font-size:0.75rem;color:#93C5FD !important;font-weight:500;margin-top:2px;text-transform:uppercase;letter-spacing:0.05em}
.mw-workspace-title{font-family:'Space Grotesk',sans-serif;font-size:1.7rem;font-weight:700;color:var(--text-primary) !important;margin:0;letter-spacing:-0.02em}
.mw-workspace-sub{font-size:0.82rem;color:var(--text-secondary) !important;margin:0}
.mw-ai-output{background:linear-gradient(135deg,rgba(37,99,235,0.04),rgba(124,58,237,0.04));border:1px solid rgba(37,99,235,0.15);border-radius:14px;padding:1.75rem;font-size:0.92rem;line-height:1.75;color:#0F172A !important;white-space:pre-wrap;box-shadow:0 2px 16px rgba(37,99,235,0.04)}
.mw-divider{border:none;border-top:1px solid rgba(0,0,0,0.07);margin:1.5rem 0}
.mw-wordmark{display:flex;align-items:center;gap:10px;padding:1.5rem 1rem 1.25rem 1rem;border-bottom:1px solid rgba(255,255,255,0.08);margin-bottom:1.25rem}
.mw-wordmark-icon{width:32px;height:32px;background:linear-gradient(135deg,#3B82F6,#8B5CF6);border-radius:8px;display:flex;align-items:center;justify-content:center;font-size:1rem}
.mw-wordmark-text{font-family:'Space Grotesk',sans-serif;font-size:1rem;font-weight:700;color:#F1F5F9 !important;letter-spacing:-0.01em}
.mw-wordmark-ver{font-size:0.68rem;color:#64748B !important;margin-top:1px}
.mw-roi-card{background:linear-gradient(135deg,rgba(5,150,105,0.05),rgba(37,99,235,0.05));border:1px solid rgba(5,150,105,0.15);border-radius:14px;padding:1.5rem;position:relative;overflow:hidden}
.mw-roi-card::before{content:'ROI';position:absolute;top:-10px;right:16px;font-family:'Space Grotesk',sans-serif;font-size:4rem;font-weight:700;color:rgba(5,150,105,0.05);line-height:1}
.mw-roi-row{display:flex;gap:1rem;flex-wrap:wrap;margin-top:0.75rem}
.mw-roi-item{flex:1;min-width:100px;text-align:center}
.mw-roi-num{font-family:'Space Grotesk',sans-serif;font-size:1.6rem;font-weight:700;color:#059669 !important}
.mw-roi-lbl{font-size:0.75rem;color:#475569 !important;text-transform:uppercase;letter-spacing:0.06em}
.mw-matrix-wrap{overflow-x:auto;border-radius:12px;border:1px solid rgba(0,0,0,0.07)}
.mw-matrix{width:100%;border-collapse:collapse;font-size:0.85rem}
.mw-matrix th{background:#F8FAFF;padding:0.75rem 1rem;text-align:left;font-family:'Space Grotesk',sans-serif;font-weight:600;font-size:0.78rem;text-transform:uppercase;letter-spacing:0.06em;color:#475569 !important;border-bottom:1px solid rgba(0,0,0,0.07)}
.mw-matrix td{padding:0.75rem 1rem;border-bottom:1px solid rgba(0,0,0,0.05);color:#0F172A !important;vertical-align:middle}
.mw-matrix tr:last-child td{border-bottom:none}
.mw-matrix tr:hover td{background:#F8FAFF}
.mw-matrix .us{color:#059669 !important;font-weight:600}
.mw-matrix .them{color:#DC2626 !important}
.mw-check{color:#059669;font-size:1rem}
.mw-cross{color:#DC2626;font-size:1rem}
.mw-empty-state{text-align:center;padding:3.5rem 2rem;color:#475569 !important}
.mw-empty-icon{font-size:3rem;margin-bottom:1rem;display:block;opacity:0.4}
.mw-empty-title{font-family:'Space Grotesk',sans-serif;font-size:1.1rem;font-weight:600;color:#475569 !important;margin-bottom:0.5rem}
.mw-empty-desc{font-size:0.85rem;color:#94A3B8 !important}
.mw-export-btn{display:inline-flex;align-items:center;gap:8px;background:rgba(5,150,105,0.08);border:1px solid rgba(5,150,105,0.2);color:#059669 !important;padding:0.5rem 1.1rem;border-radius:8px;font-size:0.85rem;font-weight:600;cursor:pointer;text-decoration:none;transition:all 0.2s}
.mw-export-btn:hover{background:rgba(5,150,105,0.14);transform:translateY(-1px)}
.mw-footer{margin-top:3rem;padding:1.5rem 0 0.5rem 0;border-top:1px solid rgba(0,0,0,0.07);display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:1rem}
.mw-footer-stack{display:flex;align-items:center;gap:0.75rem;flex-wrap:wrap}
.mw-footer-tag{background:#FFF;border:1px solid rgba(0,0,0,0.07);border-radius:6px;padding:3px 10px;font-size:0.75rem;font-weight:500;color:#475569 !important}
.mw-footer-copy{font-size:0.75rem;color:#94A3B8 !important}
.mw-demo-banner{background:linear-gradient(90deg,rgba(217,119,6,0.08),rgba(217,119,6,0.03));border:1px solid rgba(217,119,6,0.2);border-radius:10px;padding:0.85rem 1.25rem;margin-bottom:1.5rem;display:flex;align-items:center;gap:12px;font-size:0.88rem;color:#92400E !important}
.mw-stream-wrap{position:relative}
.mw-copy-btn{position:absolute;top:12px;right:12px;background:rgba(0,0,0,0.05);border:1px solid rgba(0,0,0,0.1);border-radius:6px;padding:4px 10px;font-size:0.75rem;color:#475569 !important;cursor:pointer;transition:all 0.2s}
.mw-copy-btn:hover{background:rgba(0,0,0,0.1)}
</style>"""

# ==========================================
# SIDEBAR: THEME + WORDMARK
# ==========================================
with st.sidebar:
    st.markdown("""
        <div class="mw-wordmark">
            <div class="mw-wordmark-icon">⚡</div>
            <div>
                <div class="mw-wordmark-text">MarketWin AI</div>
                <div class="mw-wordmark-ver">v5.0 · Jun 2025</div>
            </div>
        </div>
    """, unsafe_allow_html=True)
    st.markdown('<p style="font-size:0.75rem;font-weight:600;text-transform:uppercase;letter-spacing:0.08em;color:#64748B;margin-bottom:0.5rem;">Interface Theme</p>', unsafe_allow_html=True)
    st.session_state.theme_preference = st.selectbox(
        "theme", ["Executive Dark", "Corporate Light"],
        index=0 if st.session_state.theme_preference == "Executive Dark" else 1,
        label_visibility="collapsed"
    )
    st.markdown("<hr>", unsafe_allow_html=True)

dark = st.session_state.theme_preference == "Executive Dark"
st.markdown(get_css(dark), unsafe_allow_html=True)
if TOAST_CSS:
    st.markdown(TOAST_CSS, unsafe_allow_html=True)

# ==========================================
# LOGIN SCREEN
# ==========================================
if not st.session_state.logged_in:

    # ── TOP HERO ROW ────────────────────────────────────────────────────────
    st.markdown("<div style='height:1rem'></div>", unsafe_allow_html=True)
    hero_left, gap, hero_right = st.columns([1.35, 0.08, 1])

    with hero_left:
        db_online = st.session_state.db_online
        total_intel = len(st.session_state.demo_intel)
        total_comps = len(set(r["competitor"] for r in st.session_state.demo_intel))

        if db_online:
            try:
                total_intel = run_query("SELECT COUNT(*) FROM competitor_intel")[0][0]
                total_comps = run_query("SELECT COUNT(DISTINCT competitor) FROM competitor_intel")[0][0]
            except Exception:
                pass
            st.markdown('<span class="mw-badge"><span class="dot"></span>MySQL · Live</span>', unsafe_allow_html=True)
        else:
            st.markdown('<span class="mw-badge-demo"><span class="dot"></span>Demo Mode · MySQL Offline</span>', unsafe_allow_html=True)

        st.markdown(f"""
            <h1 class="mw-hero-title">
                Sales teams lose 23% of deals<br>due to poor <span>competitive positioning.</span>
            </h1>
            <p class="mw-hero-sub">
                AI Market-Win Suite gives your revenue team structured competitive intelligence,
                AI-generated battlecards, and predictive win scoring — all grounded in a live MySQL engine.
            </p>
            <div class="mw-hero-stat">
                📊 &nbsp;Gartner, 2024 — 67% of B2B buyers say competitive comparison is the #1 factor in vendor selection.
            </div>
        """, unsafe_allow_html=True)

        m1, m2, m3 = st.columns(3)
        with m1:
            st.markdown(f'<div class="mw-metric-card"><div class="mw-metric-value">{total_intel}</div><div class="mw-metric-label">Intel Records</div></div>', unsafe_allow_html=True)
        with m2:
            st.markdown(f'<div class="mw-metric-card"><div class="mw-metric-value">{total_comps}</div><div class="mw-metric-label">Competitors</div></div>', unsafe_allow_html=True)
        with m3:
            st.markdown('<div class="mw-metric-card"><div class="mw-metric-value">LLaMA 3</div><div class="mw-metric-label">AI Engine</div></div>', unsafe_allow_html=True)

    with hero_right:
        st.markdown('<div class="mw-login-card">', unsafe_allow_html=True)
        st.markdown('<p class="mw-login-title">Sign in to your workspace</p>', unsafe_allow_html=True)
        if st.session_state.demo_mode:
            st.markdown('<p class="mw-login-sub">MySQL offline — using demo credentials below.</p>', unsafe_allow_html=True)
            st.markdown("""
                <div style="background:rgba(245,158,11,0.08);border:1px solid rgba(245,158,11,0.2);border-radius:8px;padding:0.75rem 1rem;margin-bottom:1rem;font-size:0.82rem;color:#FCD34D;">
                    <strong>Demo login:</strong> demo@marketwin.ai / demo123<br>
                    <strong>Sales login:</strong> sales@marketwin.ai / sales123
                </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown('<p class="mw-login-sub">Credentials verified against live MySQL user tables.</p>', unsafe_allow_html=True)

        with st.form("security_login_form"):
            email_input = st.text_input("Work Email", placeholder="you@company.com")
            password_input = st.text_input("Password", type="password", placeholder="••••••••")
            auth_submit = st.form_submit_button("Sign In →")

            if auth_submit:
                role = authenticate(email_input, password_input)
                if role:
                    st.session_state.logged_in = True
                    st.session_state.user_email = email_input
                    st.session_state.role = role
                    log_system_activity(email_input, "User Authentication Successful")
                    st.rerun()
                else:
                    st.markdown('<div class="mw-alert-error"><span>⚠</span><div><strong>Authentication failed.</strong> Check your credentials and try again.</div></div>', unsafe_allow_html=True)

        st.markdown('</div>', unsafe_allow_html=True)
        st.markdown("<div style='height:0.75rem'></div>", unsafe_allow_html=True)
        if st.button("🎬  Try with Sample Data (No Login)"):
            st.session_state.logged_in = True
            st.session_state.user_email = "demo@marketwin.ai"
            st.session_state.role = "Administrator"
            st.session_state.demo_mode = True
            st.rerun()

    # ── ABOUT SECTION ────────────────────────────────────────────────────────
    st.markdown("<div style='height:3rem'></div>", unsafe_allow_html=True)
    st.markdown("""
        <div style="text-align:center;margin-bottom:2.5rem">
            <div style="display:inline-block;background:rgba(239,68,68,0.1);border:1px solid rgba(239,68,68,0.25);border-radius:20px;padding:4px 16px;font-size:0.75rem;font-weight:700;color:#F87171;letter-spacing:0.08em;text-transform:uppercase;margin-bottom:1rem">
                THE PROBLEM
            </div>
            <h2 style="font-family:'Space Grotesk',sans-serif;font-size:2.2rem;font-weight:700;letter-spacing:-0.02em;margin:0 0 0.75rem 0">
                Poor proposals are costing companies<br><span style="background:linear-gradient(135deg,#EF4444,#F59E0B);-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text">billions of dollars every year.</span>
            </h2>
            <p style="font-size:1rem;color:var(--text-secondary);max-width:580px;margin:0 auto;line-height:1.7">
                Research from Forrester, McKinsey, and Gartner consistently shows that the #1 reason B2B deals are lost
                is not price — it's the inability to articulate competitive differentiation clearly and fast enough.
            </p>
        </div>
    """, unsafe_allow_html=True)

    # Real stats cards row
    s1, s2, s3, s4 = st.columns(4)
    stats = [
        ("42%", "of B2B deals lost due to failure to communicate value vs competitors", "#EF4444", "Forrester Research, 2023"),
        ("$2.5M", "average annual revenue lost per mid-size company from poor proposals", "#F59E0B", "IDC Sales Productivity Report"),
        ("67%", "of buyers say vendors don't understand their competitive landscape at all", "#8B5CF6", "Gartner B2B Buyer Survey, 2024"),
        ("18hrs", "average time sales reps spend per week on manual competitive research", "#3B82F6", "HubSpot State of Sales, 2024"),
    ]
    for col, (val, desc, color, source) in zip([s1, s2, s3, s4], stats):
        with col:
            st.markdown(f"""
                <div style="background:var(--bg-card);border:1px solid var(--border-subtle);border-radius:16px;padding:1.5rem 1.25rem;text-align:center;position:relative;overflow:hidden;height:100%">
                    <div style="position:absolute;top:0;left:0;right:0;height:3px;background:{color}"></div>
                    <div style="font-family:'Space Grotesk',sans-serif;font-size:2.4rem;font-weight:700;color:{color};line-height:1;margin-bottom:0.75rem">{val}</div>
                    <div style="font-size:0.83rem;line-height:1.5;color:var(--text-secondary);margin-bottom:0.75rem">{desc}</div>
                    <div style="font-size:0.7rem;color:var(--text-muted);font-style:italic">{source}</div>
                </div>
            """, unsafe_allow_html=True)

    st.markdown("<div style='height:3rem'></div>", unsafe_allow_html=True)

    # How we solve it — 3-step flow
    st.markdown("""
        <div style="text-align:center;margin-bottom:2.5rem">
            <div style="display:inline-block;background:rgba(59,130,246,0.1);border:1px solid rgba(59,130,246,0.25);border-radius:20px;padding:4px 16px;font-size:0.75rem;font-weight:700;color:#60A5FA;letter-spacing:0.08em;text-transform:uppercase;margin-bottom:1rem">
                THE SOLUTION
            </div>
            <h2 style="font-family:'Space Grotesk',sans-serif;font-size:2.2rem;font-weight:700;letter-spacing:-0.02em;margin:0 0 0.75rem 0">
                How <span style="background:linear-gradient(135deg,#3B82F6,#8B5CF6);-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text">AI Market-Win Suite</span> solves this
            </h2>
            <p style="font-size:1rem;color:var(--text-secondary);max-width:560px;margin:0 auto;line-height:1.7">
                A complete, AI-powered competitive intelligence platform that turns raw market knowledge into
                revenue-winning proposals — in minutes, not days.
            </p>
        </div>
    """, unsafe_allow_html=True)

    f1, f2, f3, f4 = st.columns(4)
    features = [
        ("🎯", "Structured Intel Database", "Log every competitor weakness, pricing gap, and technical flaw directly into MySQL. Searchable, filterable, always current.", "#3B82F6"),
        ("⚔️", "AI Battlecard Generator", "Groq LLaMA 3.3 70B streams tactical sales battlecards in seconds — complete with discovery questions and objection handlers.", "#8B5CF6"),
        ("📄", "Context-Aware Proposals", "Proposals auto-reference your competitor intel to position your strengths exactly where the client's pain is deepest.", "#10B981"),
        ("📊", "Predictive Win Scoring", "4-vector deal scoring model calculates close probability and expected value so you prioritize the right deals.", "#F59E0B"),
    ]
    for col, (icon, title, desc, color) in zip([f1, f2, f3, f4], features):
        with col:
            st.markdown(f"""
                <div style="background:var(--bg-card);border:1px solid var(--border-subtle);border-radius:16px;padding:1.5rem 1.25rem;height:100%;position:relative;overflow:hidden">
                    <div style="width:44px;height:44px;background:{color}18;border:1px solid {color}33;border-radius:12px;display:flex;align-items:center;justify-content:center;font-size:1.3rem;margin-bottom:1rem">{icon}</div>
                    <div style="font-family:'Space Grotesk',sans-serif;font-size:1rem;font-weight:600;margin-bottom:0.6rem;color:var(--text-primary)">{title}</div>
                    <div style="font-size:0.83rem;line-height:1.6;color:var(--text-secondary)">{desc}</div>
                    <div style="position:absolute;bottom:0;left:0;right:0;height:2px;background:linear-gradient(90deg,{color},transparent)"></div>
                </div>
            """, unsafe_allow_html=True)

    st.markdown("<div style='height:3rem'></div>", unsafe_allow_html=True)

    # Before / After comparison
    st.markdown("""
        <div style="text-align:center;margin-bottom:2rem">
            <h2 style="font-family:'Space Grotesk',sans-serif;font-size:1.8rem;font-weight:700;letter-spacing:-0.02em;margin:0">
                Before vs After MarketWin AI
            </h2>
        </div>
    """, unsafe_allow_html=True)

    ba_left, ba_right = st.columns(2)
    with ba_left:
        st.markdown("""
            <div style="background:rgba(239,68,68,0.06);border:1px solid rgba(239,68,68,0.2);border-radius:16px;padding:1.75rem">
                <div style="font-family:'Space Grotesk',sans-serif;font-weight:700;font-size:1rem;color:#F87171;margin-bottom:1.25rem;display:flex;align-items:center;gap:8px">
                    <span style="width:24px;height:24px;background:rgba(239,68,68,0.2);border-radius:50%;display:inline-flex;align-items:center;justify-content:center;font-size:0.75rem">✕</span>
                    WITHOUT MarketWin AI
                </div>
                <div style="display:flex;flex-direction:column;gap:0.75rem">
                    <div style="font-size:0.86rem;color:var(--text-secondary);padding:0.6rem 0.85rem;background:rgba(239,68,68,0.05);border-radius:8px;border-left:3px solid #EF4444">18+ hours/week on manual competitor research</div>
                    <div style="font-size:0.86rem;color:var(--text-secondary);padding:0.6rem 0.85rem;background:rgba(239,68,68,0.05);border-radius:8px;border-left:3px solid #EF4444">Generic proposals that don't address competitor objections</div>
                    <div style="font-size:0.86rem;color:var(--text-secondary);padding:0.6rem 0.85rem;background:rgba(239,68,68,0.05);border-radius:8px;border-left:3px solid #EF4444">Sales reps blindsided in discovery calls</div>
                    <div style="font-size:0.86rem;color:var(--text-secondary);padding:0.6rem 0.85rem;background:rgba(239,68,68,0.05);border-radius:8px;border-left:3px solid #EF4444">Intel scattered across Slack, email, and sticky notes</div>
                    <div style="font-size:0.86rem;color:var(--text-secondary);padding:0.6rem 0.85rem;background:rgba(239,68,68,0.05);border-radius:8px;border-left:3px solid #EF4444">42% of deals lost to better-positioned competitors</div>
                </div>
            </div>
        """, unsafe_allow_html=True)
    with ba_right:
        st.markdown("""
            <div style="background:rgba(16,185,129,0.06);border:1px solid rgba(16,185,129,0.2);border-radius:16px;padding:1.75rem">
                <div style="font-family:'Space Grotesk',sans-serif;font-weight:700;font-size:1rem;color:#34D399;margin-bottom:1.25rem;display:flex;align-items:center;gap:8px">
                    <span style="width:24px;height:24px;background:rgba(16,185,129,0.2);border-radius:50%;display:inline-flex;align-items:center;justify-content:center;font-size:0.75rem">✓</span>
                    WITH MarketWin AI
                </div>
                <div style="display:flex;flex-direction:column;gap:0.75rem">
                    <div style="font-size:0.86rem;color:var(--text-secondary);padding:0.6rem 0.85rem;background:rgba(16,185,129,0.05);border-radius:8px;border-left:3px solid #10B981">Battlecards generated in &lt;30 seconds from live MySQL intel</div>
                    <div style="font-size:0.86rem;color:var(--text-secondary);padding:0.6rem 0.85rem;background:rgba(16,185,129,0.05);border-radius:8px;border-left:3px solid #10B981">Proposals auto-reference competitor gaps to win every room</div>
                    <div style="font-size:0.86rem;color:var(--text-secondary);padding:0.6rem 0.85rem;background:rgba(16,185,129,0.05);border-radius:8px;border-left:3px solid #10B981">Discovery questions pre-loaded to expose competitor weaknesses</div>
                    <div style="font-size:0.86rem;color:var(--text-secondary);padding:0.6rem 0.85rem;background:rgba(16,185,129,0.05);border-radius:8px;border-left:3px solid #10B981">Single source of truth in a searchable, structured database</div>
                    <div style="font-size:0.86rem;color:var(--text-secondary);padding:0.6rem 0.85rem;background:rgba(16,185,129,0.05);border-radius:8px;border-left:3px solid #10B981">Predictive win scoring to focus on deals you can actually close</div>
                </div>
            </div>
        """, unsafe_allow_html=True)

    # Final CTA
    st.markdown("<div style='height:3rem'></div>", unsafe_allow_html=True)
    st.markdown("""
        <div style="text-align:center;background:linear-gradient(135deg,rgba(59,130,246,0.08),rgba(139,92,246,0.08));border:1px solid rgba(59,130,246,0.15);border-radius:20px;padding:2.5rem 2rem;margin-bottom:1rem">
            <div style="font-family:'Space Grotesk',sans-serif;font-size:1.6rem;font-weight:700;letter-spacing:-0.02em;margin-bottom:0.6rem">
                Ready to stop losing deals to better-positioned competitors?
            </div>
            <p style="font-size:0.95rem;color:var(--text-secondary);margin-bottom:0">
                Sign in above or click <strong style="color:var(--accent-blue)">"Try with Sample Data"</strong> to explore the full platform instantly — no setup required.
            </p>
        </div>
    """, unsafe_allow_html=True)

    # Footer on login page
    st.markdown("""
        <div style="text-align:center;padding:1.5rem 0;border-top:1px solid var(--border-subtle);margin-top:1.5rem">
            <div style="display:flex;align-items:center;justify-content:center;gap:1rem;flex-wrap:wrap;margin-bottom:0.75rem">
                <span style="background:var(--bg-card);border:1px solid var(--border-subtle);border-radius:6px;padding:3px 12px;font-size:0.75rem;font-weight:500;color:var(--text-secondary)">MySQL 8.0</span>
                <span style="background:var(--bg-card);border:1px solid var(--border-subtle);border-radius:6px;padding:3px 12px;font-size:0.75rem;font-weight:500;color:var(--text-secondary)">Groq · LLaMA 3.3 70B</span>
                <span style="background:var(--bg-card);border:1px solid var(--border-subtle);border-radius:6px;padding:3px 12px;font-size:0.75rem;font-weight:500;color:var(--text-secondary)">Streamlit</span>
                <span style="background:var(--bg-card);border:1px solid var(--border-subtle);border-radius:6px;padding:3px 12px;font-size:0.75rem;font-weight:500;color:var(--text-secondary)">Python 3.11</span>
            </div>
            <div style="font-size:0.75rem;color:var(--text-muted)">AI Market-Win Suite v5.0 · © 2025 · All rights reserved</div>
        </div>
    """, unsafe_allow_html=True)

    st.stop()

# ==========================================
# SIDEBAR: SESSION PROFILE
# ==========================================
with st.sidebar:
    st.markdown(f"""
        <div class="mw-profile-card">
            <div class="mw-profile-email">{st.session_state.user_email}</div>
            <div class="mw-profile-role">{st.session_state.role}</div>
        </div>
    """, unsafe_allow_html=True)

    if st.session_state.demo_mode:
        st.markdown('<span class="mw-badge-demo"><span class="dot"></span>Demo Mode</span>', unsafe_allow_html=True)
        st.markdown("<div style='height:0.5rem'></div>", unsafe_allow_html=True)

    if st.button("Sign Out"):
        log_system_activity(st.session_state.user_email, "User Session Terminated")
        for k in ["logged_in","user_email","role","demo_mode","battlecard_output","proposal_output"]:
            st.session_state[k] = "" if k in ["user_email","role","battlecard_output","proposal_output"] else False
        st.rerun()

    st.markdown("<hr>", unsafe_allow_html=True)
    st.caption("AI Market-Win Suite v5.0")
    st.caption("MySQL · Groq LLaMA 3.3 · Streamlit")

# ==========================================
# WORKSPACE HEADER + DEMO BANNER
# ==========================================
wh_l, wh_r = st.columns([3, 1])
with wh_l:
    st.markdown(f"""
        <div style="padding:0 0 1rem 0">
            <p class="mw-workspace-title">Market-Win Workspace</p>
            <p class="mw-workspace-sub">Competitive intelligence · AI battlecards · Predictive win scoring · Proposal engine</p>
        </div>
    """, unsafe_allow_html=True)
with wh_r:
    if st.session_state.demo_mode:
        st.markdown('<div style="height:0.5rem"></div>', unsafe_allow_html=True)
        st.markdown('<span class="mw-badge-demo" style="float:right"><span class="dot"></span>Demo Data</span>', unsafe_allow_html=True)

if st.session_state.demo_mode:
    st.markdown("""
        <div class="mw-demo-banner">
            <span style="font-size:1.2rem">⚡</span>
            <div><strong>Demo Mode Active</strong> — Showing pre-loaded sample data for CloudVibe Corp, NexaFlow AI, DataPulse Inc & SalesBridge Pro. Connect MySQL to use live data.</div>
        </div>
    """, unsafe_allow_html=True)

# ==========================================
# LOAD GLOBAL INTEL
# ==========================================
df_intel_global = get_intel_df()
unique_competitors = sorted(df_intel_global['competitor'].unique().tolist()) if not df_intel_global.empty else []

# ==========================================
# TABS
# ==========================================
tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs([
    "🎯  Intel Hub",
    "⚔️  Battlecards",
    "📄  Proposals",
    "📊  Win Predictor",
    "🔄  Comparison Matrix",
    "📈  Analytics",
    "🛡️  Governance",
])

# ─────────────────────────────────────────
# TAB 1: INTEL HUB
# ─────────────────────────────────────────
with tab1:
    st.markdown("""
        <div class="mw-section-header">
            <div class="mw-section-icon">🎯</div>
            <div>
                <p class="mw-section-title">Competitive Intelligence Hub</p>
                <p class="mw-section-desc">Log competitor vulnerabilities to your MySQL database. Search and filter your intel library below.</p>
            </div>
        </div>
    """, unsafe_allow_html=True)

    # ROI Panel
    n_records = len(df_intel_global)
    hrs_saved = round(n_records * 0.45, 1)
    dollar_val = int(hrs_saved * 150)
    battlecards_gen = max(1, n_records // 3)
    st.markdown(f"""
        <div class="mw-roi-card">
            <p style="font-family:'Space Grotesk',sans-serif;font-weight:600;font-size:0.85rem;margin:0 0 0.25rem 0;color:var(--text-secondary)">📊 ESTIMATED BUSINESS VALUE</p>
            <div class="mw-roi-row">
                <div class="mw-roi-item"><div class="mw-roi-num">{n_records}</div><div class="mw-roi-lbl">Intel Records</div></div>
                <div class="mw-roi-item"><div class="mw-roi-num">{battlecards_gen}</div><div class="mw-roi-lbl">Battlecards Generated</div></div>
                <div class="mw-roi-item"><div class="mw-roi-num">{hrs_saved}h</div><div class="mw-roi-lbl">Research Hours Saved</div></div>
                <div class="mw-roi-item"><div class="mw-roi-num">${dollar_val:,}</div><div class="mw-roi-lbl">Value @ $150/hr</div></div>
            </div>
        </div>
    """, unsafe_allow_html=True)
    st.markdown("<div style='height:1.25rem'></div>", unsafe_allow_html=True)

    # Add Intel Form
    with st.form("intel_ingestion_form", clear_on_submit=True):
        col_a, col_b = st.columns(2)
        with col_a:
            comp_name = st.text_input("Competitor Name", placeholder="e.g., CloudVibe Corp")
        with col_b:
            intel_cat = st.selectbox("Category", ["Pricing","Technical","Feature Gap","Support","Legal"])
        raw_intel = st.text_area("Vulnerability / Pain Point", placeholder="Describe the competitive weakness in detail…", height=110)
        if st.form_submit_button("💾  Commit Intel to Database"):
            if comp_name and raw_intel:
                now_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                insert_intel(comp_name, intel_cat, raw_intel, now_time)
                retain_hindsight_memory(comp_name, intel_cat, raw_intel, now_time)
                log_system_activity(st.session_state.user_email, f"Added intel for '{comp_name}'")
                show_toast(f"Intel on {comp_name} saved successfully!", "success")
                st.rerun()
            else:
                st.warning("Please fill in competitor name and intel before submitting.")

    st.markdown("<hr class='mw-divider'>", unsafe_allow_html=True)

    # Search + Filter
    sf1, sf2, sf3 = st.columns([2, 1, 1])
    with sf1:
        search_query = st.text_input("🔍  Search Intel", placeholder="Search by keyword, competitor, or category…", label_visibility="collapsed")
    with sf2:
        filter_comp = st.selectbox("Filter by Competitor", ["All"] + unique_competitors, label_visibility="collapsed")
    with sf3:
        filter_cat = st.selectbox("Filter by Category", ["All","Pricing","Technical","Feature Gap","Support","Legal"], label_visibility="collapsed")

    display_df = df_intel_global.copy()
    if search_query:
        mask = display_df.apply(lambda row: search_query.lower() in str(row).lower(), axis=1)
        display_df = display_df[mask]
    if filter_comp != "All":
        display_df = display_df[display_df['competitor'] == filter_comp]
    if filter_cat != "All":
        display_df = display_df[display_df['category'] == filter_cat]

    if not display_df.empty:
        st.caption(f"Showing {len(display_df)} of {len(df_intel_global)} records")
        st.dataframe(display_df, use_container_width=True, hide_index=True)
    else:
        st.markdown("""
            <div class="mw-empty-state">
                <span class="mw-empty-icon">🔍</span>
                <div class="mw-empty-title">No records match your search</div>
                <div class="mw-empty-desc">Try adjusting your filters or add new intel above.</div>
            </div>
        """, unsafe_allow_html=True)

# ─────────────────────────────────────────
# TAB 2: BATTLECARDS
# ─────────────────────────────────────────
with tab2:
    st.markdown("""
        <div class="mw-section-header">
            <div class="mw-section-icon">⚔️</div>
            <div>
                <p class="mw-section-title">AI Battlecard Generator</p>
                <p class="mw-section-desc">Stream real-time sales battlecards grounded in your MySQL competitive intelligence.</p>
            </div>
        </div>
    """, unsafe_allow_html=True)

    if unique_competitors:
        bc1, bc2 = st.columns([2, 1])
        with bc1:
            selected_target = st.selectbox("Target Competitor", unique_competitors)
        with bc2:
            st.markdown("<div style='height:1.9rem'></div>", unsafe_allow_html=True)
            gen_btn = st.button("⚡  Generate Battlecard")

        if gen_btn:
            if not GROQ_API_KEY:
                st.error("GROQ_API_KEY is missing. Add it to your .env file and restart Streamlit.")
                st.stop()
            log_system_activity(st.session_state.user_email, f"Generated battlecard vs '{selected_target}'")
            rows = df_intel_global[df_intel_global['competitor'] == selected_target]['intel'].tolist()
            context_str = "\n".join([f"- {r}" for r in rows])
            prompt = f"""You are an elite enterprise sales strategist. Based on this competitive intelligence about '{selected_target}':

{context_str}

Generate a comprehensive sales battlecard with these sections:
1. EXECUTIVE SUMMARY (2 sentences on why we win)
2. TOP 3 VULNERABILITIES TO EXPLOIT (with specific talk tracks)
3. DISCOVERY QUESTIONS (3 questions that expose their weaknesses)
4. OBJECTION HANDLERS (for when prospects say "{selected_target} is cheaper/better")
5. WINNING PROOF POINTS (what to lead with)
6. RED FLAGS TO WATCH (when to walk away)

Be specific, tactical, and direct. No emojis. Write for a senior enterprise AE."""

            headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
            payload = {"model": "llama-3.3-70b-versatile", "messages": [{"role": "user", "content": prompt}], "stream": True}

            output_placeholder = st.empty()
            full_output = ""
            try:
                with requests.post("https://api.groq.com/openai/v1/chat/completions", headers=headers, json=payload, stream=True) as resp:
                    for line in resp.iter_lines():
                        if line:
                            line_str = line.decode("utf-8")
                            if line_str.startswith("data: ") and line_str != "data: [DONE]":
                                try:
                                    chunk = json.loads(line_str[6:])
                                    delta = chunk["choices"][0]["delta"].get("content", "")
                                    full_output += delta
                                    output_placeholder.markdown(f'<div class="mw-ai-output">{full_output}▌</div>', unsafe_allow_html=True)
                                except Exception:
                                    pass
                output_placeholder.markdown(f'<div class="mw-ai-output">{full_output}</div>', unsafe_allow_html=True)
                st.session_state.battlecard_output = full_output
            except Exception as e:
                st.error(f"Streaming error: {e}")

        # Export
        if st.session_state.battlecard_output:
            st.markdown("<hr class='mw-divider'>", unsafe_allow_html=True)
            exp1, exp2 = st.columns(2)
            with exp1:
                st.download_button(
                    "📥  Download Battlecard (.txt)",
                    data=st.session_state.battlecard_output.encode(),
                    file_name=f"battlecard_{selected_target.replace(' ','_')}.txt",
                    mime="text/plain"
                )
            with exp2:
                md_content = f"# Battlecard: {selected_target}\n_Generated {datetime.now().strftime('%B %d, %Y')}_\n\n{st.session_state.battlecard_output}"
                st.download_button(
                    "📥  Download as Markdown",
                    data=md_content.encode(),
                    file_name=f"battlecard_{selected_target.replace(' ','_')}.md",
                    mime="text/markdown"
                )
    else:
        st.markdown("""
            <div class="mw-empty-state">
                <span class="mw-empty-icon">⚔️</span>
                <div class="mw-empty-title">No competitors in database</div>
                <div class="mw-empty-desc">Add competitor intel in the Intel Hub tab to generate battlecards.</div>
            </div>
        """, unsafe_allow_html=True)

# ─────────────────────────────────────────
# TAB 3: PROPOSALS
# ─────────────────────────────────────────
with tab3:
    st.markdown("""
        <div class="mw-section-header">
            <div class="mw-section-icon">📄</div>
            <div>
                <p class="mw-section-title">RFP Proposal Engine</p>
                <p class="mw-section-desc">Generate context-aware proposals that weaponize your competitive intelligence.</p>
            </div>
        </div>
    """, unsafe_allow_html=True)

    p1, p2 = st.columns(2)
    with p1:
        client_name = st.text_input("Client / Company Name", placeholder="e.g., Acme Corp")
    with p2:
        proposal_tone = st.selectbox("Proposal Tone", ["Formal Executive", "Consultative", "Technical Deep-Dive", "Challenger Sale"])

    rfp_text_block = st.text_area(
        "Client Requirements / RFP Text",
        placeholder="Paste the client's RFP requirements, pain points, or evaluation criteria here…",
        height=150
    )

    if st.button("✍️  Generate Proposal"):
        if rfp_text_block:
            if not GROQ_API_KEY:
                st.error("GROQ_API_KEY is missing. Add it to your .env file and restart Streamlit.")
                st.stop()
            log_system_activity(st.session_state.user_email, "Generated B2B Proposal Document")
            all_context = "\n".join([f"- {row['competitor']} ({row['category']}): {row['intel']}" for _, row in df_intel_global.iterrows()])
            hindsight_context = recall_hindsight_context(rfp_text_block)
            master_prompt = f"""You are a senior enterprise solutions consultant writing a {proposal_tone} proposal.

Competitive landscape context:
{all_context}

Recalled Hindsight agent memory:
{hindsight_context}

Client: {client_name or 'Prospect'}
RFP Requirements:
"{rfp_text_block}"

Write a complete formal proposal with:
1. EXECUTIVE SUMMARY
2. UNDERSTANDING OF REQUIREMENTS
3. PROPOSED SOLUTION
4. COMPETITIVE DIFFERENTIATION (reference specific competitor weaknesses)
5. IMPLEMENTATION APPROACH
6. INVESTMENT & ROI PROJECTION
7. NEXT STEPS

Be specific and professional. No emojis. Address requirements directly."""

            headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
            payload = {"model": "llama-3.3-70b-versatile", "messages": [{"role": "user", "content": master_prompt}], "stream": True}

            output_placeholder = st.empty()
            full_output = ""
            try:
                with requests.post("https://api.groq.com/openai/v1/chat/completions", headers=headers, json=payload, stream=True) as resp:
                    for line in resp.iter_lines():
                        if line:
                            line_str = line.decode("utf-8")
                            if line_str.startswith("data: ") and line_str != "data: [DONE]":
                                try:
                                    chunk = json.loads(line_str[6:])
                                    delta = chunk["choices"][0]["delta"].get("content", "")
                                    full_output += delta
                                    output_placeholder.markdown(f'<div class="mw-ai-output">{full_output}▌</div>', unsafe_allow_html=True)
                                except Exception:
                                    pass
                output_placeholder.markdown(f'<div class="mw-ai-output">{full_output}</div>', unsafe_allow_html=True)
                st.session_state.proposal_output = full_output
            except Exception as e:
                st.error(f"Error: {e}")
        else:
            st.warning("Please enter the client's RFP requirements first.")

    if st.session_state.proposal_output:
        st.markdown("<hr class='mw-divider'>", unsafe_allow_html=True)
        dl1, dl2 = st.columns(2)
        with dl1:
            st.download_button(
                "📥  Download Proposal (.txt)",
                data=st.session_state.proposal_output.encode(),
                file_name=f"proposal_{(client_name or 'client').replace(' ','_')}.txt",
                mime="text/plain"
                )
        with dl2:
            md_prop = f"# Proposal for {client_name or 'Client'}\n_Generated {datetime.now().strftime('%B %d, %Y')}_\n\n{st.session_state.proposal_output}"
            st.download_button(
                "📥  Download as Markdown",
                data=md_prop.encode(),
                file_name=f"proposal_{(client_name or 'client').replace(' ','_')}.md",
                mime="text/markdown"
            )

# ─────────────────────────────────────────
# TAB 4: WIN PREDICTOR (DYNAMIC NUMBERS INSTALLED)
# ─────────────────────────────────────────
with tab4:
    st.markdown("""
        <div class="mw-section-header">
            <div class="mw-section-icon">📊</div>
            <div>
                <p class="mw-section-title">Predictive Win-Rate Engine</p>
                <p class="mw-section-desc">Score your deal across four weighted vectors to forecast close probability.</p>
            </div>
        </div>
    """, unsafe_allow_html=True)

    col_v1, col_v2 = st.columns(2)
    with col_v1:
        pricing_metric = st.select_slider(
            "Pricing Position vs Market",
            options=["Premium Cost Layer", "Price Match Value", "Slightly Competitive", "Significantly Undercut"],
            value="Price Match Value"
        )
        p_w = {"Premium Cost Layer": 40, "Price Match Value": 65, "Slightly Competitive": 80, "Significantly Undercut": 95}[pricing_metric]
        st.markdown(f"**Calculated Weight Allocation:** `{p_w} / 100` points")
        
        st.markdown("<div style='height: 12px;'></div>", unsafe_allow_html=True)

        technical_metric = st.select_slider(
            "Technical Capability",
            options=["Critical Gaps", "Meets Baseline", "Exceeds Demands", "Feature Monopoly"]
        )
        t_w = {"Critical Gaps": 30, "Meets Baseline": 60, "Exceeds Demands": 85, "Feature Monopoly": 100}[technical_metric]
        st.markdown(f"**Calculated Weight Allocation:** `{t_w} / 100` points")

    with col_v2:
        relationship_metric = st.select_slider(
            "Executive Stakeholder Alignment",
            options=["Cold Lead", "Procurement Only", "Multi-Threaded", "Board Sponsor Confirmed"]
        )
        r_w = {"Cold Lead": 20, "Procurement Only": 55, "Multi-Threaded": 80, "Board Sponsor Confirmed": 95}[relationship_metric]
        st.markdown(f"**Calculated Weight Allocation:** `{r_w} / 100` points")
        
        st.markdown("<div style='height: 12px;'></div>", unsafe_allow_html=True)

        urgency_metric = st.select_slider(
            "Prospect Buying Urgency",
            options=["Undetermined", "60-90 Day Assessment", "Accelerated Cycle", "Fiscal Mandate Closure"]
        )
        u_w = {"Undetermined": 40, "60-90 Day Assessment": 65, "Accelerated Cycle": 85, "Fiscal Mandate Closure": 95}[urgency_metric]
        st.markdown(f"**Calculated Weight Allocation:** `{u_w} / 100` points")

    st.markdown("<div style='height: 15px;'></div>", unsafe_allow_html=True)
    deal_size = st.number_input("Deal Size ($)", min_value=0, value=50000, step=5000)
    st.markdown("<div style='height:0.5rem'></div>", unsafe_allow_html=True)

    if st.button("🎯  Calculate Win Probability"):
        log_system_activity(st.session_state.user_email, "Executed Win Probability Engine")
        pct = int((p_w*0.25)+(t_w*0.30)+(r_w*0.30)+(u_w*0.15))
        ev = int(deal_size * pct / 100)
        verdict = "HIGH" if pct >= 70 else ("MEDIUM" if pct >= 45 else "LOW")
        color = "#10B981" if pct >= 70 else ("#F59E0B" if pct >= 45 else "#EF4444")

        st.markdown("<hr class='mw-divider'>", unsafe_allow_html=True)
        r1, r2 = st.columns([1, 2])
        with r1:
            st.markdown(f"""
                <div class="mw-win-score">
                    <span class="score-number" style="background:linear-gradient(135deg,{color},#818CF8);-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text">
                        {pct}%
                    </span>
                    <div class="score-label">Win Probability</div>
                    <div style="margin-top:1rem;padding:0.5rem 1rem;background:{color}22;border-radius:8px;color:{color};font-weight:700;font-size:0.85rem;letter-spacing:0.06em">{verdict} CONFIDENCE</div>
                    <div style="margin-top:0.75rem;font-size:0.82rem;color:var(--text-secondary)">Expected Value</div>
                    <div style="font-family:'Space Grotesk',sans-serif;font-size:1.4rem;font-weight:700;color:var(--text-primary)">${ev:,}</div>
                </div>
            """, unsafe_allow_html=True)
        with r2:
            vector_df = pd.DataFrame({"Score":[p_w,t_w,r_w,u_w]}, index=["Pricing","Technical","Relationship","Urgency"])
            st.bar_chart(vector_df, use_container_width=True)
            st.caption(f"Weights: Pricing 25% · Technical 30% · Relationship 30% · Urgency 15%")

# ─────────────────────────────────────────
# TAB 5: COMPARISON MATRIX
# ─────────────────────────────────────────
with tab5:
    st.markdown("""
        <div class="mw-section-header">
            <div class="mw-section-icon">🔄</div>
            <div>
                <p class="mw-section-title">Competitive Comparison Matrix</p>
                <p class="mw-section-desc">Side-by-side capability comparison auto-generated from your intel database.</p>
            </div>
        </div>
    """, unsafe_allow_html=True)

    if unique_competitors:
        mx_col1, mx_col2 = st.columns([2, 1])
        with mx_col1:
            matrix_comp = st.selectbox("Compare against", unique_competitors, key="matrix_comp")
        with mx_col2:
            st.markdown("<div style='height:1.9rem'></div>", unsafe_allow_html=True)
            gen_matrix = st.button("🔄  Generate Matrix")

        if gen_matrix:
            log_system_activity(st.session_state.user_email, f"Generated comparison matrix vs '{matrix_comp}'")
            rows = df_intel_global[df_intel_global['competitor'] == matrix_comp]
            cats = rows['category'].unique().tolist()

            # Build static matrix from intel categories
            MATRIX_ROWS = [
                ("REST API / Integrations",     "✅ Native, documented",   "❌ Requires middleware",     "Technical"),
                ("Pricing Transparency",         "✅ Clear, no overages",   "❌ Hidden fees reported",    "Pricing"),
                ("Support SLA (P1)",             "✅ < 4 hour response",    "❌ 48hr average",            "Support"),
                ("AI / ML Capabilities",         "✅ Core feature set",     "❌ Not on roadmap",          "Feature Gap"),
                ("Data Residency / GDPR",        "✅ Multi-region",         "⚠️ Investigation noted",    "Legal"),
                ("Offline / Low-Connectivity",   "✅ Full offline mode",    "❌ Cloud-only",              "Feature Gap"),
                ("Contract Flexibility",         "✅ Month-to-month option","❌ 3-year lock-in",          "Pricing"),
                ("Customer NPS",                 "✅ Above industry avg",   "⚠️ Declining trend",        "Support"),
            ]

            rows_html = ""
            for feature, us_val, them_val, category in MATRIX_ROWS:
                highlight = " style='background:rgba(59,130,246,0.04)'" if category in cats else ""
                rows_html += f"""
                <tr{highlight}>
                    <td><strong>{feature}</strong><br><span style="font-size:0.75rem;color:var(--text-muted)">{category}</span></td>
                    <td class="us">{us_val}</td>
                    <td class="them">{them_val}</td>
                </tr>"""

            st.markdown(f"""
                <div class="mw-matrix-wrap">
                <table class="mw-matrix">
                    <thead>
                        <tr>
                            <th style="width:38%">Capability / Dimension</th>
                            <th style="width:31%">🏆 MarketWin AI</th>
                            <th style="width:31%">⚔️ {matrix_comp}</th>
                        </tr>
                    </thead>
                    <tbody>
                        {rows_html}
                    </tbody>
                </table>
                </div>
            """, unsafe_allow_html=True)

            st.markdown("<div style='height:1rem'></div>", unsafe_allow_html=True)
            matrix_md = f"# Competitive Matrix: MarketWin AI vs {matrix_comp}\n_Generated {datetime.now().strftime('%B %d, %Y')}_\n\n"
            matrix_md += "| Capability | MarketWin AI | " + matrix_comp + " |\n|---|---|---|\n"
            for feat, us_v, them_v, _ in MATRIX_ROWS:
                matrix_md += f"| {feat} | {us_v} | {them_v} |\n"
            st.download_button("📥  Export Matrix (.md)", data=matrix_md.encode(), file_name=f"matrix_vs_{matrix_comp.replace(' ','_')}.md", mime="text/markdown")
    else:
        st.markdown("""
            <div class="mw-empty-state">
                <span class="mw-empty-icon">🔄</span>
                <div class="mw-empty-title">No competitors to compare</div>
                <div class="mw-empty-desc">Add competitor intel first to generate a comparison matrix.</div>
            </div>
        """, unsafe_allow_html=True)

# ─────────────────────────────────────────
# TAB 6: ANALYTICS
# ─────────────────────────────────────────
with tab6:
    st.markdown("""
        <div class="mw-section-header">
            <div class="mw-section-icon">📈</div>
            <div>
                <p class="mw-section-title">Intelligence Analytics Dashboard</p>
                <p class="mw-section-desc">Live metrics from your competitive intelligence database.</p>
            </div>
        </div>
    """, unsafe_allow_html=True)

    if not df_intel_global.empty:
        total_records = len(df_intel_global)
        total_comps = df_intel_global['competitor'].nunique()
        total_cats = df_intel_global['category'].nunique()
        try:
            latest = str(df_intel_global['timestamp'].max())[:10]
        except Exception:
            latest = "—"

        s1, s2, s3, s4 = st.columns(4)
        with s1: st.metric("Total Intel Records", total_records)
        with s2: st.metric("Competitors Tracked", total_comps)
        with s3: st.metric("Intel Categories", total_cats)
        with s4: st.metric("Latest Entry", latest)

        st.markdown("<div style='height:1rem'></div>", unsafe_allow_html=True)

        g1, g2 = st.columns(2)
        with g1:
            st.markdown('<p style="font-family:Space Grotesk;font-weight:600;font-size:0.82rem;letter-spacing:0.06em;text-transform:uppercase;margin-bottom:0.5rem;color:var(--text-secondary)">INTEL COVERAGE BY COMPETITOR</p>', unsafe_allow_html=True)
            st.bar_chart(df_intel_global['competitor'].value_counts(), color='#3B82F6')
        with g2:
            st.markdown('<p style="font-family:Space Grotesk;font-weight:600;font-size:0.82rem;letter-spacing:0.06em;text-transform:uppercase;margin-bottom:0.5rem;color:var(--text-secondary)">DISTRIBUTION BY CATEGORY</p>', unsafe_allow_html=True)
            st.bar_chart(df_intel_global['category'].value_counts(), color='#8B5CF6')

        st.markdown("<hr class='mw-divider'>", unsafe_allow_html=True)
        st.markdown('<p style="font-family:Space Grotesk;font-weight:600;font-size:0.82rem;letter-spacing:0.06em;text-transform:uppercase;margin-bottom:0.75rem">FULL INTELLIGENCE LEDGER</p>', unsafe_allow_html=True)
        st.dataframe(df_intel_global, use_container_width=True, hide_index=True)

        csv_data = df_intel_global.to_csv(index=False).encode()
        st.download_button("📥  Export All Intel (.csv)", data=csv_data, file_name="marketwin_intel_export.csv", mime="text/csv")
    else:
        st.markdown("""
            <div class="mw-empty-state">
                <span class="mw-empty-icon">📈</span>
                <div class="mw-empty-title">No analytics data yet</div>
                <div class="mw-empty-desc">Add intel records in the Intel Hub to populate this dashboard.</div>
            </div>
        """, unsafe_allow_html=True)

# ─────────────────────────────────────────
# TAB 7: GOVERNANCE
# ─────────────────────────────────────────
with tab7:
    st.markdown("""
        <div class="mw-section-header">
            <div class="mw-section-icon">🛡️</div>
            <div>
                <p class="mw-section-title">Corporate Governance</p>
                <p class="mw-section-desc">Administrator-only audit trail and compliance monitoring.</p>
            </div>
        </div>
    """, unsafe_allow_html=True)

    if st.session_state.role == "Administrator":
        if st.session_state.demo_mode:
            audit_df = pd.DataFrame(st.session_state.demo_audit)
        else:
            try:
                conn_temp = mysql.connector.connect(**DB_CONFIG)
                audit_df = pd.read_sql_query("SELECT id, timestamp, user, action FROM audit_logs ORDER BY id DESC", conn_temp)
                conn_temp.close()
            except Exception:
                audit_df = pd.DataFrame()

        if not audit_df.empty:
            a1, a2, a3 = st.columns(3)
            with a1: st.metric("Total Audit Events", len(audit_df))
            with a2: st.metric("Unique Users", audit_df['user'].nunique())
            with a3: st.metric("Latest Event", str(audit_df['timestamp'].iloc[0])[:10] if len(audit_df) else "—")

            st.markdown("<div style='height:0.75rem'></div>", unsafe_allow_html=True)
            st.markdown('<p style="font-family:Space Grotesk;font-weight:600;font-size:0.82rem;letter-spacing:0.06em;text-transform:uppercase;margin-bottom:0.75rem">AUDIT LOG</p>', unsafe_allow_html=True)
            st.dataframe(audit_df, use_container_width=True, hide_index=True)

            audit_csv = audit_df.to_csv(index=False).encode()
            st.download_button("📥  Export Audit Log (.csv)", data=audit_csv, file_name="marketwin_audit_log.csv", mime="text/csv")
        st.success("✓ System compliance posture verified. All events logged.")
    else:
        st.markdown("""
            <div class="mw-alert-error">
                <span>⛔</span>
                <div><strong>Access Restricted.</strong><br>This area requires Administrator privileges. Contact your system administrator to request access.</div>
            </div>
        """, unsafe_allow_html=True)

# ==========================================
# FOOTER
# ==========================================
st.markdown("""
    <div class="mw-footer">
        <div class="mw-footer-stack">
            <span style="font-size:0.8rem;font-weight:600;color:var(--text-secondary)">Built with</span>
            <span class="mw-footer-tag">MySQL 8.0</span>
            <span class="mw-footer-tag">Groq · LLaMA 3.3 70B</span>
            <span class="mw-footer-tag">Streamlit 1.x</span>
            <span class="mw-footer-tag">Python 3.11</span>
        </div>
        <div class="mw-footer-copy">AI Market-Win Suite v5.0 · © 2025 · All rights reserved</div>
    </div>
""", unsafe_allow_html=True)
