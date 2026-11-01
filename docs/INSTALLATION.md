# TRUTHMAP AI — Installation & Setup Guide

This guide provides end-to-end instructions for installing, configuring, and verifying TRUTHMAP AI on Windows, Linux, and macOS.

---

## 1. System Requirements

- **Python:** Version 3.11 or higher (Python 3.14 compatible)
- **Node.js:** Version 18.0.0 or higher (with `npm`)
- **Git:** Version 2.40+
- **Memory:** Minimum 4 GB RAM (8 GB recommended)
- **Disk Space:** ~500 MB for dependencies and local database

---

## 2. Clone and Setup Environment

### Step 1: Clone Repository
```bash
git clone https://github.com/your-username/truthmap-ai.git
cd truthmap-ai
```

### Step 2: Configure Environment Variables
Copy the provided template:
```bash
cp .env.example .env
```

Open `.env` in an editor and optionally configure your keys:
```ini
# Google Gemini API Key (Optional — system automatically uses deterministic engine if omitted or quota exhausted)
GEMINI_API_KEY=your_gemini_api_key_here
GEMINI_MODEL=gemini-2.0-flash

# External Search Provider (Optional — set to 'none' for manual entry mode)
SEARCH_PROVIDER=none
TAVILY_API_KEY=
SEARCH_TIMEOUT_SECONDS=10
SEARCH_MAX_RESULTS=5
```

---

## 3. Backend Installation & Startup

### Step 1: Create a Python Virtual Environment
**Windows (PowerShell):**
```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

**macOS / Linux:**
```bash
python3 -m venv venv
source venv/bin/activate
```

### Step 2: Install Python Dependencies
```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### Step 3: Launch the FastAPI Backend Server
```bash
uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload
```
The API documentation is accessible at:
- **Swagger UI:** [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- **Health Check:** [http://127.0.0.1:8000/api/health](http://127.0.0.1:8000/api/health)

---

## 4. Frontend Installation & Startup

Open a separate terminal window:

### Step 1: Install Node Dependencies
```bash
npm install
```

### Step 2: Launch Vite Development Server
```bash
npm run dev -- --host 127.0.0.1 --port 5173
```
The TruthMap AI Web Dashboard will be live at:
- **Web UI:** [http://127.0.0.1:5173](http://127.0.0.1:5173)

---

## 5. Verification & Testing

### 1. Run Automated Test Suite
Ensure all 159 unit and integration tests pass:
```bash
python -m pytest backend/tests/ -q
```

### 2. Verify Frontend Production Build
Confirm the client compiles cleanly:
```bash
npm run build
```

### 3. Run Live End-to-End Kaveri Components Demonstration
Execute the automated demonstration CLI:
```bash
python scratch/run_kaveri_demo.py
```
This script runs through components C01 to C10, ingesting the simulated proposal and official public sources, outputting measured conflicts, DFI scores, and the final executive verdict.
