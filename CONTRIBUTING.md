# Contributing to TRUTHMAP AI

Thank you for your interest in contributing to TRUTHMAP AI! We welcome contributions that uphold our core principles of **data honesty**, **epistemic traceability**, and **zero synthetic metrics**.

---

## 1. Development Principles

1. **Honesty Rules are Non-Negotiable:**
   - Never report a feature or endpoint as functional unless backed by an automated test or real execution log.
   - Never hardcode fake dashboard metrics, synthetic scores, or predetermined outcomes.
   - Do not claim external search or LLM features are working unless actively verified.
2. **Deterministic Fallbacks:**
   - Every AI/LLM analytical component must feature a deterministic heuristic fallback engine so the platform remains fully functional offline or under quota exhaustion.
3. **Epistemic Traceability:**
   - Every claim, conflict, and report section must link back to an immutable, SHA-256 hashed source passage.

---

## 2. Setting Up Your Development Environment

1. Fork and clone the repository:
   ```bash
   git clone https://github.com/your-username/truthmap-ai.git
   cd truthmap-ai
   ```
2. Set up Python virtual environment (Python 3.11+):
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: .\venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   ```
3. Set up Frontend (Node 18+):
   ```bash
   npm install
   ```
4. Copy the environment template:
   ```bash
   cp .env.example .env
   ```

---

## 3. Pull Request Guidelines

1. **Create a Feature Branch:**
   ```bash
   git checkout -b feature/your-feature-name
   ```
2. **Run Tests Before Submitting:**
   ```bash
   # Run all backend tests
   python -m pytest backend/tests/ -q

   # Verify frontend build
   npm run build
   ```
3. **Commit Messages:**
   Use conventional commits (e.g. `feat: add export credit parser`, `fix: handle 429 quota backoff`, `docs: update runbook`).

4. **Submit PR:**
   Provide a clear description of the change, test evidence, and any affected component schemas.
