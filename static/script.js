// ── Helpers ───────────────────────────────────────────────────────────────────

async function analyzeWebsite() {
    const urlInput = document.getElementById('urlInput');
    const analyzeBtn = document.getElementById('analyzeBtn');
    const loadingSection = document.getElementById('loadingSection');
    const errorSection = document.getElementById('errorSection');
    const resultsSection = document.getElementById('resultsSection');

    const url = urlInput.value.trim();
    const maxPages = parseInt(document.getElementById('maxPagesInput').value) || 20;

    if (!url) { showError('Please enter a valid URL'); return; }

    // Reset UI
    errorSection.style.display = 'none';
    resultsSection.style.display = 'none';
    loadingSection.style.display = 'block';
    analyzeBtn.disabled = true;
    analyzeBtn.querySelector('.btn-text').style.display = 'none';
    analyzeBtn.querySelector('.btn-loader').style.display = 'inline';

    try {
        // 1. Submit job
        const submitRes = await fetch('/analyze', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ url, max_pages: maxPages }),
        });

        const submitData = await submitRes.json();
        if (!submitRes.ok) throw new Error(submitData.error || 'Failed to start analysis');

        const jobId = submitData.job_id;

        // 2. Poll until done
        const data = await pollJob(jobId);

        // 3. Render
        displayResults(data);

    } catch (err) {
        showError(err.message);
    } finally {
        loadingSection.style.display = 'none';
        setLoadingProgress(0, 'queued', '');
        analyzeBtn.disabled = false;
        analyzeBtn.querySelector('.btn-text').style.display = 'inline';
        analyzeBtn.querySelector('.btn-loader').style.display = 'none';
    }
}

// ── Job polling ───────────────────────────────────────────────────────────────

const STAGE_LABELS = {
    queued: '⏳ Queued — starting shortly…',
    crawling: '🕷️ Crawling pages…',
    security: '🔒 Checking security headers & SSL…',
    analysing: '🔬 Running all checks…',
    done: '✅ Analysis complete!',
    error: '❌ Analysis failed',
};

async function pollJob(jobId) {
    const POLL_INTERVAL_MS = 800;
    const MAX_WAIT_MS = 5 * 60 * 1000;   // 5 min hard cap
    const started = Date.now();

    while (Date.now() - started < MAX_WAIT_MS) {
        await sleep(POLL_INTERVAL_MS);

        const res = await fetch(`/status/${jobId}`);
        const data = await res.json();

        if (!res.ok) throw new Error(data.error || 'Status check failed');

        // Update progress UI
        setLoadingProgress(data.progress || 0, data.stage || 'running', data.detail || '');

        if (data.status === 'error') throw new Error(data.error || 'Analysis failed on server');

        if (data.status === 'done') {
            // Fetch final result
            const resultRes = await fetch(`/result/${jobId}`);
            const resultData = await resultRes.json();
            if (!resultRes.ok) throw new Error(resultData.error || 'Failed to retrieve result');
            return resultData;
        }
    }
    throw new Error('Analysis timed out. Try reducing the Max Pages count.');
}

function sleep(ms) { return new Promise(resolve => setTimeout(resolve, ms)); }

// ── Progress UI ───────────────────────────────────────────────────────────────

function setLoadingProgress(pct, stage, detail) {
    const bar = document.getElementById('progressBar');
    const label = document.getElementById('progressLabel');
    const subtext = document.getElementById('progressSubtext');

    if (bar) bar.style.width = `${Math.min(100, pct)}%`;
    if (label) label.textContent = STAGE_LABELS[stage] || 'Analysing…';
    if (subtext) subtext.textContent = detail || '';
}

// ── Error display ─────────────────────────────────────────────────────────────

function showError(message) {
    const errorSection = document.getElementById('errorSection');
    document.getElementById('errorMessage').textContent = message;
    errorSection.style.display = 'block';
}

// ── Score helpers ─────────────────────────────────────────────────────────────

function getScoreClass(score) {
    if (score >= 90) return 'excellent';
    if (score >= 70) return 'good';
    if (score >= 50) return 'fair';
    return 'poor';
}

// ── Results rendering ─────────────────────────────────────────────────────────

