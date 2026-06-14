# AI Market-Win Suite

AI Market-Win Suite is a Streamlit-based B2B competitive intelligence and sales enablement platform. It helps sales teams capture competitor insights, generate AI-powered battlecards, create RFP proposals, and calculate deal win probability.

## Features

- Secure login flow with Sales and Administrator roles
- Competitor intelligence hub for tracking pricing, technical gaps, support issues, legal risks, and feature weaknesses
- AI battlecard generation using Groq LLaMA
- RFP proposal generation grounded in stored competitive intelligence
- Predictive win-rate calculator with expected deal value
- Admin governance dashboard with audit log export
- Demo mode fallback when MySQL is unavailable

## Tech Stack

- Python
- Streamlit
- MySQL
- Pandas
- Hindsight Agent Memory Framework
- Groq API
- LLaMA 3.3 70B

## Project Structure

```txt
ai-market-win-suite/
  app.py
  llm_manager.py
  memory_manager.py
  main.py
  requirements.txt
  README.md
```

## Setup

Install dependencies:

```bash
pip install -r ai-market-win-suite/requirements.txt
```

Create a `.env` file inside `ai-market-win-suite/`:

```env
GROQ_API_KEY=your_groq_api_key_here

DB_HOST=localhost
DB_USER=root
DB_PASSWORD=your_mysql_password
DB_NAME=marketwin_db

HINDSIGHT_API_KEY=your_hindsight_api_key_here
```

Run the app:

```bash
streamlit run ai-market-win-suite/app.py
```

## Security Note

The `.env` file contains private API keys and database credentials. It is intentionally excluded from GitHub using `.gitignore`.
