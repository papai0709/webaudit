async function analyzeWebsite() {
    const urlInput = document.getElementById('urlInput');
    const analyzeBtn = document.getElementById('analyzeBtn');
    const loadingSection = document.getElementById('loadingSection');
    const errorSection = document.getElementById('errorSection');
    const resultsSection = document.getElementById('resultsSection');

    const url = urlInput.value.trim();
    const maxPages = parseInt(document.getElementById('maxPagesInput').value) || 20;

    if (!url) {
        showError('Please enter a valid URL');
        return;
    }

    // Reset UI
    errorSection.style.display = 'none';
    resultsSection.style.display = 'none';
    loadingSection.style.display = 'block';
    analyzeBtn.disabled = true;
    analyzeBtn.querySelector('.btn-text').style.display = 'none';
    analyzeBtn.querySelector('.btn-loader').style.display = 'inline';

    try {
        const response = await fetch('/analyze', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ url: url, max_pages: maxPages })
        });

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.error || 'Failed to analyze website');
        }

        displayResults(data);

    } catch (error) {
        showError(error.message);
    } finally {
        loadingSection.style.display = 'none';
        analyzeBtn.disabled = false;
        analyzeBtn.querySelector('.btn-text').style.display = 'inline';
        analyzeBtn.querySelector('.btn-loader').style.display = 'none';
    }
}

function showError(message) {
    const errorSection = document.getElementById('errorSection');
    const errorMessage = document.getElementById('errorMessage');

    errorMessage.textContent = message;
    errorSection.style.display = 'block';
}

function getScoreClass(score) {
    if (score >= 90) return 'excellent';
    if (score >= 70) return 'good';
    if (score >= 50) return 'fair';
    return 'poor';
}

function displayOverallSummary(data) {
    const overallScores = document.getElementById('overallScores');

    const scores = [
        { name: 'Security', score: data.security?.score || 0, icon: '🔒' },
        { name: 'SEO', score: data.seo?.score || 0, icon: '🎯' },
        { name: 'Accessibility', score: data.accessibility?.score || 0, icon: '♿' },
        { name: 'Rendering', score: data.rendering?.score || 0, icon: '🎨' },
        { name: 'Mobile', score: data.mobile?.score || 0, icon: '📱' }
    ];

    // Calculate overall average
    const avgScore = Math.round(scores.reduce((sum, s) => sum + s.score, 0) / scores.length);
    scores.unshift({ name: 'Overall', score: avgScore, icon: '⭐' });

    overallScores.innerHTML = scores.map(item => `
        <div class="score-item">
            <div class="score-circle ${getScoreClass(item.score)}">
                <span>${item.score}</span>
            </div>
            <div class="score-name">${item.icon} ${item.name}</div>
        </div>
    `).join('');
}