function displayOverallSummary(data) {
    const scores = [
        { name: 'Security', score: data.security?.score || 0, icon: '🔒' },
        { name: 'SEO', score: data.seo?.score || 0, icon: '🎯' },
        { name: 'Accessibility', score: data.accessibility?.score || 0, icon: '♿' },
        { name: 'Rendering', score: data.rendering?.score || 0, icon: '🎨' },
        { name: 'Mobile', score: data.mobile?.score || 0, icon: '📱' },
    ];
    const avgScore = Math.round(scores.reduce((s, i) => s + i.score, 0) / scores.length);
    scores.unshift({ name: 'Overall', score: avgScore, icon: '⭐' });

    document.getElementById('overallScores').innerHTML = scores.map(item => `
        <div class="score-item">
            <div class="score-circle ${getScoreClass(item.score)}"><span>${item.score}</span></div>
            <div class="score-name">${item.icon} ${item.name}</div>
        </div>`).join('');
}

function displayResults(data) {
    document.getElementById('analyzedUrl').innerHTML =
        `<strong>URL:</strong> <a href="${data.url}" target="_blank">${data.url}</a>`;
    document.getElementById('timestamp').innerHTML =
        `<strong>Analysed:</strong> ${data.timestamp}`;

    const pageCount = data.pages_crawled || 1;
    document.getElementById('crawlSummary').innerHTML =
        `🗺️ <strong>${pageCount}</strong> page${pageCount !== 1 ? 's' : ''} crawled — all checks run across every page and results aggregated.`;

    const crawledCard = document.getElementById('crawledPagesCard');
    const crawledBody = document.getElementById('crawledPagesBody');
    if (data.per_page_summary?.length > 0) {
        crawledCard.style.display = 'block';
        document.getElementById('pagesCount').textContent =
            `${data.per_page_summary.length} page${data.per_page_summary.length !== 1 ? 's' : ''}`;
        crawledBody.innerHTML = data.per_page_summary.map(p => {
            const short = p.url.replace(/^https?:\/\/[^/]+/, '') || '/';
            return `<tr>
                <td><a href="${p.url}" target="_blank" title="${p.url}">${short || p.url}</a></td>
                <td><span class="mini-score ${getScoreClass(p.seo_score)}">${p.seo_score}</span></td>
                <td><span class="mini-score ${getScoreClass(p.perf_score)}">${p.perf_score}</span></td>
                <td><span class="mini-score ${getScoreClass(p.acc_score)}">${p.acc_score}</span></td>
                <td><span class="mini-score ${getScoreClass(p.mob_score)}">${p.mob_score}</span></td>
                <td><span class="mini-score ${p.broken_count > 0 ? 'poor' : 'excellent'}">${p.broken_count}</span></td>
            </tr>`;
        }).join('');
    } else {
        crawledCard.style.display = 'none';
    }

    displayOverallSummary(data);
    displaySecurity(data.security);
    displayBrokenLinks(data.broken_links);
    displayPerformance(data.performance);
    displayRendering(data.rendering);
    displayImprovements(data.improvements);
    displaySEO(data.seo);
    displayAccessibility(data.accessibility);
    displayMobile(data.mobile);

    const resultsSection = document.getElementById('resultsSection');
    resultsSection.style.display = 'block';
    resultsSection.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}

// ── Section renderers ─────────────────────────────────────────────────────────

function displaySecurity(security) {
    document.getElementById('securityScore').textContent = `Score: ${security.score || 0}/100`;

    const passed = document.getElementById('securityPassed');
    passed.innerHTML = security.passed?.length > 0
        ? '<h4 style="margin-bottom:15px;color:#4caf50;">✓ Passed Security Checks</h4>' +
        security.passed.map(i => `<div class="passed-item">${i}</div>`).join('')
        : '';

    const issues = document.getElementById('securityIssues');
    issues.innerHTML = security.issues?.length > 0
        ? '<h4 style="margin-bottom:15px;color:#ff9800;">⚠ Security Issues Found</h4>' +
        security.issues.map(i => `
            <div class="issue-item ${i.severity}">
                <span class="issue-severity severity-${i.severity}">${i.severity}</span>
                <div class="issue-title">${i.issue}</div>
                <div class="issue-description">${i.description}</div>
            </div>`).join('')
        : '<div class="passed-item">No security issues found! 🎉</div>';
}

