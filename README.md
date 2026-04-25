# 🌊 ENSO Intelligence Platform

> An AI-powered system that detects El Niño from NASA satellite imagery and autonomously generates climate risk intelligence reports using a multi-agent pipeline.

![Status](https://img.shields.io/badge/Status-In%20Development-blue)
![Python](https://img.shields.io/badge/Python-3.11-blue)
![License](https://img.shields.io/badge/License-MIT-green)

---

## 🚀 Live Demo
> 🔗 Coming soon — deploying on Render + Vercel (Week 8)

---

## 📌 What This Project Does

Most climate tools give you pre-processed index numbers. This system goes upstream:

1. **Fetches raw NASA satellite SST (Sea Surface Temperature) images** of the Pacific Ocean
2. **Runs them through a Vision Transformer (ViT)** fine-tuned to detect El Niño, La Niña, or Neutral conditions
3. **Feeds the prediction into a 4-agent LangGraph pipeline** that pulls live news, commodity prices, and synthesizes everything
4. **Auto-generates a PDF intelligence report every week** — zero human intervention

---

## 🏗️ System Architecture

```
NASA Satellite Images (SST)
        │
        ▼
┌─────────────────────┐
│  Vision Transformer  │  ← Fine-tuned ViT on 40+ years of Pacific SST data
│  (PyTorch + HF)     │  → Outputs: El Niño / Neutral / La Niña + confidence
└─────────────────────┘
        │
        ▼
┌──────────────────────────────────────────────────────────┐
│                  LangGraph Multi-Agent Pipeline           │
│                                                          │
│  Agent 1: ENSO Monitor   → Reads CV model prediction     │
│  Agent 2: News Analyst   → Scrapes El Niño news          │
│  Agent 3: Market Analyzer → Commodity price correlation  │
│  Agent 4: Report Generator → Synthesizes everything      │
└──────────────────────────────────────────────────────────┘
        │
        ▼
┌─────────────────────┐
│   PDF Report        │  ← Auto-generated every Monday via Celery
│   React Dashboard   │  ← Live metrics, GradCAM overlay, news feed
└─────────────────────┘
```

---

## ⚙️ Tech Stack

| Layer | Technology |
|---|---|
| **CV Model** | PyTorch, HuggingFace ViT, GradCAM |
| **Agent Framework** | LangGraph, Groq LLM API |
| **Data Sources** | NASA Earthdata, NewsAPI, yfinance |
| **Backend** | FastAPI, Celery, Redis, PostgreSQL |
| **Frontend** | React, Recharts, Leaflet.js |
| **DevOps** | Docker, Docker Compose, GitHub Actions |
| **ML Ops** | MLflow |
| **Deployment** | Render (backend), Vercel (frontend) |

---

## 📂 Project Structure

```
ENSO-Intelligence-Platform/
│
├── data/
│   ├── raw/                  # Raw NASA NetCDF files, news JSON, price CSV
│   └── processed/            # Preprocessed PNG images with labels
│
├── cv_model/
│   ├── dataset.py            # PyTorch Dataset for SST images
│   ├── train_cnn.py          # Baseline CNN training script
│   ├── train_vit.py          # Vision Transformer fine-tuning
│   ├── gradcam.py            # GradCAM visualization
│   └── evaluate.py           # Confusion matrix, backtest on 1997/2015
│
├── agents/
│   ├── agent1_enso.py        # ENSO Monitor agent
│   ├── agent2_news.py        # News Analyst agent
│   ├── agent3_market.py      # Market Analyzer agent
│   ├── agent4_report.py      # Report Generator agent
│   └── pipeline.py           # LangGraph master pipeline
│
├── data_pipeline/
│   ├── fetch_noaa.py         # NOAA ENSO data fetcher
│   ├── fetch_news.py         # NewsAPI scraper
│   ├── fetch_prices.py       # yfinance commodity fetcher
│   └── store.py              # PostgreSQL storage
│
├── backend/
│   ├── main.py               # FastAPI app
│   ├── tasks.py              # Celery tasks
│   └── pdf_generator.py      # ReportLab PDF builder
│
├── frontend/
│   └── enso-dashboard/       # React app
│
├── .github/
│   └── workflows/
│       ├── weekly_fetch.yml  # Auto data fetch every Monday
│       └── tests.yml         # Run tests on every push
│
├── .env.example              # Environment variable template
├── docker-compose.yml        # Runs all services together
├── requirements.txt
└── README.md
```

---

## 🛠️ Setup & Installation

### Prerequisites
- Python 3.11+
- Docker & Docker Compose
- Node.js 18+ (for frontend)
- PostgreSQL

### 1. Clone the repo
```bash
git clone https://github.com/vanshrana369/ENSO-Intelligence-Platform.git
cd ENSO-Intelligence-Platform
```

### 2. Setup environment variables
```bash
cp .env.example .env
# Fill in your API keys in .env
```

Your `.env` file should look like:
```
GROQ_API_KEY=your_groq_key_here
NEWS_API_KEY=your_newsapi_key_here
DATABASE_URL=postgresql://user:password@localhost:5432/enso_db
```

### 3. Install Python dependencies
```bash
python -m venv venv
source venv/bin/activate        # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 4. Run with Docker (recommended)
```bash
docker-compose up --build
```

This starts:
- FastAPI backend at `http://localhost:8000`
- React frontend at `http://localhost:3000`
- Celery worker (background jobs)
- Redis (task queue)
- PostgreSQL (database)

### 5. Run data pipeline manually
```bash
python data_pipeline/fetch_noaa.py
python data_pipeline/fetch_news.py
python data_pipeline/fetch_prices.py
```

---

## 🤖 Running the Agent Pipeline
```bash
python agents/pipeline.py
```
Output: generates a PDF report in `/outputs/` with date-stamp.

---

## 🧠 Training the CV Model

### Step 1 — Download NASA SST data
1. Create free account at [earthdata.nasa.gov](https://earthdata.nasa.gov)
2. Go to [NASA Giovanni](https://giovanni.gsfc.nasa.gov)
3. Download SST data for Niño 3.4 region (5°N–5°S, 170°W–120°W), 1980–2026

### Step 2 — Preprocess
```bash
python cv_model/dataset.py
```

### Step 3 — Train baseline CNN
```bash
python cv_model/train_cnn.py
```

### Step 4 — Fine-tune Vision Transformer
```bash
python cv_model/train_vit.py
```

### Step 5 — Generate GradCAM visualizations
```bash
python cv_model/gradcam.py --image data/processed/2026_01.png
```

---

## 📊 Model Performance

| Model | Accuracy | F1 Score | Notes |
|---|---|---|---|
| CNN Baseline | -- | -- | *(updating after training)* |
| ViT Fine-tuned | -- | -- | *(updating after training)* |

Backtest results on historical El Niño events:
- **1997–98 Super El Niño:** *(updating)*
- **2015–16 El Niño:** *(updating)*

---

## 📈 Sample Output

> PDF report and dashboard screenshots coming in Week 4 of development.

---

## 🔄 Automated Pipeline

The full pipeline runs automatically every **Monday at 8:00 AM** via Celery Beat:

```
Fetch new data → Run CV model → 4 agents process → PDF generated → Dashboard updated
```

You can also trigger it manually:
```bash
curl -X POST http://localhost:8000/run-now
```

---

## 🗺️ Development Roadmap

- [x] Project setup + GitHub repo
- [ ] Week 1: NOAA + NewsAPI + yfinance data pipeline
- [ ] Week 2: LangGraph multi-agent system (4 agents)
- [ ] Week 3: Agent 4 (Report Generator) + PDF output
- [ ] Week 4: Celery automation + FastAPI + GitHub Actions
- [ ] Week 5: NASA satellite data pipeline + CNN baseline
- [ ] Week 6: Vision Transformer fine-tuning + GradCAM
- [ ] Week 7: React dashboard + Docker containerization
- [ ] Week 8: Deploy + documentation + Medium article

---

## 💡 Why This Project?

El Niño 2026 is actively developing right now (NOAA: 61% probability by May-July 2026). Most systems use pre-processed NOAA index numbers. This platform goes upstream — directly analyzing raw satellite imagery — and connects the prediction to real market and policy impacts through autonomous AI agents.

---

## 📚 Resources & References

- [NOAA ENSO Data](https://psl.noaa.gov/enso/mei/)
- [NASA Earthdata](https://earthdata.nasa.gov)
- [LangGraph Documentation](https://langchain-ai.github.io/langgraph/)
- [HuggingFace ViT](https://huggingface.co/google/vit-base-patch16-224)
- [IRI ENSO Forecast (April 2026)](https://iri.columbia.edu/our-expertise/climate/forecasts/enso/current/)

---

## 👤 Author

**Vansh Rana**
B.Tech Computer Science

[![LinkedIn](https://img.shields.io/badge/LinkedIn-vanshrana369-blue)](https://www.linkedin.com/in/vanshrana369)
[![GitHub](https://img.shields.io/badge/GitHub-vanshrana369-black)](https://github.com/vanshrana369)

---

## 📄 License

MIT License — feel free to use and learn from this project.

---

> ⭐ Star this repo if you find it interesting — it helps with visibility!
