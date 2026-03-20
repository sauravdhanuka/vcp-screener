/* ==========================================================================
   VCP Screener — Client-side JavaScript
   ========================================================================== */

// ---------------------------------------------------------------------------
// Toast Notification System
// ---------------------------------------------------------------------------

/**
 * Show a toast notification.
 * @param {string} message - Text to display.
 * @param {'success'|'error'|'info'} type - Toast style.
 * @param {number} duration - Auto-dismiss in milliseconds.
 */
function showToast(message, type = 'success', duration = 3000) {
    const container = document.getElementById('toast-container');
    if (!container) return;

    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.textContent = message;
    container.appendChild(toast);

    // Auto-remove after duration
    setTimeout(() => {
        toast.classList.add('toast-removing');
        toast.addEventListener('animationend', () => toast.remove());
    }, duration);
}

// ---------------------------------------------------------------------------
// HTMX Event Listeners
// ---------------------------------------------------------------------------

// Show toast from HX-Trigger response header
// Server can send: HX-Trigger: {"showToast": {"message": "Done!", "type": "success"}}
document.addEventListener('showToast', function (evt) {
    const detail = evt.detail || {};
    showToast(detail.message || 'Done', detail.type || 'success');
});

// Generic after-swap handler: check for toast headers
document.addEventListener('htmx:afterSwap', function (evt) {
    const trigger = evt.detail.xhr?.getResponseHeader('HX-Trigger');
    if (trigger) {
        try {
            const parsed = JSON.parse(trigger);
            if (parsed.showToast) {
                showToast(parsed.showToast.message, parsed.showToast.type);
            }
        } catch (_) {
            // Not JSON, ignore
        }
    }
});

// Show error toast on request failure
document.addEventListener('htmx:responseError', function (evt) {
    showToast('Request failed. Please try again.', 'error');
});

// ---------------------------------------------------------------------------
// Tab Switching Helper
// ---------------------------------------------------------------------------

/**
 * Activate a tab and load its content via HTMX.
 * Tabs should have [data-tab] attribute, panels should have [data-tab-panel].
 * @param {string} tabGroup - The tab group name (e.g. 'portfolio').
 * @param {string} tabName - The tab to activate.
 */
function switchTab(tabGroup, tabName) {
    // Update tab button styles
    document.querySelectorAll(`[data-tab-group="${tabGroup}"] [data-tab]`).forEach(btn => {
        if (btn.dataset.tab === tabName) {
            btn.classList.add('border-accent-blue', 'text-white');
            btn.classList.remove('border-transparent', 'text-text-muted');
        } else {
            btn.classList.remove('border-accent-blue', 'text-white');
            btn.classList.add('border-transparent', 'text-text-muted');
        }
    });

    // Show/hide panels (for non-HTMX tabs)
    document.querySelectorAll(`[data-tab-group="${tabGroup}"] [data-tab-panel]`).forEach(panel => {
        if (panel.dataset.tabPanel === tabName) {
            panel.classList.remove('hidden');
        } else {
            panel.classList.add('hidden');
        }
    });
}

// ---------------------------------------------------------------------------
// Chart.js — Nifty Chart Initialization
// ---------------------------------------------------------------------------

/**
 * Initialize a Nifty 50 line chart on the market page.
 * @param {string} canvasId - The canvas element ID.
 * @param {Array<{date: string, close: number}>} data - Nifty price data.
 */
function initNiftyChart(canvasId, data) {
    const canvas = document.getElementById(canvasId);
    if (!canvas || !data || data.length === 0) return;

    const ctx = canvas.getContext('2d');

    // Compute SMA-50 and SMA-200
    const closes = data.map(d => d.close);
    const sma50 = computeSMA(closes, 50);
    const sma200 = computeSMA(closes, 200);

    new Chart(ctx, {
        type: 'line',
        data: {
            labels: data.map(d => d.date),
            datasets: [
                {
                    label: 'Nifty 50',
                    data: closes,
                    borderColor: '#c9d1d9',
                    backgroundColor: 'rgba(201, 209, 217, 0.05)',
                    borderWidth: 1.5,
                    pointRadius: 0,
                    fill: true,
                    tension: 0.1,
                },
                {
                    label: 'SMA 50',
                    data: sma50,
                    borderColor: '#79c0ff',
                    borderWidth: 1,
                    pointRadius: 0,
                    borderDash: [],
                },
                {
                    label: 'SMA 200',
                    data: sma200,
                    borderColor: '#d2a8ff',
                    borderWidth: 1,
                    pointRadius: 0,
                    borderDash: [4, 2],
                },
            ],
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: {
                mode: 'index',
                intersect: false,
            },
            plugins: {
                legend: {
                    position: 'top',
                    labels: {
                        color: '#8b949e',
                        usePointStyle: true,
                        pointStyle: 'line',
                        font: { size: 11 },
                    },
                },
                tooltip: {
                    backgroundColor: '#161b22',
                    titleColor: '#c9d1d9',
                    bodyColor: '#8b949e',
                    borderColor: '#21262d',
                    borderWidth: 1,
                },
            },
            scales: {
                x: {
                    ticks: {
                        color: '#8b949e',
                        maxTicksLimit: 12,
                        font: { size: 10 },
                    },
                    grid: { color: '#21262d' },
                },
                y: {
                    ticks: {
                        color: '#8b949e',
                        font: { size: 10 },
                    },
                    grid: { color: '#21262d' },
                },
            },
        },
    });
}

/**
 * Compute Simple Moving Average.
 * @param {number[]} data - Array of values.
 * @param {number} period - SMA period.
 * @returns {(number|null)[]} SMA values (null where insufficient data).
 */
function computeSMA(data, period) {
    const result = [];
    for (let i = 0; i < data.length; i++) {
        if (i < period - 1) {
            result.push(null);
        } else {
            let sum = 0;
            for (let j = i - period + 1; j <= i; j++) {
                sum += data[j];
            }
            result.push(sum / period);
        }
    }
    return result;
}

// ---------------------------------------------------------------------------
// Clickable Table Rows
// ---------------------------------------------------------------------------

document.addEventListener('click', function (evt) {
    const row = evt.target.closest('tr[data-href]');
    if (row) {
        window.location.href = row.dataset.href;
    }
});

// ---------------------------------------------------------------------------
// Sidebar mobile toggle sync
// ---------------------------------------------------------------------------

document.addEventListener('click', function (evt) {
    const sidebar = document.getElementById('sidebar');
    const overlay = document.getElementById('sidebar-overlay');
    const toggle = document.getElementById('sidebar-toggle');

    if (!sidebar || !overlay) return;

    // When sidebar opens, show overlay
    if (toggle && toggle.contains(evt.target)) {
        const isHidden = sidebar.classList.contains('-translate-x-full');
        if (isHidden) {
            overlay.classList.remove('hidden');
        } else {
            overlay.classList.add('hidden');
        }
    }
});
