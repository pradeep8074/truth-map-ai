# Security Policy — TRUTHMAP AI

## 1. Security Architecture & Safeguards

TRUTHMAP AI is built with strict defensive controls to protect data integrity, prevent unauthorized network traversal, and ensure secure ingestion:

### Server-Side Request Forgery (SSRF) Protection
All URL ingestion routines (`backend/services/web_scraper.py`) evaluate destination IP addresses prior to initiating network requests:
- **Blocked IP Networks:** Private RFC 1918 ranges (`10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`), loopbacks (`127.0.0.0/8`, `::1/128`), link-local/carrier-grade NAT (`100.64.0.0/10`), and cloud metadata services (`169.254.169.254`).
- **Scheme Validation:** Only explicit `http` and `https` schemes are accepted. File schemes (`file://`), internal protocols (`gopher://`, `dict://`), and raw sockets are strictly rejected.
- **Payload Limits:** Maximum response size capped at 15 MB to prevent memory exhaustion and decompression bombs.

### Local-First Evidentiary Privacy
- The forensic ledger is maintained locally in an embedded SQLite database (`truthmap.db`).
- No proprietary investigation data is transmitted to third parties unless the user explicitly configures an external API key (such as Google Gemini or Tavily).
- Demonstration vendor documents are clearly labelled `SIMULATED DEMONSTRATION DOCUMENT`.

### Credential & Secret Management
- `.env` files are strictly gitignored.
- Only safe placeholder templates (`.env.example`) are checked into the public repository.
- No production secrets or personal API keys are baked into the codebase or test fixtures.

---

## 2. Reporting a Vulnerability

If you discover a potential security vulnerability within TRUTHMAP AI, please report it responsibly:
- **Email:** `security@truthmap.ai` (or via GitHub Security Advisories)
- Please include steps to reproduce, affected component(s), and potential impact.
- We will acknowledge receipt within 48 hours and work with you on a coordinated disclosure timeline.
