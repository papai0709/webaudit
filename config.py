"""
config.py — Centralised configuration for Web Analyser.
All tuneable constants live here. Override via environment variables.
"""
import os

# ── HTTP / Network ─────────────────────────────────────────────────────────────
# Seconds before a single HTTP request is abandoned
REQUEST_TIMEOUT: int = int(os.getenv("WA_REQUEST_TIMEOUT", 10))

# Seconds for quick HEAD probes (rendering CSS check, security sensitive files)
HEAD_TIMEOUT: int = int(os.getenv("WA_HEAD_TIMEOUT", 5))

# Maximum number of pages the BFS crawler will visit
DEFAULT_MAX_PAGES: int = int(os.getenv("WA_DEFAULT_MAX_PAGES", 20))

# Maximum number of external links to probe for broken-link detection per page
MAX_LINKS_PER_PAGE: int = int(os.getenv("WA_MAX_LINKS_PER_PAGE", 50))

# Maximum number of CSS resources to probe per page
MAX_CSS_PER_PAGE: int = int(os.getenv("WA_MAX_CSS_PER_PAGE", 10))

# Maximum total links to check in the legacy (non-crawl) broken-link method
MAX_LINKS_LEGACY: int = int(os.getenv("WA_MAX_LINKS_LEGACY", 100))

# ── Concurrency ────────────────────────────────────────────────────────────────
# Thread-pool size for concurrent link checks
LINK_CHECK_WORKERS: int = int(os.getenv("WA_LINK_CHECK_WORKERS", 12))

# Thread-pool size for concurrent per-page analysis
PAGE_ANALYSIS_WORKERS: int = int(os.getenv("WA_PAGE_ANALYSIS_WORKERS", 6))

# ── Scoring weights ────────────────────────────────────────────────────────────
# Points deducted per issue (severity-independent simple checks)
SCORE_DEDUCTION_PER_ISSUE: int = int(os.getenv("WA_SCORE_DEDUCTION", 15))

# Security score deduction per issue
SECURITY_DEDUCTION_PER_ISSUE: int = int(os.getenv("WA_SECURITY_DEDUCTION", 15))

# Performance score deduction per issue
PERF_DEDUCTION_PER_ISSUE: int = int(os.getenv("WA_PERF_DEDUCTION", 15))

# SEO score deduction per issue
SEO_DEDUCTION_PER_ISSUE: int = int(os.getenv("WA_SEO_DEDUCTION", 10))

# Accessibility score deduction per issue
ACC_DEDUCTION_PER_ISSUE: int = int(os.getenv("WA_ACC_DEDUCTION", 12))

# Mobile score deduction per issue
MOB_DEDUCTION_PER_ISSUE: int = int(os.getenv("WA_MOB_DEDUCTION", 15))

# Rendering deductions by severity
RENDER_DEDUCTION_HIGH: int = int(os.getenv("WA_RENDER_HIGH", 20))
RENDER_DEDUCTION_MEDIUM: int = int(os.getenv("WA_RENDER_MEDIUM", 10))
RENDER_DEDUCTION_LOW: int = int(os.getenv("WA_RENDER_LOW", 5))

# ── Performance thresholds ─────────────────────────────────────────────────────
# Page load time (seconds) above which a "Slow Load" issue is raised
SLOW_LOAD_THRESHOLD_S: float = float(os.getenv("WA_SLOW_LOAD_S", 3.0))

# Page HTML size (KB) above which a "Large Page" issue is raised
LARGE_PAGE_THRESHOLD_KB: float = float(os.getenv("WA_LARGE_PAGE_KB", 2000.0))

# Number of embedded resources above which "Too Many Resources" is raised
MAX_RESOURCES: int = int(os.getenv("WA_MAX_RESOURCES", 50))

# ── Job queue ──────────────────────────────────────────────────────────────────
# How long (seconds) completed job results stay in memory before being purged
JOB_TTL_SECONDS: int = int(os.getenv("WA_JOB_TTL", 3600))

# ── HTTP Status codes treated as potential false-positives ─────────────────────
# These codes trigger a GET retry before calling a link broken
FALSE_POSITIVE_CODES: frozenset = frozenset({403, 405, 406, 429, 503})

# ── Browser-like headers sent with every outbound request ─────────────────────
BROWSER_HEADERS: dict = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
}
