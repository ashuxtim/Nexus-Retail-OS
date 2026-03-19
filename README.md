<div align="center">

<img src="./assets/logo.png" alt="Nexus Retail OS" width="90" height="90" style="border-radius: 20px"/>

<h1>Nexus Retail OS</h1>

[![Typing SVG](https://readme-typing-svg.demolab.com?font=Fira+Code&weight=500&size=18&pause=1000&color=3B82F6&center=true&vCenter=true&width=600&lines=XGBoost+%C2%B7+Prophet+%C2%B7+Monte+Carlo+%C2%B7+FP-Growth;LangGraph+ReAct+Agent+%C2%B7+15+Tools;ChromaDB+%C2%B7+Whisper+%C2%B7+Llama+Vision;Offline-first+%C2%B7+On-premise+%C2%B7+Production-grade)](https://git.io/typing-svg)

<p><strong>A production-grade desktop ERP with a full ML/AI backend</strong><br/>
<em>Offline-first · On-premise data · Optional AI powered by Groq</em></p>

[![React](https://img.shields.io/badge/React-18.2-61DAFB?style=for-the-badge&logo=react&logoColor=white)](https://react.dev)
[![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![Electron](https://img.shields.io/badge/Electron-28.2-47848F?style=for-the-badge&logo=electron&logoColor=white)](https://electronjs.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.123-009688?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![XGBoost](https://img.shields.io/badge/XGBoost-3.1.3-FF6600?style=for-the-badge)](https://xgboost.readthedocs.io)
[![LangGraph](https://img.shields.io/badge/LangGraph-1.0-7C3AED?style=for-the-badge)](https://langchain-ai.github.io/langgraph)
[![License](https://img.shields.io/badge/License-MIT-22c55e?style=for-the-badge)](LICENSE)
[![CI](https://img.shields.io/github/actions/workflow/status/ashuxtim/Nexus-Retail-OS/nexus_ci.yml?style=for-the-badge&label=CI&logo=github)](https://github.com/ashuxtim/Nexus-Retail-OS/actions)

[ML Pipeline](#-ml-pipeline) · [AI Assistant](#-ai-assistant) · [Architecture](#-architecture) · [Tech Stack](#-tech-stack) · [Installation](#-installation)

</div>

---

## The problem

Every SaaS retail tool is cloud-first, subscription-based, and generic. A small business owner in a low-connectivity environment needs their data local, their analytics fast, and their intelligence domain-specific — not a dashboard that phones home.

Nexus Retail OS is what an ML engineer would actually build for that problem. All transactions, inventory, and analytics run locally on SQLite. Four ML models run in background threads, maintain a versioned model registry, and persist results to a snapshot table so the dashboard loads instantly. The optional AI assistant needs a Groq API key; everything else works completely offline.

> **In one line:** 4 ML models · 10,000 Monte Carlo simulations per product · XGBoost churn scoring with MLOps registry · LangGraph ReAct agent with 15 tools · all on-device, no cloud required.

---

## Table of contents

- [Project showcase](#-project-showcase)
- [ML pipeline](#-ml-pipeline)
  - [Churn prediction — XGBoost](#churn-prediction--xgboost)
  - [Stockout prediction — Monte Carlo](#stockout-prediction--monte-carlo-simulation)
  - [Revenue forecasting — Prophet](#revenue-forecasting--facebook-prophet)
  - [Market basket analysis — FP-Growth](#market-basket-analysis--fp-growth)
  - [Analytics snapshot system](#analytics-snapshot-system)
- [AI assistant](#-ai-assistant)
- [Architecture](#-architecture)
- [Full application](#-full-application--12-pages)
- [Tech stack](#-tech-stack)
- [Installation](#-installation)
- [CI pipeline](#-ci-pipeline)
- [Project structure](#-project-structure)

---

## 🎬 Project showcase

### Executive dashboard

https://github.com/user-attachments/assets/f22f630e-6169-4404-a1b9-a7587fc5662f

The dashboard runs in two modes. **Overview** shows a 30-day Prophet revenue forecast with 95% confidence bands alongside a live debt/stock panel. **AI Intelligence** surfaces all four ML model outputs — churn scores, stockout probabilities, market basket rules — each on its own TTL schedule, loaded instantly from an analytics snapshot table on startup.

### OCR receipt processing

https://github.com/user-attachments/assets/9954378b-6846-4a53-a921-1f02b04acd31

Upload a receipt image → Llama 4 Scout extracts structured JSON in ~2 seconds → entity resolution matches supplier and products against live DB tables → one-click purchase invoice with automatic stock reconciliation.

---

## 🧠 ML pipeline

Four independent ML systems, each with its own caching layer, TTL schedule, and fallback logic. All run in background threads on startup without blocking the UI.

---

### Churn prediction — XGBoost

**What it does:** Scores every customer with a churn probability using RFM + velocity features, ranks them by risk, and maintains a versioned model registry with daily validation.

<details>
<summary><strong>Feature engineering details</strong></summary>

All features computed in `churn_features.py` using a 365-day lookback window:

| Feature | Description |
|---------|-------------|
| Recency | Days since last purchase (anchor: T-90 for training, now for inference) |
| Frequency | Transaction count over lookback window |
| Monetary | Average transaction value |
| Velocity | Ratio of last-30-day spend to long-term monthly average, clipped [0, 3] |

**Training strategy — time-travel labelling:** Features computed at T-90, labels assigned based on whether the customer purchased in the following 90 days. Eliminates data leakage and simulates real prediction conditions.

**Eligibility filter:** Only customers with 3+ purchases qualify for the training set. Minimum 10 rows required to proceed — training never runs on insufficient data.

</details>

<details>
<summary><strong>MLOps model registry</strong></summary>

Every trained model is registered in a SQLite `model_registry` table (`model_manager.py`) with full metadata: version, algorithm, metrics JSON, trained_rows, trained_at, promoted_at, replaced_by.

- A model is promoted to active only if it scores `AUC ≥ 0.85` on holdout data
- If no qualified model exists, `HeuristicChurnModel` activates automatically — predictions never fail
- `model_performance.py` re-evaluates the active model daily and writes results back to registry
- Full version history retained across model generations

</details>

| Metric tracked | ✓ |
|---------------|---|
| AUC-ROC | ✅ |
| Accuracy | ✅ |
| Precision / Recall / F1 | ✅ |
| Training & validation sample counts | ✅ |

---

### Stockout prediction — Monte Carlo simulation

**What it does:** For every product variant, simulates 10,000 demand scenarios over the next 30 days and outputs stockout probability, days-to-stockout distribution, safety stock, and EOQ.

<details>
<summary><strong>Simulation implementation</strong></summary>

Fully vectorised NumPy matrix operations in `monte_carlo_simulator.py` — no Python loops over simulations:

```python
# Shape: (10000, 30) — all scenarios, all days, one call
demands = np.random.normal(mean, std, (self.n_simulations, self.forecast_days))
cumulative_demand = np.cumsum(demands, axis=1)
stockout_mask = cumulative_demand >= current_stock
stockout_prob = stockout_mask.any(axis=1).mean()
```

**Demand modelling (`demand_analyzer.py`):** Chooses Poisson distribution for low-variance products, normal otherwise, based on 90-day sales history and coefficient of variation.

</details>

<details>
<summary><strong>Output per variant</strong></summary>

| Output | Description |
|--------|-------------|
| Stockout probability | 0–1 score from 10,000 simulations |
| Expected days to stockout | Mean of first-stockout distribution |
| Confidence intervals | 50th / 75th / 90th percentile of days |
| Safety stock | 95% service level, z = 1.65 |
| EOQ | Economic Order Quantity |
| Burn rate | Daily demand mean |
| Demand volatility | Coefficient of variation × 100 |
| Recommendation | `Buy Now` or `Monitor` |

Cached per-variant as JSON with 4-hour TTL, auto-invalidated if stock level changes.

</details>

---

### Revenue forecasting — Facebook Prophet

**What it does:** Trains on up to 730 days of daily revenue history and generates a 30-day forecast with 95% confidence intervals and full model metrics.

<details>
<summary><strong>Seasonality configuration & metrics</strong></summary>

| Seasonality component | Setting |
|----------------------|---------|
| Weekly | Always enabled |
| Monthly | Custom (period=30.5, Fourier order=5) |
| Yearly | Enabled only if >365 days of data |
| Daily | Disabled |

Metrics computed on in-sample residuals:

| Metric | Description |
|--------|-------------|
| MAPE | Mean Absolute Percentage Error |
| MAE | Mean Absolute Error |
| RMSE | Root Mean Square Error |
| R² | Coefficient of determination |
| AIC / BIC | Model complexity penalties |

Cache: date-keyed daily JSON. Old files auto-deleted on new generation. Minimum 14 days of data required.

</details>

---

### Market basket analysis — FP-Growth

**What it does:** Mines association rules from the last 90 days of sales (up to 10,000 transactions) to identify products that sell together.

<details>
<summary><strong>Algorithm & rule metrics</strong></summary>

FP-Growth via `mlxtend`, sparse matrix encoding for memory efficiency (`analyzer.py`). Rules filtered by `lift ≥ 1.5`, sorted by lift descending. Top 50 rules cached. Global threading lock prevents duplicate FP-Growth processes.

| Metric | Description |
|--------|-------------|
| Support | Transaction frequency of the itemset |
| Confidence | P(consequent \| antecedent) |
| Lift | Strength above random chance |
| Conviction | Directional rule strength |
| Leverage | Absolute co-occurrence above independence |
| Zhang's metric | Bidirectional association measure |

Rules are dynamically generated from live sales data. No hardcoded examples.

</details>

---

### Analytics snapshot system

All four model outputs are persisted to an `analytics_snapshot` SQLite table after every run. On every app startup, the dashboard hydrates instantly from snapshots — no waiting for models. Each model has its own TTL:

| Model | Cache TTL |
|-------|-----------|
| Stockout (Monte Carlo) | 4 hours |
| Churn (XGBoost) | 24 hours |
| Forecast (Prophet) | 24 hours |
| Market Basket (FP-Growth) | 30 days |

---

## 🤖 AI assistant

A three-tier routing pipeline designed to minimise LLM calls. The vast majority of queries are handled without touching an LLM at all.

```
User query
  │
  ├─ Greeting? ──────────────────────► Hardcoded response     [0 LLM calls]
  │
  ├─ Pattern match (router.py) ──────► Pre-written SQL query  [0 LLM calls]
  │   today's sales · weekly/monthly revenue · top customers
  │   low stock · out of stock · recent sales · suppliers
  │
  ├─ Intent classifier ──────────────► llama-3.1-8b-instant
  │   CHAT ──────────────────────────► Direct LLM reply
  │
  └─ QUERY ──────────────────────────► LangGraph ReAct agent
                                        qwen/qwen3-32b · 15 tools · 60s timeout · 2 retries
```

<details>
<summary><strong>All 15 agent tools</strong></summary>

| Tool | What it does |
|------|--------------|
| `resolve_entity_tool` | Fuzzy name → exact DB ID for any entity |
| `search_catalog_tool` | Semantic search across products, customers, suppliers |
| `search_supplier_tool` | SQL fallback for exact supplier name lookup |
| `get_product_stockout_tool` | Monte Carlo predictions for a named product |
| `get_product_basket_tool` | FP-Growth associations for a named product |
| `get_customer_churn_for_product_tool` | Churn profile of buyers of a specific product |
| `get_business_overview_tool` | Full strategy report: revenue, products, customers, inventory |
| `check_churn_risk_tool` | All at-risk customers ranked by churn score |
| `get_market_insights_tool` | Overall market basket associations |
| `get_sales_trends_tool` | Daily/weekly/monthly revenue trend with growth % |
| `get_top_performers_tool` | Top sellers and dead stock |
| `get_customer_segments_tool` | Top spenders, inactive, new customers, average basket |
| `get_inventory_velocity_tool` | Out-of-stock list, urgent restocks, fast movers, days-of-stock |
| `get_revenue_comparison_tool` | This week vs last, this month vs last, by category |
| `run_sql_query` | Dynamic read-only SELECT for ad-hoc data questions |

**Hard constraints enforced in code:** System prompt explicitly forbids add/delete/update. `run_sql_query` rejects any non-SELECT query. No CRUD operations are possible through the AI layer.

</details>

<details>
<summary><strong>Semantic search — ChromaDB</strong></summary>

`all-MiniLM-L6-v2` embeddings, three collections: `product`, `customer`, `supplier`. Background polling sync every 5 minutes reconciles new, updated, and deleted records. Cosine similarity scoring with brand-level deduplication (max 5 variants per brand in results). Old FAISS index files cleaned up automatically on first run.

</details>

<details>
<summary><strong>Vision & voice</strong></summary>

**Receipt OCR:** `meta-llama/llama-4-maverick-17b-128e-instruct` via Groq Vision. Extracts structured JSON (supplier, line items, totals, date). Output matched against live supplier and product tables for one-click invoice creation.

**Voice transcription:** `whisper-large-v3` via Groq. Audio recorded client-side, uploaded as blob, transcript returned. Domain-specific prompt improves accuracy for grocery/retail vocabulary. Transcript feeds directly into the same assistant pipeline as typed queries.

</details>

---

## 🏗 Architecture

<details>
<summary><strong>Process model & data flow</strong></summary>

```
┌─────────────────────────────────────────────────────────┐
│                   Electron Main Process                  │
│                                                         │
│   ┌─────────────┐      ┌──────────────────────────┐    │
│   │  React UI   │      │  IPC Handlers            │    │
│   │  (Renderer) │◄────►│  fetchPython() helper    │    │
│   │  12 pages   │      │  Worker threads (search) │    │
│   └─────────────┘      └───────────┬──────────────┘    │
│                                    │ HTTP · localhost   │
└────────────────────────────────────┼────────────────────┘
                                     │
┌────────────────────────────────────▼────────────────────┐
│             Python Backend  ·  FastAPI / Uvicorn         │
│                       127.0.0.1:8000                     │
│                                                         │
│  /ask  /forecast  /analytics/dashboard  /health         │
│  /transcribe  /scan_receipt  /api/stockout/*            │
│                                                         │
│  ┌─────────────┐  ┌─────────────┐  ┌────────────────┐  │
│  │  LangGraph  │  │  Analytics  │  │  SmartSearch   │  │
│  │ ReAct Agent │  │   Engine    │  │  (ChromaDB)    │  │
│  └─────────────┘  └─────────────┘  └────────────────┘  │
│                                                         │
│  ┌─────────────────────────────────────────────────┐   │
│  │          ML Model Registry  (SQLite)             │   │
│  │  XGBoost · Prophet · Monte Carlo · FP-Growth     │   │
│  │  register → validate → promote → version history │   │
│  └─────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────┘
```

**Key design decision:** The renderer process never contacts Python directly. All calls go through `window.api` (Electron IPC) → `fetchPython()` helper in the main process → FastAPI. This keeps the renderer sandboxed and centralises auth, timeouts, and error wrapping.

</details>

<details>
<summary><strong>Production packaging</strong></summary>

Python backend compiled to a single `NexusBackend.exe` via PyInstaller 6.18. Electron Builder bundles the exe inside `extraResources` and produces a single `NexusRetailOS-Setup.exe` installer. End users need no Python or Node.js installation.

**Dev vs production:** In dev mode, Electron skips backend spawning — run `python_server/main.py` manually. In production, the exe is spawned as a child process on app start with `NEXUS_USER_DATA` injected for shared data path.

</details>

<details>
<summary><strong>Security — key storage</strong></summary>

API keys are encrypted with Fernet (AES-128-CBC + HMAC-SHA256) using a machine-specific PBKDF2-derived key (480,000 iterations, OWASP recommendation). Encrypted values persisted to `keys.enc` in the app data directory. The PBKDF2 key is derived from a machine ID read from the OS credential store (`safeStorage` on Electron side, Windows Registry `MachineGuid` on Python side). Keys cannot be decrypted on a different machine.

</details>

---

## 📱 Full application — 12 pages

<details>
<summary><strong>Page list</strong></summary>

| Page | Description |
|------|-------------|
| Dashboard | ML analytics, revenue forecast, KPI grid, expert/simple mode toggle, data freshness timer |
| New Sale | Full transaction entry with product search and payment handling |
| Daybook | Daily transaction log |
| Products | Inventory management with variant support |
| Customers | Customer list with paginated search |
| Customer Detail | Per-customer ledger, purchase history, churn score |
| Sales Ledger | Full sales history with CSV export via worker thread |
| Purchases | Purchase invoice management |
| Purchase Ledger | Supplier-wise purchase history |
| Supplier Details | Per-supplier purchase history and contact |
| Search Results | Global fuzzy search across all entities |
| Settings | API key configuration, AI model status, force refresh |

All pages lazy-loaded. Global search in a dedicated worker thread to prevent UI blocking. Dark/light mode with persistence. Notification panel with due-payment alerts polled every 5 minutes.

</details>

---

## 🛠 Tech stack

<div align="center">

![React](https://img.shields.io/badge/React_18.2-20232A?style=for-the-badge&logo=react&logoColor=61DAFB)
![Vite](https://img.shields.io/badge/Vite_7.3-646CFF?style=for-the-badge&logo=vite&logoColor=white)
![TailwindCSS](https://img.shields.io/badge/Tailwind_CSS-06B6D4?style=for-the-badge&logo=tailwindcss&logoColor=white)
![Electron](https://img.shields.io/badge/Electron_28-2C2E3B?style=for-the-badge&logo=electron&logoColor=9FEAF9)
![Python](https://img.shields.io/badge/Python_3.10+-3776AB?style=for-the-badge&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-005571?style=for-the-badge&logo=fastapi)
![SQLite](https://img.shields.io/badge/SQLite-07405E?style=for-the-badge&logo=sqlite&logoColor=white)
![XGBoost](https://img.shields.io/badge/XGBoost_3.1-FF6600?style=for-the-badge)
![scikit-learn](https://img.shields.io/badge/scikit--learn-F7931E?style=for-the-badge&logo=scikit-learn&logoColor=white)
![NumPy](https://img.shields.io/badge/NumPy-013243?style=for-the-badge&logo=numpy&logoColor=white)
![Pandas](https://img.shields.io/badge/Pandas-150458?style=for-the-badge&logo=pandas&logoColor=white)
![Groq](https://img.shields.io/badge/Groq_API-F55036?style=for-the-badge)
![LangChain](https://img.shields.io/badge/LangGraph_1.0-1C3C3C?style=for-the-badge)
![Docker](https://img.shields.io/badge/Docker-2496ED?style=for-the-badge&logo=docker&logoColor=white)

</div>

<details>
<summary><strong>Full stack table</strong></summary>

| Layer | Technology |
|-------|-----------|
| Frontend | React 18.2 · Vite 7.3 · React Router 6.22 |
| UI | Tailwind CSS 3.4 · Shadcn UI (Radix) · Framer Motion 12.26 |
| Desktop | Electron 28.2 · electron-builder · electron-updater |
| Backend | Python 3.10+ · FastAPI 0.123 · Uvicorn |
| Database | SQLite (WAL mode) · SQLAlchemy 2.0 |
| ML | XGBoost 3.1.3 · Facebook Prophet 1.2 · scikit-learn 1.7 · mlxtend 0.23 |
| AI agent | LangGraph 1.0 · LangChain-Groq · qwen/qwen3-32b · llama-3.1-8b-instant |
| Vision | meta-llama/llama-4-maverick-17b-128e-instruct (Groq) |
| Voice | whisper-large-v3 (Groq) |
| Vector store | ChromaDB 0.5 · sentence-transformers 5.2 · all-MiniLM-L6-v2 |
| Packaging | PyInstaller 6.18 · electron-builder 24 |
| Caching | LRU Cache (Node) · date-keyed JSON · analytics_snapshot (SQLite) |

</details>

---

## ⚙️ Installation

### Prerequisites

- Node.js 18+
- Python 3.10+
- Git

### Setup

```bash
# 1. Clone
git clone https://github.com/ashuxtim/Nexus-Retail-OS.git
cd Nexus-Retail-OS

# 2. Node dependencies
npm install
npx electron-rebuild

# 3. Python virtual environment
cd python_server
python -m venv venv

# Windows
venv\Scripts\activate
# macOS / Linux
source venv/bin/activate

pip install -r requirements.txt
cd ..
```

### Environment variables

```bash
GROQ_API_KEY=gsk_...        # Required for AI features — groq.com/console
GOOGLE_API_KEY=AIzaSy...    # Optional, reserved for future integrations
```

Keys can also be set through the Settings page after launch. They are encrypted before storage.

### Development

```bash
# Terminal 1 — React + Electron
npm run electron-dev

# Terminal 2 — Python backend
cd python_server
source venv/bin/activate     # or venv\Scripts\activate on Windows
uvicorn main:app --reload
```

<details>
<summary><strong>First launch behaviour</strong></summary>

On first startup the churn model trains automatically once enough qualifying customer data exists (customers with 3+ purchases, minimum 10 training rows). The other three models run in background threads and persist results to the analytics snapshot table. Subsequent startups load from snapshots instantly — no waiting.

AI features require a Groq API key set in Settings. Without a key, all core ERP functionality (sales, inventory, customers, purchases, reports) works fully offline.

</details>

---

## ✅ CI pipeline

Three jobs run on every push to `main`:

| Job | What it checks |
|-----|---------------|
| `backend-quality` | Black formatting + Flake8 syntax (Python 3.12) |
| `frontend-build` | React/Vite build verification (Node 20) |
| `simulation-check` | Seeds a test database, runs daily simulation script |

---

## 📁 Project structure

<details>
<summary><strong>Full directory tree</strong></summary>

```
nexus-retail-os/
├── .github/workflows/
│   └── nexus_ci.yml               # 3-job CI pipeline
│
├── electron/
│   ├── main.js                    # App lifecycle, IPC, backend spawn, key injection
│   ├── preload.js                 # Context bridge — window.api (40+ methods)
│   ├── workers/                   # Worker threads: search, ledger export
│   └── database/
│       ├── repositories/          # ProductRepo, CustomerRepo, SaleRepo, SupplierRepo
│       ├── cacheManager.js        # LRU cache with TTL
│       └── migrationManager.js    # Schema migration runner
│
├── python_server/
│   ├── main.py                    # FastAPI app, route registration, startup
│   ├── core/
│   │   ├── startup.py             # AI init, analytics pipeline, snapshot loader
│   │   ├── key_store.py           # Fernet AES-128 + PBKDF2 key persistence
│   │   └── state.py               # Shared runtime state
│   ├── ai_engine/
│   │   ├── agent_builder.py       # LangGraph ReAct agent, 15 tools, system prompt
│   │   ├── safety.py              # Intent classifier (QUERY / CHAT)
│   │   ├── router.py              # Regex pattern router — zero LLM cost
│   │   ├── queries.py             # Pre-written SQL query functions
│   │   ├── tools.py               # 14 analytics/search tools
│   │   ├── vision.py              # Receipt OCR — Llama 4 Maverick
│   │   └── voice.py               # Whisper transcription
│   ├── models/
│   │   ├── churn/                 # XGBoost classifier + HeuristicChurnModel fallback
│   │   ├── stockout/              # Monte Carlo simulator + demand analyzer
│   │   ├── forecast/              # Prophet revenue forecaster
│   │   └── market_basket/         # FP-Growth association rule miner
│   ├── mlops/
│   │   ├── model_manager.py       # Registry: register, promote, version history
│   │   └── model_performance.py   # Daily validation — churn and forecast
│   ├── features/
│   │   ├── churn_features.py      # RFM + velocity feature engineering
│   │   └── inventory/             # Demand analysis for stockout
│   ├── routes/
│   │   ├── ai_chat.py             # POST /ask — three-tier routing pipeline
│   │   ├── analytics.py           # Dashboard, forecast, churn, stockout, cache endpoints
│   │   ├── media.py               # POST /scan_receipt · POST /transcribe
│   │   └── settings.py            # POST /settings — key injection + AI reinit
│   ├── vector_store.py            # ChromaDB + SentenceTransformer, 3 collections
│   ├── analytics.py               # AnalyticsEngine — coordinates all 4 ML models
│   └── scripts/
│       ├── seed_database.py       # Test data seeding
│       └── daily_seed.py          # Daily simulation for CI
│
├── src/
│   ├── pages/                     # 12 lazy-loaded route-level page components
│   ├── components/
│   │   ├── AiAssistant.jsx        # AI chat panel — text + voice input
│   │   └── ui/                    # Shadcn component library
│   └── lib/utils.jsx
│
├── package.json
└── vite.config.js
```

</details>

---

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/your-feature`
3. Commit your changes: `git commit -m 'Add your feature'`
4. Push: `git push origin feature/your-feature`
5. Open a Pull Request

---

## 📄 License

MIT — see [LICENSE](LICENSE) for details.

---

## 🙏 Acknowledgements

- [Groq](https://groq.com) — LLM, Whisper, and Vision inference
- [LangGraph](https://langchain-ai.github.io/langgraph) — ReAct agent execution framework
- [ChromaDB](https://trychroma.com) — Persistent vector store
- [Facebook Prophet](https://facebook.github.io/prophet) — Time series forecasting
- [XGBoost](https://xgboost.readthedocs.io) — Gradient boosting framework
- [mlxtend](http://rasbt.github.io/mlxtend) — FP-Growth implementation
- [Shadcn UI](https://ui.shadcn.com) — Radix-based component library

---

<div align="center">

Built by [Ashutosh Pathak](https://github.com/ashuxtim)

[![GitHub stars](https://img.shields.io/github/stars/ashuxtim/Nexus-Retail-OS?style=social)](https://github.com/ashuxtim/Nexus-Retail-OS/stargazers)

*If this project was useful, a ⭐ is appreciated.*

</div>
