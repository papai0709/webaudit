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
    errorSection.classList.add('hidden');
    resultsSection.classList.add('hidden');
    loadingSection.classList.remove('hidden');
    
    analyzeBtn.disabled = true;
    analyzeBtn.querySelector('.btn-text').classList.add('hidden');
    analyzeBtn.querySelector('.btn-loader').classList.remove('hidden');

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
        loadingSection.classList.add('hidden');
        analyzeBtn.disabled = false;
        analyzeBtn.querySelector('.btn-text').classList.remove('hidden');
        analyzeBtn.querySelector('.btn-loader').classList.add('hidden');
    }
}

function showError(message) {
    const errorSection = document.getElementById('errorSection');
    const errorMessage = document.getElementById('errorMessage');

    errorMessage.textContent = message;
    errorSection.classList.remove('hidden');
    errorSection.scrollIntoView({ behavior: 'smooth', block: 'center' });
}

function getScoreBadge(score) {
    if (score >= 90) return 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30';
    if (score >= 70) return 'bg-blue-500/20 text-blue-400 border border-blue-500/30';
    if (score >= 50) return 'bg-orange-500/20 text-orange-400 border border-orange-500/30';
    return 'bg-rose-500/20 text-rose-400 border border-rose-500/30';
}

function createProgressRing(name, score, colorClass, dropShadow) {
    const radius = 50;
    const circumference = 2 * Math.PI * radius; // Approx 314
    const offset = circumference - (score / 100) * circumference;
    
    return `
        <div class="flex flex-col items-center gap-4">
            <div class="relative w-28 h-28 flex items-center justify-center">
                <svg class="w-full h-full transform -rotate-90">
                    <circle class="text-white/5" cx="56" cy="56" fill="transparent" r="${radius}" stroke="currentColor" stroke-width="4"></circle>
                    <circle class="${colorClass} ${dropShadow} progress-ring-circle" cx="56" cy="56" fill="transparent" r="${radius}" stroke="currentColor" stroke-dasharray="${circumference}" stroke-dashoffset="${offset}" stroke-linecap="round" stroke-width="4"></circle>
                </svg>
                <span class="absolute text-2xl font-black text-white text-shadow-sm">${score}</span>
            </div>
            <span class="text-[10px] uppercase tracking-[0.2em] ${colorClass} font-black text-center">${name}</span>
        </div>
    `;
}

