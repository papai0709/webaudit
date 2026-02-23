<div align="center">

# 🔍 webaudit

**A comprehensive website auditing tool that analyzes security, SEO, performance, accessibility, broken links, and mobile optimization — all from a single URL input.**

[![Python](https://img.shields.io/badge/Python-3.8%2B-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![Flask](https://img.shields.io/badge/Flask-2.x-000000?style=for-the-badge&logo=flask&logoColor=white)](https://flask.palletsprojects.com/)
[![HTML5](https://img.shields.io/badge/HTML5-E34F26?style=for-the-badge&logo=html5&logoColor=white)](https://developer.mozilla.org/en-US/docs/Web/HTML)
[![CSS3](https://img.shields.io/badge/CSS3-1572B6?style=for-the-badge&logo=css3&logoColor=white)](https://developer.mozilla.org/en-US/docs/Web/CSS)
[![JavaScript](https://img.shields.io/badge/JavaScript-F7DF1E?style=for-the-badge&logo=javascript&logoColor=black)](https://developer.mozilla.org/en-US/docs/Web/JavaScript)
[![License](https://img.shields.io/badge/License-Open%20Source-22c55e?style=for-the-badge&logo=opensourceinitiative&logoColor=white)](LICENSE)
[![Status](https://img.shields.io/badge/Status-Active-brightgreen?style=for-the-badge&logo=statuspage&logoColor=white)]()

---

### 🤖 Built with **Antigravity** — AI Coding Assistant by Google DeepMind

[![Antigravity](https://img.shields.io/badge/Built%20with-Antigravity%20AI-6366f1?style=for-the-badge&logo=google&logoColor=white)](https://deepmind.google/)
[![Google DeepMind](https://img.shields.io/badge/Powered%20by-Google%20DeepMind-4285F4?style=for-the-badge&logo=google&logoColor=white)](https://deepmind.google/)

> *"This project was entirely designed, developed, and deployed using **Antigravity**, a powerful agentic AI coding assistant built by the Google DeepMind team — from initial architecture to the final GitHub push."*

</div>

---

## 🚀 What is webaudit?

**webaudit** is a Flask-powered web application that performs a full-spectrum health check on any website. Enter a URL and get an instant, detailed report covering **7 critical dimensions** — comparable to professional tools like Google Lighthouse, GTmetrix, and WebPageTest, but running entirely on your own machine.

---

## ✨ Features

### 🔒 Security Analysis
- ✅ HTTPS encryption verification
- ✅ SSL certificate validation
- ✅ Security headers audit (HSTS, CSP, X-Frame-Options, X-XSS-Protection)
- ✅ Mixed content detection
- ✅ Exposed sensitive files scanner (`.git`, `.env`, config files)
- ✅ Cookie security flags (HttpOnly, Secure, SameSite)

### 🔗 Broken Link Detection
- 🔎 Scans up to 100 links per page
- 🧠 Smart false-positive reduction (handles bot-detection, rate limiting)
- 🔄 Automatic HEAD → GET fallback for edge cases
- 📋 Provides HTTP status codes and failure reasons for every broken link

### ⚡ Performance Analysis
- ⏱️ Real-time page load time measurement
- 📦 Page size evaluation
- 📊 Resource count analysis
- 🗜️ Compression detection (gzip / brotli)
- 🗄️ Caching headers verification
- 🖼️ Image optimization checks (flags images > 500KB)

### 🎯 SEO Analysis
- 📝 Title tag length optimization (30–60 characters)
- 📄 Meta description validation (120–160 characters)
- 🏗️ Heading hierarchy (H1–H6 structure)
- 🔗 Canonical URL presence
- 📣 Open Graph tags for social media sharing
- 🐦 Twitter Card tags
- 🗂️ Schema.org structured data markup
- 🤖 Robots meta tag configuration

### ♿ Accessibility Analysis
- 🌍 Language declaration (`<html lang="">`)
- 🖼️ Alt text for all images
- 🏷️ Form input labels and ARIA labels
- 🗺️ ARIA landmarks for screen reader navigation
- ⬆️ Skip navigation links
- 🏛️ Semantic HTML usage
- ⚖️ WCAG-aligned compliance checks

### 📱 Mobile Optimization
- 📐 Viewport meta tag configuration
- 🍎 Apple touch icons for iOS
- 📲 Progressive Web App (PWA) manifest detection
- 🔤 Mobile-friendly font sizes
- 🖼️ Responsive images (`srcset`) detection
- 👆 Touch-friendly interactive element checks

### 🖥️ Rendering Analysis
- 🔍 Client-side rendering detection
- ⚙️ JavaScript dependency identification

### 💡 Improvement Suggestions
- 🔴 High / 🟡 Medium / 🟢 Low priority recommendations
- 🎯 Category-specific, actionable fixes
- 📚 Best practices enforcement across all dimensions

---

## 📊 Dashboard Score Guide

| Score | Range | Indicator |
|-------|-------|-----------|
| 🟢 **Excellent** | 90–100 | Outstanding |
| 🔵 **Good** | 70–89 | Above Average |
| 🟡 **Fair** | 50–69 | Needs Attention |
| 🔴 **Poor** | 0–49 | Critical Issues |

The dashboard features **animated score circles**, gradient section headers, colour-coded severity badges, hover card effects, smooth scrolling, and a fully responsive layout.

---

## 🛠️ Tech Stack

| Layer | Technology | Badge |
|-------|-----------|-------|
| 🐍 Backend | Python 3.8+, Flask | [![Python](https://img.shields.io/badge/Python-3776AB?style=flat-square&logo=python&logoColor=white)](https://www.python.org/) |
| 🔬 Parsing | BeautifulSoup4, requests | [![BeautifulSoup](https://img.shields.io/badge/BeautifulSoup4-59666C?style=flat-square&logo=python&logoColor=white)]() |
| 🎨 Frontend | Vanilla JavaScript, CSS3 | [![JS](https://img.shields.io/badge/JavaScript-F7DF1E?style=flat-square&logo=javascript&logoColor=black)](https://developer.mozilla.org/en-US/docs/Web/JavaScript) |
| 🔐 Security | SSL verification, HTTP header analysis | [![SSL](https://img.shields.io/badge/SSL-Verified-22c55e?style=flat-square&logo=letsencrypt&logoColor=white)]() |
| 🧮 Analysis | Custom algorithms per category | [![Custom](https://img.shields.io/badge/Custom-Algorithms-6366f1?style=flat-square)]() |

---

## 📁 Project Structure

```
webaudit/
├── 📄 app.py                 # Flask application & REST endpoints
├── 🧠 analyzer.py            # Core website analysis engine
├── 📋 requirements.txt       # Python dependencies
├── 📖 README.md              # Documentation
├── 📁 static/
│   ├── 🎨 style.css          # Styling & animations
│   └── ⚡ script.js          # Frontend logic & result rendering
└── 📁 templates/
    └── 🌐 index.html         # Dashboard HTML template
```

---

## 🚀 Installation & Setup

### Prerequisites
- 🐍 Python 3.8 or higher
- 📦 pip package manager

### Steps

```bash
# 1. Clone the repository
git clone https://github.com/papai0709/webaudit.git
cd webaudit

# 2. (Optional) Create a virtual environment
python -m venv .venv
source .venv/bin/activate   # macOS/Linux
.venv\Scripts\activate      # Windows

# 3. Install dependencies
pip install -r requirements.txt

# 4. Start the server
python app.py
```

Then open your browser and go to: **`http://localhost:5002`**

---

## 📖 Usage

1. 🌐 **Enter a URL** — with or without `https://` (auto-detected)
2. 🔍 **Click "Analyse Website"** — the engine runs all checks in parallel
3. 📊 **Review the Report** — explore scores, issues, and recommendations per category

### Example Output

```
Overall Score: 83/100

🔒 Security: 85/100
  ✓ HTTPS enabled
  ✓ Valid SSL certificate
  ⚠ Missing Content-Security-Policy header

🎯 SEO: 78/100
  ✓ Title length optimal: 45 characters
  ✓ Open Graph tags present
  ⚠ Missing Schema.org structured data

♿ Accessibility: 92/100
  ✓ All images have alt text
  ✓ Language declared: en
  ✓ ARIA landmarks present

📱 Mobile: 88/100
  ✓ Responsive viewport configured
  ✓ Web app manifest present
  ⚠ No responsive images (srcset)
```

---

## 📈 Scoring Model

Each category scores from **0 to 100** based on the number of issues detected:

| Category | Penalty per issue |
|----------|------------------|
| 🔒 Security | −15 points |
| 🎯 SEO | −10 points |
| ♿ Accessibility | −12 points |
| 📱 Mobile | −15 points |

---

## 🗺️ Roadmap

- [ ] 📄 PDF report export
- [ ] 📈 Historical scan tracking & trend graphs
- [ ] ⚔️ Competitor side-by-side comparison
- [ ] 💡 Lighthouse API integration
- [ ] 🕐 Automated scheduled scans
- [ ] 📧 Email alerts for critical issues
- [ ] 🔌 REST API for programmatic access
- [ ] 🧩 Browser extension
- [ ] 📦 Bulk URL batch analysis
- [ ] 🔄 CI/CD pipeline integration

---

## 🤝 Contributing

Contributions are welcome!

- 🐛 Report bugs via [Issues](../../issues)
- 💡 Suggest features via [Discussions](../../discussions)
- 🔧 Submit a [Pull Request](../../pulls)
- 📝 Improve the documentation

Please fork the repository and create a feature branch before submitting a PR.

---

## 📄 License

This project is open source and available for personal and commercial use.

---

## 🤖 Built with Antigravity

<div align="center">

[![Antigravity](https://img.shields.io/badge/Built%20with-Antigravity%20AI-6366f1?style=for-the-badge&logo=google&logoColor=white)](https://deepmind.google/)

This entire project — from architecture design and code implementation to testing, documentation, and Git publishing — was built using **Antigravity**, an advanced agentic AI coding assistant developed by the **Google DeepMind** team.

> *Antigravity pair-programmed every feature in this repository, demonstrating the power of AI-assisted software development.*

[![Google DeepMind](https://img.shields.io/badge/Google-DeepMind-4285F4?style=for-the-badge&logo=google&logoColor=white)](https://deepmind.google/)
[![AI Assisted](https://img.shields.io/badge/AI-Assisted%20Development-a855f7?style=for-the-badge&logo=openai&logoColor=white)]()
[![Agentic Coding](https://img.shields.io/badge/Agentic-Coding-ec4899?style=for-the-badge&logo=robot&logoColor=white)]()

</div>

---

## 🙏 Acknowledgments

Built with modern Python web technologies and designed to deliver professional-grade website analysis accessible to everyone — developers, designers, and site owners alike.

Special thanks to **Google DeepMind** and the **Antigravity** team for making AI-powered development a reality.

---

<div align="center">

*Made with ❤️ using 🤖 Antigravity — webaudit*

[![GitHub](https://img.shields.io/badge/GitHub-papai0709%2Fwebaudit-181717?style=for-the-badge&logo=github&logoColor=white)](https://github.com/papai0709/webaudit)

</div>
