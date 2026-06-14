// ======================= GLOBAL STATE & CONFIG =======================
const API_BASE_URL = window.location.origin.includes('localhost') || window.location.origin.includes('127.0.0.1')
    ? 'http://127.0.0.1:8000'
    : window.location.origin + '/request';

let currentOwnerKey = '';
let registeredUsers = [];

// ======================= SPA ROUTER =======================
function navigate(hash) {
    window.location.hash = hash;
}

function handleRouting() {
    const hash = window.location.hash || '#home';
    document.querySelectorAll('.page-view').forEach(p => {
        p.classList.toggle('active', `#${p.id}` === hash);
    });
    document.querySelectorAll('.nav-links a').forEach(a => {
        a.classList.toggle('active', a.getAttribute('href') === hash);
    });
    window.scrollTo(0, 0);
}

window.addEventListener('hashchange', handleRouting);

// ======================= BOOT =======================
document.addEventListener('DOMContentLoaded', () => {
    handleRouting();
    initHeroDemo();
    initPasswordToggle();
    initSignup();
    initLogin();
    checkStoredSession();
});

// ======================= TOAST =======================
function showToast(message, type = 'info') {
    const container = document.getElementById('toastContainer');
    if (!container) return;
    const icons = { success: '✓', error: '⚠', info: '⚡' };
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.innerHTML = `
        <div class="toast-icon">${icons[type] || '⚡'}</div>
        <div class="toast-message">${message}</div>
        <div class="toast-progress"></div>
    `;
    container.appendChild(toast);
    const bar = toast.querySelector('.toast-progress');
    bar.style.transition = 'width 3500ms linear';
    bar.style.width = '100%';
    setTimeout(() => { bar.style.width = '0%'; }, 50);
    setTimeout(() => {
        toast.style.animation = 'slideInRight 0.25s reverse forwards';
        setTimeout(() => toast.remove(), 260);
    }, 3500);
}

// ======================= API CALL =======================
async function apiCall(endpoint, options = {}) {
    const url = `${API_BASE_URL}${endpoint}`;
    try {
        const res = await fetch(url, {
            headers: { 'Content-Type': 'application/json', ...options.headers },
            ...options
        });
        if (!res.ok) {
            const err = await res.json().catch(() => ({ detail: res.statusText }));
            throw new Error(err.detail || `HTTP ${res.status}`);
        }
        return await res.json();
    } catch (e) {
        throw e;
    }
}

// ======================= COPY =======================
function copyToClipboard(text, label = 'Copied') {
    navigator.clipboard.writeText(text).then(() => showToast(`${label} copied!`, 'success'));
}

// ======================= PASSWORD TOGGLE =======================
function initPasswordToggle() {
    const btn = document.getElementById('togglePasswordBtn');
    const input = document.getElementById('ownerKeyInput');
    if (!btn || !input) return;
    btn.addEventListener('click', () => {
        const isPass = input.type === 'password';
        input.type = isPass ? 'text' : 'password';
        btn.textContent = isPass ? 'Hide' : 'Show';
    });
}

// ======================= HERO DEMO =======================
const HERO_DATA = {
    sales: {
        request: `{
  "action": "sales",
  "item": "Laptop",
  "qty": 2,
  "selling_price": 1200
}`,
        journal: [
            { type: 'debit',  account: 'Cash',          value: '$2,400.00' },
            { type: 'credit', account: 'Sales Revenue',  value: '$2,400.00' },
            { type: 'debit',  account: 'COGS',           value: '$1,000.00' },
            { type: 'credit', account: 'Inventory',      value: '$1,000.00' }
        ]
    },
    purchase: {
        request: `{
  "action": "purchase",
  "item": "Keyboard",
  "qty": 10,
  "unit_cost": 25
}`,
        journal: [
            { type: 'debit',  account: 'Inventory',  value: '$250.00' },
            { type: 'credit', account: 'Cash',        value: '$250.00' }
        ]
    },
    initialize: {
        request: `{
  "action": "initialize",
  "inventory": ["Widget"],
  "qty": [100],
  "unit_cost": [5],
  "asset": ["Cash"],
  "value": [5000]
}`,
        journal: [
            { type: 'debit',  account: 'Inventory',       value: '$500.00' },
            { type: 'credit', account: "Owner's Equity",   value: '$500.00' },
            { type: 'debit',  account: 'Cash',             value: '$5,000.00' },
            { type: 'credit', account: "Owner's Equity",   value: '$5,000.00' }
        ]
    }
};

