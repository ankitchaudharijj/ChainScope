# 🔎 ChainScope

### AI-Assisted Blockchain Financial Crime Investigation Platform

> **Trace the money. Understand the movement. Connect the evidence.**

ChainScope is an open-source blockchain investigation platform designed to help analysts trace wallet activity, analyze multi-hop fund flows, identify potential VASP/entity relationships, assess risk signals, analyze wallet behaviour, and generate investigation-ready reports.

The platform combines:

- 🔗 Blockchain transaction analysis
- 🕸️ Graph-based fund-flow investigation
- ⏱️ Temporal / multi-hop analysis
- 🏢 VASP & entity attribution
- ⚠️ Rule-based risk analysis
- 🤖 ML-assisted wallet behaviour analysis
- 📊 Wallet clustering
- 📄 Investigation report generation
- 📝 Case management and audit logging

---

## 🚨 The Problem

Blockchain transactions are transparent, but investigating complex financial flows can be difficult.

A single suspicious wallet may interact with multiple intermediary addresses before funds reach an identifiable service or VASP.

Investigators may need to answer questions such as:

- Where did the funds come from?
- Where did they move next?
- Which wallets are connected?
- Is there a known VASP relationship?
- Are there multi-hop relationships?
- What risk signals are present?
- What behavioural patterns does the wallet exhibit?
- What evidence should be included in an investigation report?

Traditional single-hop analysis can miss relationships that become visible only when transaction networks are analyzed as a graph.

---

# 💡 The ChainScope Approach

ChainScope brings multiple investigation capabilities into a single workflow.

```text
                 Blockchain Data
                       │
                       ▼
              ┌─────────────────┐
              │    ChainScope   │
              └─────────────────┘
                       │
        ┌──────────────┼──────────────┐
        ▼              ▼              ▼
   Attribution       Risk          Graph
     Engine         Engine         Engine
        │              │              │
        └──────────────┼──────────────┘
                       ▼
                 ML Intelligence
                       │
                       ▼
             Investigation Report
```

The goal is not simply to produce a risk score. ChainScope attempts to provide the surrounding evidence and context that helps an analyst understand how that result was obtained.

---

# ✨ Key Features

## 🔗 Wallet Examination

Analyze a wallet address and retrieve:

- Transaction information
- Attribution signals
- Risk indicators
- Behavioural information
- Connected VASP information
- Graph relationships

The backend can use cached database information or fetch blockchain data for supported address formats.

---

## 🏢 VASP Attribution Engine

ChainScope evaluates whether a wallet may be associated with a known Virtual Asset Service Provider (VASP).

The attribution engine considers available evidence such as:

- Known VASP addresses
- Direct transaction relationships
- Address metadata
- Graph proximity
- Attribution evidence

The result is presented as an evidence-based candidate rather than assuming that every address belongs to a known entity.

### Attribution workflow

```text
Wallet Address
      │
      ▼
Transaction Analysis
      │
      ▼
Known Address Matching
      │
      ▼
Graph / Relationship Analysis
      │
      ▼
VASP Candidates
      │
      ▼
Evidence + Attribution Result
```

---

# ⚠️ Risk Analysis Engine

ChainScope includes a server-side rule-based Risk Engine.

It evaluates available wallet activity and produces risk-related signals based on the configured investigation rules.

Example signals include:

- Rapid fund movement
- VASP interaction
- Mixer-related relationships
- Transaction activity
- Other investigation-relevant indicators

Risk analysis is intended as an analytical signal and should not be treated as a definitive determination of criminal activity.

---

# 🕸️ Graph Investigation Engine

Neo4j is used to model blockchain relationships as a graph.

Instead of looking only at:

```text
Wallet A → VASP
```

ChainScope can investigate relationships such as:

```text
Wallet A
   │
   ▼
Wallet B
   │
   ▼
Wallet C
   │
   ▼
VASP
```

The Graph Engine can search multi-hop relationships and return the shortest discovered paths to relevant VASP nodes.

The current implementation supports graph proximity analysis up to four hops.

### Why a graph database?