function displayBrokenLinks(brokenLinks) {
    const brokenCount = brokenLinks.broken_count || 0;
    const workingCount = brokenLinks.working_count || 0;
    const totalChecked = brokenLinks.total_checked || 0;

    document.getElementById('brokenLinksCount').textContent = `${brokenCount} broken`;

    document.getElementById('linksStats').innerHTML = `
        <div class="stat-box"><span class="stat-value">${totalChecked}</span><span class="stat-label">Total Links Checked</span></div>
        <div class="stat-box"><span class="stat-value" style="color:#4caf50;">${workingCount}</span><span class="stat-label">Working Links</span></div>
        <div class="stat-box"><span class="stat-value" style="color:#f44336;">${brokenCount}</span><span class="stat-label">Broken Links</span></div>`;

    document.getElementById('brokenLinksList').innerHTML = brokenLinks.broken?.length > 0
        ? '<h4 style="margin-bottom:15px;color:#f44336;">🔴 Broken Links</h4>' +
        brokenLinks.broken.map(link => `
            <div class="broken-link">
                <div class="broken-link-url">${link.url}</div>
                <div class="broken-link-status">
                    <span class="status-code">${link.status_code}</span>
                    <span class="status-reason">${link.reason}</span>
                </div>
                ${link.found_on ? `<div class="broken-link-found">Found on: <a href="${link.found_on}" target="_blank">${link.found_on.replace(/^https?:\/\/[^/]+/, '') || '/'}</a></div>` : ''}
            </div>`).join('')
        : '<div class="passed-item">No broken links found! All links are working properly. ✓</div>';
}

function displayPerformance(performance) {
    document.getElementById('performanceMetrics').innerHTML = `
        <div class="metric-box"><span class="metric-value">${performance.load_time || 'N/A'}</span><span class="metric-label">Load Time</span></div>
        <div class="metric-box"><span class="metric-value">${performance.page_size || 'N/A'}</span><span class="metric-label">Page Size</span></div>`;

    const good = document.getElementById('performanceGood');
    good.innerHTML = performance.good?.length > 0
        ? '<h4 style="margin-bottom:15px;color:#4caf50;">✓ Good Performance</h4>' +
        performance.good.map(i => `<div class="passed-item">${i}</div>`).join('')
        : '';

    document.getElementById('performanceIssues').innerHTML = performance.issues?.length > 0
        ? '<h4 style="margin-bottom:15px;color:#ff9800;">⚠ Performance Issues</h4>' +
        performance.issues.map(i => `
            <div class="issue-item">
                <div class="issue-title">${i.issue}</div>
                <div class="issue-description">${i.description}</div>
                ${i.value !== 'N/A' ? `<div style="margin-top:5px;color:#667eea;font-weight:bold;">Current: ${i.value}</div>` : ''}
            </div>`).join('')
        : '<div class="passed-item">No performance issues found! Site is well optimized. 🚀</div>';
}

function displayImprovements(improvements) {
    document.getElementById('improvementsCount').textContent =
        `${improvements.total_count || 0} suggestions`;

    document.getElementById('improvementsList').innerHTML = improvements.suggestions?.length > 0
        ? improvements.suggestions.map(i => `
            <div class="improvement-item">
                <div class="improvement-header">
                    <span class="improvement-category">${i.category}</span>
                    <span class="improvement-priority priority-${i.priority}">${i.priority} priority</span>
                </div>
                <div class="improvement-title">${i.suggestion}</div>
                <div class="improvement-description">${i.description}</div>
            </div>`).join('')
        : '<div class="passed-item">No improvements needed! Your website is in great shape. 🌟</div>';
}

function displaySEO(seo) {
    document.getElementById('seoScore').textContent = `Score: ${seo.score || 0}/100`;

    document.getElementById('seoGood').innerHTML = seo.good?.length > 0
        ? '<h4 style="margin-bottom:15px;color:#4caf50;">✓ SEO Strengths</h4>' +
        seo.good.map(i => `<div class="passed-item">${i}</div>`).join('')
        : '';

    document.getElementById('seoIssues').innerHTML = seo.issues?.length > 0
        ? '<h4 style="margin-bottom:15px;color:#ff9800;">⚠ SEO Issues</h4>' +
        seo.issues.map(i => `
            <div class="issue-item">
                <div class="issue-title">${i.issue}</div>
                <div class="issue-description">${i.description}</div>
            </div>`).join('')
        : '<div class="passed-item">Excellent SEO! No issues found. 🎯</div>';
}

