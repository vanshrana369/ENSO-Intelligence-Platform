# ENSO Intelligence Platform

An AI-powered climate risk intelligence system that monitors El Niño/La Niña (ENSO) conditions in real time, forecasts phase transitions up to 9 months ahead, and quantifies market risk across commodities — fully automated and deployed.

**Live Demo:** [enso-intelligence-platform.vercel.app](https://enso-intelligence-platform.vercel.app)  
**API:** [enso-intelligence-platform.onrender.com](https://enso-intelligence-platform.onrender.com)

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Data Sources                             │
│   NOAA MEI Index       Yahoo Finance        NewsAPI             │
│   (MEI since 1979)    (Wheat/Oil/Soy)     (Climate News)       │
└────────────┬───────────────┬───────────────────┬───────────────┘
             │               │                   │
             ▼               ▼                   ▼
┌─────────────────────────────────────────────────────────────────┐
│                   4-Agent AI Pipeline (LangGraph)               │
│                                                                 │
│  Agent 1          Agent 2          Agent 3          Agent 4     │
│  ENSO Monitor  →  News Analyst  →  Market Risk  →  Report Gen  │
│  (fetches MEI)   (fetches news)   (commodity     (LLM report   │
│                                    analysis)      + PDF)        │
└──────────────────────────────┬──────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│              PostgreSQL (Render)  ←→  FastAPI Backend           │
│         enso_data | news_data | commodity_prices | reports      │
└──────────────────────────────┬──────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│                    React Dashboard (Vercel)                      │
│   Risk Gauge · Phase Timeline · Sparklines · Commodity Cards    │
│   ML Forecast Chart · Analytics · Live News Feed · PDF Export   │
└─────────────────────────────────────────────────────────────────┘
```

---

## Features

### AI Pipeline
- **4-agent LangGraph pipeline** — agents share state and run sequentially: ENSO Monitor → News Analyst → Market Analyzer → Report Generator
- **LLM-generated reports** via Groq (Llama 3.1 8B) — executive summary, commodity outlooks with geographic specificity, and actionable recommendations
- **Automated weekly runs** — cron-job.org triggers the pipeline every Monday at 9 AM UTC; runs in background so the server responds instantly

### Machine Learning
- **9-month ENSO forecast** using Gradient Boosting Regressor trained on NOAA MEI data (1979–present)
- **Confidence intervals** — upper/lower bound models for uncertainty quantification
- **Backtest accuracy** — MAE, directional accuracy, and within-threshold accuracy reported live

### Analytics (6 modules)
| Module | Description |
|--------|-------------|
| Phase Probabilities | Historical frequency of each ENSO phase at current MEI level |
| Anomaly Detection | Z-score on month-over-month MEI change |
| Seasonal Decomposition | Trend + seasonal + residual via 12-month rolling average |
| Forecast Accuracy | Walk-forward backtest on last 12 months |
| Commodity Sensitivity | Pearson correlation between MEI and wheat/oil/soybean |
| Similar Historical Events | Cosine similarity search across all 12-month MEI windows since 1979 |

### Dashboard
- SVG semicircular **risk gauge** (1–10 scale)
- **Sparkline** showing 12-month MEI trend with delta indicator
- **Phase timeline** — color-coded history strip (blue = La Niña, red = El Niño, gray = Neutral) with dashed forecast segments
- Commodity cards with risk-colored borders and outlook text
- Live news feed with source, date, and clickable links (climate-filtered)
- PDF report download

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | React, Recharts, Axios |
| Backend | FastAPI, SQLAlchemy, APScheduler |
| AI / LLM | LangGraph, LangChain, Groq (Llama 3.1 8B) |
| ML | scikit-learn (Gradient Boosting), NumPy, pandas |
| Database | PostgreSQL |
| Data Sources | NOAA PSL, Yahoo Finance (yfinance), NewsAPI |
| Deployment | Vercel (frontend), Render (backend + DB) |
| Automation | cron-job.org (weekly pipeline trigger) |

---

## Project Structure

```
ENSO/
├── agents/
│   ├── agent1_enso.py       # Fetches MEI, determines ENSO phase
│   ├── agent2_news.py       # Fetches & analyzes climate news
│   ├── agent3_market.py     # Analyzes commodity market risk
│   ├── agent4_report.py     # Generates structured JSON report + PDF
│   └── pipeline.py          # LangGraph state graph wiring all agents
├── ml/
│   ├── forecaster.py        # Gradient Boosting ENSO forecast model
│   └── analytics.py         # 6 analytics modules
├── data_pipeline/
│   ├── fetch_noaa.py        # Downloads MEI data from NOAA PSL
│   ├── fetch_prices.py      # Downloads commodity prices via yfinance
│   └── fetch_news.py        # Fetches climate news from NewsAPI
├── backend/
│   └── main.py              # FastAPI app — routes, scheduler, DB logic
├── frontend/
│   └── enso-dashboard/      # React dashboard
└── outputs/                 # Generated PDF reports
```

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | Health check + endpoint listing |
| GET | `/status` | Current ENSO phase, MEI value, risk score |
| GET | `/latest-report` | Full JSON report |
| GET | `/latest-report/download` | PDF report download |
| GET | `/forecast` | 9-month ML forecast with confidence intervals |
| GET | `/analytics` | All 6 analytics modules |
| POST | `/run-now` | Trigger pipeline manually (requires `X-Cron-Secret` header) |

---

## Local Setup

### Prerequisites
- Python 3.10+
- Node.js 18+
- PostgreSQL

### Backend
```bash
# Clone the repo
git clone https://github.com/vanshrana369/ENSO-Intelligence-Platform.git
cd ENSO-Intelligence-Platform

# Install dependencies
pip install -r requirements.txt

# Create .env
DATABASE_URL=your_postgresql_url
GROQ_API_KEY=your_groq_key
NEWS_API_KEY=your_newsapi_key
CRON_SECRET=your_secret

# Run backend
cd backend
uvicorn main:app --reload
```

### Frontend
```bash
cd frontend/enso-dashboard
npm install
npm start
```

### Run the Pipeline Manually
```bash
cd agents
python pipeline.py
```

---

## Environment Variables

| Variable | Description |
|----------|-------------|
| `DATABASE_URL` | PostgreSQL connection string |
| `GROQ_API_KEY` | Groq API key for LLM inference |
| `NEWS_API_KEY` | NewsAPI key for live climate news |
| `CRON_SECRET` | Secret header value for `/run-now` protection |

---

## How It Works

1. **Every Monday at 9 AM UTC**, cron-job.org sends a POST to `/run-now`
2. The server immediately returns `202 Accepted` and starts the pipeline in a background thread
3. **Agent 1** pulls the latest MEI data from NOAA and commodity prices from Yahoo Finance, stores both to PostgreSQL, then determines the current ENSO phase
4. **Agent 2** fetches fresh climate news from NewsAPI, filters for relevance using keyword matching, and uses the LLM to extract the top 3 impact stories
5. **Agent 3** reads live commodity prices and uses the LLM to assess market risk for wheat, crude oil, and soybean under current ENSO conditions
6. **Agent 4** combines all outputs and prompts the LLM to produce a structured JSON report with executive summary, commodity outlooks, recommendations, and a 1–10 risk score — saved to PostgreSQL and a PDF
7. The **React dashboard** polls the API and renders the latest report with charts, gauges, and analytics

---

## Author

**Vansh Rana**  
[GitHub](https://github.com/vanshrana369)