A relational database can store individual transactions effectively, but graph traversal becomes particularly useful when the investigation requires understanding relationships across multiple intermediary wallets.

---

# 🤖 ML-Assisted Behaviour Analysis

ChainScope contains a separate ML component from the rule-based Risk Engine.

The current ML Engine uses a `RandomForestClassifier` trained on a small synthetic labelled dataset.

It currently models five behavioural classes:

```text
Normal
Exchange-like
Mixer-related
High-risk
Rapid Fund Movement
```

The model returns:

- Predicted behaviour
- Confidence
- Class probability distribution

### Important limitation

The current model is trained on synthetic examples rather than a large labelled real-world financial crime dataset.

Therefore, ML results should be treated as an additional analytical signal rather than a definitive classification.

---

# 🧬 Wallet Clustering

ChainScope also provides behavioural clustering using KMeans.

The clustering engine groups known wallets according to behavioural similarity.

```text
Wallet Dataset
      │
      ▼
Feature Extraction
      │
      ▼
KMeans Clustering
      │
      ▼
Behavioural Groups
```

With the small demonstration dataset, clustering separation is limited. The capability becomes more meaningful as the dataset grows.

---

# 📄 Investigation Reports

ChainScope can generate PDF investigation reports using ReportLab.

### Wallet Report

```text
GET /wallets/{address}/report.pdf
```

Generates a report using the current wallet examination.

### Case Report

```text
GET /cases/{case_number}/report.pdf
```

Generates a report from the case's stored snapshot.

This allows the filed case report to represent the information that was recorded when the case was created.

---

# 🗂️ Case Management

Investigators can:

- Create investigation cases
- View existing cases
- Retrieve individual cases
- Change case status
- Generate case reports

Example workflow:

```text
Wallet Examination
       │
       ▼
Investigation Findings
       │
       ▼
    File Case
       │
       ▼
 Case Snapshot
       │
       ▼
 Investigation Report
```

---

# 🔐 Authentication & Audit

The backend provides:

- JWT-based authentication
- Protected API endpoints
- Case management
- Audit logging

Except for authentication and health endpoints, API routes require an authenticated Bearer token.

---

# 🏗️ System Architecture

```text
                         ┌──────────────────────┐
                         │      Frontend        │
                         │  Investigation UI    │
                         └──────────┬───────────┘
                                    │
                                    ▼
                         ┌──────────────────────┐
                         │     FastAPI API      │
                         └──────────┬───────────┘
                                    │
             ┌──────────────────────┼──────────────────────┐
             │                      │                      │
             ▼                      ▼                      ▼
     ┌───────────────┐      ┌───────────────┐      ┌──────────────┐
     │  PostgreSQL   │      │     Neo4j     │      │ ML Engine    │
     │               │      │               │      │              │
     │ Wallets       │      │ Fund Graph    │      │ Behaviour    │
     │ Cases         │      │ Relationships │      │ Classification│
     │ VASPs         │      │ Multi-hop     │      │ Clustering   │
     │ Audit Logs    │      │ Proximity     │      │              │
     └───────────────┘      └───────────────┘      └──────────────┘
             │                      │                      │
             └──────────────────────┼──────────────────────┘
                                    ▼
                         ┌──────────────────────┐
                         │ Investigation Engine │
                         └──────────┬───────────┘
                                    ▼
                         ┌──────────────────────┐
                         │   PDF / Findings     │
                         └──────────────────────┘
```

---

# 🧰 Technology Stack

| Layer | Technology |
|---|---|
| Frontend | HTML / CSS / JavaScript |
| Backend | Python + FastAPI |
| Relational Database | PostgreSQL |
| Graph Database | Neo4j |
| ML | scikit-learn |
| Authentication | JWT |
| API Documentation | OpenAPI / Swagger |
| PDF Reports | ReportLab |
| Containerization | Docker + Docker Compose |
| Blockchain Data | Etherscan / Blockstream |
| Graph Queries | Cypher |

---

# 📁 Project Structure