function displayResults(data) {
    _lastAnalysisData = data;
    const resultsSection = document.getElementById('resultsSection');

    // Header Meta
    document.getElementById('analyzedUrlContainer').textContent = data.url;
    document.getElementById('timestamp').textContent = `Last active: ${data.timestamp}`;
    const pageCount = data.pages_crawled || 1;
    document.getElementById('crawlSummary').textContent = `${pageCount} Page Audited`;

    // Overview Rings
    const overallScores = document.getElementById('overallScores');
    const sections = [
        { name: 'Security', score: data.security?.score || 0, color: 'text-blue-400', shadow: 'drop-shadow-[0_0_8px_rgba(96,165,250,0.6)]' },
        { name: 'SEO', score: data.seo?.score || 0, color: 'text-purple-400', shadow: 'drop-shadow-[0_0_8px_rgba(168,85,247,0.6)]' },
        { name: 'Perf', score: data.performance?.score || 0, color: 'text-cyan-400', shadow: 'drop-shadow-[0_0_8px_rgba(34,211,238,0.6)]' },
        { name: 'Access', score: data.accessibility?.score || 0, color: 'text-orange-400', shadow: 'drop-shadow-[0_0_8px_rgba(251,146,60,0.6)]' },
        { name: 'Mobile', score: data.mobile?.score || 0, color: 'text-emerald-400', shadow: 'drop-shadow-[0_0_8px_rgba(52,211,153,0.6)]' }
    ];
    overallScores.innerHTML = sections.map(s => createProgressRing(s.name, s.score, s.color, s.shadow)).join('');

    // Quick Stats
    document.getElementById('totalLinksChecked').textContent = (data.broken_links?.total_checked || 0).toLocaleString();
    document.getElementById('brokenLinksCount').textContent = (data.broken_links?.broken_count || 0).toLocaleString();

    // Table
    const crawledCard = document.getElementById('crawledPagesCard');
    const pagesCount = document.getElementById('pagesCount');
    const crawledBody = document.getElementById('crawledPagesBody');
    if (data.per_page_summary && data.per_page_summary.length > 0) {
        crawledCard.classList.remove('hidden');
        pagesCount.textContent = `(${data.per_page_summary.length}/${data.per_page_summary.length} Analyzed)`;
        crawledBody.innerHTML = data.per_page_summary.map(p => {
            const short = p.url.replace(/^https?:\/\/[^/]+/, '') || '/';
            return `<tr class="hover:bg-white/[0.04] transition-colors group">
                <td class="px-8 py-5 font-mono text-blue-300 font-semibold truncate max-w-[200px]"><a href="${p.url}" target="_blank" title="${p.url}">${short}</a></td>
                <td class="px-8 py-5"><span class="${getScoreBadge(p.seo_score)} px-3 py-1 rounded-lg text-xs font-black">${p.seo_score}</span></td>
                <td class="px-8 py-5"><span class="${getScoreBadge(p.perf_score)} px-3 py-1 rounded-lg text-xs font-black">${p.perf_score}</span></td>
                <td class="px-8 py-5"><span class="${getScoreBadge(p.acc_score)} px-3 py-1 rounded-lg text-xs font-black">${p.acc_score}</span></td>
                <td class="px-8 py-5"><span class="${getScoreBadge(p.mob_score)} px-3 py-1 rounded-lg text-xs font-black">${p.mob_score}</span></td>
                <td class="px-8 py-5 font-bold ${p.broken_count > 0 ? 'text-rose-400' : 'text-on-surface-variant'}">${p.broken_count} Broken</td>
            </tr>`;
        }).join('');
    } else {
        crawledCard.classList.add('hidden');
    }

    // Detail Sections
    displaySection('security', data.security, 'text-blue-400', 'bg-blue-500/20 text-blue-300 border border-blue-500/30');
    displayPerformanceSection(data.performance);
    displaySection('seo', data.seo, 'text-emerald-400', 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/30');
    displaySection('accessibility', data.accessibility, 'text-orange-400', 'bg-orange-500/20 text-orange-300 border border-orange-500/30');
    displaySection('mobile', data.mobile, 'text-emerald-400', 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/30');
    
    // Improvements
    const improvementsList = document.getElementById('improvementsList');
    if (data.improvements?.suggestions) {
        improvementsList.innerHTML = data.improvements.suggestions.map(s => `
            <div class="p-6 bg-white/[0.03] rounded-2xl border border-white/5 hover:border-white/10 transition-colors">
                <div class="flex justify-between items-start mb-4">
                    <span class="px-3 py-1 bg-white/5 rounded-full text-[9px] uppercase font-black tracking-widest text-on-surface-variant">${s.category}</span>
                    <span class="text-[9px] font-black tracking-widest uppercase ${s.priority === 'high' ? 'text-rose-400' : 'text-purple-400'}">${s.priority} PRO</span>
                </div>
                <h5 class="font-black text-white mb-2 leading-tight">${s.suggestion}</h5>
                <p class="text-xs text-on-surface-variant leading-relaxed opacity-70">${s.description}</p>
            </div>
        `).join('');
    }

    resultsSection.classList.remove('hidden');
    resultsSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

function displaySection(id, sectionData, iconColor, badgeClass) {
    const scoreEl = document.getElementById(`${id}Score`);
    const badgeEl = document.getElementById(`${id}Badge`);
    const resultsEl = document.getElementById(`${id}Results`);

    if (!sectionData) return;

    if (scoreEl) scoreEl.textContent = `Score: ${sectionData.score}/100`;
    if (badgeEl) {
        badgeEl.className = `${badgeClass} px-4 py-1 rounded-full text-[10px] font-black tracking-widest`;
        badgeEl.textContent = sectionData.score >= 90 ? 'OPTIMIZED' : (sectionData.score >= 50 ? 'STABLE' : 'CRITICAL');
    }

    let html = '';
    if (sectionData.passed) {
        html += sectionData.passed.map(item => `
            <div class="flex items-center gap-3 text-xs text-on-surface font-medium">
                <span class="material-symbols-outlined text-emerald-400 text-xl" style="font-variation-settings: 'FILL' 1">verified</span>
                ${item}
            </div>
        `).join('');
    }
    if (sectionData.issues) {
        html += sectionData.issues.map(issue => `
            <div class="flex items-start gap-3 p-3 bg-white/[0.03] rounded-xl border border-white/5">
                <span class="material-symbols-outlined text-rose-500 text-xl" style="font-variation-settings: 'FILL' 1">report</span>
                <div>
                    <div class="font-bold text-white text-xs">${issue.issue || issue}</div>
                    ${issue.description ? `<div class="text-[10px] text-on-surface-variant opacity-70 mt-1">${issue.description}</div>` : ''}
                </div>
            </div>
        `).join('');
    }
    resultsEl.innerHTML = html;
}

function displayPerformanceSection(perf) {
    const metricsEl = document.getElementById('performanceMetrics');
    if (metricsEl) {
        metricsEl.innerHTML = `
            <div class="flex-1 p-4 bg-white/[0.03] rounded-xl border border-white/5 text-center">
                <div class="text-xl font-black text-white">${perf.load_time || 'N/A'}</div>
                <div class="text-[9px] text-on-surface-variant font-black uppercase tracking-widest mt-1">Velocity</div>
            </div>
            <div class="flex-1 p-4 bg-white/[0.03] rounded-xl border border-white/5 text-center">
                <div class="text-xl font-black text-white">${perf.page_size || 'N/A'}</div>
                <div class="text-[9px] text-on-surface-variant font-black uppercase tracking-widest mt-1">Weight</div>
            </div>
        `;
    }
    displaySection('performance', perf, 'text-purple-400', 'bg-purple-500/20 text-purple-300 border border-purple-500/30');
}

// ── Cached analysis data for export ──────────────────────────────
let _lastAnalysisData = null;

function exportToPdf() {
    if (!_lastAnalysisData) {
        alert('No analysis data to export. Please analyze a website first.');
        return;
    }
    const data = _lastAnalysisData;

    // ── Helper: score colour palette ─────────────────────────────
    const scoreColor = (s) => {
        if (s >= 90) return { bg: 'rgba(52,211,153,0.15)', border: 'rgba(52,211,153,0.4)', text: '#34d399', ring: '#34d399', label: 'OPTIMIZED' };
        if (s >= 70) return { bg: 'rgba(96,165,250,0.15)', border: 'rgba(96,165,250,0.4)', text: '#60a5fa', ring: '#60a5fa', label: 'STABLE' };
        if (s >= 50) return { bg: 'rgba(251,146,60,0.15)', border: 'rgba(251,146,60,0.4)', text: '#fb923c', ring: '#fb923c', label: 'NEEDS WORK' };
        return { bg: 'rgba(251,113,133,0.15)', border: 'rgba(251,113,133,0.4)', text: '#fb7185', ring: '#fb7185', label: 'CRITICAL' };
    };

    // ── Helper: SVG progress ring ────────────────────────────────
    const progressRing = (label, score, color) => {
        const r = 40, c = 2 * Math.PI * r, off = c - (score / 100) * c;
        return `
        <div style="display:flex;flex-direction:column;align-items:center;gap:10px;">
            <div style="position:relative;width:96px;height:96px;">
                <svg viewBox="0 0 96 96" style="transform:rotate(-90deg);width:100%;height:100%;">
                    <circle cx="48" cy="48" r="${r}" fill="none" stroke="rgba(255,255,255,0.06)" stroke-width="5"/>
                    <circle cx="48" cy="48" r="${r}" fill="none" stroke="${color}" stroke-width="5"
                        stroke-dasharray="${c}" stroke-dashoffset="${off}" stroke-linecap="round"
                        style="filter:drop-shadow(0 0 6px ${color})"/>
                </svg>
                <span style="position:absolute;inset:0;display:flex;align-items:center;justify-content:center;font-size:22px;font-weight:900;color:#fff;">${score}</span>
            </div>
            <span style="font-size:9px;text-transform:uppercase;letter-spacing:0.2em;font-weight:800;color:${color};">${label}</span>
        </div>`;
    };

    // ── Helper: section card ─────────────────────────────────────
    const sectionCard = (icon, title, gradientColors, sectionData) => {
        if (!sectionData) return '';
        const sc = scoreColor(sectionData.score);
        let items = '';
        if (sectionData.passed) {
            items += sectionData.passed.map(p => `
                <div style="display:flex;align-items:center;gap:10px;padding:10px 14px;border-radius:10px;background:rgba(52,211,153,0.06);border:1px solid rgba(52,211,153,0.12);margin-bottom:8px;">
                    <span style="color:#34d399;font-size:16px;">✓</span>
                    <span style="font-size:12px;color:#d1d5db;">${p}</span>
                </div>`).join('');
        }
        if (sectionData.issues) {
            items += sectionData.issues.map(issue => {
                const issueText = issue.issue || issue;
                const desc = issue.description || '';
                return `
                <div style="display:flex;align-items:flex-start;gap:10px;padding:12px 14px;border-radius:10px;background:rgba(251,113,133,0.06);border:1px solid rgba(251,113,133,0.12);margin-bottom:8px;">
                    <span style="color:#fb7185;font-size:16px;margin-top:1px;">⚠</span>
                    <div>
                        <div style="font-size:12px;font-weight:700;color:#fff;">${issueText}</div>
                        ${desc ? `<div style="font-size:11px;color:#9ca3af;margin-top:4px;">${desc}</div>` : ''}
                    </div>
                </div>`;
            }).join('');
        }
        return `
        <div style="background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.08);border-radius:16px;overflow:hidden;page-break-inside:avoid;margin-bottom:24px;">
            <div style="height:4px;background:linear-gradient(90deg,${gradientColors});"></div>
            <div style="padding:28px;">
                <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:20px;">
                    <div style="display:flex;align-items:center;gap:12px;">
                        <span style="font-size:28px;">${icon}</span>
                        <span style="font-size:18px;font-weight:800;color:#fff;">${title}</span>
                    </div>
                    <div style="display:flex;flex-direction:column;align-items:flex-end;gap:4px;">
                        <span style="padding:4px 14px;border-radius:999px;font-size:9px;font-weight:900;letter-spacing:0.15em;background:${sc.bg};color:${sc.text};border:1px solid ${sc.border};">${sc.label}</span>
                        <span style="font-size:10px;color:#9ca3af;font-weight:600;">Score: ${sectionData.score}/100</span>
                    </div>
                </div>
                ${items}
            </div>
        </div>`;
    };

    // ── Helper: performance metrics ──────────────────────────────
    const perfMetrics = (perf) => {
        if (!perf) return '';
        return `
        <div style="display:flex;gap:16px;margin-bottom:16px;">
            <div style="flex:1;padding:16px;text-align:center;background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.08);border-radius:12px;">
                <div style="font-size:20px;font-weight:900;color:#fff;">${perf.load_time || 'N/A'}</div>
                <div style="font-size:9px;color:#9ca3af;font-weight:800;text-transform:uppercase;letter-spacing:0.15em;margin-top:6px;">Velocity</div>
            </div>
            <div style="flex:1;padding:16px;text-align:center;background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.08);border-radius:12px;">
                <div style="font-size:20px;font-weight:900;color:#fff;">${perf.page_size || 'N/A'}</div>
                <div style="font-size:9px;color:#9ca3af;font-weight:800;text-transform:uppercase;letter-spacing:0.15em;margin-top:6px;">Weight</div>
            </div>
        </div>`;
    };

    // ── Helper: crawled pages table ──────────────────────────────
    const pagesTable = () => {
        if (!data.per_page_summary || !data.per_page_summary.length) return '';
        const rows = data.per_page_summary.map(p => {
            const short = p.url.replace(/^https?:\/\/[^/]+/, '') || '/';
            const cell = (score) => {
                const c = scoreColor(score);
                return `<td style="padding:12px 16px;"><span style="padding:4px 12px;border-radius:8px;font-size:11px;font-weight:900;background:${c.bg};color:${c.text};border:1px solid ${c.border};">${score}</span></td>`;
            };
            return `<tr style="border-bottom:1px solid rgba(255,255,255,0.05);">
                <td style="padding:12px 16px;font-family:monospace;font-size:12px;color:#60a5fa;font-weight:600;max-width:220px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;" title="${p.url}">${short}</td>
                ${cell(p.seo_score)}${cell(p.perf_score)}${cell(p.acc_score)}${cell(p.mob_score)}
                <td style="padding:12px 16px;font-weight:700;font-size:12px;color:${p.broken_count > 0 ? '#fb7185' : '#9ca3af'};">${p.broken_count} Broken</td>
            </tr>`;
        }).join('');

        return `
        <div style="background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.08);border-radius:16px;overflow:hidden;margin-bottom:24px;">
            <div style="padding:24px 28px;border-bottom:1px solid rgba(255,255,255,0.05);display:flex;align-items:center;gap:10px;">
                <div style="width:4px;height:20px;background:#a855f7;border-radius:4px;"></div>
                <span style="font-size:16px;font-weight:800;color:#fff;">Pages Audited</span>
                <span style="font-size:12px;color:#9ca3af;">(${data.per_page_summary.length})</span>
            </div>
            <table style="width:100%;border-collapse:collapse;font-size:13px;">
                <thead>
                    <tr style="background:rgba(0,0,0,0.3);">
                        <th style="padding:14px 16px;text-align:left;font-size:9px;font-weight:900;text-transform:uppercase;letter-spacing:0.15em;color:#9ca3af;">Target URL</th>
                        <th style="padding:14px 16px;text-align:left;font-size:9px;font-weight:900;text-transform:uppercase;letter-spacing:0.15em;color:#9ca3af;">SEO</th>
                        <th style="padding:14px 16px;text-align:left;font-size:9px;font-weight:900;text-transform:uppercase;letter-spacing:0.15em;color:#9ca3af;">Perf</th>
                        <th style="padding:14px 16px;text-align:left;font-size:9px;font-weight:900;text-transform:uppercase;letter-spacing:0.15em;color:#9ca3af;">Access</th>
                        <th style="padding:14px 16px;text-align:left;font-size:9px;font-weight:900;text-transform:uppercase;letter-spacing:0.15em;color:#9ca3af;">Mobile</th>
                        <th style="padding:14px 16px;text-align:left;font-size:9px;font-weight:900;text-transform:uppercase;letter-spacing:0.15em;color:#9ca3af;">Links</th>
                    </tr>
                </thead>
                <tbody>${rows}</tbody>
            </table>
        </div>`;
    };

    // ── Helper: improvements ─────────────────────────────────────
    const improvementsGrid = () => {
        if (!data.improvements?.suggestions?.length) return '';
        const cards = data.improvements.suggestions.map(s => `
            <div style="flex:1;min-width:260px;padding:20px;background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.06);border-radius:14px;">
                <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px;">
                    <span style="padding:3px 10px;border-radius:999px;font-size:8px;font-weight:900;letter-spacing:0.15em;text-transform:uppercase;background:rgba(255,255,255,0.05);color:#9ca3af;">${s.category}</span>
                    <span style="font-size:8px;font-weight:900;letter-spacing:0.15em;text-transform:uppercase;color:${s.priority === 'high' ? '#fb7185' : '#c084fc'};">${s.priority} PRI</span>
                </div>
                <div style="font-size:13px;font-weight:800;color:#fff;margin-bottom:6px;line-height:1.4;">${s.suggestion}</div>
                <div style="font-size:11px;color:#6b7280;line-height:1.5;">${s.description}</div>
            </div>`).join('');

        return `
        <div style="background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.08);border-radius:16px;padding:28px;margin-bottom:24px;page-break-inside:avoid;">
            <div style="display:flex;align-items:center;gap:12px;margin-bottom:24px;">
                <span style="font-size:28px;">💡</span>
                <span style="font-size:20px;font-weight:900;color:#fff;">Strategic Improvements</span>
            </div>
            <div style="display:flex;flex-wrap:wrap;gap:16px;">${cards}</div>
        </div>`;
    };

    // ── Scores ───────────────────────────────────────────────────
    const scores = [
        { name: 'Security', score: data.security?.score || 0, color: '#60a5fa' },
        { name: 'SEO',      score: data.seo?.score || 0,      color: '#c084fc' },
        { name: 'Perf',     score: data.performance?.score || 0, color: '#22d3ee' },
        { name: 'Access',   score: data.accessibility?.score || 0, color: '#fb923c' },
        { name: 'Mobile',   score: data.mobile?.score || 0,   color: '#34d399' },
    ];

    const pageCount = data.pages_crawled || 1;
    const totalLinks = data.broken_links?.total_checked || 0;
    const brokenLinks = data.broken_links?.broken_count || 0;
    const now = data.timestamp || new Date().toLocaleString();

    // ── Build HTML document ──────────────────────────────────────
    const html = `<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8"/>
    <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
    <title>Web Audit Report — ${data.url}</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&display=swap" rel="stylesheet"/>
    <link href="https://fonts.googleapis.com/css2?family=Bungee&display=swap" rel="stylesheet"/>
    <style>
        * { margin:0; padding:0; box-sizing:border-box; }
        html, body {
            font-family: 'Inter', sans-serif;
            background: #050505;
            color: #ffffff;
            -webkit-print-color-adjust: exact !important;
            print-color-adjust: exact !important;
        }
        @page {
            size: A4;
            margin: 12mm 14mm;
        }
        @media print {
            html, body { background: #050505 !important; color: #ffffff !important; }
            .no-print { display: none !important; }
            .page-break { page-break-before: always; }
        }
        .bungee { font-family: 'Bungee', cursive; }
    </style>
</head>
<body>

<!-- ─── Cover Page ─────────────────────────────────────────────── -->
<div style="min-height:100vh;display:flex;flex-direction:column;justify-content:center;align-items:center;text-align:center;padding:60px 40px;background:radial-gradient(ellipse at 20% 20%, rgba(59,130,246,0.25) 0%, transparent 50%), radial-gradient(ellipse at 80% 30%, rgba(168,85,247,0.2) 0%, transparent 50%), radial-gradient(ellipse at 50% 90%, rgba(34,211,238,0.15) 0%, transparent 50%), #050505;">
    <div style="margin-bottom:40px;">
        <div style="width:60px;height:4px;border-radius:4px;background:linear-gradient(90deg,#3b82f6,#8b5cf6,#22d3ee);margin:0 auto 24px auto;"></div>
    </div>
    <h1 class="bungee" style="font-size:52px;letter-spacing:2px;color:#c4b5fd;margin-bottom:16px;">WEB AUDIT</h1>
    <p style="font-size:14px;color:#9ca3af;letter-spacing:0.15em;text-transform:uppercase;font-weight:700;margin-bottom:48px;">Professional Intelligence Report</p>

    <div style="background:rgba(255,255,255,0.04);border:1px solid rgba(255,255,255,0.08);border-radius:16px;padding:28px 40px;max-width:520px;width:100%;margin-bottom:48px;">
        <div style="font-size:10px;color:#6b7280;text-transform:uppercase;letter-spacing:0.15em;font-weight:700;margin-bottom:8px;">Analyzed URL</div>
        <div style="font-family:monospace;font-size:15px;color:#60a5fa;font-weight:600;word-break:break-all;">${data.url}</div>
        <div style="margin-top:16px;display:flex;justify-content:center;gap:32px;">
            <div>
                <div style="font-size:10px;color:#6b7280;text-transform:uppercase;letter-spacing:0.1em;font-weight:700;">Pages Crawled</div>
                <div style="font-size:22px;font-weight:900;color:#fff;margin-top:4px;">${pageCount}</div>
            </div>
            <div style="width:1px;background:rgba(255,255,255,0.1);"></div>
            <div>
                <div style="font-size:10px;color:#6b7280;text-transform:uppercase;letter-spacing:0.1em;font-weight:700;">Links Checked</div>
                <div style="font-size:22px;font-weight:900;color:#fff;margin-top:4px;">${totalLinks.toLocaleString()}</div>
            </div>
            <div style="width:1px;background:rgba(255,255,255,0.1);"></div>
            <div>
                <div style="font-size:10px;color:#6b7280;text-transform:uppercase;letter-spacing:0.1em;font-weight:700;">Broken Links</div>
                <div style="font-size:22px;font-weight:900;color:${brokenLinks > 0 ? '#fb7185' : '#34d399'};margin-top:4px;">${brokenLinks}</div>
            </div>
        </div>
    </div>

    <div style="font-size:11px;color:#4b5563;">Generated on ${now}</div>
    <div style="font-size:10px;color:#374151;margin-top:4px;">Engine v2.4.0 · Powered by Luminous Observer Intelligence</div>
</div>

<!-- ─── Scores Overview ────────────────────────────────────────── -->
<div class="page-break"></div>
<div style="padding:48px 40px;">
    <div style="display:flex;align-items:center;gap:10px;margin-bottom:32px;">
        <div style="width:4px;height:24px;background:#3b82f6;border-radius:4px;"></div>
        <h2 style="font-size:22px;font-weight:800;">Ecosystem Health Overview</h2>
    </div>
    <div style="display:flex;justify-content:space-around;flex-wrap:wrap;gap:24px;background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.08);border-radius:16px;padding:36px 24px;">
        ${scores.map(s => progressRing(s.name, s.score, s.color)).join('')}
    </div>

    <!-- Quick Stats -->
    <div style="display:flex;gap:16px;margin-top:24px;">
        <div style="flex:1;background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.08);border-radius:16px;padding:24px;">
            <div style="font-size:9px;text-transform:uppercase;letter-spacing:0.15em;font-weight:900;color:#9ca3af;margin-bottom:8px;">Total Checked</div>
            <div style="font-size:32px;font-weight:900;color:#fff;">${totalLinks.toLocaleString()}</div>
        </div>
        <div style="flex:1;background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.08);border-radius:16px;padding:24px;">
            <div style="font-size:9px;text-transform:uppercase;letter-spacing:0.15em;font-weight:900;color:#9ca3af;margin-bottom:8px;">Broken Links</div>
            <div style="font-size:32px;font-weight:900;color:${brokenLinks > 0 ? '#fb7185' : '#34d399'};">${brokenLinks}</div>
        </div>
    </div>
</div>

<!-- ─── Pages Audited Table ────────────────────────────────────── -->
<div class="page-break"></div>
<div style="padding:48px 40px;">
    ${pagesTable()}
</div>

<!-- ─── Detail Sections ────────────────────────────────────────── -->
<div class="page-break"></div>
<div style="padding:48px 40px;">
    ${sectionCard('🛡️', 'Security Protocol', '#2563eb, #60a5fa, #22d3ee', data.security)}
    ${perfMetrics(data.performance)}
    ${sectionCard('⚡', 'Performance Audit', '#9333ea, #c084fc, #f472b6', data.performance)}
    ${sectionCard('🔎', 'SEO Integrity', '#0d9488, #34d399, #60a5fa', data.seo)}
    ${sectionCard('♿', 'Accessibility', '#ea580c, #fb923c, #fbbf24', data.accessibility)}
    ${sectionCard('📱', 'Mobile Optimisation', '#059669, #34d399, #22d3ee', data.mobile)}
</div>

<!-- ─── Improvements ───────────────────────────────────────────── -->
<div class="page-break"></div>
<div style="padding:48px 40px;">
    ${improvementsGrid()}
</div>

<!-- ─── Footer ─────────────────────────────────────────────────── -->
<div style="padding:40px;border-top:1px solid rgba(255,255,255,0.06);text-align:center;margin-top:40px;">
    <div style="font-size:9px;font-weight:900;text-transform:uppercase;letter-spacing:0.3em;color:#4b5563;">
        Web Audit © 2026 <span style="margin:0 8px;color:rgba(255,255,255,0.1);">|</span> Precision Intelligent Systems <span style="margin:0 8px;color:rgba(255,255,255,0.1);">|</span> Made with ❤️ by Jay
    </div>
</div>

<!-- ─── Auto-print trigger ─────────────────────────────────────── -->
<div class="no-print" style="position:fixed;bottom:24px;right:24px;z-index:100;">
    <button onclick="window.print()" style="padding:14px 28px;background:linear-gradient(135deg,#3b82f6,#8b5cf6);color:#fff;font-weight:800;font-size:13px;border:none;border-radius:12px;cursor:pointer;box-shadow:0 8px 24px rgba(59,130,246,0.4);letter-spacing:0.05em;">
        📄 Save as PDF
    </button>
</div>
<script>
    window.onload = function() { document.fonts.ready.then(function() { setTimeout(function() { window.print(); }, 400); }); };
</script>
</body>
</html>`;

    const reportWindow = window.open('', '_blank');
    if (reportWindow) {
        reportWindow.document.write(html);
        reportWindow.document.close();
    } else {
        alert('Pop-up blocked. Please allow pop-ups for this site to export the report.');
    }
}

document.addEventListener('DOMContentLoaded', () => {
    const urlInput = document.getElementById('urlInput');
    if (urlInput) {
        urlInput.addEventListener('keypress', (e) => { if (e.key === 'Enter') analyzeWebsite(); });
    }
});
