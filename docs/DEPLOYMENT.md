# TRUTHMAP AI — Production Cloud Deployment Guide

This guide provides exact, step-by-step instructions to deploy **TRUTHMAP AI** to production using **Render** (Backend API & Database) and **Vercel** (Frontend UI).

---

## 1. Deployment Architecture

```
                    ┌────────────────────────────────────────┐
                    │          End User Browser              │
                    └──────────────────┬─────────────────────┘
                                       │ HTTPS
                                       ▼
                    ┌────────────────────────────────────────┐
                    │          Vercel Edge Network           │
                    │   React 18 + Vite SPA (frontend/)      │
                    │   https://truthmap-ai.vercel.app       │
                    └──────────────────┬─────────────────────┘
                                       │ CORS REST API
                                       ▼
                    ┌────────────────────────────────────────┐
                    │            Render Web Service          │
                    │      FastAPI Engine (backend/)         │
                    │   https://truthmap-api.onrender.com    │
                    └───────┬────────────────────────┬───────┘
                            │                        │
               HTTPS / TLS  │                        │ File I/O
                            ▼                        ▼
              ┌─────────────────────┐      ┌─────────────────────────┐
              │  Google Gemini API  │      │ Render Persistent Disk  │
              │  (2.0 Flash / LLM)  │      │ (/var/data/truthmap.db) │
              │  + Fallback Engine  │      │  All forensic evidence  │
              └─────────────────────┘      └─────────────────────────┘
```

---

## 2. Part 1: Backend Deployment on Render