```text
ChainScope/
│
├── backend/
│   ├── app/
│   │   ├── data/
│   │   │   └── seed.py
│   │   ├── routers/
│   │   │   ├── audit.py
│   │   │   ├── auth.py
│   │   │   ├── cases.py
│   │   │   ├── graph.py
│   │   │   ├── ml.py
│   │   │   ├── vasps.py
│   │   │   └── wallets.py
│   │   ├── services/
│   │   │   ├── attribution.py
│   │   │   ├── blockchain.py
│   │   │   ├── ml_engine.py
│   │   │   ├── pdf_report.py
│   │   │   └── risk.py
│   │   ├── graph.py
│   │   ├── models.py
│   │   ├── schemas.py
│   │   ├── security.py
│   │   └── main.py
│   ├── Dockerfile
│   ├── docker-compose.yml
│   ├── requirements.txt
│   └── .env.example
│
├── frontend/
│   └── chainscope_frontend_connected.html
│
├── .gitignore
└── README.md
```

---

# 🚀 Quick Start

## Prerequisites

Install:

- Docker Desktop
- Git
- Python 3.12+ (for running the frontend locally)

Make sure Docker Desktop is running before starting the backend.

---

## 1. Clone the repository

```bash
git clone https://github.com/ankitchaudharijj/ChainScope.git
cd ChainScope
```

---

## 2. Configure the backend

```bash
cd backend
```

### Linux / macOS

```bash
cp .env.example .env
```

### Windows PowerShell

```powershell
Copy-Item .env.example .env
```

If you want live Ethereum lookups, configure:

```env
ETHERSCAN_API_KEY=your_api_key
```

Do not commit your real `.env` file or API keys.

---

# 🐳 3. Start the Backend

From the `backend` directory:

```bash
docker compose up --build
```

Once the containers are running, seed the demonstration data:

```bash
docker compose exec api python -m app.data.seed
```

The API should now be available at:

```text
http://localhost:8000
```

Interactive API documentation:

```text
http://localhost:8000/docs
```

Neo4j Browser:

```text
http://localhost:7474
```

---

# 🌐 4. Start the Frontend

Open another terminal:

```bash
cd frontend
python -m http.server 3000
```

Open:

```text
http://localhost:3000/chainscope_frontend_connected.html
```

The frontend's API Base URL defaults to:

```text
http://localhost:8000
```

---

# 🔑 Demo Login

The repository includes a seeded demonstration account for local development.

```text
Email:
io.cyber@i4c.gov.in

Password:
demo123
```

> ⚠️ **Demo environment only.**
>
> Do not use these credentials for a production deployment.

---

# 🧪 API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| POST | `/auth/login` | Authenticate and obtain JWT |
| GET | `/health` | API health check |
| GET | `/wallets` | List known wallets |
| GET | `/wallets/{address}/examine` | Examine wallet |
| POST | `/cases` | Create investigation case |
| GET | `/cases` | List cases |
| GET | `/cases/{case_number}` | Retrieve case |
| PATCH | `/cases/{case_number}/status` | Update case status |
| GET | `/vasps` | List VASP directory |
| GET | `/wallets/{address}/report.pdf` | Generate wallet report |
| GET | `/cases/{case_number}/report.pdf` | Generate case report |
| GET | `/graph/{address}/proximity` | Multi-hop VASP proximity |
| GET | `/graph/{address}/subgraph` | Local transaction subgraph |
| GET | `/ml/{address}/behaviour` | Behaviour classification |
| GET | `/ml/clusters` | Behavioural clustering |
| GET | `/audit` | Audit log |

Interactive documentation:

```text
http://localhost:8000/docs
```

---

# 🔍 Example Investigation Workflow

```text
                 Wallet Address
                       │
                       ▼
               Wallet Examination
                       │
          ┌────────────┼────────────┐
          ▼            ▼            ▼
     Attribution      Risk       Behaviour
       Analysis      Analysis     Analysis
          │            │            │
          └────────────┼────────────┘
                       ▼
                 Graph Analysis
                       │
                       ▼
              Multi-hop Relationships
                       │
                       ▼
                 Investigation Case
                       │
                       ▼
                 PDF Report
```

---

# 📊 Data Sources & Attribution

The current project contains both:

### Synthetic demonstration data

Used to provide predictable examples for development and demonstrations.

### Selected public VASP-related addresses

The repository also contains a limited set of publicly tagged addresses used for attribution experiments.

This is **not a production-scale VASP directory**.

A production deployment would require a much larger, continuously maintained and independently verified attribution dataset.

---

# ⚠️ Important Limitations

ChainScope is currently a research / prototype platform.

### ML Dataset

The ML Engine currently uses synthetic training data.

It should not be interpreted as a production fraud-detection model.

### VASP Coverage

The current VASP directory contains a small number of curated addresses and does not represent complete exchange/address coverage.

### Blockchain Coverage

Current live blockchain integration focuses on supported ETH and BTC address lookups.

### Attribution

A wallet being associated with a known address or VASP does not by itself establish ownership, control, or criminal activity.

### Risk Scores

Risk outputs are analytical signals intended to support investigation, not definitive legal or criminal determinations.

---

# 🔐 Security

Never commit:

```text
.env
API keys
JWT secrets
Database passwords
Private keys
Production credentials
```

The repository includes `.gitignore` rules for common secret and development files.

If you discover a security vulnerability, please follow the process described in `SECURITY.md`.

---

# 🌍 Open Source

ChainScope is being developed as an open-source project.

Contributions are welcome across areas such as:

- 🔗 Blockchain integrations
- 🕸️ Graph algorithms
- 🏢 Entity attribution
- ⚠️ Risk detection rules
- 🤖 ML experimentation
- 🎨 Frontend / UX
- 🧪 Testing
- 📚 Documentation

Before contributing, please read:

```text
CONTRIBUTING.md
```

---

# 🤝 Contributing

A typical contribution workflow:

```text
Fork
  ↓
Create Branch
  ↓
Make Changes
  ↓
Test
  ↓
Commit
  ↓
Pull Request
  ↓
Review
  ↓
Merge
```

Example:

```bash
git checkout -b feature/new-risk-rule
```

Then:

```bash
git add .
git commit -m "Add new risk detection rule"
git push origin feature/new-risk-rule
```

Open a Pull Request on GitHub.

---

# 🗺️ Roadmap

## Current

- [x] FastAPI backend
- [x] PostgreSQL persistence
- [x] Neo4j graph engine
- [x] VASP attribution
- [x] Risk analysis
- [x] Multi-hop graph proximity
- [x] ML behaviour classification
- [x] Wallet clustering
- [x] Case management
- [x] Audit logging
- [x] PDF investigation reports
- [x] Blockchain lookup integration

## Planned

- [ ] Expand verified VASP/entity datasets
- [ ] Multi-chain expansion
- [ ] Larger labelled ML datasets
- [ ] Advanced temporal graph analysis
- [ ] Real-time transaction monitoring
- [ ] Investigation collaboration
- [ ] Advanced evidence correlation
- [ ] Production-grade database migrations
- [ ] Improved investigator workflows

---

# 🏆 Hacktoberfest Hack Day 2026

ChainScope is being developed and demonstrated as part of:

**Hacktoberfest Hack Day Chandigarh 2026**

The Hack Day version focuses on demonstrating how open-source technologies can be combined to build practical blockchain investigation tooling.

### Hack Day Investigation Flow

```text
Transaction / Wallet
        ↓
Blockchain Data
        ↓
Attribution
        ↓
Risk Signals
        ↓
Temporal / Graph Analysis
        ↓
ML Behaviour Signals
        ↓
Evidence
        ↓
Investigation Report
```

---

# 📜 License

This project is open source.

See the repository license for the terms under which the code can be used, modified and redistributed.

---

# 👨‍💻 Project

**ChainScope**

AI-Assisted Blockchain Financial Crime Investigation Platform

GitHub:

https://github.com/ankitchaudharijj/ChainScope

---

## ⭐ If you find ChainScope useful

Star the repository ⭐

Explore the code 🔎

Open an issue 🐛

Contribute a feature 🚀

Share the project 🌍

---

> **ChainScope**
>
> **Trace the money. Understand the movement. Connect the evidence.**
