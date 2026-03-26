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

function exportToPdf() { window.print(); }

document.addEventListener('DOMContentLoaded', () => {
    const urlInput = document.getElementById('urlInput');
    if (urlInput) {
        urlInput.addEventListener('keypress', (e) => { if (e.key === 'Enter') analyzeWebsite(); });
    }
});
