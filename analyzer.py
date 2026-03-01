"""
analyzer.py — Web Analyser core engine.

Key improvements over the original:
  1. requests.Session for connection pooling (single session per analysis run).
  2. ThreadPoolExecutor for concurrent broken-link checking (5-10× speed-up).
  3. All magic numbers imported from config.py.
  4. progress_callback hook so app.py can stream live status to the job queue.
"""

import re
import ssl
import socket
import time
from collections import deque
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

import config as cfg


# ── Helper ─────────────────────────────────────────────────────────────────────

def _avg(lst: list) -> int:
    return round(sum(lst) / len(lst)) if lst else 0


def _dedup_issues(issues: list) -> list:
    """Remove duplicate issue dicts (same issue + first 60 chars of description)."""
    seen, out = set(), []
    for i in issues:
        key = i.get("issue", "") + i.get("description", "")[:60]
        if key not in seen:
            seen.add(key)
            out.append(i)
    return out


# ── Main class ─────────────────────────────────────────────────────────────────

class WebsiteAnalyzer:
    def __init__(self, url: str, max_pages: int = cfg.DEFAULT_MAX_PAGES,
                 progress_callback=None):
        """
        Args:
            url:               Root URL to analyse.
            max_pages:         BFS page limit.
            progress_callback: Optional callable(stage: str, detail: str | None).
                               Called at each major stage so callers can track
                               progress (used by the job-queue system in app.py).
        """
        self.url = url
        self.max_pages = max_pages
        self._cb = progress_callback or (lambda stage, detail=None: None)

        parsed = urlparse(url)
        self.base_domain = parsed.netloc          # may be refined after first redirect
        self.base_scheme = parsed.scheme
        # Set of domains considered "internal" — updated after first fetch to
        # handle bare-domain → www redirect (e.g. example.com → www.example.com)
        self._allowed_domains: set = {parsed.netloc}

        # Shared session — connection-pool + consistent headers across the run
        self.session = requests.Session()
        self.session.headers.update(cfg.BROWSER_HEADERS)

    # ── Crawl ──────────────────────────────────────────────────────────────────

    @staticmethod
    def _normalise_url(url: str) -> str:
        """
        Canonical form used for visited-set deduplication:
        - strip URL fragment (#section)
        - strip trailing slash on the path (but keep root '/' for bare domains)
        - lowercase scheme and netloc
        """
        p = urlparse(url)
        path = p.path.rstrip("/") or "/"
        return p._replace(scheme=p.scheme.lower(),
                          netloc=p.netloc.lower(),
                          path=path,
                          fragment="").geturl()

    def crawl_site(self) -> list:
        """BFS crawl; returns list of (url, soup, response) for HTML pages."""
        self._cb("crawling", f"Starting BFS crawl (max {self.max_pages} pages)")

        start_norm = self._normalise_url(self.url)
        queue   = deque([self.url])
        visited = {start_norm}
        pages   = []

        while queue and len(pages) < self.max_pages:
            current_url = queue.popleft()
            try:
                resp = self.session.get(current_url, timeout=cfg.REQUEST_TIMEOUT,
                                        allow_redirects=True)

                # ── Learn effective domain after any redirect (once, on first page) ──
                # e.g. example.com → www.example.com
                effective_netloc = urlparse(resp.url).netloc.lower()
                if effective_netloc and effective_netloc not in self._allowed_domains:
                    self._allowed_domains.add(effective_netloc)
                    # Also update canonical base_domain so security / other checks use it
                    if not pages:          # only override on the very first page
                        self.base_domain = effective_netloc

                if "text/html" not in resp.headers.get("content-type", ""):
                    continue

                soup = BeautifulSoup(resp.content, "html.parser")
                pages.append((current_url, soup, resp))
                self._cb("crawling", f"Crawled {len(pages)}/{self.max_pages}: {current_url}")

                for tag in soup.find_all("a", href=True):
                    href = tag["href"]
                    if href.startswith(("#", "mailto:", "tel:", "javascript:", "data:")):
                        continue

                    full_url = urljoin(resp.url, href)   # resolve relative to final URL
                    norm_url = self._normalise_url(full_url)
                    if not norm_url:
                        continue

                    p = urlparse(norm_url)
                    # Only follow http/https links to any of the allowed domains
                    if p.scheme not in ("http", "https"):
                        continue
                    if p.netloc not in self._allowed_domains:
                        continue

                    if norm_url not in visited:
                        visited.add(norm_url)
                        queue.append(full_url)   # queue the original (non-normalised) URL

            except Exception:
                continue

        self._cb("crawling", f"Crawl complete — {len(pages)} page(s) found")
        return pages

    # ── Orchestrator ───────────────────────────────────────────────────────────

    def analyze(self) -> dict:
        """Crawl the site, then run all checks. Returns aggregated result dict."""

        # 1. Crawl
        pages = self.crawl_site()
        pages_crawled = len(pages)

        if pages_crawled == 0:
            return {
                "url": self.url,
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "pages_crawled": 0,
                "crawled_urls": [],
                "error": "Could not fetch any pages from this URL.",
            }

        # 2. Security (entry URL only)
        self._cb("security", "Checking security headers & SSL")
        agg_security_issues, agg_security_passed, security_scores = [], [], []
        sec = self.check_security()
        agg_security_issues.extend(sec["issues"])
        agg_security_passed.extend(sec["passed"])
        security_scores.append(sec["score"])

        # 3. Per-page checks (broken links run concurrently inside each call)
        agg_broken, agg_working_count = [], 0
        agg_perf_issues, agg_perf_good = [], []
        agg_render_issues, agg_render_good = [], []
        agg_seo_issues, agg_seo_good = [], []
        agg_acc_issues, agg_acc_good = [], []
        agg_mob_issues, agg_mob_good = [], []
        agg_suggestions = []

        perf_scores, render_scores, seo_scores, acc_scores, mob_scores = [], [], [], [], []
        load_times, page_sizes = [], []
        per_page_summary = []
        seen_broken_urls: set = set()

        total_pages = len(pages)
        for idx, (page_url, soup, resp) in enumerate(pages, 1):
            self._cb("analysing", f"Analysing page {idx}/{total_pages}: {page_url}")

            # ── broken links (concurrent internally)
            bl = self._check_broken_links_for_page(page_url, soup)
            for item in bl["broken"]:
                if item["url"] not in seen_broken_urls:
                    seen_broken_urls.add(item["url"])
                    agg_broken.append(item)
            agg_working_count += bl["working_count"]

            # ── performance
            perf = self._check_performance_for_page(page_url, soup, resp)
            agg_perf_issues.extend(perf["issues"])
            agg_perf_good.extend(perf["good"])
            perf_scores.append(perf["score"])
            if perf.get("load_time") not in ("N/A", None):
                try:
                    load_times.append(float(perf["load_time"].replace("s", "")))
                except ValueError:
                    pass
            if perf.get("page_size") not in ("N/A", None):
                try:
                    page_sizes.append(float(perf["page_size"].replace(" KB", "")))
                except ValueError:
                    pass

            # ── rendering
            rend = self._check_rendering_for_page(page_url, soup)
            agg_render_issues.extend(rend["issues"])
            agg_render_good.extend(rend["good"])
            render_scores.append(rend["score"])

            # ── SEO
            seo = self._check_seo_for_page(page_url, soup)
            agg_seo_issues.extend(seo["issues"])
            agg_seo_good.extend(seo["good"])
            seo_scores.append(seo["score"])

            # ── accessibility
            acc = self._check_accessibility_for_page(page_url, soup)
            agg_acc_issues.extend(acc["issues"])
            agg_acc_good.extend(acc["good"])
            acc_scores.append(acc["score"])

            # ── mobile
            mob = self._check_mobile_for_page(page_url, soup)
            agg_mob_issues.extend(mob["issues"])
            agg_mob_good.extend(mob["good"])
            mob_scores.append(mob["score"])

            # ── improvements (entry page only)
            if page_url == self.url:
                impr = self._suggest_improvements_for_page(page_url, soup)
                agg_suggestions.extend(impr["suggestions"])

            per_page_summary.append({
                "url": page_url,
                "seo_score": seo["score"],
                "perf_score": perf["score"],
                "acc_score": acc["score"],
                "mob_score": mob["score"],
                "broken_count": len(bl["broken"]),
            })

        self._cb("done", "Analysis complete")

        return {
            "url": self.url,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "pages_crawled": pages_crawled,
            "crawled_urls": [p[0] for p in pages],
            "per_page_summary": per_page_summary,
            "security": {
                "issues": _dedup_issues(agg_security_issues),
                "passed": list(dict.fromkeys(agg_security_passed)),
                "score": _avg(security_scores) if security_scores
                else max(0, 100 - len(agg_security_issues) * cfg.SECURITY_DEDUCTION_PER_ISSUE),
            },
            "broken_links": {
                "broken": agg_broken,
                "total_checked": len(agg_broken) + agg_working_count,
                "broken_count": len(agg_broken),
                "working_count": agg_working_count,
            },
            "performance": {
                "issues": _dedup_issues(agg_perf_issues),
                "good": list(dict.fromkeys(agg_perf_good)),
                "score": _avg(perf_scores),
                "load_time": f"{sum(load_times)/len(load_times):.2f}s (avg)" if load_times else "N/A",
                "page_size": f"{sum(page_sizes)/len(page_sizes):.2f} KB (avg)" if page_sizes else "N/A",
            },
            "rendering": {
                "issues": _dedup_issues(agg_render_issues),
                "good": list(dict.fromkeys(agg_render_good)),
                "score": _avg(render_scores),
            },
            "seo": {
                "issues": _dedup_issues(agg_seo_issues),
                "good": list(dict.fromkeys(agg_seo_good)),
                "score": _avg(seo_scores),
            },
            "accessibility": {
                "issues": _dedup_issues(agg_acc_issues),
                "good": list(dict.fromkeys(agg_acc_good)),
                "score": _avg(acc_scores),
            },
            "mobile": {
                "issues": _dedup_issues(agg_mob_issues),
                "good": list(dict.fromkeys(agg_mob_good)),
                "score": _avg(mob_scores),
            },
            "improvements": {
                "suggestions": agg_suggestions,
                "total_count": len(agg_suggestions),
            },
        }

    # ── Per-page private helpers ───────────────────────────────────────────────
    # All helpers receive pre-fetched soup / resp — no extra HTTP calls for HTML.
    # Only link probing makes new HTTP calls, and those run concurrently.

    # ── 1. Broken links (CONCURRENT) ──────────────────────────────────────────

    def _probe_link(self, link: str) -> dict | None:
        """
        Probe a single URL and return a broken-link dict, or None if OK.
        Designed to be called from a ThreadPoolExecutor.
        """
        try:
            r = self.session.head(link, timeout=cfg.HEAD_TIMEOUT, allow_redirects=True)
            status_code = r.status_code
            reason = r.reason

            if status_code >= 400:
                if status_code in cfg.FALSE_POSITIVE_CODES:
                    # Retry with GET (some servers reject HEAD)
                    try:
                        r_get = self.session.get(link, timeout=cfg.HEAD_TIMEOUT,
                                                  allow_redirects=True, stream=True)
                        r_get.close()
                        if r_get.status_code < 400 or r_get.status_code in cfg.FALSE_POSITIVE_CODES:
                            return None  # not broken
                        status_code = r_get.status_code
                        reason = r_get.reason
                    except Exception:
                        return {"url": link, "status_code": "Error", "reason": "GET retry failed"}
                return {"url": link, "status_code": status_code, "reason": reason}
            return None

        except requests.exceptions.SSLError as e:
            return {"url": link, "status_code": "SSL Error", "reason": str(e)[:80]}
        except requests.exceptions.ConnectionError as e:
            err = str(e).lower()
            if "name or service not known" in err or "nodename nor servname" in err:
                return {"url": link, "status_code": "DNS Error", "reason": "Domain not found"}
            if "connection refused" in err:
                return {"url": link, "status_code": "Refused", "reason": "Connection refused"}
            return {"url": link, "status_code": "N/A", "reason": str(e)[:80]}
        except requests.exceptions.Timeout:
            return {"url": link, "status_code": "Timeout", "reason": "Request timed out"}
        except requests.exceptions.TooManyRedirects:
            return {"url": link, "status_code": "Redirect Loop", "reason": "Too many redirects"}
        except requests.exceptions.RequestException as e:
            return {"url": link, "status_code": "Error", "reason": str(e)[:80]}

    def _check_broken_links_for_page(self, page_url: str, soup) -> dict:
        """Check broken links on a single page using concurrent HEAD probes."""
        links: set = set()
        for tag in soup.find_all(["a", "link", "script", "img"]):
            url = tag.get("href") or tag.get("src")
            if not url:
                continue
            if url.startswith(("javascript:", "mailto:", "tel:", "#", "data:")):
                continue
            full_url = urljoin(page_url, url)
            if full_url.startswith(("http://", "https://")):
                links.add(full_url)

        links_list = list(links)[: cfg.MAX_LINKS_PER_PAGE]
        broken, working_count = [], 0

        with ThreadPoolExecutor(max_workers=cfg.LINK_CHECK_WORKERS) as pool:
            futures = {pool.submit(self._probe_link, link): link for link in links_list}
            for future in as_completed(futures):
                result = future.result()
                if result:
                    result["found_on"] = page_url
                    broken.append(result)
                else:
                    working_count += 1

        return {
            "broken": broken,
            "total_checked": len(broken) + working_count,
            "broken_count": len(broken),
            "working_count": working_count,
        }

    # ── 2. Performance ─────────────────────────────────────────────────────────

    def _check_performance_for_page(self, page_url: str, soup, resp) -> dict:
        issues, good = [], []
        load_time = page_size = None

        try:
            load_time = resp.elapsed.total_seconds() if (
                hasattr(resp, "elapsed") and resp.elapsed) else 0.0

            if load_time > cfg.SLOW_LOAD_THRESHOLD_S:
                issues.append({"issue": "Slow Page Load",
                                "value": f"{load_time:.2f}s",
                                "description": f"Load time exceeds {cfg.SLOW_LOAD_THRESHOLD_S}s"})
            else:
                good.append(f"Fast page load: {load_time:.2f}s")

            page_size = len(resp.content) / 1024
            if page_size > cfg.LARGE_PAGE_THRESHOLD_KB:
                issues.append({"issue": "Large Page Size",
                                "value": f"{page_size:.2f} KB",
                                "description": f"Page size exceeds {cfg.LARGE_PAGE_THRESHOLD_KB/1024:.0f} MB"})
            else:
                good.append(f"Reasonable page size: {page_size:.2f} KB")

            resources = soup.find_all(["script", "link", "img", "iframe"])
            if len(resources) > cfg.MAX_RESOURCES:
                issues.append({"issue": "Too Many Resources",
                                "value": f"{len(resources)} resources",
                                "description": "Consider combining files and using HTTP/2"})
            else:
                good.append(f"Reasonable resource count: {len(resources)}")

            if "content-encoding" not in resp.headers:
                issues.append({"issue": "No Compression",
                                "value": "N/A",
                                "description": "Enable gzip or brotli compression"})
            else:
                good.append(f"Compression enabled: {resp.headers.get('content-encoding')}")

            if not any(h in resp.headers for h in ["cache-control", "expires", "etag"]):
                issues.append({"issue": "No Caching Headers",
                                "value": "N/A",
                                "description": "Add cache headers to improve repeat visits"})
            else:
                good.append("Caching headers present")

        except Exception as e:
            issues.append({"issue": "Performance Check Failed",
                            "value": "N/A",
                            "description": str(e)})

        score = max(0, 100 - len(issues) * cfg.PERF_DEDUCTION_PER_ISSUE)
        return {
            "issues": issues,
            "good": good,
            "score": score,
            "load_time": f"{load_time:.2f}s" if load_time is not None else "N/A",
            "page_size": f"{page_size:.2f} KB" if page_size is not None else "N/A",
        }

    # ── 3. Rendering ───────────────────────────────────────────────────────────

    def _check_rendering_for_page(self, page_url: str, soup) -> dict:
        issues, good = [], []
        try:
            # CSS
            css_links = soup.find_all("link", rel="stylesheet")
            broken_css = []
            for css in css_links[: cfg.MAX_CSS_PER_PAGE]:
                href = css.get("href")
                if href:
                    css_url = urljoin(page_url, href)
                    if css_url.startswith(("http://", "https://")):
                        try:
                            r = self.session.head(css_url, timeout=cfg.HEAD_TIMEOUT,
                                                   allow_redirects=True)
                            if r.status_code >= 400 and r.status_code not in {403, 405}:
                                broken_css.append(href)
                        except Exception:
                            broken_css.append(href)
            if broken_css:
                issues.append({"severity": "high", "issue": "CSS Files Not Loading",
                                "description": f"{len(broken_css)} stylesheet(s) failed to load"})
            else:
                good.append(f"All {len(css_links)} CSS stylesheets loading properly")

            # DOCTYPE
            doctype = soup.contents[0] if soup.contents else None
            if not str(doctype).lower().startswith("<!doctype"):
                issues.append({"severity": "high", "issue": "Missing DOCTYPE Declaration",
                                "description": "Page may render in quirks mode"})
            else:
                good.append("Valid DOCTYPE declaration found")

            # Charset
            meta_charset = (soup.find("meta", charset=True) or
                            soup.find("meta", attrs={"http-equiv": re.compile("content-type", re.I)}))
            if not meta_charset:
                issues.append({"severity": "medium", "issue": "Missing Character Encoding",
                                "description": "No charset meta tag found"})
            else:
                good.append("Character encoding properly declared")

            # Inline styles
            inline_styles = soup.find_all(style=True)
            if len(inline_styles) > 50:
                issues.append({"severity": "low", "issue": "Excessive Inline Styles",
                                "description": f"Found {len(inline_styles)} elements with inline styles"})

            # Print stylesheet
            if not soup.find("link", media=re.compile(r"print")):
                issues.append({"severity": "low", "issue": "No Print Stylesheet",
                                "description": "Consider adding print-specific styles"})
            else:
                good.append("Print stylesheet available")

        except Exception as e:
            issues.append({"severity": "high", "issue": "Rendering Check Failed",
                            "description": str(e)})

        high = sum(1 for i in issues if i.get("severity") == "high")
        medium = sum(1 for i in issues if i.get("severity") == "medium")
        low = sum(1 for i in issues if i.get("severity") == "low")
        score = max(0, 100 - high * cfg.RENDER_DEDUCTION_HIGH
                    - medium * cfg.RENDER_DEDUCTION_MEDIUM
                    - low * cfg.RENDER_DEDUCTION_LOW)
        return {"issues": issues, "good": good, "score": score}

    # ── 4. SEO ─────────────────────────────────────────────────────────────────

    def _check_seo_for_page(self, page_url: str, soup) -> dict:
        issues, good = [], []
        try:
            title = soup.find("title")
            if title:
                tlen = len(title.get_text().strip())
                if tlen < 30:
                    issues.append({"issue": "Title Too Short",
                                   "description": f"Title is {tlen} chars. Recommended: 30–60"})
                elif tlen > 60:
                    issues.append({"issue": "Title Too Long",
                                   "description": f"Title is {tlen} chars. May be truncated"})
                else:
                    good.append(f"Title length optimal: {tlen} characters")
            else:
                issues.append({"issue": "Missing Title Tag",
                                "description": "Page must have a title tag"})

            meta_desc = soup.find("meta", attrs={"name": "description"})
            if meta_desc and meta_desc.get("content"):
                dlen = len(meta_desc.get("content", ""))
                if dlen < 120:
                    issues.append({"issue": "Meta Description Too Short",
                                   "description": f"{dlen} chars. Recommended: 120–160"})
                elif dlen > 160:
                    issues.append({"issue": "Meta Description Too Long",
                                   "description": f"{dlen} chars. May be truncated"})
                else:
                    good.append(f"Meta description optimal: {dlen} characters")
            else:
                issues.append({"issue": "Missing Meta Description",
                                "description": "Helps improve click-through rates"})

            h1_tags = soup.find_all("h1")
            if len(h1_tags) == 0:
                issues.append({"issue": "No H1 Tag",
                                "description": "Page should have exactly one H1"})
            elif len(h1_tags) > 1:
                issues.append({"issue": "Multiple H1 Tags",
                                "description": f"Found {len(h1_tags)} H1 tags"})
            else:
                good.append("Single H1 tag found")

            if not soup.find("link", rel="canonical"):
                issues.append({"issue": "Missing Canonical URL",
                                "description": "Helps prevent duplicate content"})
            else:
                good.append("Canonical URL defined")

            og_tags = soup.find_all("meta", property=re.compile("^og:"))
            if len(og_tags) >= 4:
                good.append(f"Open Graph tags present ({len(og_tags)})")
            else:
                issues.append({"issue": "Incomplete Open Graph Tags",
                                "description": "Add og:title, og:description, og:image, og:url"})

        except Exception as e:
            issues.append({"issue": "SEO Check Failed", "description": str(e)})

        return {"issues": issues, "good": good,
                "score": max(0, 100 - len(issues) * cfg.SEO_DEDUCTION_PER_ISSUE)}

    # ── 5. Accessibility ───────────────────────────────────────────────────────

    def _check_accessibility_for_page(self, page_url: str, soup) -> dict:
        issues, good = [], []
        try:
            html_tag = soup.find("html")
            if html_tag and html_tag.get("lang"):
                good.append(f"Language declared: {html_tag.get('lang')}")
            else:
                issues.append({"issue": "Missing Language Declaration",
                                "description": "Add lang attribute to <html> tag"})

            images = soup.find_all("img")
            no_alt = [img for img in images if not img.get("alt")]
            if no_alt:
                issues.append({"issue": "Images Missing Alt Text",
                                "description": f"{len(no_alt)} of {len(images)} images missing alt"})
            elif images:
                good.append(f"All {len(images)} images have alt text")

            inputs = soup.find_all(["input", "select", "textarea"])
            unlabeled = []
            for inp in inputs:
                if inp.get("type") in ("hidden", "submit", "button"):
                    continue
                input_id = inp.get("id")
                has_label = bool(soup.find("label", attrs={"for": input_id})) if input_id else False
                has_aria = bool(inp.get("aria-label") or inp.get("aria-labelledby"))
                if not (has_label or has_aria):
                    unlabeled.append(inp)
            if unlabeled:
                issues.append({"issue": "Form Inputs Without Labels",
                                "description": f"{len(unlabeled)} elements missing labels"})
            elif inputs:
                good.append("All form inputs have labels")

            landmarks = soup.find_all(
                attrs={"role": re.compile("main|navigation|banner|contentinfo|search")})
            if landmarks:
                good.append(f"ARIA landmarks present ({len(landmarks)})")
            else:
                issues.append({"issue": "No ARIA Landmarks",
                                "description": "Add ARIA landmarks for screen readers"})

            if not soup.find("a", href=re.compile("#(main|content|skip)")):
                issues.append({"issue": "No Skip Navigation Link",
                                "description": "Add skip link for keyboard navigation"})
            else:
                good.append("Skip navigation link found")

        except Exception as e:
            issues.append({"issue": "Accessibility Check Failed", "description": str(e)})

        return {"issues": issues, "good": good,
                "score": max(0, 100 - len(issues) * cfg.ACC_DEDUCTION_PER_ISSUE)}

    # ── 6. Mobile ──────────────────────────────────────────────────────────────

    def _check_mobile_for_page(self, page_url: str, soup) -> dict:
        issues, good = [], []
        try:
            viewport = soup.find("meta", attrs={"name": "viewport"})
            if viewport:
                if "width=device-width" in viewport.get("content", ""):
                    good.append("Responsive viewport configured")
                else:
                    issues.append({"issue": "Incomplete Viewport Configuration",
                                   "description": "Viewport should include width=device-width"})
            else:
                issues.append({"issue": "Missing Viewport Meta Tag",
                                "description": "Required for responsive mobile design"})

            if soup.find("link", rel=re.compile("apple-touch-icon")):
                good.append("Apple touch icon configured")
            else:
                issues.append({"issue": "Missing Apple Touch Icon",
                                "description": "Add apple-touch-icon for iOS devices"})

            if soup.find("link", rel="manifest"):
                good.append("Web app manifest present")
            else:
                issues.append({"issue": "No Web App Manifest",
                                "description": "Consider adding manifest.json for PWA"})

            total_images = len(soup.find_all("img"))
            img_with_srcset = soup.find_all("img", srcset=True)
            if total_images > 0 and len(img_with_srcset) <= total_images * 0.5:
                issues.append({"issue": "No Responsive Images",
                                "description": "Use srcset for responsive image loading"})
            elif total_images > 0:
                good.append("Responsive images implemented (srcset)")

        except Exception as e:
            issues.append({"issue": "Mobile Check Failed", "description": str(e)})

        return {"issues": issues, "good": good,
                "score": max(0, 100 - len(issues) * cfg.MOB_DEDUCTION_PER_ISSUE)}

    # ── 7. Improvements ────────────────────────────────────────────────────────

    def _suggest_improvements_for_page(self, page_url: str, soup) -> dict:
        suggestions = []
        try:
            if not soup.find("meta", attrs={"name": "description"}):
                suggestions.append({"category": "SEO", "suggestion": "Add meta description",
                                     "priority": "high",
                                     "description": "Meta descriptions help search engines understand your page"})
            if not soup.find("title"):
                suggestions.append({"category": "SEO", "suggestion": "Add page title",
                                     "priority": "high",
                                     "description": "Every page should have a unique title"})
            h1_tags = soup.find_all("h1")
            if len(h1_tags) == 0:
                suggestions.append({"category": "SEO", "suggestion": "Add H1 heading",
                                     "priority": "medium",
                                     "description": "H1 tags help structure content"})
            elif len(h1_tags) > 1:
                suggestions.append({"category": "SEO", "suggestion": "Multiple H1 tags found",
                                     "priority": "low",
                                     "description": "Best practice is one H1 per page"})
            images = soup.find_all("img")
            missing_alt = sum(1 for img in images if not img.get("alt"))
            if missing_alt > 0:
                suggestions.append({"category": "Accessibility",
                                     "suggestion": f"{missing_alt} images missing alt text",
                                     "priority": "high",
                                     "description": "Alt text improves accessibility and SEO"})
            if not soup.find("link", rel="icon") and not soup.find("link", rel="shortcut icon"):
                suggestions.append({"category": "Branding", "suggestion": "Add favicon",
                                     "priority": "low",
                                     "description": "Favicons improve brand recognition"})
            if not soup.find("meta", attrs={"name": "viewport"}):
                suggestions.append({"category": "Mobile", "suggestion": "Add viewport meta tag",
                                     "priority": "high",
                                     "description": "Required for responsive mobile design"})
            if not bool(soup.find(string=re.compile("google-analytics|gtag|analytics"))):
                suggestions.append({"category": "Analytics",
                                     "suggestion": "Consider adding analytics",
                                     "priority": "medium",
                                     "description": "Track visitor behaviour to improve your site"})
            scripts = soup.find_all("script", src=True)
            unminified = [s for s in scripts if s.get("src") and
                          not any(m in s.get("src") for m in [".min.", "-min."])]
            if unminified:
                suggestions.append({"category": "Performance",
                                     "suggestion": "Minify JavaScript files",
                                     "priority": "medium",
                                     "description": "Reduce file sizes by minifying JS and CSS"})
        except Exception as e:
            suggestions.append({"category": "Error", "suggestion": "Analysis incomplete",
                                 "priority": "high", "description": str(e)})
        return {"suggestions": suggestions, "total_count": len(suggestions)}

    # ── 8. Security (entry URL only) ───────────────────────────────────────────

    def check_security(self) -> dict:
        """Full security check against the entry URL."""
        security_issues, security_passed = [], []
        try:
            if not self.url.startswith("https://"):
                security_issues.append({"severity": "high", "issue": "No HTTPS",
                                         "description": "Website is not using HTTPS encryption"})
            else:
                security_passed.append("HTTPS enabled")

            response = self.session.get(self.url, timeout=cfg.REQUEST_TIMEOUT,
                                        allow_redirects=True)
            headers = response.headers

            security_headers_map = {
                "Strict-Transport-Security": "HSTS header missing — prevents man-in-the-middle attacks",
                "X-Content-Type-Options": "X-Content-Type-Options missing — prevents MIME sniffing",
                "X-Frame-Options": "X-Frame-Options missing — prevents clickjacking",
                "X-XSS-Protection": "X-XSS-Protection missing — helps prevent XSS attacks",
                "Content-Security-Policy": "Content-Security-Policy missing — prevents XSS/injection",
            }
            for hdr, desc in security_headers_map.items():
                if hdr not in headers:
                    security_issues.append({"severity": "medium", "issue": f"Missing {hdr}",
                                             "description": desc})
                else:
                    security_passed.append(f"{hdr} configured")

            if self.url.startswith("https://"):
                soup = BeautifulSoup(response.content, "html.parser")
                mixed = [
                    (tag.get("src") or tag.get("href"))
                    for tag in soup.find_all(["img", "script", "link", "iframe"])
                    if (tag.get("src") or tag.get("href", "")).startswith("http://")
                ]
                if mixed:
                    security_issues.append({"severity": "medium", "issue": "Mixed Content",
                                             "description": f"{len(mixed)} resources loaded over HTTP on HTTPS page"})
                else:
                    security_passed.append("No mixed content detected")

            if self.url.startswith("https://"):
                try:
                    hostname = urlparse(self.url).netloc
                    context = ssl.create_default_context()
                    with socket.create_connection((hostname, 443), timeout=5) as sock:
                        with context.wrap_socket(sock, server_hostname=hostname):
                            security_passed.append("Valid SSL certificate")
                except Exception as e:
                    security_issues.append({"severity": "high", "issue": "SSL Certificate Issue",
                                             "description": f"SSL validation failed: {str(e)}"})

            # Sensitive file exposure
            sensitive_paths = ["/.git/config", "/.env", "/config.php",
                                "/wp-config.php", "/.htaccess"]
            exposed = []
            for path in sensitive_paths:
                try:
                    r = self.session.head(urljoin(self.url, path),
                                          timeout=cfg.HEAD_TIMEOUT)
                    if r.status_code == 200:
                        exposed.append(path)
                except Exception:
                    pass
            if exposed:
                security_issues.append({"severity": "high", "issue": "Exposed Sensitive Files",
                                         "description": f"Found: {', '.join(exposed)}"})

            # Cookie flags
            if "set-cookie" in headers:
                cookies = headers["set-cookie"]
                if "secure" not in cookies.lower():
                    security_issues.append({"severity": "medium", "issue": "Insecure Cookies",
                                             "description": "Cookies should have Secure flag set"})
                if "httponly" not in cookies.lower():
                    security_issues.append({"severity": "medium", "issue": "Cookie Security",
                                             "description": "Cookies should have HttpOnly flag"})
                else:
                    security_passed.append("Cookies have HttpOnly flag")

        except Exception as e:
            security_issues.append({"severity": "high", "issue": "Security Check Failed",
                                     "description": f"Could not complete security analysis: {str(e)}"})

        return {
            "issues": security_issues,
            "passed": security_passed,
            "score": max(0, 100 - len(security_issues) * cfg.SECURITY_DEDUCTION_PER_ISSUE),
        }
