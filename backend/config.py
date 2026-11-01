import os
from pathlib import Path

# Inject Windows system certificates if truststore is available
try:
    import truststore
    truststore.inject_into_ssl()
except Exception:
    pass

# Load environment variables from .env if present
try:
    from dotenv import load_dotenv
    _backend_dir = Path(__file__).resolve().parent
    load_dotenv(_backend_dir.parent / ".env")
    load_dotenv(_backend_dir / ".env")
except ImportError:
    pass

# Paths
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = DATA_DIR / "truthmap.db"

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
