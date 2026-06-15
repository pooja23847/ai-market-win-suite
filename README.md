<div align="center">

# ⚡ AI Market-Win Suite

### Enterprise B2B Competitive Intelligence & Sales Enablement Platform

[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.x-FF4B4B?style=for-the-badge&logo=streamlit&logoColor=white)](https://streamlit.io)
[![MySQL](https://img.shields.io/badge/MySQL-8.0-4479A1?style=for-the-badge&logo=mysql&logoColor=white)](https://mysql.com)
[![Groq](https://img.shields.io/badge/Groq-LLaMA_3.3_70B-F55036?style=for-the-badge)](https://groq.com)
[![License](https://img.shields.io/badge/License-MIT-10B981?style=for-the-badge)](LICENSE)

**Sales teams lose 23% of deals due to poor competitive positioning.**  
AI Market-Win Suite fixes that — turning raw competitor intelligence into winning proposals in seconds.

[🚀 Quick Start](#-quick-start) · [✨ Features](#-features) · [🏗️ Architecture](#️-architecture) · [📸 Screenshots](#-screenshots) · [🤝 Contributing](#-contributing)

</div>

---

## 🎯 The Problem

> *"67% of B2B buyers say vendors don't understand their competitive landscape."*  
> — Gartner B2B Buyer Survey, 2024

| Pain Point | Impact |
|---|---|
| Manual competitive research | **18+ hours/week** per sales rep |
| Generic proposals that miss competitor objections | **42% of deals lost** (Forrester, 2023) |
| Intel scattered across Slack, email, and sticky notes | No single source of truth |
| Sales reps blindsided in discovery calls | Lost deals, wasted cycles |

**AI Market-Win Suite** is a full-stack intelligence platform that solves all of this — structured competitor data in MySQL, AI-generated battlecards via Groq LLaMA 3.3, and predictive win scoring — all in one place.

---

## ✨ Features

### 🎯 Competitive Intelligence Hub
Log every competitor weakness — pricing gaps, technical flaws, support failures, legal risks — directly into a **live MySQL database**. Searchable and filterable in real time.

### ⚔️ AI Battlecard Generator
Select any tracked competitor and stream a complete **tactical sales battlecard** in under 30 seconds — including discovery questions, objection handlers, and proof points. Powered by **Groq LLaMA 3.3 70B** with token-by-token streaming.

### 📄 RFP Proposal Engine
Paste any client RFP. The engine auto-references your stored competitor intel to generate a **context-aware proposal** that positions your strengths exactly where the client's pain is deepest. Supports 4 tones: Formal Executive, Consultative, Technical, Challenger Sale.

### 📊 Predictive Win-Rate Engine
Score your deal across 4 weighted vectors — Pricing Position, Technical Capability, Stakeholder Alignment, Buying Urgency — to get a **close probability %** and **expected deal value**.

### 🔄 Competitor Comparison Matrix
Auto-generate a **side-by-side capability matrix** (your product vs. any competitor) from your intel database. Exportable as Markdown.

### 📈 Analytics Dashboard
Live charts showing intel coverage by competitor and category, total records, and a full audit-ready data table. CSV export included.

### 🛡️ Governance & Audit Trail
Administrator-only audit log with every user action timestamped and exportable. Full role-based access control (Administrator / Sales).

### 🧠 Hindsight Memory Layer
Integrates with **Vectorize Hindsight Cloud API** for semantic memory — recalled competitor context is injected into proposals automatically. Falls back to local in-memory mode gracefully.

### 🎬 Demo Mode
Works completely **offline with zero setup** — pre-loaded with 10 realistic intel records across 4 competitors. Perfect for demos when MySQL isn't available.

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Streamlit Frontend                        │
│  Login → Intel Hub → Battlecards → Proposals → Win Score   │
└────────────────────┬──────────────────────┬─────────────────┘
                     │                      │
          ┌──────────▼──────────┐  ┌───────▼────────────────┐
          │   MySQL 8.0 DB      │  │   Groq API             │
          │   competitor_intel  │  │   LLaMA 3.3 70B        │
          │   users             │  │   Streaming SSE        │
          │   audit_logs        │  └───────┬────────────────┘
          └─────────────────────┘          │
                                  ┌────────▼────────────────┐
                                  │  Hindsight Memory API   │
                                  │  (Vectorize Cloud)      │
                                  │  Semantic recall layer  │
                                  └─────────────────────────┘
```

### Tech Stack

| Layer | Technology |
|---|---|
| Frontend | Streamlit 1.x + custom CSS (Space Grotesk, Inter) |
| AI Engine | Groq API · LLaMA 3.3 70B · Streaming SSE |
| Database | MySQL 8.0 (with demo fallback) |
| Memory | Vectorize Hindsight Cloud API |
| Language | Python 3.11 |
| Data | Pandas |

---

## 🚀 Quick Start

### Option A — Demo Mode (No setup needed)

```bash
git clone https://github.com/pooja23847/ai-market-win-suite.git
cd ai-market-win-suite/ai-market-win-suite
pip install -r requirements.txt
streamlit run app.py
```

Then click **"Try with Sample Data (No Login)"** on the login page.  
Or log in with: `demo@marketwin.ai` / `demo123`

---

### Option B — Full Setup with MySQL + Groq

**1. Clone the repo**
```bash
git clone https://github.com/pooja23847/ai-market-win-suite.git
cd ai-market-win-suite/ai-market-win-suite
```

**2. Install dependencies**
```bash
pip install -r requirements.txt
```

**3. Create your `.env` file**
```env
# Groq API — get yours free at https://console.groq.com
GROQ_API_KEY=your_groq_api_key_here

# MySQL Database
DB_HOST=localhost
DB_USER=root
DB_PASSWORD=your_mysql_password
DB_NAME=marketwin_db

# Hindsight Memory Layer (optional)
HINDSIGHT_API_KEY=your_hindsight_api_key_here
```

**4. Set up MySQL**

```sql
CREATE DATABASE marketwin_db;
USE marketwin_db;

CREATE TABLE users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    password VARCHAR(255) NOT NULL,
    role VARCHAR(50) NOT NULL
);

CREATE TABLE competitor_intel (
    id INT AUTO_INCREMENT PRIMARY KEY,
    competitor VARCHAR(255),
    category VARCHAR(100),
    intel TEXT,
    timestamp DATETIME
);

CREATE TABLE audit_logs (
    id INT AUTO_INCREMENT PRIMARY KEY,
    timestamp DATETIME,
    user VARCHAR(255),
    action TEXT
);

-- Add a test user
INSERT INTO users (email, password, role) VALUES ('admin@yourco.com', 'yourpassword', 'Administrator');
```

**5. Run**
```bash
streamlit run app.py
# or
python main.py
```

Open [http://localhost:8501](http://localhost:8501)

---

## 📁 Project Structure

```
ai-market-win-suite/
├── ai-market-win-suite/
│   ├── app.py               # Main Streamlit application (all UI + logic)
│   ├── llm_manager.py       # Groq LLM client (LLaMA 3.3 70B)
│   ├── memory_manager.py    # Hindsight Cloud memory layer
│   ├── main.py              # Entry point launcher
│   ├── requirements.txt     # Python dependencies
│   ├── .env                 # Your secrets (gitignored)
│   ├── .gitignore
│   ├── .streamlit/
│   │   └── config.toml      # Streamlit dark theme config
│   └── README.md
└── README.md
```

---

## 🔑 Login Credentials

| Role | Email | Password |
|---|---|---|
| Administrator | `demo@marketwin.ai` | `demo123` |
| Sales | `sales@marketwin.ai` | `sales123` |

> These are demo credentials for offline/demo mode. In production, users are verified against the MySQL `users` table.

---

## 🌟 Key Design Decisions

**Why MySQL over a vector DB for intel storage?**  
Sales teams need structured, auditable, role-controlled data. MySQL gives us transactions, audit trails, and SQL querying — all essential for enterprise use. Semantic search is handled by the Hindsight memory layer layered on top.

**Why Groq over OpenAI?**  
Groq's inference speed (300+ tokens/sec) makes streaming feel instantaneous. For a live demo, this is crucial — judges see results appearing word-by-word rather than waiting on a spinner.

**Why demo mode?**  
Every hackathon demo has a risk of infra failing. Demo mode ensures the app always works on any machine, even with no internet, no MySQL, and no API key.

---

## 📦 Dependencies

```
streamlit          # UI framework
pandas             # Data manipulation
requests           # HTTP + SSE streaming
mysql-connector-python  # MySQL integration
groq               # Official Groq Python client
fastapi            # (for future API endpoints)
uvicorn            # ASGI server
pydantic           # Data validation
fpdf2              # PDF export
python-dotenv      # Environment variable loading
```

---

## 🔒 Security

- All credentials loaded via `os.getenv()` — never hardcoded
- `.env` and `.streamlit/secrets.toml` are gitignored
- Role-based access control (Administrator vs Sales)
- Full audit log of every user action with timestamps
- No secrets have ever been committed to this repository

---

## 🤝 Contributing

Pull requests are welcome. For major changes, please open an issue first.

1. Fork the repo
2. Create your branch (`git checkout -b feature/my-feature`)
3. Commit your changes (`git commit -m 'Add my feature'`)
4. Push to the branch (`git push origin feature/my-feature`)
5. Open a Pull Request

---

## 📄 License

MIT License — see [LICENSE](LICENSE) for details.

---

<div align="center">

Built with ⚡ for hackathon · MySQL · Groq LLaMA 3.3 · Streamlit · Python 3.11

**[⬆ Back to top](#-ai-market-win-suite)**

</div>