function highlight(json) {
    return json
        .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
        .replace(/(\"[\w\s]+\"\s*:)/g, '<span class="code-key">$1</span>')
        .replace(/:\s*(\"[^\"]*\")/g, ': <span class="code-string">$1</span>')
        .replace(/:\s*(\d+\.?\d*)/g, ': <span class="code-number">$1</span>');
}

function initHeroDemo() {
    const tabs = document.querySelectorAll('.hero-tab-btn');
    const reqCode = document.getElementById('heroRequestCode');
    const journalList = document.getElementById('heroJournalList');
    if (!reqCode || !journalList) return;

    function loadDemo(id) {
        const d = HERO_DATA[id];
        if (!d) return;
        reqCode.innerHTML = highlight(d.request);
        journalList.innerHTML = '';
        d.journal.forEach((row, i) => {
            const el = document.createElement('div');
            el.className = `ledger-row ${row.type}`;
            el.style.animationDelay = `${i * 80}ms`;
            el.innerHTML = `
                <div>
                    <span class="badge" style="margin-right:8px;font-size:0.7rem;">${row.type.toUpperCase()}</span>
                    <span class="ledger-account">${row.account}</span>
                </div>
                <div class="ledger-val">${row.value}</div>`;
            journalList.appendChild(el);
        });
    }

    tabs.forEach(tab => tab.addEventListener('click', () => {
        tabs.forEach(t => t.classList.remove('active'));
        tab.classList.add('active');
        loadDemo(tab.dataset.demo);
    }));
    loadDemo('sales');
}

// ======================= SIGNUP (REGISTRATION) =======================
function initSignup() {
    const btn = document.getElementById('signUpBtn');
    if (!btn) return;

    btn.addEventListener('click', async () => {
        const entity = document.getElementById('signupEntityInput')?.value.trim();
        const ownerName = document.getElementById('signupOwnerNameInput')?.value.trim();

        if (!entity) { showToast('App / Organization name is required.', 'error'); return; }
        if (!ownerName) { showToast('Your name is required.', 'error'); return; }

        btn.disabled = true;
        btn.textContent = 'Creating account...';

        try {
            const res = await apiCall(`/register?entity=${encodeURIComponent(entity)}&owner_name=${encodeURIComponent(ownerName)}`, { method: 'POST' });

            // Show the generated key
            const resultBox = document.getElementById('signupResultContainer');
            resultBox.innerHTML = `
                <div class="credential-display-card" style="margin-top:20px; border-color:var(--success);">
                    <div style="font-weight:700; margin-bottom:8px; display:flex; align-items:center; gap:8px;">
                        <span style="color:var(--success)">✓</span> Account created for <strong>${res.entity}</strong>
                    </div>
                    <p style="font-size:0.85rem; color:var(--text-secondary); margin-bottom:16px;">
                        This is your Developer API Key. Copy it now — we won't show it again.
                    </p>
                    <label style="font-size:0.75rem; color:var(--text-muted); text-transform:uppercase; letter-spacing:0.05em;">Developer API Key</label>
                    <div style="display:flex; gap:8px; margin-top:6px; margin-bottom:16px;">
                        <input type="text" readonly value="${res.api_key}" 
                            style="font-family:'JetBrains Mono',monospace; font-size:0.9rem; font-weight:600; letter-spacing:0.05em; padding:10px 14px; background:var(--bg-primary);">
                        <button class="btn btn-outline" style="padding:10px 14px;" onclick="copyToClipboard('${res.api_key}', 'API Key')">Copy</button>
                    </div>
                    <button class="btn btn-primary" id="autoLoginAfterSignup" style="width:100%;">
                        Open My Dashboard →
                    </button>
                </div>`;

            document.getElementById('autoLoginAfterSignup').addEventListener('click', () => {
                autoLogin(res.api_key);
            });

            showToast(`Welcome, ${ownerName}! Account ready.`, 'success');
        } catch (err) {
            showToast(err.message, 'error');
        } finally {
            btn.disabled = false;
            btn.textContent = 'Create Account & Get Key';
        }
    });
}

// ======================= LOGIN =======================
function initLogin() {
    const btn = document.getElementById('loginBtn');
    if (!btn) return;
    btn.addEventListener('click', () => {
        const key = document.getElementById('ownerKeyInput')?.value.trim();
        if (!key) { showToast('Enter your Developer API Key.', 'error'); return; }
        autoLogin(key);
    });
}

async function autoLogin(apiKey, silent = false) {
    const loginBtn = document.getElementById('loginBtn');
    if (loginBtn) { loginBtn.disabled = true; loginBtn.textContent = 'Connecting...'; }

    try {
        const data = await apiCall(`/owner/users?api_key=${encodeURIComponent(apiKey)}`);
        currentOwnerKey = apiKey;
        localStorage.setItem('cognov_owner_key', apiKey);

        // Switch UI
        document.getElementById('authView').style.display = 'none';
        const dash = document.getElementById('dashboardView');
        dash.style.display = 'block';

        renderDashboard(data);
        if (!silent) showToast('Connected to your dashboard.', 'success');
    } catch (err) {
        localStorage.removeItem('cognov_owner_key');
        if (!silent) showToast(`Authentication failed: ${err.message}`, 'error');
    } finally {
        if (loginBtn) { loginBtn.disabled = false; loginBtn.textContent = 'Connect Console →'; }
    }
}

function checkStoredSession() {
    const key = localStorage.getItem('cognov_owner_key');
    if (key) {
        const input = document.getElementById('ownerKeyInput');
        if (input) input.value = key;
        setTimeout(() => autoLogin(key, true), 200);
    }
}

// ======================= DASHBOARD =======================
function renderDashboard(data) {
    registeredUsers = data.users || [];

    // Stats
    document.getElementById('statTotalClients').textContent = registeredUsers.length;
    document.getElementById('statTotalTransactions').textContent = (data.total_transactions || 0).toLocaleString();
    document.getElementById('statTotalCost').textContent = `$${(data.total_cost_usd || 0).toFixed(2)}`;

    renderUsersTable();
}

function renderUsersTable() {
    const tbody = document.getElementById('usersTableBody');
    if (!tbody) return;

    if (registeredUsers.length === 0) {
        tbody.innerHTML = `<tr><td colspan="4" style="text-align:center; padding:40px 0; color:var(--text-muted);">
            No users registered yet under your API key.
        </td></tr>`;
        return;
    }

    tbody.innerHTML = registeredUsers.map(u => {
        const created = new Date(u.created_at).toLocaleDateString('en-US', { day: 'numeric', month: 'short', year: 'numeric' });
        return `
        <tr>
            <td>
                <span class="mono" onclick="copyToClipboard('${u.user_id}', 'User ID')" 
                    style="cursor:pointer; text-decoration:underline; text-underline-offset:3px;" 
                    title="Click to copy full ID">
                    ${u.user_id}
                </span>
                <div style="font-size:0.75rem; color:var(--text-muted); margin-top:3px;">${created}</div>
            </td>
            <td class="mono" style="font-size:1.1rem; font-weight:600;">${u.transaction_count_last_24h}</td>
            <td class="mono" style="font-size:1.1rem; font-weight:600;">${u.transaction_count_all_time}</td>
            <td style="text-align:right;">
                <button class="btn btn-outline" 
                    style="padding:6px 14px; font-size:0.8rem;" 
                    onclick="openLedger('${u.user_id}')">
                    View Ledger
                </button>
            </td>
        </tr>`;
    }).join('');
}

async function refreshDashboard() {
    if (!currentOwnerKey) return;
    const btn = document.getElementById('refreshDashboardBtn');
    if (btn) { btn.disabled = true; btn.textContent = '⟳ Refreshing...'; }
    try {
        const data = await apiCall(`/owner/users?api_key=${encodeURIComponent(currentOwnerKey)}`);
        renderDashboard(data);
        showToast('Dashboard updated.', 'success');
    } catch (err) {
        showToast(`Refresh failed: ${err.message}`, 'error');
    } finally {
        if (btn) { btn.disabled = false; btn.textContent = '⟳ Refresh'; }
    }
}

async function registerNewUser() {
    if (!currentOwnerKey) return;
    const btn = document.getElementById('registerUserBtn');
    btn.disabled = true;
    btn.textContent = 'Registering...';
    try {
        const res = await apiCall(`/register_user?api_key=${encodeURIComponent(currentOwnerKey)}`, { method: 'POST' });
        // Show result inline
        const result = document.getElementById('registerResult');
        result.style.display = 'block';
        result.innerHTML = `
            <div class="credential-display-card" style="border-color:var(--success); background:rgba(34,197,94,0.02); margin-top:16px;">
                <div style="font-weight:700; margin-bottom:12px; display:flex; align-items:center; gap:8px;">
                    <span style="color:var(--success)">✓</span> User ID Generated
                </div>
                <label style="font-size:0.75rem; color:var(--text-muted); text-transform:uppercase;">User ID (share with your client)</label>
                <div style="display:flex; gap:8px; margin-top:6px;">
                    <input type="text" readonly value="${res.user_id}" class="mono" style="font-size:1rem; font-weight:700; letter-spacing:0.1em; padding:10px 14px; background:var(--bg-primary);">
                    <button class="btn btn-outline" style="padding:10px 14px;" onclick="copyToClipboard('${res.user_id}', 'User ID')">Copy</button>
                </div>
            </div>`;
        showToast('New user registered!', 'success');
        refreshDashboard();
    } catch (err) {
        showToast(`Failed: ${err.message}`, 'error');
    } finally {
        btn.disabled = false;
        btn.textContent = 'Register New User';
    }
}

function logout() {
    localStorage.removeItem('cognov_owner_key');
    currentOwnerKey = '';
    registeredUsers = [];
    document.getElementById('authView').style.display = 'block';
    document.getElementById('dashboardView').style.display = 'none';
    document.getElementById('registerResult').style.display = 'none';
    document.getElementById('registerResult').innerHTML = '';
    showToast('Logged out.', 'success');
}

// ======================= LEDGER MODAL =======================
let activeLedgerUserId = '';

async function openLedger(userId) {
    activeLedgerUserId = userId;
    const overlay = document.getElementById('explorerModal');
    const title = document.getElementById('modalClientTitle');
    if (!overlay) return;
    if (title) title.textContent = `Ledger — ${userId}`;
    overlay.classList.add('active');
    document.body.style.overflow = 'hidden';
    switchExplorerTab('journal');
}

function closeLedger() {
    const overlay = document.getElementById('explorerModal');
    if (overlay) overlay.classList.remove('active');
    document.body.style.overflow = '';
    activeLedgerUserId = '';
}

async function switchExplorerTab(tabId) {
    document.querySelectorAll('.modal-tab-btn').forEach(t => t.classList.toggle('active', t.dataset.tab === tabId));
    const content = document.getElementById('modalTabContent');
    content.innerHTML = `<div style="text-align:center; padding:60px 0; color:var(--text-muted);" class="animate-pulse-subtle">Loading ${tabId}…</div>`;
    try {
        const data = await apiCall(`/fetch/${activeLedgerUserId}/${tabId}?api_key=${encodeURIComponent(currentOwnerKey)}`);
        if (tabId === 'journal') renderJournal(data.journal, content);
        else if (tabId === 'trialbalance') renderTrialBalance(data.trial_balance, content);
        else if (tabId === 'balancesheet') renderBalanceSheet(data.balance_sheet, content);
    } catch (err) {
        content.innerHTML = `<div class="alert alert-error" style="margin:20px;">Error: ${err.message}</div>`;
    }
}

function renderJournal(entries, container) {
    if (!entries?.length) { container.innerHTML = '<p style="text-align:center;padding:40px;color:var(--text-muted)">No journal entries yet.</p>'; return; }
    container.innerHTML = `
        <div class="table-wrapper">
            <table>
                <thead><tr><th>Date</th><th>Action</th><th>Debit (Dr)</th><th>Credit (Cr)</th><th style="text-align:right">Amount</th></tr></thead>
                <tbody>
                    ${entries.map(e => `
                    <tr>
                        <td style="font-size:0.82rem;color:var(--text-secondary);">${new Date(e.date).toLocaleString('en-US',{month:'short',day:'numeric',hour:'2-digit',minute:'2-digit'})}</td>
                        <td><span class="badge">${e.action}</span></td>
                        <td style="font-weight:500;">${e.debit_account}</td>
                        <td style="color:var(--text-secondary);">${e.credit_account}</td>
                        <td class="mono" style="text-align:right;font-weight:600;">$${e.amount.toFixed(2)}</td>
                    </tr>`).join('')}
                </tbody>
            </table>
        </div>`;
}

function renderTrialBalance(rows, container) {
    if (!rows?.length) { container.innerHTML = '<p style="text-align:center;padding:40px;color:var(--text-muted)">No data yet.</p>'; return; }
    let totalDr = 0, totalCr = 0;
    rows.forEach(r => { totalDr += parseFloat(r.debit_balance || 0); totalCr += parseFloat(r.credit_balance || 0); });
    container.innerHTML = `
        <div class="table-wrapper">
            <table>
                <thead><tr><th>Account</th><th style="text-align:right">Debit ($)</th><th style="text-align:right">Credit ($)</th></tr></thead>
                <tbody>
                    ${rows.map(r => {
                        const dr = parseFloat(r.debit_balance || 0);
                        const cr = parseFloat(r.credit_balance || 0);
                        return `<tr>
                            <td>${r.account_name}</td>
                            <td class="mono" style="text-align:right;">${dr > 0 ? '$' + dr.toFixed(2) : '—'}</td>
                            <td class="mono" style="text-align:right;">${cr > 0 ? '$' + cr.toFixed(2) : '—'}</td>
                        </tr>`;
                    }).join('')}
                    <tr style="border-top:2px solid var(--border-active);font-weight:700;background:var(--bg-secondary);">
                        <td>Total</td>
                        <td class="mono" style="text-align:right;">$${totalDr.toFixed(2)}</td>
                        <td class="mono" style="text-align:right;">$${totalCr.toFixed(2)}</td>
                    </tr>
                </tbody>
            </table>
        </div>`;
}

function renderBalanceSheet(sheet, container) {
    if (!sheet) { container.innerHTML = '<p style="text-align:center;padding:40px;color:var(--text-muted)">No balance sheet yet.</p>'; return; }
    const section = (title, map) => `
        <div style="margin-bottom:24px;">
            <div style="font-size:0.75rem;font-weight:700;text-transform:uppercase;color:var(--text-muted);letter-spacing:0.05em;margin-bottom:8px;">${title}</div>
            ${Object.entries(map || {}).map(([k,v]) => `
                <div class="flex-between" style="padding:8px 0;border-bottom:1px solid var(--border-subtle);font-size:0.9rem;">
                    <span>${k}</span><span class="mono">$${parseFloat(v).toFixed(2)}</span>
                </div>`).join('') || '<div style="color:var(--text-muted);font-size:0.85rem;padding:8px 0;">None</div>'}
        </div>`;
    container.innerHTML = `
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:32px;">
            <div>${section('Assets', sheet.assets)}</div>
            <div>
                ${section('Liabilities', sheet.liabilities)}
                ${section('Equity', sheet.equity)}
            </div>
        </div>
        <div class="flex-between" style="margin-top:20px;padding-top:16px;border-top:2px solid var(--border-active);font-weight:700;">
            <span>Total Assets</span><span class="mono">$${(sheet.total_assets||0).toFixed(2)}</span>
        </div>`;
}

// Modal close events
document.addEventListener('DOMContentLoaded', () => {
    document.getElementById('modalCloseBtn')?.addEventListener('click', closeLedger);
    document.getElementById('explorerModal')?.addEventListener('click', e => { if (e.target === e.currentTarget) closeLedger(); });
    window.addEventListener('keydown', e => { if (e.key === 'Escape') closeLedger(); });
    document.getElementById('refreshDashboardBtn')?.addEventListener('click', refreshDashboard);
    document.getElementById('registerUserBtn')?.addEventListener('click', registerNewUser);
    document.getElementById('logoutBtn')?.addEventListener('click', logout);
});