function displayAccessibility(accessibility) {
    document.getElementById('accessibilityScore').textContent =
        `Score: ${accessibility.score || 0}/100`;

    document.getElementById('accessibilityGood').innerHTML = accessibility.good?.length > 0
        ? '<h4 style="margin-bottom:15px;color:#4caf50;">✓ Accessibility Features</h4>' +
        accessibility.good.map(i => `<div class="passed-item">${i}</div>`).join('')
        : '';

    document.getElementById('accessibilityIssues').innerHTML = accessibility.issues?.length > 0
        ? '<h4 style="margin-bottom:15px;color:#ff9800;">⚠ Accessibility Issues</h4>' +
        accessibility.issues.map(i => `
            <div class="issue-item">
                <div class="issue-title">${i.issue}</div>
                <div class="issue-description">${i.description}</div>
            </div>`).join('')
        : '<div class="passed-item">Fully accessible! Great job. ♿</div>';
}

function displayMobile(mobile) {
    document.getElementById('mobileScore').textContent = `Score: ${mobile.score || 0}/100`;

    document.getElementById('mobileGood').innerHTML = mobile.good?.length > 0
        ? '<h4 style="margin-bottom:15px;color:#4caf50;">✓ Mobile-Friendly Features</h4>' +
        mobile.good.map(i => `<div class="passed-item">${i}</div>`).join('')
        : '';

    document.getElementById('mobileIssues').innerHTML = mobile.issues?.length > 0
        ? '<h4 style="margin-bottom:15px;color:#ff9800;">⚠ Mobile Optimization Issues</h4>' +
        mobile.issues.map(i => `
            <div class="issue-item">
                <div class="issue-title">${i.issue}</div>
                <div class="issue-description">${i.description}</div>
            </div>`).join('')
        : '<div class="passed-item">Perfectly optimized for mobile! 📱</div>';
}

function displayRendering(rendering) {
    const renderingScore = document.getElementById('renderingScore');
    const renderingGood = document.getElementById('renderingGood');
    const renderingIssues = document.getElementById('renderingIssues');

    if (!rendering) {
        renderingScore.textContent = 'N/A';
        renderingGood.innerHTML = '';
        renderingIssues.innerHTML = '<div class="issue-item">Rendering analysis not available</div>';
        return;
    }

    renderingScore.textContent = `Score: ${rendering.score || 0}/100`;

    renderingGood.innerHTML = rendering.good?.length > 0
        ? '<h4 style="margin-bottom:15px;color:#4caf50;">✓ Rendering Checks Passed</h4>' +
        rendering.good.map(i => `<div class="passed-item">${i}</div>`).join('')
        : '';

    renderingIssues.innerHTML = rendering.issues?.length > 0
        ? '<h4 style="margin-bottom:15px;color:#ff9800;">⚠ Rendering Issues</h4>' +
        rendering.issues.map(i => `
            <div class="issue-item ${i.severity || ''}">
                ${i.severity ? `<span class="issue-severity severity-${i.severity}">${i.severity}</span>` : ''}
                <div class="issue-title">${i.issue}</div>
                <div class="issue-description">${i.description}</div>
            </div>`).join('')
        : '<div class="passed-item">No rendering issues found! Page renders correctly. 🎨</div>';
}

// ── PDF export ────────────────────────────────────────────────────────────────

function exportToPdf() {
    document.body.classList.add('printing');
    const urlEl = document.getElementById('analyzedUrl');
    const sanitized = (urlEl ? urlEl.textContent.replace('URL: ', '').trim() : 'website')
        .replace(/[^a-zA-Z0-9]/g, '_').substring(0, 50);
    const orig = document.title;
    document.title = `Web_Analysis_Report_${sanitized}`;
    window.print();
    setTimeout(() => { document.title = orig; document.body.classList.remove('printing'); }, 1000);
}

// ── Enter key binding ─────────────────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', () => {
    document.getElementById('urlInput').addEventListener('keypress', e => {
        if (e.key === 'Enter') analyzeWebsite();
    });
});
