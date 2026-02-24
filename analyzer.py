import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import time
import ssl
import socket
from datetime import datetime
import re
from collections import deque

class WebsiteAnalyzer:
    def __init__(self, url, max_pages=50):
        self.url = url
        self.max_pages = max_pages
        self.visited_urls = set()
        self.broken_links = []
        self.all_links = []
        parsed = urlparse(url)
        self.base_domain = parsed.netloc
        self.base_scheme = parsed.scheme
        
    def crawl_site(self):
        """BFS crawl to discover all internal sub-pages up to max_pages.
        Returns a list of (url, soup) tuples for pages successfully fetched."""
        browser_headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
        }

        queue = deque([self.url])
        visited = set([self.url])
        pages = []  # list of (url, soup, response)

        while queue and len(pages) < self.max_pages:
            current_url = queue.popleft()
            try:
                resp = requests.get(current_url, timeout=10, headers=browser_headers, allow_redirects=True)
                # Only process HTML pages
                content_type = resp.headers.get('content-type', '')
                if 'text/html' not in content_type:
                    continue
                soup = BeautifulSoup(resp.content, 'html.parser')
                pages.append((current_url, soup, resp))
                self.visited_urls.add(current_url)

                # Discover internal links from this page
                for tag in soup.find_all('a', href=True):
                    href = tag['href']
                    # Skip fragments, mailto, tel, javascript
                    if href.startswith(('#', 'mailto:', 'tel:', 'javascript:', 'data:')):
                        continue
                    full_url = urljoin(current_url, href)
                    # Normalise: strip fragment
                    full_url = full_url.split('#')[0].rstrip('/')
                    if not full_url:
                        continue
                    parsed = urlparse(full_url)
                    # Only follow same-domain http/https links
                    if parsed.netloc != self.base_domain:
                        continue
                    if parsed.scheme not in ('http', 'https'):
                        continue
                    if full_url not in visited:
                        visited.add(full_url)
                        queue.append(full_url)
            except Exception:
                continue

        return pages

    def analyze(self):
        """Crawl the site then run all analysis checks across every page."""
        # ── 1. Crawl ──────────────────────────────────────────────────────────
        pages = self.crawl_site()
        pages_crawled = len(pages)

        if pages_crawled == 0:
            return {
                'url': self.url,
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'pages_crawled': 0,
                'crawled_urls': [],
                'error': 'Could not fetch any pages from this URL.'
            }

        # ── 2. Per-page checks ─────────────────────────────────────────────────
        # We aggregate issues/good lists and average scores
        agg_security_issues, agg_security_passed = [], []
        agg_broken, agg_working_count = [], 0
        agg_perf_issues, agg_perf_good = [], []
        agg_render_issues, agg_render_good = [], []
        agg_seo_issues, agg_seo_good = [], []
        agg_acc_issues, agg_acc_good = [], []
        agg_mob_issues, agg_mob_good = [], []
        agg_suggestions = []

        security_scores, perf_scores, render_scores, seo_scores, acc_scores, mob_scores = [], [], [], [], [], []
        load_times, page_sizes = [], []
        per_page_summary = []

        seen_broken_urls = set()

        for page_url, soup, resp in pages:
            # ── security (only run on entry URL to avoid N×SSL checks)
            if page_url == self.url:
                sec = self.check_security()
                agg_security_issues.extend(sec['issues'])
                agg_security_passed.extend(sec['passed'])
                security_scores.append(sec['score'])

            # ── broken links
            bl = self._check_broken_links_for_page(page_url, soup)
            for item in bl['broken']:
                if item['url'] not in seen_broken_urls:
                    seen_broken_urls.add(item['url'])
                    agg_broken.append(item)
            agg_working_count += bl['working_count']

            # ── performance
            perf = self._check_performance_for_page(page_url, soup, resp)
            agg_perf_issues.extend(perf['issues'])
            agg_perf_good.extend(perf['good'])
            perf_scores.append(perf['score'])
            if perf.get('load_time') not in ('N/A', None):
                load_times.append(float(perf['load_time'].replace('s', '')))
            if perf.get('page_size') not in ('N/A', None):
                page_sizes.append(float(perf['page_size'].replace(' KB', '')))

            # ── rendering
            rend = self._check_rendering_for_page(page_url, soup)
            agg_render_issues.extend(rend['issues'])
            agg_render_good.extend(rend['good'])
            render_scores.append(rend['score'])

            # ── seo
            seo = self._check_seo_for_page(page_url, soup)
            agg_seo_issues.extend(seo['issues'])
            agg_seo_good.extend(seo['good'])
            seo_scores.append(seo['score'])

            # ── accessibility
            acc = self._check_accessibility_for_page(page_url, soup)
            agg_acc_issues.extend(acc['issues'])
            agg_acc_good.extend(acc['good'])
            acc_scores.append(acc['score'])

            # ── mobile
            mob = self._check_mobile_for_page(page_url, soup)
            agg_mob_issues.extend(mob['issues'])
            agg_mob_good.extend(mob['good'])
            mob_scores.append(mob['score'])

            # ── improvements (entry page only to avoid noise)
            if page_url == self.url:
                impr = self._suggest_improvements_for_page(page_url, soup)
                agg_suggestions.extend(impr['suggestions'])

            # ── per-page row
            per_page_summary.append({
                'url': page_url,
                'seo_score': seo['score'],
                'perf_score': perf['score'],
                'acc_score': acc['score'],
                'mob_score': mob['score'],
                'broken_count': len(bl['broken']),
            })

        def avg(lst): return round(sum(lst) / len(lst)) if lst else 0
        def dedup_issues(issues):
            seen, out = set(), []
            for i in issues:
                key = i.get('issue', '') + i.get('description', '')[:60]
                if key not in seen:
                    seen.add(key)
                    out.append(i)
            return out

        results = {
            'url': self.url,
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'pages_crawled': pages_crawled,
            'crawled_urls': [p[0] for p in pages],
            'per_page_summary': per_page_summary,
            'security': {
                'issues': dedup_issues(agg_security_issues),
                'passed': list(dict.fromkeys(agg_security_passed)),
                'score': avg(security_scores) if security_scores else max(0, 100 - len(agg_security_issues) * 15)
            },
            'broken_links': {
                'broken': agg_broken,
                'total_checked': len(agg_broken) + agg_working_count,
                'broken_count': len(agg_broken),
                'working_count': agg_working_count
            },
            'performance': {
                'issues': dedup_issues(agg_perf_issues),
                'good': list(dict.fromkeys(agg_perf_good)),
                'score': avg(perf_scores),
                'load_time': f'{sum(load_times)/len(load_times):.2f}s (avg)' if load_times else 'N/A',
                'page_size': f'{sum(page_sizes)/len(page_sizes):.2f} KB (avg)' if page_sizes else 'N/A'
            },
            'rendering': {
                'issues': dedup_issues(agg_render_issues),
                'good': list(dict.fromkeys(agg_render_good)),
                'score': avg(render_scores)
            },
            'seo': {
                'issues': dedup_issues(agg_seo_issues),
                'good': list(dict.fromkeys(agg_seo_good)),
                'score': avg(seo_scores)
            },
            'accessibility': {
                'issues': dedup_issues(agg_acc_issues),
                'good': list(dict.fromkeys(agg_acc_good)),
                'score': avg(acc_scores)
            },
            'mobile': {
                'issues': dedup_issues(agg_mob_issues),
                'good': list(dict.fromkeys(agg_mob_good)),
                'score': avg(mob_scores)
            },
            'improvements': {
                'suggestions': agg_suggestions,
                'total_count': len(agg_suggestions)
            }
        }
        return results

    # ──────────────────────────────────────────────────────────────────────────
    # Private per-page helpers (accept pre-fetched soup so no extra HTTP calls)
    # ──────────────────────────────────────────────────────────────────────────

    def _check_broken_links_for_page(self, page_url, soup):
        """Check broken links found on a single already-fetched page."""
        broken, working = [], []
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }
        false_positive_codes = {403, 405, 406, 429, 503}

        links = set()
        for tag in soup.find_all(['a', 'link', 'script', 'img']):
            url = tag.get('href') or tag.get('src')
            if url:
                if url.startswith(('javascript:', 'mailto:', 'tel:', '#', 'data:')):
                    continue
                full_url = urljoin(page_url, url)
                if full_url.startswith(('http://', 'https://')):
                    links.add(full_url)

        links = list(links)[:50]  # cap per page

        for link in links:
            is_broken = False
            status_code = None
            reason = None
            try:
                r = requests.head(link, timeout=8, allow_redirects=True, headers=headers)
                status_code = r.status_code
                reason = r.reason
                if status_code >= 400:
                    if status_code in false_positive_codes:
                        try:
                            r_get = requests.get(link, timeout=8, allow_redirects=True, headers=headers, stream=True)
                            status_code = r_get.status_code
                            reason = r_get.reason
                            r_get.close()
                            is_broken = status_code >= 400 and status_code not in false_positive_codes
                        except:
                            is_broken = True
                    else:
                        is_broken = True
            except requests.exceptions.SSLError as e:
                is_broken = True; status_code = 'SSL Error'; reason = str(e)[:80]
            except requests.exceptions.ConnectionError as e:
                err = str(e).lower()
                if 'name or service not known' in err or 'nodename nor servname' in err:
                    is_broken = True; status_code = 'DNS Error'; reason = 'Domain not found'
                elif 'connection refused' in err:
                    is_broken = True; status_code = 'Refused'; reason = 'Connection refused'
                else:
                    is_broken = True; status_code = 'N/A'; reason = str(e)[:80]
            except requests.exceptions.Timeout:
                is_broken = True; status_code = 'Timeout'; reason = 'Request timed out'
            except requests.exceptions.TooManyRedirects:
                is_broken = True; status_code = 'Redirect Loop'; reason = 'Too many redirects'
            except requests.exceptions.RequestException as e:
                is_broken = True; status_code = 'Error'; reason = str(e)[:80]

            if is_broken:
                broken.append({'url': link, 'status_code': status_code, 'reason': reason, 'found_on': page_url})
            else:
                working.append(link)

        return {
            'broken': broken,
            'total_checked': len(broken) + len(working),
            'broken_count': len(broken),
            'working_count': len(working)
        }

    def _check_performance_for_page(self, page_url, soup, resp):
        """Check performance metrics using pre-fetched response."""
        performance_issues = []
        performance_good = []
        load_time = None
        page_size = None

        try:
            # Approximate load time from response elapsed
            load_time = resp.elapsed.total_seconds() if hasattr(resp, 'elapsed') and resp.elapsed else 0.0
            if load_time > 3:
                performance_issues.append({'issue': 'Slow Page Load', 'value': f'{load_time:.2f}s', 'description': 'Page load time exceeds 3 seconds'})
            else:
                performance_good.append(f'Fast page load: {load_time:.2f}s')

            page_size = len(resp.content) / 1024
            if page_size > 2000:
                performance_issues.append({'issue': 'Large Page Size', 'value': f'{page_size:.2f} KB', 'description': 'Page size exceeds 2MB'})
            else:
                performance_good.append(f'Reasonable page size: {page_size:.2f} KB')

            resources = soup.find_all(['script', 'link', 'img', 'iframe'])
            if len(resources) > 50:
                performance_issues.append({'issue': 'Too Many Resources', 'value': f'{len(resources)} resources', 'description': 'Consider combining files'})
            else:
                performance_good.append(f'Reasonable resource count: {len(resources)}')

            if 'content-encoding' not in resp.headers:
                performance_issues.append({'issue': 'No Compression', 'value': 'N/A', 'description': 'Enable gzip or brotli compression'})
            else:
                performance_good.append(f"Compression enabled: {resp.headers.get('content-encoding')}")

            cache_headers = ['cache-control', 'expires', 'etag']
            if not any(h in resp.headers for h in cache_headers):
                performance_issues.append({'issue': 'No Caching Headers', 'value': 'N/A', 'description': 'Add cache headers'})
            else:
                performance_good.append('Caching headers present')

        except Exception as e:
            performance_issues.append({'issue': 'Performance Check Failed', 'value': 'N/A', 'description': str(e)})

        score = max(0, 100 - len(performance_issues) * 15)
        return {
            'issues': performance_issues,
            'good': performance_good,
            'score': score,
            'load_time': f'{load_time:.2f}s' if load_time is not None else 'N/A',
            'page_size': f'{page_size:.2f} KB' if page_size is not None else 'N/A'
        }

    def _check_rendering_for_page(self, page_url, soup):
        """Check rendering quality using pre-fetched soup."""
        rendering_issues = []
        rendering_good = []
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        }
        try:
            css_links = soup.find_all('link', rel='stylesheet')
            broken_css = []
            for css in css_links[:10]:
                href = css.get('href')
                if href:
                    css_url = urljoin(page_url, href)
                    if css_url.startswith(('http://', 'https://')):
                        try:
                            r = requests.head(css_url, timeout=5, headers=headers, allow_redirects=True)
                            if r.status_code >= 400 and r.status_code not in {403, 405}:
                                broken_css.append(href)
                        except:
                            broken_css.append(href)
            if broken_css:
                rendering_issues.append({'severity': 'high', 'issue': 'CSS Files Not Loading', 'description': f'{len(broken_css)} stylesheet(s) failed to load'})
            else:
                rendering_good.append(f'All {len(css_links)} CSS stylesheets loading properly')

            doctype = soup.contents[0] if soup.contents else None
            if not str(doctype).lower().startswith('<!doctype'):
                rendering_issues.append({'severity': 'high', 'issue': 'Missing DOCTYPE Declaration', 'description': 'Page may render in quirks mode'})
            else:
                rendering_good.append('Valid DOCTYPE declaration found')

            meta_charset = soup.find('meta', charset=True) or soup.find('meta', attrs={'http-equiv': re.compile('content-type', re.I)})
            if not meta_charset:
                rendering_issues.append({'severity': 'medium', 'issue': 'Missing Character Encoding', 'description': 'No charset meta tag found'})
            else:
                rendering_good.append('Character encoding properly declared')

            inline_styles = soup.find_all(style=True)
            if len(inline_styles) > 50:
                rendering_issues.append({'severity': 'low', 'issue': 'Excessive Inline Styles', 'description': f'Found {len(inline_styles)} elements with inline styles'})

            print_css = soup.find('link', media=re.compile(r'print'))
            if not print_css:
                rendering_issues.append({'severity': 'low', 'issue': 'No Print Stylesheet', 'description': 'Consider adding print-specific styles'})
            else:
                rendering_good.append('Print stylesheet available')

        except Exception as e:
            rendering_issues.append({'severity': 'high', 'issue': 'Rendering Check Failed', 'description': str(e)})

        high_issues = sum(1 for i in rendering_issues if i.get('severity') == 'high')
        medium_issues = sum(1 for i in rendering_issues if i.get('severity') == 'medium')
        low_issues = sum(1 for i in rendering_issues if i.get('severity') == 'low')
        score = max(0, 100 - (high_issues * 20) - (medium_issues * 10) - (low_issues * 5))
        return {'issues': rendering_issues, 'good': rendering_good, 'score': score}

    def _check_seo_for_page(self, page_url, soup):
        """Check SEO using pre-fetched soup."""
        seo_issues = []
        seo_good = []
        try:
            title = soup.find('title')
            if title:
                tlen = len(title.get_text().strip())
                if tlen < 30:
                    seo_issues.append({'issue': 'Title Too Short', 'description': f'Title is {tlen} chars. Recommended: 30-60'})
                elif tlen > 60:
                    seo_issues.append({'issue': 'Title Too Long', 'description': f'Title is {tlen} chars. May be truncated'})
                else:
                    seo_good.append(f'Title length optimal: {tlen} characters')
            else:
                seo_issues.append({'issue': 'Missing Title Tag', 'description': 'Page must have a title tag'})

            meta_desc = soup.find('meta', attrs={'name': 'description'})
            if meta_desc and meta_desc.get('content'):
                dlen = len(meta_desc.get('content', ''))
                if dlen < 120:
                    seo_issues.append({'issue': 'Meta Description Too Short', 'description': f'{dlen} chars. Recommended: 120-160'})
                elif dlen > 160:
                    seo_issues.append({'issue': 'Meta Description Too Long', 'description': f'{dlen} chars. May be truncated'})
                else:
                    seo_good.append(f'Meta description optimal: {dlen} characters')
            else:
                seo_issues.append({'issue': 'Missing Meta Description', 'description': 'Helps improve click-through rates'})

            h1_tags = soup.find_all('h1')
            if len(h1_tags) == 0:
                seo_issues.append({'issue': 'No H1 Tag', 'description': 'Page should have exactly one H1'})
            elif len(h1_tags) > 1:
                seo_issues.append({'issue': 'Multiple H1 Tags', 'description': f'Found {len(h1_tags)} H1 tags'})
            else:
                seo_good.append('Single H1 tag found')

            if not soup.find('link', rel='canonical'):
                seo_issues.append({'issue': 'Missing Canonical URL', 'description': 'Helps prevent duplicate content'})
            else:
                seo_good.append('Canonical URL defined')

            og_tags = soup.find_all('meta', property=re.compile('^og:'))
            if len(og_tags) >= 4:
                seo_good.append(f'Open Graph tags present ({len(og_tags)})')
            else:
                seo_issues.append({'issue': 'Incomplete Open Graph Tags', 'description': 'Add og:title, og:description, og:image, og:url'})

        except Exception as e:
            seo_issues.append({'issue': 'SEO Check Failed', 'description': str(e)})

        return {'issues': seo_issues, 'good': seo_good, 'score': max(0, 100 - len(seo_issues) * 10)}

    def _check_accessibility_for_page(self, page_url, soup):
        """Check accessibility using pre-fetched soup."""
        issues = []
        good = []
        try:
            html_tag = soup.find('html')
            if html_tag and html_tag.get('lang'):
                good.append(f'Language declared: {html_tag.get("lang")}')
            else:
                issues.append({'issue': 'Missing Language Declaration', 'description': 'Add lang attribute to <html> tag'})

            images = soup.find_all('img')
            no_alt = [img for img in images if not img.get('alt')]
            if no_alt:
                issues.append({'issue': 'Images Missing Alt Text', 'description': f'{len(no_alt)} of {len(images)} images missing alt'})
            elif images:
                good.append(f'All {len(images)} images have alt text')

            inputs = soup.find_all(['input', 'select', 'textarea'])
            unlabeled = []
            for inp in inputs:
                if inp.get('type') in ['hidden', 'submit', 'button']:
                    continue
                input_id = inp.get('id')
                has_label = bool(soup.find('label', attrs={'for': input_id})) if input_id else False
                has_aria = bool(inp.get('aria-label') or inp.get('aria-labelledby'))
                if not (has_label or has_aria):
                    unlabeled.append(inp)
            if unlabeled:
                issues.append({'issue': 'Form Inputs Without Labels', 'description': f'{len(unlabeled)} elements missing labels'})
            elif inputs:
                good.append('All form inputs have labels')

            landmarks = soup.find_all(attrs={'role': re.compile('main|navigation|banner|contentinfo|search')})
            if landmarks:
                good.append(f'ARIA landmarks present ({len(landmarks)})')
            else:
                issues.append({'issue': 'No ARIA Landmarks', 'description': 'Add ARIA landmarks for screen readers'})

            if not soup.find('a', href=re.compile('#(main|content|skip)')):
                issues.append({'issue': 'No Skip Navigation Link', 'description': 'Add skip link for keyboard navigation'})
            else:
                good.append('Skip navigation link found')

        except Exception as e:
            issues.append({'issue': 'Accessibility Check Failed', 'description': str(e)})

        return {'issues': issues, 'good': good, 'score': max(0, 100 - len(issues) * 12)}

    def _check_mobile_for_page(self, page_url, soup):
        """Check mobile optimisation using pre-fetched soup."""
        issues = []
        good = []
        try:
            viewport = soup.find('meta', attrs={'name': 'viewport'})
            if viewport:
                if 'width=device-width' in viewport.get('content', ''):
                    good.append('Responsive viewport configured')
                else:
                    issues.append({'issue': 'Incomplete Viewport Configuration', 'description': 'Viewport should include width=device-width'})
            else:
                issues.append({'issue': 'Missing Viewport Meta Tag', 'description': 'Required for responsive mobile design'})

            if soup.find('link', rel=re.compile('apple-touch-icon')):
                good.append('Apple touch icon configured')
            else:
                issues.append({'issue': 'Missing Apple Touch Icon', 'description': 'Add apple-touch-icon for iOS devices'})

            if soup.find('link', rel='manifest'):
                good.append('Web app manifest present')
            else:
                issues.append({'issue': 'No Web App Manifest', 'description': 'Consider adding manifest.json for PWA'})

            total_images = len(soup.find_all('img'))
            img_with_srcset = soup.find_all('img', srcset=True)
            if total_images > 0 and len(img_with_srcset) <= total_images * 0.5:
                issues.append({'issue': 'No Responsive Images', 'description': 'Use srcset for responsive image loading'})
            elif total_images > 0:
                good.append('Responsive images implemented (srcset)')

        except Exception as e:
            issues.append({'issue': 'Mobile Check Failed', 'description': str(e)})

        return {'issues': issues, 'good': good, 'score': max(0, 100 - len(issues) * 15)}

    def _suggest_improvements_for_page(self, page_url, soup):
        """Suggest improvements using pre-fetched soup."""
        suggestions = []
        try:
            if not soup.find('meta', attrs={'name': 'description'}):
                suggestions.append({'category': 'SEO', 'suggestion': 'Add meta description', 'priority': 'high', 'description': 'Meta descriptions help search engines understand your page'})
            if not soup.find('title'):
                suggestions.append({'category': 'SEO', 'suggestion': 'Add page title', 'priority': 'high', 'description': 'Every page should have a unique title'})
            h1_tags = soup.find_all('h1')
            if len(h1_tags) == 0:
                suggestions.append({'category': 'SEO', 'suggestion': 'Add H1 heading', 'priority': 'medium', 'description': 'H1 tags help structure content'})
            elif len(h1_tags) > 1:
                suggestions.append({'category': 'SEO', 'suggestion': 'Multiple H1 tags found', 'priority': 'low', 'description': 'Best practice is one H1 per page'})
            images = soup.find_all('img')
            missing_alt = sum(1 for img in images if not img.get('alt'))
            if missing_alt > 0:
                suggestions.append({'category': 'Accessibility', 'suggestion': f'{missing_alt} images missing alt text', 'priority': 'high', 'description': 'Alt text improves accessibility and SEO'})
            if not soup.find('link', rel='icon') and not soup.find('link', rel='shortcut icon'):
                suggestions.append({'category': 'Branding', 'suggestion': 'Add favicon', 'priority': 'low', 'description': 'Favicons improve brand recognition'})
            if not soup.find('meta', attrs={'name': 'viewport'}):
                suggestions.append({'category': 'Mobile', 'suggestion': 'Add viewport meta tag', 'priority': 'high', 'description': 'Required for responsive mobile design'})
            if not bool(soup.find(string=re.compile('google-analytics|gtag|analytics'))):
                suggestions.append({'category': 'Analytics', 'suggestion': 'Consider adding analytics', 'priority': 'medium', 'description': 'Track visitor behaviour to improve your site'})
            scripts = soup.find_all('script', src=True)
            unminified = [s for s in scripts if s.get('src') and not any(m in s.get('src') for m in ['.min.', '-min.'])]
            if unminified:
                suggestions.append({'category': 'Performance', 'suggestion': 'Minify JavaScript files', 'priority': 'medium', 'description': 'Reduce file sizes by minifying JS and CSS'})
        except Exception as e:
            suggestions.append({'category': 'Error', 'suggestion': 'Analysis incomplete', 'priority': 'high', 'description': str(e)})
        return {'suggestions': suggestions, 'total_count': len(suggestions)}

    def check_security(self):
        """Check security issues"""
        security_issues = []
        security_passed = []
        
        try:
            # Check HTTPS
            if not self.url.startswith('https://'):
                security_issues.append({
                    'severity': 'high',
                    'issue': 'No HTTPS',
                    'description': 'Website is not using HTTPS encryption'
                })
            else:
                security_passed.append('HTTPS enabled')
            
            # Make request and check headers
            response = requests.get(self.url, timeout=10, allow_redirects=True)
            headers = response.headers
            
            # Check security headers
            security_headers = {
                'Strict-Transport-Security': 'HSTS header missing - helps prevent man-in-the-middle attacks',
                'X-Content-Type-Options': 'X-Content-Type-Options missing - prevents MIME type sniffing',
                'X-Frame-Options': 'X-Frame-Options missing - prevents clickjacking attacks',
                'X-XSS-Protection': 'X-XSS-Protection missing - helps prevent XSS attacks',
                'Content-Security-Policy': 'Content-Security-Policy missing - helps prevent XSS and injection attacks'
            }
            
            for header, description in security_headers.items():
                if header not in headers:
                    security_issues.append({
                        'severity': 'medium',
                        'issue': f'Missing {header}',
                        'description': description
                    })
                else:
                    security_passed.append(f'{header} configured')
            
            # Check for mixed content
            if self.url.startswith('https://'):
                soup = BeautifulSoup(response.content, 'html.parser')
                mixed_content = []
                
                for tag in soup.find_all(['img', 'script', 'link', 'iframe']):
                    src = tag.get('src') or tag.get('href')
                    if src and src.startswith('http://'):
                        mixed_content.append(src)
                
                if mixed_content:
                    security_issues.append({
                        'severity': 'medium',
                        'issue': 'Mixed Content',
                        'description': f'Found {len(mixed_content)} resources loaded over HTTP on HTTPS page'
                    })
                else:
                    security_passed.append('No mixed content detected')
            
            # Check SSL certificate (if HTTPS)
            if self.url.startswith('https://'):
                try:
                    hostname = urlparse(self.url).netloc
                    context = ssl.create_default_context()
                    with socket.create_connection((hostname, 443), timeout=5) as sock:
                        with context.wrap_socket(sock, server_hostname=hostname) as ssock:
                            cert = ssock.getpeercert()
                            security_passed.append('Valid SSL certificate')
                except Exception as e:
                    security_issues.append({
                        'severity': 'high',
                        'issue': 'SSL Certificate Issue',
                        'description': f'SSL certificate validation failed: {str(e)}'
                    })
            
            # Check for exposed sensitive files
            sensitive_paths = ['/robots.txt', '/.git/config', '/.env', '/config.php', '/wp-config.php', '/.htaccess']
            exposed_files = []
            
            for path in sensitive_paths:
                try:
                    test_url = urljoin(self.url, path)
                    r = requests.head(test_url, timeout=3)
                    if r.status_code == 200 and path not in ['/robots.txt']:
                        exposed_files.append(path)
                except:
                    pass
            
            if exposed_files:
                security_issues.append({
                    'severity': 'high',
                    'issue': 'Exposed Sensitive Files',
                    'description': f'Found exposed files: {", ".join(exposed_files)}'
                })
            
            # Check cookies
            if 'set-cookie' in headers:
                cookies = headers['set-cookie']
                if 'secure' not in cookies.lower():
                    security_issues.append({
                        'severity': 'medium',
                        'issue': 'Insecure Cookies',
                        'description': 'Cookies should have Secure flag set'
                    })
                if 'httponly' not in cookies.lower():
                    security_issues.append({
                        'severity': 'medium',
                        'issue': 'Cookie Security',
                        'description': 'Cookies should have HttpOnly flag to prevent XSS'
                    })
                else:
                    security_passed.append('Cookies have HttpOnly flag')
            
        except Exception as e:
            security_issues.append({
                'severity': 'high',
                'issue': 'Security Check Failed',
                'description': f'Could not complete security analysis: {str(e)}'
            })
        
        return {
            'issues': security_issues,
            'passed': security_passed,
            'score': max(0, 100 - (len(security_issues) * 15))
        }
    
    def check_broken_links(self):
        """Check for broken links with improved accuracy"""
        broken = []
        working = []
        
        # Browser-like headers to avoid false positives from bot detection
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }
        
        # Status codes that often give false positives (not truly broken)
        # 403: Forbidden - often bot detection blocking non-browser requests
        # 405: Method Not Allowed - server doesn't support HEAD, try GET
        # 406: Not Acceptable - content negotiation issue
        # 429: Too Many Requests - rate limiting
        # 503: Service Unavailable - temporary, often behind cloudflare
        false_positive_codes = {403, 405, 406, 429, 503}
        
        try:
            # Get main page with browser headers
            response = requests.get(self.url, timeout=10, headers=headers)
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Find all links
            links = set()
            for tag in soup.find_all(['a', 'link', 'script', 'img']):
                url = tag.get('href') or tag.get('src')
                if url:
                    # Skip javascript:, mailto:, tel:, and anchor-only links
                    if url.startswith(('javascript:', 'mailto:', 'tel:', '#', 'data:')):
                        continue
                    full_url = urljoin(self.url, url)
                    if full_url.startswith(('http://', 'https://')):
                        links.add(full_url)
            
            # Limit number of links to check
            links = list(links)[:100]
            
            # Check each link with improved logic
            for link in links:
                is_broken = False
                status_code = None
                reason = None
                
                try:
                    # Step 1: Try HEAD request first (faster)
                    r = requests.head(link, timeout=10, allow_redirects=True, headers=headers)
                    status_code = r.status_code
                    reason = r.reason
                    
                    if status_code >= 400:
                        # Step 2: For potential false positives, retry with GET request
                        if status_code in false_positive_codes:
                            try:
                                # Use GET with stream=True to avoid downloading full content
                                r_get = requests.get(link, timeout=10, allow_redirects=True, 
                                                    headers=headers, stream=True)
                                status_code = r_get.status_code
                                reason = r_get.reason
                                r_get.close()  # Close connection immediately
                                
                                if status_code < 400:
                                    is_broken = False
                                elif status_code in false_positive_codes:
                                    # Still getting blocked - likely bot detection, not broken
                                    # Mark as working with a note
                                    is_broken = False
                                else:
                                    is_broken = True
                            except:
                                # GET also failed, consider it potentially broken
                                is_broken = True
                        else:
                            is_broken = True
                    else:
                        is_broken = False
                        
                except requests.exceptions.SSLError as e:
                    # SSL errors could be certificate issues - actually broken
                    is_broken = True
                    status_code = 'SSL Error'
                    reason = f'SSL certificate issue: {str(e)[:80]}'
                    
                except requests.exceptions.ConnectionError as e:
                    # Connection refused or DNS failure - likely actually broken
                    error_msg = str(e).lower()
                    # Check if it's a DNS/connection issue vs temporary
                    if 'name or service not known' in error_msg or 'nodename nor servname' in error_msg:
                        is_broken = True
                        status_code = 'DNS Error'
                        reason = 'Domain not found'
                    elif 'connection refused' in error_msg:
                        is_broken = True
                        status_code = 'Refused'
                        reason = 'Connection refused by server'
                    else:
                        # Retry once for transient connection issues
                        try:
                            time.sleep(0.5)
                            r_retry = requests.head(link, timeout=15, allow_redirects=True, headers=headers)
                            if r_retry.status_code < 400:
                                is_broken = False
                            else:
                                is_broken = True
                                status_code = r_retry.status_code
                                reason = r_retry.reason
                        except:
                            is_broken = True
                            status_code = 'N/A'
                            reason = f'Connection failed: {str(e)[:80]}'
                            
                except requests.exceptions.Timeout:
                    # Timeout - retry once with longer timeout
                    try:
                        time.sleep(0.5)
                        r_retry = requests.head(link, timeout=20, allow_redirects=True, headers=headers)
                        if r_retry.status_code < 400:
                            is_broken = False
                        else:
                            is_broken = True
                            status_code = r_retry.status_code
                            reason = r_retry.reason
                    except:
                        is_broken = True
                        status_code = 'Timeout'
                        reason = 'Request timed out after retries'
                        
                except requests.exceptions.TooManyRedirects:
                    is_broken = True
                    status_code = 'Redirect Loop'
                    reason = 'Too many redirects detected'
                    
                except requests.exceptions.RequestException as e:
                    is_broken = True
                    status_code = 'Error'
                    reason = f'Request failed: {str(e)[:80]}'
                
                if is_broken:
                    broken.append({
                        'url': link,
                        'status_code': status_code,
                        'reason': reason
                    })
                else:
                    working.append(link)
            
        except Exception as e:
            broken.append({
                'url': self.url,
                'status_code': 'N/A',
                'reason': f'Failed to analyze: {str(e)}'
            })
        
        return {
            'broken': broken,
            'total_checked': len(broken) + len(working),
            'broken_count': len(broken),
            'working_count': len(working)
        }
    
    def check_performance(self):
        """Check performance metrics"""
        performance_issues = []
        performance_good = []
        
        try:
            # Measure page load time
            start_time = time.time()
            response = requests.get(self.url, timeout=30)
            load_time = time.time() - start_time
            
            # Check load time
            if load_time > 3:
                performance_issues.append({
                    'issue': 'Slow Page Load',
                    'value': f'{load_time:.2f}s',
                    'description': 'Page load time exceeds 3 seconds'
                })
            else:
                performance_good.append(f'Fast page load: {load_time:.2f}s')
            
            # Check page size
            page_size = len(response.content) / 1024  # KB
            if page_size > 2000:  # 2MB
                performance_issues.append({
                    'issue': 'Large Page Size',
                    'value': f'{page_size:.2f} KB',
                    'description': 'Page size exceeds 2MB, consider optimization'
                })
            else:
                performance_good.append(f'Reasonable page size: {page_size:.2f} KB')
            
            # Parse HTML
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Check number of requests (approximate)
            resources = soup.find_all(['script', 'link', 'img', 'iframe'])
            resource_count = len(resources)
            
            if resource_count > 50:
                performance_issues.append({
                    'issue': 'Too Many Resources',
                    'value': f'{resource_count} resources',
                    'description': 'Consider combining files and using sprites'
                })
            else:
                performance_good.append(f'Reasonable resource count: {resource_count}')
            
            # Check compression
            if 'content-encoding' not in response.headers:
                performance_issues.append({
                    'issue': 'No Compression',
                    'value': 'N/A',
                    'description': 'Enable gzip or brotli compression'
                })
            else:
                performance_good.append(f"Compression enabled: {response.headers.get('content-encoding')}")
            
            # Check caching headers
            cache_headers = ['cache-control', 'expires', 'etag']
            has_caching = any(h in response.headers for h in cache_headers)
            
            if not has_caching:
                performance_issues.append({
                    'issue': 'No Caching Headers',
                    'value': 'N/A',
                    'description': 'Add cache headers to improve repeat visits'
                })
            else:
                performance_good.append('Caching headers present')
            
            # Check image optimization
            images = soup.find_all('img')
            large_images = 0
            for img in images[:20]:  # Check first 20 images
                img_src = img.get('src')
                if img_src:
                    img_url = urljoin(self.url, img_src)
                    try:
                        img_response = requests.head(img_url, timeout=3)
                        size = int(img_response.headers.get('content-length', 0))
                        if size > 500000:  # 500KB
                            large_images += 1
                    except:
                        pass
            
            if large_images > 0:
                performance_issues.append({
                    'issue': 'Large Images',
                    'value': f'{large_images} images > 500KB',
                    'description': 'Optimize images to reduce file size'
                })
            
        except Exception as e:
            performance_issues.append({
                'issue': 'Performance Check Failed',
                'value': 'N/A',
                'description': f'Could not complete analysis: {str(e)}'
            })
        
        return {
            'issues': performance_issues,
            'good': performance_good,
            'load_time': f'{load_time:.2f}s' if 'load_time' in locals() else 'N/A',
            'page_size': f'{page_size:.2f} KB' if 'page_size' in locals() else 'N/A'
        }
    
    def suggest_improvements(self):
        """Suggest improvements"""
        suggestions = []
        
        try:
            response = requests.get(self.url, timeout=10)
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Check meta tags
            if not soup.find('meta', attrs={'name': 'description'}):
                suggestions.append({
                    'category': 'SEO',
                    'suggestion': 'Add meta description',
                    'priority': 'high',
                    'description': 'Meta descriptions help search engines understand your page'
                })
            
            if not soup.find('title'):
                suggestions.append({
                    'category': 'SEO',
                    'suggestion': 'Add page title',
                    'priority': 'high',
                    'description': 'Every page should have a unique, descriptive title'
                })
            
            # Check for h1 tag
            h1_tags = soup.find_all('h1')
            if len(h1_tags) == 0:
                suggestions.append({
                    'category': 'SEO',
                    'suggestion': 'Add H1 heading',
                    'priority': 'medium',
                    'description': 'H1 tags help structure content and improve SEO'
                })
            elif len(h1_tags) > 1:
                suggestions.append({
                    'category': 'SEO',
                    'suggestion': 'Multiple H1 tags found',
                    'priority': 'low',
                    'description': 'Best practice is to have one H1 per page'
                })
            
            # Check images for alt text
            images = soup.find_all('img')
            images_without_alt = sum(1 for img in images if not img.get('alt'))
            
            if images_without_alt > 0:
                suggestions.append({
                    'category': 'Accessibility',
                    'suggestion': f'{images_without_alt} images missing alt text',
                    'priority': 'high',
                    'description': 'Alt text improves accessibility and SEO'
                })
            
            # Check for favicon
            if not soup.find('link', rel='icon') and not soup.find('link', rel='shortcut icon'):
                suggestions.append({
                    'category': 'Branding',
                    'suggestion': 'Add favicon',
                    'priority': 'low',
                    'description': 'Favicons improve brand recognition'
                })
            
            # Check for viewport meta tag
            if not soup.find('meta', attrs={'name': 'viewport'}):
                suggestions.append({
                    'category': 'Mobile',
                    'suggestion': 'Add viewport meta tag',
                    'priority': 'high',
                    'description': 'Required for responsive mobile design'
                })
            
            # Check for analytics
            has_analytics = bool(soup.find(string=re.compile('google-analytics|gtag|analytics')))
            if not has_analytics:
                suggestions.append({
                    'category': 'Analytics',
                    'suggestion': 'Consider adding analytics',
                    'priority': 'medium',
                    'description': 'Track visitor behavior to improve your site'
                })
            
            # Check minification
            scripts = soup.find_all('script', src=True)
            unminified = [s for s in scripts if s.get('src') and not any(m in s.get('src') for m in ['.min.', '-min.'])]
            
            if len(unminified) > 0:
                suggestions.append({
                    'category': 'Performance',
                    'suggestion': 'Minify JavaScript files',
                    'priority': 'medium',
                    'description': 'Reduce file sizes by minifying JS and CSS'
                })
            
            # Check for responsive design indicators
            if not soup.find('meta', attrs={'name': 'viewport'}):
                suggestions.append({
                    'category': 'Mobile',
                    'suggestion': 'Implement responsive design',
                    'priority': 'high',
                    'description': 'Ensure site works well on mobile devices'
                })
            
        except Exception as e:
            suggestions.append({
                'category': 'Error',
                'suggestion': 'Analysis incomplete',
                'priority': 'high',
                'description': f'Could not complete analysis: {str(e)}'
            })
        
        return {
            'suggestions': suggestions,
            'total_count': len(suggestions)
        }
    
    def check_seo(self):
        """Check SEO optimization"""
        seo_issues = []
        seo_good = []
        
        try:
            response = requests.get(self.url, timeout=10)
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Check title
            title = soup.find('title')
            if title:
                title_text = title.get_text().strip()
                title_length = len(title_text)
                
                if title_length < 30:
                    seo_issues.append({
                        'issue': 'Title Too Short',
                        'description': f'Title is {title_length} characters. Recommended: 30-60 characters'
                    })
                elif title_length > 60:
                    seo_issues.append({
                        'issue': 'Title Too Long',
                        'description': f'Title is {title_length} characters. May be truncated in search results'
                    })
                else:
                    seo_good.append(f'Title length optimal: {title_length} characters')
            else:
                seo_issues.append({
                    'issue': 'Missing Title Tag',
                    'description': 'Page must have a title tag for SEO'
                })
            
            # Check meta description
            meta_desc = soup.find('meta', attrs={'name': 'description'})
            if meta_desc and meta_desc.get('content'):
                desc_length = len(meta_desc.get('content', ''))
                if desc_length < 120:
                    seo_issues.append({
                        'issue': 'Meta Description Too Short',
                        'description': f'Description is {desc_length} characters. Recommended: 120-160'
                    })
                elif desc_length > 160:
                    seo_issues.append({
                        'issue': 'Meta Description Too Long',
                        'description': f'Description is {desc_length} characters. May be truncated'
                    })
                else:
                    seo_good.append(f'Meta description optimal: {desc_length} characters')
            else:
                seo_issues.append({
                    'issue': 'Missing Meta Description',
                    'description': 'Meta description helps improve click-through rates'
                })
            
            # Check heading structure
            h1_tags = soup.find_all('h1')
            if len(h1_tags) == 0:
                seo_issues.append({
                    'issue': 'No H1 Tag',
                    'description': 'Page should have exactly one H1 tag'
                })
            elif len(h1_tags) > 1:
                seo_issues.append({
                    'issue': 'Multiple H1 Tags',
                    'description': f'Found {len(h1_tags)} H1 tags. Best practice is one per page'
                })
            else:
                seo_good.append('Single H1 tag found')
            
            # Check for canonical URL
            canonical = soup.find('link', rel='canonical')
            if canonical:
                seo_good.append('Canonical URL defined')
            else:
                seo_issues.append({
                    'issue': 'Missing Canonical URL',
                    'description': 'Helps prevent duplicate content issues'
                })
            
            # Check Open Graph tags
            og_tags = soup.find_all('meta', property=re.compile('^og:'))
            if len(og_tags) >= 4:
                seo_good.append(f'Open Graph tags present ({len(og_tags)} tags)')
            else:
                seo_issues.append({
                    'issue': 'Incomplete Open Graph Tags',
                    'description': 'Add og:title, og:description, og:image, og:url for social sharing'
                })
            
            # Check Twitter Card tags
            twitter_tags = soup.find_all('meta', attrs={'name': re.compile('^twitter:')})
            if len(twitter_tags) >= 3:
                seo_good.append('Twitter Card tags present')
            else:
                seo_issues.append({
                    'issue': 'Missing Twitter Card Tags',
                    'description': 'Add Twitter Card tags for better social media integration'
                })
            
            # Check for schema.org markup
            has_schema = bool(soup.find(attrs={'itemtype': re.compile('schema.org')})) or \
                        bool(soup.find('script', type='application/ld+json'))
            if has_schema:
                seo_good.append('Structured data (Schema.org) found')
            else:
                seo_issues.append({
                    'issue': 'No Structured Data',
                    'description': 'Add Schema.org markup for rich search results'
                })
            
            # Check robots meta tag
            robots_meta = soup.find('meta', attrs={'name': 'robots'})
            if robots_meta:
                content = robots_meta.get('content', '').lower()
                if 'noindex' in content or 'nofollow' in content:
                    seo_issues.append({
                        'issue': 'Restrictive Robots Tag',
                        'description': f'Robots tag set to: {content}'
                    })
                else:
                    seo_good.append('Robots meta tag configured')
            
            # Check internal vs external links
            all_links = soup.find_all('a', href=True)
            internal_links = sum(1 for a in all_links if not a['href'].startswith(('http://', 'https://', '//')))
            external_links = len(all_links) - internal_links
            
            if internal_links > 0:
                seo_good.append(f'Internal linking: {internal_links} internal links')
            
        except Exception as e:
            seo_issues.append({
                'issue': 'SEO Check Failed',
                'description': f'Could not complete SEO analysis: {str(e)}'
            })
        
        return {
            'issues': seo_issues,
            'good': seo_good,
            'score': max(0, 100 - (len(seo_issues) * 10))
        }
    
    def check_accessibility(self):
        """Check accessibility features"""
        accessibility_issues = []
        accessibility_good = []
        
        try:
            response = requests.get(self.url, timeout=10)
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Check language declaration
            html_tag = soup.find('html')
            if html_tag and html_tag.get('lang'):
                accessibility_good.append(f'Language declared: {html_tag.get("lang")}')
            else:
                accessibility_issues.append({
                    'issue': 'Missing Language Declaration',
                    'description': 'Add lang attribute to <html> tag'
                })
            
            # Check images for alt text
            images = soup.find_all('img')
            images_without_alt = [img for img in images if not img.get('alt')]
            
            if images_without_alt:
                accessibility_issues.append({
                    'issue': 'Images Missing Alt Text',
                    'description': f'{len(images_without_alt)} out of {len(images)} images missing alt attributes'
                })
            else:
                accessibility_good.append(f'All {len(images)} images have alt text')
            
            # Check form labels
            inputs = soup.find_all(['input', 'select', 'textarea'])
            unlabeled_inputs = []
            
            for inp in inputs:
                input_id = inp.get('id')
                input_type = inp.get('type', 'text')
                
                # Skip hidden and submit buttons
                if input_type in ['hidden', 'submit', 'button']:
                    continue
                
                # Check for associated label
                has_label = bool(soup.find('label', attrs={'for': input_id})) if input_id else False
                has_aria_label = bool(inp.get('aria-label') or inp.get('aria-labelledby'))
                
                if not (has_label or has_aria_label):
                    unlabeled_inputs.append(inp)
            
            if unlabeled_inputs:
                accessibility_issues.append({
                    'issue': 'Form Inputs Without Labels',
                    'description': f'{len(unlabeled_inputs)} form elements missing labels or ARIA labels'
                })
            elif inputs:
                accessibility_good.append('All form inputs have labels')
            
            # Check for ARIA landmarks
            landmarks = soup.find_all(attrs={'role': re.compile('main|navigation|banner|contentinfo|search')})
            if landmarks:
                accessibility_good.append(f'ARIA landmarks present ({len(landmarks)} found)')
            else:
                accessibility_issues.append({
                    'issue': 'No ARIA Landmarks',
                    'description': 'Add ARIA landmarks for better screen reader navigation'
                })
            
            # Check for skip navigation link
            skip_link = soup.find('a', href=re.compile('#(main|content|skip)'))
            if skip_link:
                accessibility_good.append('Skip navigation link found')
            else:
                accessibility_issues.append({
                    'issue': 'No Skip Navigation Link',
                    'description': 'Add skip link for keyboard navigation users'
                })
            
            # Check for buttons vs links
            clickable_divs = soup.find_all('div', attrs={'onclick': True})
            if clickable_divs:
                accessibility_issues.append({
                    'issue': 'Non-Semantic Click Handlers',
                    'description': f'Found {len(clickable_divs)} clickable divs. Use <button> instead'
                })
            
        except Exception as e:
            accessibility_issues.append({
                'issue': 'Accessibility Check Failed',
                'description': f'Could not complete analysis: {str(e)}'
            })
        
        return {
            'issues': accessibility_issues,
            'good': accessibility_good,
            'score': max(0, 100 - (len(accessibility_issues) * 12))
        }
    
    def check_mobile_optimization(self):
        """Check mobile optimization"""
        mobile_issues = []
        mobile_good = []
        
        try:
            response = requests.get(self.url, timeout=10)
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Check viewport meta tag
            viewport = soup.find('meta', attrs={'name': 'viewport'})
            if viewport:
                content = viewport.get('content', '')
                if 'width=device-width' in content:
                    mobile_good.append('Responsive viewport configured')
                else:
                    mobile_issues.append({
                        'issue': 'Incomplete Viewport Configuration',
                        'description': 'Viewport should include width=device-width'
                    })
            else:
                mobile_issues.append({
                    'issue': 'Missing Viewport Meta Tag',
                    'description': 'Required for responsive mobile design'
                })
            
            # Check for touch icons
            apple_touch_icon = soup.find('link', rel=re.compile('apple-touch-icon'))
            if apple_touch_icon:
                mobile_good.append('Apple touch icon configured')
            else:
                mobile_issues.append({
                    'issue': 'Missing Apple Touch Icon',
                    'description': 'Add apple-touch-icon for iOS devices'
                })
            
            # Check manifest for PWA
            manifest = soup.find('link', rel='manifest')
            if manifest:
                mobile_good.append('Web app manifest present (PWA support)')
            else:
                mobile_issues.append({
                    'issue': 'No Web App Manifest',
                    'description': 'Consider adding manifest.json for PWA features'
                })
            
            # Check for mobile-friendly font sizes
            styles = soup.find_all('style')
            font_size_issues = False
            
            for style in styles:
                if 'font-size' in style.string if style.string else '':
                    # Simple check for absolute small font sizes
                    if re.search(r'font-size:\s*[0-9]{1,2}px', style.string):
                        font_size_issues = True
                        break
            
            if font_size_issues:
                mobile_issues.append({
                    'issue': 'Small Font Sizes Detected',
                    'description': 'Use relative units (rem, em) and ensure fonts are readable on mobile'
                })
            
            # Check for responsive images
            img_with_srcset = soup.find_all('img', srcset=True)
            total_images = len(soup.find_all('img'))
            
            if total_images > 0:
                if len(img_with_srcset) > total_images * 0.5:
                    mobile_good.append('Responsive images implemented (srcset)')
                else:
                    mobile_issues.append({
                        'issue': 'No Responsive Images',
                        'description': 'Use srcset for responsive image loading'
                    })
            
            # Check for touch-friendly tap targets
            buttons = soup.find_all(['button', 'a'])
            if len(buttons) > 0:
                mobile_good.append(f'Interactive elements found: {len(buttons)} buttons/links')
            
        except Exception as e:
            mobile_issues.append({
                'issue': 'Mobile Check Failed',
                'description': f'Could not complete analysis: {str(e)}'
            })
        
        return {
            'issues': mobile_issues,
            'good': mobile_good,
            'score': max(0, 100 - (len(mobile_issues) * 15))
        }
    
    def check_rendering(self):
        """Check for potential rendering issues"""
        rendering_issues = []
        rendering_good = []
        
        # Browser-like headers for accurate responses
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
        }
        
        try:
            response = requests.get(self.url, timeout=15, headers=headers)
            soup = BeautifulSoup(response.content, 'html.parser')
            base_domain = urlparse(self.url).netloc
            
            # Check 1: CSS Loading Issues
            css_links = soup.find_all('link', rel='stylesheet')
            broken_css = []
            external_css_count = 0
            
            for css in css_links[:15]:  # Check first 15 CSS files
                href = css.get('href')
                if href:
                    css_url = urljoin(self.url, href)
                    if css_url.startswith(('http://', 'https://')):
                        external_css_count += 1
                        try:
                            r = requests.head(css_url, timeout=5, headers=headers, allow_redirects=True)
                            if r.status_code >= 400 and r.status_code not in {403, 405}:
                                broken_css.append(href)
                        except:
                            broken_css.append(href)
            
            if broken_css:
                rendering_issues.append({
                    'severity': 'high',
                    'issue': 'CSS Files Not Loading',
                    'description': f'{len(broken_css)} stylesheet(s) failed to load, which may cause layout issues'
                })
            else:
                rendering_good.append(f'All {external_css_count} CSS stylesheets loading properly')
            
            # Check 2: JavaScript Loading Issues
            scripts = soup.find_all('script', src=True)
            broken_scripts = []
            critical_scripts = []
            
            for script in scripts[:20]:  # Check first 20 scripts
                src = script.get('src')
                if src:
                    script_url = urljoin(self.url, src)
                    if script_url.startswith(('http://', 'https://')):
                        try:
                            r = requests.head(script_url, timeout=5, headers=headers, allow_redirects=True)
                            if r.status_code >= 400 and r.status_code not in {403, 405}:
                                broken_scripts.append(src)
                                # Check if it's a critical library
                                if any(lib in src.lower() for lib in ['jquery', 'react', 'vue', 'angular', 'bootstrap']):
                                    critical_scripts.append(src)
                        except:
                            broken_scripts.append(src)
            
            if critical_scripts:
                rendering_issues.append({
                    'severity': 'high',
                    'issue': 'Critical JavaScript Library Missing',
                    'description': f'Core library not loading: {critical_scripts[0][:60]} - This may break page functionality'
                })
            elif broken_scripts:
                rendering_issues.append({
                    'severity': 'medium',
                    'issue': 'JavaScript Files Not Loading',
                    'description': f'{len(broken_scripts)} script(s) failed to load'
                })
            else:
                rendering_good.append(f'All {len(scripts)} JavaScript files loading properly')
            
            # Check 3: Web Fonts Loading
            font_links = soup.find_all('link', href=re.compile(r'fonts\.(googleapis|gstatic|typekit|fontawesome|cdnfonts)'))
            font_faces = soup.find_all('style', string=re.compile(r'@font-face', re.IGNORECASE)) if soup.find_all('style') else []
            
            if font_links or font_faces:
                broken_fonts = []
                for font in font_links[:5]:
                    href = font.get('href')
                    if href:
                        try:
                            r = requests.head(href, timeout=5, headers=headers, allow_redirects=True)
                            if r.status_code >= 400 and r.status_code not in {403, 405}:
                                broken_fonts.append(href)
                        except:
                            broken_fonts.append(href)
                
                if broken_fonts:
                    rendering_issues.append({
                        'severity': 'medium',
                        'issue': 'Web Fonts Not Loading',
                        'description': 'Custom fonts may not display, causing text rendering with fallback fonts'
                    })
                else:
                    rendering_good.append('Web fonts loading correctly')
            
            # Check 4: Inline Styles (potential rendering maintenance issues)
            inline_styles = soup.find_all(style=True)
            if len(inline_styles) > 50:
                rendering_issues.append({
                    'severity': 'low',
                    'issue': 'Excessive Inline Styles',
                    'description': f'Found {len(inline_styles)} elements with inline styles, making rendering maintenance difficult'
                })
            
            # Check 5: Hidden Content / Display Issues
            hidden_elements = soup.find_all(style=re.compile(r'display\s*:\s*none|visibility\s*:\s*hidden', re.IGNORECASE))
            if len(hidden_elements) > 20:
                rendering_issues.append({
                    'severity': 'low',
                    'issue': 'Many Hidden Elements',
                    'description': f'Found {len(hidden_elements)} hidden elements - ensure content is intentionally hidden'
                })
            
            # Check 6: DOCTYPE Declaration
            doctype = soup.contents[0] if soup.contents else None
            has_doctype = str(doctype).lower().startswith('<!doctype')
            
            if not has_doctype:
                rendering_issues.append({
                    'severity': 'high',
                    'issue': 'Missing DOCTYPE Declaration',
                    'description': 'Page may render in quirks mode, causing inconsistent rendering across browsers'
                })
            else:
                rendering_good.append('Valid DOCTYPE declaration found')
            
            # Check 7: Image Loading Issues
            images = soup.find_all('img')
            broken_images = []
            large_dimension_images = []
            
            for img in images[:15]:  # Check first 15 images
                src = img.get('src')
                if src and not src.startswith('data:'):
                    img_url = urljoin(self.url, src)
                    if img_url.startswith(('http://', 'https://')):
                        try:
                            r = requests.head(img_url, timeout=5, headers=headers, allow_redirects=True)
                            if r.status_code >= 400 and r.status_code not in {403, 405}:
                                broken_images.append(src)
                        except:
                            pass  # Don't count network issues as broken images
                
                # Check for explicit large dimensions
                width = img.get('width', '')
                height = img.get('height', '')
                try:
                    if (width and int(width.replace('px', '')) > 2000) or \
                       (height and int(height.replace('px', '')) > 2000):
                        large_dimension_images.append(src)
                except:
                    pass
            
            if broken_images:
                rendering_issues.append({
                    'severity': 'medium',
                    'issue': 'Broken Images',
                    'description': f'{len(broken_images)} image(s) not loading: {broken_images[0][:50]}...'
                })
            else:
                rendering_good.append('All checked images loading properly')
            
            # Check 8: Layout Framework Detection
            has_grid = bool(soup.find(class_=re.compile(r'grid|col-|row')))
            has_flex = bool(soup.find(class_=re.compile(r'flex|d-flex')))
            has_bootstrap = bool(soup.find(class_=re.compile(r'container|row|col-')))
            has_tailwind = bool(soup.find(class_=re.compile(r'^(flex|grid|m-\d|p-\d|text-|bg-|w-|h-)')))
            
            layout_info = []
            if has_bootstrap:
                layout_info.append('Bootstrap grid')
            if has_tailwind:
                layout_info.append('Tailwind CSS')
            if has_grid and not has_bootstrap and not has_tailwind:
                layout_info.append('CSS Grid')
            if has_flex and not has_bootstrap and not has_tailwind:
                layout_info.append('Flexbox')
            
            if layout_info:
                rendering_good.append(f'Modern layout system detected: {", ".join(layout_info)}')
            
            # Check 9: Z-index Conflicts (potential overlapping issues)
            styles_text = ' '.join([s.string for s in soup.find_all('style') if s.string])
            high_zindex = re.findall(r'z-index\s*:\s*(\d+)', styles_text)
            if high_zindex:
                max_z = max(int(z) for z in high_zindex)
                if max_z > 10000:
                    rendering_issues.append({
                        'severity': 'low',
                        'issue': 'Very High Z-Index Values',
                        'description': f'Z-index values up to {max_z} found, which may cause stacking issues'
                    })
            
            # Check 10: CSS Animations and Transitions
            has_animations = bool(re.search(r'animation|transition|@keyframes', styles_text, re.IGNORECASE))
            if has_animations:
                rendering_good.append('CSS animations/transitions detected for smooth interactions')
            
            # Check 11: Print Stylesheet
            print_css = soup.find('link', media=re.compile(r'print'))
            if print_css:
                rendering_good.append('Print stylesheet available for better print rendering')
            else:
                rendering_issues.append({
                    'severity': 'low',
                    'issue': 'No Print Stylesheet',
                    'description': 'Consider adding print-specific styles for better document printing'
                })
            
            # Check 12: Character Encoding
            meta_charset = soup.find('meta', charset=True) or soup.find('meta', attrs={'http-equiv': re.compile('content-type', re.I)})
            if meta_charset:
                rendering_good.append('Character encoding properly declared')
            else:
                rendering_issues.append({
                    'severity': 'medium',
                    'issue': 'Missing Character Encoding',
                    'description': 'No charset meta tag found - may cause text rendering issues with special characters'
                })
            
        except Exception as e:
            rendering_issues.append({
                'severity': 'high',
                'issue': 'Rendering Check Failed',
                'description': f'Could not complete rendering analysis: {str(e)}'
            })
        
        # Calculate score
        high_issues = sum(1 for i in rendering_issues if i.get('severity') == 'high')
        medium_issues = sum(1 for i in rendering_issues if i.get('severity') == 'medium')
        low_issues = sum(1 for i in rendering_issues if i.get('severity') == 'low')
        score = max(0, 100 - (high_issues * 20) - (medium_issues * 10) - (low_issues * 5))
        
        return {
            'issues': rendering_issues,
            'good': rendering_good,
            'score': score
        }