function displayResults(data) {
    const resultsSection = document.getElementById('resultsSection');

    // Update header
    document.getElementById('analyzedUrl').innerHTML = `<strong>URL:</strong> <a href="${data.url}" target="_blank">${data.url}</a>`;
    document.getElementById('timestamp').innerHTML = `<strong>Analyzed:</strong> ${data.timestamp}`;

    // Crawl summary text
    const pageCount = data.pages_crawled || 1;
    document.getElementById('crawlSummary').innerHTML =
        `🗺️ <strong>${pageCount}</strong> page${pageCount !== 1 ? 's' : ''} crawled &mdash; all checks run across every page and results aggregated.`;

    // Crawled pages card
    const crawledCard = document.getElementById('crawledPagesCard');
    const pagesCount = document.getElementById('pagesCount');
    const crawledBody = document.getElementById('crawledPagesBody');
    if (data.per_page_summary && data.per_page_summary.length > 0) {
        crawledCard.style.display = 'block';
        pagesCount.textContent = `${data.per_page_summary.length} page${data.per_page_summary.length !== 1 ? 's' : ''}`;
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

    // Display overall summary
    displayOverallSummary(data);

    // Display security results
    displaySecurity(data.security);

    // Display broken links
    displayBrokenLinks(data.broken_links);

    // Display performance
    displayPerformance(data.performance);

    // Display rendering
    displayRendering(data.rendering);

    // Display improvements
    displayImprovements(data.improvements);

    // Display SEO
    displaySEO(data.seo);

    // Display Accessibility
    displayAccessibility(data.accessibility);

    // Display Mobile Optimization
    displayMobile(data.mobile);

    resultsSection.style.display = 'block';
    resultsSection.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}

function displaySecurity(security) {
    const securityScore = document.getElementById('securityScore');
    const securityPassed = document.getElementById('securityPassed');
    const securityIssues = document.getElementById('securityIssues');

    // Display score
    const score = security.score || 0;
    securityScore.textContent = `Score: ${score}/100`;

    // Display passed checks
    if (security.passed && security.passed.length > 0) {
        securityPassed.innerHTML = '<h4 style="margin-bottom: 15px; color: #4caf50;">✓ Passed Security Checks</h4>' +
            security.passed.map(item => `
                <div class="passed-item">${item}</div>
            `).join('');
    } else {
        securityPassed.innerHTML = '';
    }

    // Display issues
    if (security.issues && security.issues.length > 0) {
        securityIssues.innerHTML = '<h4 style="margin-bottom: 15px; color: #ff9800;">⚠ Security Issues Found</h4>' +
            security.issues.map(issue => `
                <div class="issue-item ${issue.severity}">
                    <span class="issue-severity severity-${issue.severity}">${issue.severity}</span>
                    <div class="issue-title">${issue.issue}</div>
                    <div class="issue-description">${issue.description}</div>
                </div>
            `).join('');
    } else {
        securityIssues.innerHTML = '<div class="passed-item">No security issues found! 🎉</div>';
    }
}

function displayBrokenLinks(brokenLinks) {
    const brokenLinksCount = document.getElementById('brokenLinksCount');
    const linksStats = document.getElementById('linksStats');
    const brokenLinksList = document.getElementById('brokenLinksList');

    const brokenCount = brokenLinks.broken_count || 0;
    const workingCount = brokenLinks.working_count || 0;
    const totalChecked = brokenLinks.total_checked || 0;

    brokenLinksCount.textContent = `${brokenCount} broken`;

    // Display stats
    linksStats.innerHTML = `
        <div class="stat-box">
            <span class="stat-value">${totalChecked}</span>
            <span class="stat-label">Total Links Checked</span>
        </div>
        <div class="stat-box">
            <span class="stat-value" style="color: #4caf50;">${workingCount}</span>
            <span class="stat-label">Working Links</span>
        </div>
        <div class="stat-box">
            <span class="stat-value" style="color: #f44336;">${brokenCount}</span>
            <span class="stat-label">Broken Links</span>
        </div>
    `;

    // Display broken links
    if (brokenLinks.broken && brokenLinks.broken.length > 0) {
        brokenLinksList.innerHTML = '<h4 style="margin-bottom: 15px; color: #f44336;">🔴 Broken Links</h4>' +
            brokenLinks.broken.map(link => `
                <div class="broken-link">
                    <div class="broken-link-url">${link.url}</div>
                    <div class="broken-link-status">
                        <span class="status-code">${link.status_code}</span>
                        <span class="status-reason">${link.reason}</span>
                    </div>
                    ${link.found_on ? `<div class="broken-link-found">Found on: <a href="${link.found_on}" target="_blank">${link.found_on.replace(/^https?:\/\/[^/]+/, '') || '/'}</a></div>` : ''}
                </div>
            `).join('');
    } else {
        brokenLinksList.innerHTML = '<div class="passed-item">No broken links found! All links are working properly. ✓</div>';
    }
}

function displayPerformance(performance) {
    const performanceMetrics = document.getElementById('performanceMetrics');
    const performanceGood = document.getElementById('performanceGood');
    const performanceIssues = document.getElementById('performanceIssues');

    // Display metrics
    performanceMetrics.innerHTML = `
        <div class="metric-box">
            <span class="metric-value">${performance.load_time || 'N/A'}</span>
            <span class="metric-label">Load Time</span>
        </div>
        <div class="metric-box">
            <span class="metric-value">${performance.page_size || 'N/A'}</span>
            <span class="metric-label">Page Size</span>
        </div>
    `;

    // Display good performance items
    if (performance.good && performance.good.length > 0) {
        performanceGood.innerHTML = '<h4 style="margin-bottom: 15px; color: #4caf50;">✓ Good Performance</h4>' +
            performance.good.map(item => `
                <div class="passed-item">${item}</div>
            `).join('');
    } else {
        performanceGood.innerHTML = '';
    }

    // Display issues
    if (performance.issues && performance.issues.length > 0) {
        performanceIssues.innerHTML = '<h4 style="margin-bottom: 15px; color: #ff9800;">⚠ Performance Issues</h4>' +
            performance.issues.map(issue => `
                <div class="issue-item">
                    <div class="issue-title">${issue.issue}</div>
                    <div class="issue-description">${issue.description}</div>
                    ${issue.value !== 'N/A' ? `<div style="margin-top: 5px; color: #667eea; font-weight: bold;">Current: ${issue.value}</div>` : ''}
                </div>
            `).join('');
    } else {
        performanceIssues.innerHTML = '<div class="passed-item">No performance issues found! Site is well optimized. 🚀</div>';
    }
}

function displayImprovements(improvements) {
    const improvementsCount = document.getElementById('improvementsCount');
    const improvementsList = document.getElementById('improvementsList');

    const count = improvements.total_count || 0;
    improvementsCount.textContent = `${count} suggestions`;

    if (improvements.suggestions && improvements.suggestions.length > 0) {
        improvementsList.innerHTML = improvements.suggestions.map(item => `
            <div class="improvement-item">
                <div class="improvement-header">
                    <span class="improvement-category">${item.category}</span>
                    <span class="improvement-priority priority-${item.priority}">${item.priority} priority</span>
                </div>
                <div class="improvement-title">${item.suggestion}</div>
                <div class="improvement-description">${item.description}</div>
            </div>
        `).join('');
    } else {
        improvementsList.innerHTML = '<div class="passed-item">No improvements needed! Your website is in great shape. 🌟</div>';
    }
}

function displaySEO(seo) {
    const seoScore = document.getElementById('seoScore');
    const seoGood = document.getElementById('seoGood');
    const seoIssues = document.getElementById('seoIssues');

    const score = seo.score || 0;
    seoScore.textContent = `Score: ${score}/100`;

    if (seo.good && seo.good.length > 0) {
        seoGood.innerHTML = '<h4 style="margin-bottom: 15px; color: #4caf50;">✓ SEO Strengths</h4>' +
            seo.good.map(item => `
                <div class="passed-item">${item}</div>
            `).join('');
    } else {
        seoGood.innerHTML = '';
    }

    if (seo.issues && seo.issues.length > 0) {
        seoIssues.innerHTML = '<h4 style="margin-bottom: 15px; color: #ff9800;">⚠ SEO Issues</h4>' +
            seo.issues.map(issue => `
                <div class="issue-item">
                    <div class="issue-title">${issue.issue}</div>
                    <div class="issue-description">${issue.description}</div>
                </div>
            `).join('');
    } else {
        seoIssues.innerHTML = '<div class="passed-item">Excellent SEO! No issues found. 🎯</div>';
    }
}

function displayAccessibility(accessibility) {
    const accessibilityScore = document.getElementById('accessibilityScore');
    const accessibilityGood = document.getElementById('accessibilityGood');
    const accessibilityIssues = document.getElementById('accessibilityIssues');

    const score = accessibility.score || 0;
    accessibilityScore.textContent = `Score: ${score}/100`;

    if (accessibility.good && accessibility.good.length > 0) {
        accessibilityGood.innerHTML = '<h4 style="margin-bottom: 15px; color: #4caf50;">✓ Accessibility Features</h4>' +
            accessibility.good.map(item => `
                <div class="passed-item">${item}</div>
            `).join('');
    } else {
        accessibilityGood.innerHTML = '';
    }

    if (accessibility.issues && accessibility.issues.length > 0) {
        accessibilityIssues.innerHTML = '<h4 style="margin-bottom: 15px; color: #ff9800;">⚠ Accessibility Issues</h4>' +
            accessibility.issues.map(issue => `
                <div class="issue-item">
                    <div class="issue-title">${issue.issue}</div>
                    <div class="issue-description">${issue.description}</div>
                </div>
            `).join('');
    } else {
        accessibilityIssues.innerHTML = '<div class="passed-item">Fully accessible! Great job. ♿</div>';
    }
}

function displayMobile(mobile) {
    const mobileScore = document.getElementById('mobileScore');
    const mobileGood = document.getElementById('mobileGood');
    const mobileIssues = document.getElementById('mobileIssues');

    const score = mobile.score || 0;
    mobileScore.textContent = `Score: ${score}/100`;

    if (mobile.good && mobile.good.length > 0) {
        mobileGood.innerHTML = '<h4 style="margin-bottom: 15px; color: #4caf50;">✓ Mobile-Friendly Features</h4>' +
            mobile.good.map(item => `
                <div class="passed-item">${item}</div>
            `).join('');
    } else {
        mobileGood.innerHTML = '';
    }

    if (mobile.issues && mobile.issues.length > 0) {
        mobileIssues.innerHTML = '<h4 style="margin-bottom: 15px; color: #ff9800;">⚠ Mobile Optimization Issues</h4>' +
            mobile.issues.map(issue => `
                <div class="issue-item">
                    <div class="issue-title">${issue.issue}</div>
                    <div class="issue-description">${issue.description}</div>
                </div>
            `).join('');
    } else {
        mobileIssues.innerHTML = '<div class="passed-item">Perfectly optimized for mobile! 📱</div>';
    }
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

    const score = rendering.score || 0;
    renderingScore.textContent = `Score: ${score}/100`;

    if (rendering.good && rendering.good.length > 0) {
        renderingGood.innerHTML = '<h4 style="margin-bottom: 15px; color: #4caf50;">✓ Rendering Checks Passed</h4>' +
            rendering.good.map(item => `
                <div class="passed-item">${item}</div>
            `).join('');
    } else {
        renderingGood.innerHTML = '';
    }

    if (rendering.issues && rendering.issues.length > 0) {
        renderingIssues.innerHTML = '<h4 style="margin-bottom: 15px; color: #ff9800;">⚠ Rendering Issues</h4>' +
            rendering.issues.map(issue => `
                <div class="issue-item ${issue.severity || ''}">
                    ${issue.severity ? `<span class="issue-severity severity-${issue.severity}">${issue.severity}</span>` : ''}
                    <div class="issue-title">${issue.issue}</div>
                    <div class="issue-description">${issue.description}</div>
                </div>
            `).join('');
    } else {
        renderingIssues.innerHTML = '<div class="passed-item">No rendering issues found! Page renders correctly. 🎨</div>';
    }
}

function exportToPdf() {
    // Add print-specific class to body
    document.body.classList.add('printing');

    // Get the analyzed URL for the filename
    const urlElement = document.getElementById('analyzedUrl');
    const analyzedUrl = urlElement ? urlElement.textContent.replace('URL: ', '').trim() : 'website';
    const sanitizedUrl = analyzedUrl.replace(/[^a-zA-Z0-9]/g, '_').substring(0, 50);

    // Store original title
    const originalTitle = document.title;

    // Set document title for PDF filename
    document.title = `Web_Analysis_Report_${sanitizedUrl}`;

    // Trigger print dialog
    window.print();

    // Restore original title after print dialog
    setTimeout(() => {
        document.title = originalTitle;
        document.body.classList.remove('printing');
    }, 1000);
}

// Allow Enter key to trigger analysis
document.addEventListener('DOMContentLoaded', function () {
    document.getElementById('urlInput').addEventListener('keypress', function (event) {
        if (event.key === 'Enter') {
            analyzeWebsite();
        }
    });
});
