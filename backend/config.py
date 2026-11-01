import os
import sys
from pathlib import Path

# Ensure both repo root and backend directory are in sys.path
_current_dir = Path(__file__).resolve().parent
_repo_root = _current_dir.parent
for _p in [str(_repo_root), str(_current_dir)]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

# Inject Windows system certificates if truststore is available
try:
    import truststore
    truststore.inject_into_ssl()
except Exception:
    pass

# Load environment variables from .env if present
try:
    from dotenv import load_dotenv
    load_dotenv(_repo_root / ".env")
    load_dotenv(_current_dir / ".env")
except ImportError:
    pass

# Paths & Storage Configuration
BASE_DIR = _current_dir

# Support configurable persistent data directory (e.g., /var/data on Render)
DATA_DIR = Path(os.getenv("DATA_DIR", BASE_DIR / "data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)

# Configurable database path (e.g., /var/data/truthmap.db for persistent Render disk)
_custom_db = os.getenv("DATABASE_PATH")
if _custom_db:
    DB_PATH = Path(_custom_db)
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
else:
    DB_PATH = DATA_DIR / "truthmap.db"

# Configurable upload directory (e.g., /var/data/uploads for persistent storage)
_custom_upload = os.getenv("UPLOAD_DIR")
if _custom_upload:
    UPLOAD_DIR = Path(_custom_upload)
else:
    UPLOAD_DIR = DATA_DIR / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

# Security & Ingestion Limits
MAX_CONTENT_LENGTH = 15 * 1024 * 1024       # 15 MB max response size for web scraping
MAX_PDF_SIZE = 25 * 1024 * 1024             # 25 MB max upload size
CONNECT_TIMEOUT = 10.0                      # seconds
READ_TIMEOUT = 15.0                         # seconds
MAX_REDIRECTS = 5

# Allowed URL schemes
ALLOWED_SCHEMES = {"http", "https"}

# Blocked IP ranges (SSRF Protection)
# Includes IPv4 private, loopback, link-local, carrier-grade NAT, and cloud metadata (169.254.169.254)
BLOCKED_IP_NETWORKS = [
    "127.0.0.0/8",      # Loopback
    "10.0.0.0/8",       # Private-use (RFC 1918)
    "172.16.0.0/12",    # Private-use (RFC 1918)
    "192.168.0.0/16",   # Private-use (RFC 1918)
    "169.254.0.0/16",   # Link-local / Cloud metadata (AWS, GCP, Azure, OpenStack)
    "100.64.0.0/10",    # Carrier-grade NAT
    "0.0.0.0/8",        # "This" network
    "::1/128",          # IPv6 loopback
    "fc00::/7",         # IPv6 unique local address
    "fe80::/10",        # IPv6 link-local
]

# Explicitly blocked hostnames
BLOCKED_HOSTNAMES = {
    "localhost",
    "metadata.google.internal",
    "metadata.internal",
    "instance-data",
}

# LLM Configuration (if available)
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-flash-lite-latest").strip()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()

# Component 10 Search Provider Configuration
SEARCH_PROVIDER = os.getenv("SEARCH_PROVIDER", "none").strip().lower()  # "none", "duckduckgo", "tavily"
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "").strip()
SEARCH_TIMEOUT_SECONDS = int(os.getenv("SEARCH_TIMEOUT_SECONDS", "10"))
SEARCH_MAX_RESULTS = int(os.getenv("SEARCH_MAX_RESULTS", "5"))

# CORS / Allowed Frontend Origins
FRONTEND_ORIGINS = os.getenv("FRONTEND_ORIGINS", "").strip()