### Step 1: Create a New Web Service on Render
1. Log in to [Render Dashboard](https://dashboard.render.com/).
2. Click **New +** -> **Web Service**.
3. Connect your GitHub repository: `truthmap-ai`.
4. Configure the service parameters:
   - **Name:** `truthmap-api` (or a name of your choice)
   - **Region:** Choose closest to your users (e.g., *Singapore*, *Frankfurt*, or *Oregon*)
   - **Branch:** `main`
   - **Root Directory:** `backend`
   - **Runtime:** `Python`
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `uvicorn main:app --host 0.0.0.0 --port $PORT`
   - **Plan:** Free or Starter

### Step 2: Configure Environment Variables on Render
Under the **Environment** section, add the following variables:

| Key | Value | Purpose |
| :--- | :--- | :--- |
| `PYTHON_VERSION` | `3.11.9` | Ensures compatible Python environment |
| `GEMINI_API_KEY` | `AIzaSy...` | Private Google Gemini API key |
| `GEMINI_MODEL` | `gemini-2.0-flash` | Selected reasoning model |
| `DATABASE_PATH` | `/var/data/truthmap.db` | Persistent SQLite database location |
| `UPLOAD_DIR` | `/var/data/uploads` | Persistent uploaded files directory |
| `FRONTEND_ORIGINS` | `https://your-frontend.vercel.app` | Allowed CORS origins (update after Vercel deployment) |
| `SEARCH_PROVIDER` | `none` | Default deterministic manual search gateway |

> [!IMPORTANT]
> Never set `GEMINI_API_KEY` to public. Render stores this securely encrypted.

### Step 3: Attach Persistent Disk (For Data Retention)
1. Go to the **Disks** tab in your Render Web Service settings.
2. Click **Add Disk**:
   - **Name:** `truthmap-data`
   - **Mount Path:** `/var/data`
   - **Size:** `1 GB` (sufficient for thousands of investigations and evidence items)
3. Click **Save Changes**.

*Note: Persistent disks are available on Render Starter plans and above. On the Free tier, data persists across service restarts, but resets on new image builds. The application automatically adapts.*

### Step 4: Verify Backend Health
Once Render finishes deploying, copy your service URL (e.g. `https://truthmap-api.onrender.com`).
Test the endpoints in your browser or terminal:
```bash
# 1. Health Endpoint
curl https://truthmap-api.onrender.com/health

# 2. AI Diagnostics (Safe, No Secrets Leaked)
curl https://truthmap-api.onrender.com/api/system/ai-status

# 3. Swagger Interactive Docs
https://truthmap-api.onrender.com/docs
```

---

## 3. Part 2: Frontend Deployment on Vercel

### Step 1: Import Repository into Vercel
1. Log in to [Vercel Dashboard](https://vercel.com/dashboard).
2. Click **Add New...** -> **Project**.
3. Import your `truthmap-ai` GitHub repository.

### Step 2: Configure Build Settings
In the Project Configuration screen:
- **Framework Preset:** `Vite`
- **Root Directory:** Click **Edit** and select **`frontend`**
- **Build Command:** `npm run build` (or leave default `vite build`)
- **Output Directory:** `dist`

### Step 3: Configure Environment Variables
Under the **Environment Variables** section, add:

| Key | Value | Note |
| :--- | :--- | :--- |
| `VITE_API_BASE_URL` | `https://truthmap-api.onrender.com` | Use your actual Render backend URL without trailing slash |

> [!NOTE]
> Do NOT add `GEMINI_API_KEY` to Vercel. All AI reasoning is securely performed by the backend on Render.

### Step 4: Deploy and Verify
1. Click **Deploy**. Vercel will build the frontend in under 30 seconds.
2. Once complete, click **Visit** to view your live app (e.g., `https://truthmap-ai.vercel.app`).
3. Verify that SPA page refresh works without 404s (handled automatically by `vercel.json`).

---

## 4. Part 3: Handshake & CORS Sync

Now that your frontend has a live domain on Vercel:

1. Return to the **Render Dashboard** -> `truthmap-api` -> **Environment**.
2. Update **`FRONTEND_ORIGINS`**:
   ```env
   FRONTEND_ORIGINS=https://truthmap-ai.vercel.app,http://localhost:5173
   ```
3. Save changes. Render will automatically redeploy the backend in seconds.

*(Note: The backend also has built-in regex matching `r"https://.*\.vercel\.app"`, so all Vercel branch previews will automatically be allowed).*

---

## 5. Part 4: End-to-End Production Verification Checklist

Run this checklist on your live Vercel URL:

- [ ] **System Status:** Top bar shows `SYSTEM STATUS: ONLINE • READY`.
- [ ] **Diagnostics:** Open **System Settings** -> Gemini Connection displays `CONNECTED` or `FALLBACK ACTIVE` with model `gemini-2.0-flash`.
- [ ] **C01 Intake:** Click **Start an Investigation** -> Create a new investigation -> Redirects with unique investigation ID.
- [ ] **C02 Ingestion:** Upload `data/demo/kaveri_solar_proposal.pdf` -> Claims extracted with SHA-256 provenance hashes.
- [ ] **C03 Contract:** Generate decision criteria -> Criteria, constraints, and assumptions synthesized.
- [ ] **C04 Graph:** Navigate to **Evidence Map** -> Interactive DAG renders nodes and topological edges.
- [ ] **C05 Conflicts:** Open **Conflicting Evidence** -> Identified contradictions displayed with severity tags.
- [ ] **C07 Stress Tests:** Run **Test Your Decision** -> Adversarial stress tests executed.
- [ ] **C08 Reports:** Open **Investigation Reports** -> Compile Decision Report dossier.
- [ ] **C09 DFI:** Check **Decision Risk Score** -> Computes deterministic DFI.
- [ ] **Persistence:** Refresh the browser -> All data, claims, and reports remain intact.

---

## 6. Troubleshooting & Diagnostics

| Symptom | Probable Cause | Resolution |
| :--- | :--- | :--- |
| `Failed to fetch` in browser | Missing or incorrect `VITE_API_BASE_URL` on Vercel | Set `VITE_API_BASE_URL=https://your-backend.onrender.com` in Vercel and redeploy |
| `403 Forbidden` / CORS Error | Origin not in `FRONTEND_ORIGINS` | Add your Vercel domain to `FRONTEND_ORIGINS` on Render |
| `429 Quota Exhausted` | Free-tier Gemini quota limit reached | System automatically falls back to deterministic rule engine; upgrade plan or wait for quota reset |
| `404 on Page Refresh` on Vercel | Missing rewrite rules | Ensure `vercel.json` exists in `frontend/` with rewrite to `/index.html` |
| Database resets on new build | Using Render Free Tier without Persistent Disk | Attach a 1 GB persistent disk mounted at `/var/data` on Render Starter |
