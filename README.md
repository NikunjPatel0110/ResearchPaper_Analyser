# 📄 Paper IQ — Research Navigator

A Flask + Streamlit + MongoDB application for uploading, analysing, comparing, and detecting plagiarism / AI-generated content in research papers.

---

## Features

| Feature | Description |
|---|---|
| 📤 Upload | PDF, TXT, DOCX — auto-parsed, summarised, embedded |
| 🔍 Insights | Keywords, named entities, similar papers |
| ⚖️ Compare | Semantic similarity, keyword Venn, side-by-side summaries |
| 🚨 Plagiarism | Chunk-level matching with source links |
| 🤖 AI Detection | Probability score with confidence rating |
| 🛡️ Admin | Invite code generation, user & code management |

---

## Prerequisites

- Python 3.10+
- MongoDB running locally on `mongodb://localhost:27017`
- (Optional) GPU for faster sentence-transformer inference

---

## Setup

### 1. Clone the repository

```bash
git clone https://github.com/NikunjPatel0110/ResearchPaper_Analyser
cd ResearchPaper_Analyser
```


### 2. Create and activate a virtual environment

```bash
python -m venv .venv
# macOS / Linux
source .venv/bin/activate
# Windows
.venv\Scripts\activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Download spaCy model

```bash
python -m spacy download en_core_web_sm
```

### 5. Configure environment variables

```bash
cp .env.example .env
```

Open `.env` and set at minimum:

```
MONGO_URI=mongodb://localhost:27017/paperiq
JWT_SECRET_KEY=your-very-secret-key-change-this
UPLOAD_FOLDER=uploads
```

### 6. Create the first admin user

```bash
python scripts/create_admin.py
```

Follow the prompts to enter name, email, and password.

> **Tip:** To seed demo data (admin + 3 invite codes) in one step, run:
> ```bash
> python scripts/seed_demo.py
> ```

---

## Running the application

### Backend (Flask — port 5000)

```bash
python -m backend.app
# or
flask --app backend.app:create_app run --port 5000 --debug
```

Verify it's up:

```bash
curl http://localhost:5000/api/v1/health
# {"success": true, "data": {"status": "ok"}, "error": null}
```

### Frontend (Streamlit — port 8501)

Open a second terminal (with the venv activated):

```bash
cd frontend
streamlit run streamlit_app.py
```

Visit **http://localhost:8501** in your browser.

---

## Project Structure

```
paper-iq/
├── requirements.txt
├── .env.example
├── backend/
│   ├── app.py                    # Flask app factory
│   ├── config.py                 # Configuration
│   ├── models/db.py              # MongoDB connection
│   ├── middleware/
│   │   └── auth_middleware.py
│   ├── services/
│   │   ├── auth_service.py
│   │   ├── parse_service.py      # PDF/DOCX/TXT parsing
│   │   ├── nlp_service.py        # spaCy NLP pipeline
│   │   ├── search_service.py     # FAISS + external search
│   │   ├── compare_service.py    # Semantic similarity
│   │   ├── plagiarism_service.py
│   │   └── ai_detect_service.py
│   ├── routes/
│   │   ├── auth.py               # /api/v1/auth/*
│   │   └── papers.py             # /api/v1/papers/*
│   └── templates/
│       ├── login.html
│       └── register.html
├── frontend/
│   ├── streamlit_app.py          # Entry point + auth
│   └── pages/
│       ├── 1_Upload.py
│       ├── 2_Insights.py
│       ├── 3_Compare.py
│       ├── 4_Plagiarism.py
│       ├── 5_AI_Detection.py
│       └── 6_Admin.py
└── scripts/
    ├── create_admin.py
    └── seed_demo.py
```

---

## API Overview

All responses follow:
```json
{ "success": true, "data": {}, "error": null }
```

Authentication uses **JWT Bearer tokens**. Include `Authorization: Bearer <token>` on all protected routes.

| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/v1/auth/login` | Obtain JWT |
| POST | `/api/v1/auth/register` | Register with invite code |
| POST | `/api/v1/auth/invite` | Generate invite (admin) |
| GET | `/api/v1/papers` | List user's papers |
| POST | `/api/v1/papers/upload` | Upload & analyse paper |
| GET | `/api/v1/papers/:id` | Get paper details |
| POST | `/api/v1/papers/compare` | Compare two papers |
| POST | `/api/v1/papers/:id/plagiarism` | Run plagiarism check |
| POST | `/api/v1/papers/:id/detect-ai` | Run AI detection |

---

## Tech Stack

- **Backend**: Flask 3.0, flask-jwt-extended, flask-cors
- **Database**: MongoDB (pymongo)
- **NLP**: spaCy `en_core_web_sm`, NLTK, sentence-transformers (`all-MiniLM-L6-v2`)
- **Vector search**: FAISS (faiss-cpu)
- **Frontend**: Streamlit 1.35, Altair 5
- **Auth**: bcrypt passwords, JWT tokens, invite-only registration

---

## Author
- **Nikunj Patel** - [GitHub Profile](https://github.com/NikunjPatel0110)

## License

MIT
