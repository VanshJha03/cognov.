// ======================= GLOBAL STATE & CONFIG =======================
let API_BASE_URL = window.location.origin.includes('localhost') || window.location.origin.includes('127.0.0.1')
    ? 'http://127.0.0.1:8000' 
    : 'https://cognov.vanshjha451.workers.dev'; // Default to user's Cloudflare Worker

let currentOwnerKey = "";
let registeredUsers = []; // Stores user records from the server

// SPA Router
function handleRouting() {
    const hash = window.location.hash || '#home';
    
    // Toggle active view pages
    const pages = document.querySelectorAll('.page-view');
    pages.forEach(p => {
        if (`#${p.id}` === hash) {
            p.classList.add('active');
        } else {
            p.classList.remove('active');
        }
    });

    // Toggle active state on header navigation links
    const navLinks = document.querySelectorAll('.nav-links a');
    navLinks.forEach(link => {
        if (link.getAttribute('href') === hash) {
            link.classList.add('active');
        } else {
            link.classList.remove('active');
        }
    });

    // Scroll back to top
    window.scrollTo(0, 0);
}

window.addEventListener('hashchange', handleRouting);

// Try to auto-detect backend URL from base display text on load
document.addEventListener("DOMContentLoaded", () => {
    // Check local storage for custom override
    const savedBaseUrl = localStorage.getItem("cognov_backend_url");
    if (savedBaseUrl) {
        API_BASE_URL = savedBaseUrl;
    }
    
    const baseUrlDisplay = document.getElementById('baseUrlDisplay');
    if (baseUrlDisplay) {
        baseUrlDisplay.innerText = API_BASE_URL;
    }
    
    // Initialize elements
    handleRouting();
    initHeroDemo();
    initDocTabs();
    initApiTester();
    initPasswordToggle();
    checkStoredSession();
    initDeveloperSignup();
});

// Toast notification helper
function showToast(message, type = 'info') {
    const container = document.getElementById('toastContainer');
    if (!container) return;

    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    
    // Icon mapping
    let icon = '⚡';
    if (type === 'success') icon = '✓';
    if (type === 'error') icon = '⚠';

    toast.innerHTML = `
        <div class="toast-icon">${icon}</div>
        <div class="toast-message">${message}</div>
        <div class="toast-progress"></div>
    `;

    container.appendChild(toast);

    // Progress bar animation
    const progress = toast.querySelector('.toast-progress');
    progress.style.transition = 'width 4000ms linear';
    progress.style.width = '100%';
    setTimeout(() => {
        progress.style.width = '0%';
    }, 50);

    // Remove toast after animation
    setTimeout(() => {
        toast.style.animation = 'slideInRight 0.3s reverse forwards';
        setTimeout(() => {
            toast.remove();
        }, 300);
    }, 4000);
}

// Global API Caller Helper
async function apiCall(endpoint, options = {}) {
    const url = `${API_BASE_URL}${endpoint}`;
    const headers = { 
        'Content-Type': 'application/json', 
        ...options.headers 
    };

    const fetchOptions = {
        ...options,
        headers
    };

    try {
        const res = await fetch(url, fetchOptions);
        if (!res.ok) {
            const errorText = await res.text();
            let parsedErr;
            try {
                parsedErr = JSON.parse(errorText);
            } catch(e) {}
            const msg = parsedErr?.detail || errorText || `HTTP ${res.status}`;
            throw new Error(msg);
        }
        return await res.json();
    } catch (err) {
        console.error(`API Call failed on ${endpoint}:`, err);
        throw err;
    }
}

// Copy to Clipboard Utility
function copyToClipboard(text, label = "Content") {
    navigator.clipboard.writeText(text).then(() => {
        showToast(`${label} copied to clipboard!`, 'success');
    }).catch(err => {
        showToast('Failed to copy to clipboard', 'error');
    });
}

// Password Visiblity Toggle
function initPasswordToggle() {
    const toggleBtn = document.getElementById('togglePasswordBtn');
    const input = document.getElementById('ownerKeyInput');
    if (!toggleBtn || !input) return;

    toggleBtn.addEventListener('click', () => {
        const type = input.getAttribute('type') === 'password' ? 'text' : 'password';
        input.setAttribute('type', type);
        toggleBtn.textContent = type === 'password' ? 'Show' : 'Hide';
    });
}


// ======================= INTERACTIVE HERO DEMO =======================
const HERO_DEMO_DATA = {
    sales: {
        request: `{
  "action": "sales",
  "item": "Laptop",
  "qty": 2,
  "selling_price": 1200
}`,
        journal: [
            { type: 'debit', account: 'Cash', value: '$2,400.00' },
            { type: 'credit', account: 'Sales Revenue', value: '$2,400.00' },
            { type: 'debit', account: 'COGS', value: '$1,000.00' },
            { type: 'credit', account: 'Inventory', value: '$1,000.00' }
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
            { type: 'debit', account: 'Inventory', value: '$250.00' },
            { type: 'credit', account: 'Cash', value: '$250.00' }
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
            { type: 'debit', account: 'Inventory', value: '$500.00' },
            { type: 'credit', account: "Owner's Equity", value: '$500.00' },
            { type: 'debit', account: 'Cash', value: '$5,000.00' },
            { type: 'credit', account: "Owner's Equity", value: '$5,000.00' }
        ]
    }
};

function initHeroDemo() {
    const tabs = document.querySelectorAll('.hero-tab-btn');
    const reqCode = document.getElementById('heroRequestCode');
    const journalList = document.getElementById('heroJournalList');
    
    if (!reqCode || !journalList) return;

    function loadDemo(tabId) {
        const data = HERO_DEMO_DATA[tabId];
        if (!data) return;

        // Render code block
        reqCode.innerHTML = PrismHighlight(data.request);

        // Render double-entry ledger output
        journalList.innerHTML = '';
        data.journal.forEach((row, index) => {
            const el = document.createElement('div');
            el.className = `ledger-row ${row.type}`;
            el.style.animationDelay = `${index * 100}ms`;
            el.innerHTML = `
                <div>
                    <span class="badge" style="margin-right: 8px;">${row.type.toUpperCase()}</span>
                    <span class="ledger-account">${row.account}</span>
                </div>
                <div class="ledger-val">${row.value}</div>
            `;
            journalList.appendChild(el);
        });
    }

    tabs.forEach(tab => {
        tab.addEventListener('click', () => {
            tabs.forEach(t => t.classList.remove('active'));
            tab.classList.add('active');
            loadDemo(tab.dataset.demo);
        });
    });

    // Load default
    loadDemo('sales');
}

// Simple JSON highlighting formatter (replaces Prism dependency locally)
function PrismHighlight(jsonString) {
    // Escape HTML characters
    let escaped = jsonString
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;");

    // Syntax regex rules
    return escaped.replace(/("(\\u[a-zA-Z0-9]{4}|\\[^u]|[^\\"])*"(\s*:)?|\b(true|false|null)\b|-?\d+(?:\.\d*)?(?:[eE][+-]?\d+)?)/g, function (match) {
        let cls = 'code-number';
        if (/^"/.test(match)) {
            if (/:$/.test(match)) {
                cls = 'code-key';
            } else {
                cls = 'code-string';
            }
        } else if (/true|false/.test(match)) {
            cls = 'code-boolean';
        } else if (/null/.test(match)) {
            cls = 'code-null';
        }
        return '<span class="' + cls + '">' + match + '</span>';
    });
}


// ======================= DOCS & TABS =======================
function initDocTabs() {
    const navLinks = document.querySelectorAll('.docs-nav-link');
    const sections = document.querySelectorAll('.docs-section');

    // Smooth active tab switching on scroll
    window.addEventListener('scroll', () => {
        let currentSectionId = "";
        sections.forEach(sec => {
            const rect = sec.getBoundingClientRect();
            if (rect.top <= 150) {
                currentSectionId = sec.id;
            }
        });

        if (currentSectionId) {
            navLinks.forEach(link => {
                if (link.getAttribute('href') === `#${currentSectionId}`) {
                    link.classList.add('active');
                } else {
                    link.classList.remove('active');
                }
            });
        }
    });
}


// ======================= OWNER SESSION & DASHBOARD =======================
const loginCard = document.getElementById('loginCard');
const dashboardContent = document.getElementById('dashboardContent');
const ownerKeyInput = document.getElementById('ownerKeyInput');
const loginBtn = document.getElementById('loginBtn');
const registerUserBtn = document.getElementById('registerUserBtn');
const refreshDashboardBtn = document.getElementById('refreshDashboardBtn');
const usersTableBody = document.getElementById('usersTableBody');
const registerResult = document.getElementById('registerResult');
const backendUrlInput = document.getElementById('backendUrlInput');
const saveBackendUrlBtn = document.getElementById('saveBackendUrlBtn');

// Stats DOM elements
const totalClientsSpan = document.getElementById('statTotalClients');
const totalTxnSpan = document.getElementById('statTotalTransactions');
const totalCostSpan = document.getElementById('statTotalCost');

// Setup backend URL configuration control
if (saveBackendUrlBtn && backendUrlInput) {
    backendUrlInput.value = API_BASE_URL;
    saveBackendUrlBtn.addEventListener('click', () => {
        const url = backendUrlInput.value.trim();
        if (url) {
            API_BASE_URL = url;
            localStorage.setItem("cognov_backend_url", url);
            const display = document.getElementById('baseUrlDisplay');
            if (display) display.innerText = url;
            showToast(`Backend API URL updated to: ${url}`, 'success');
            // If logged in, reload
            if (currentOwnerKey) {
                loadDashboardData();
            }
        }
    });
}

function checkStoredSession() {
    const storedKey = localStorage.getItem('cognov_owner_key');
    if (storedKey && ownerKeyInput) {
        ownerKeyInput.value = storedKey;
        // Attempt auto-login
        setTimeout(() => {
            handleLogin(storedKey, true);
        }, 150);
    }
}

async function handleLogin(apiKey, isAuto = false) {
    if (!apiKey) return;
    
    if (loginBtn) {
        loginBtn.disabled = true;
        loginBtn.innerText = "Authenticating...";
    }

    try {
        // Try calling the users endpoint to check validation
        const data = await apiCall(`/owner/users?api_key=${encodeURIComponent(apiKey)}`);
        
        currentOwnerKey = apiKey;
        localStorage.setItem('cognov_owner_key', apiKey);
        
        // UI toggle
        if (loginCard) loginCard.style.display = 'none';
        if (dashboardContent) {
            dashboardContent.style.display = 'block';
            dashboardContent.style.animation = 'fadeIn 0.5s ease-in-out';
        }
        
        showToast("Logged in successfully!", "success");
        
        // Render stats & list
        renderDashboard(data);
        
        // Initialize Live API Tester parameters
        updateTesterClientDropdown(data.users);
        
    } catch (err) {
        console.error(err);
        if (isAuto) {
            // Remove corrupted session key
            localStorage.removeItem('cognov_owner_key');
        } else {
            showToast(`Authentication failed: ${err.message}`, 'error');
        }
    } finally {
        if (loginBtn) {
            loginBtn.disabled = false;
            loginBtn.innerText = "Login to dashboard";
        }
    }
}

if (loginBtn) {
    loginBtn.addEventListener('click', () => {
        const key = ownerKeyInput.value.trim();
        if (!key) {
            showToast("Please enter an Owner API Key", "error");
            return;
        }
        handleLogin(key);
    });
}

async function loadDashboardData() {
    if (!currentOwnerKey) return;
    try {
        const data = await apiCall(`/owner/users?api_key=${encodeURIComponent(currentOwnerKey)}`);
        renderDashboard(data);
        updateTesterClientDropdown(data.users);
    } catch (err) {
        showToast(`Failed to refresh data: ${err.message}`, 'error');
    }
}

if (refreshDashboardBtn) {
    refreshDashboardBtn.addEventListener('click', () => {
        loadDashboardData();
        showToast("Dashboard data updated", "success");
    });
}

function renderDashboard(data) {
    registeredUsers = data.users || [];
    
    // Update Stats Card Values
    if (totalClientsSpan) totalClientsSpan.innerText = registeredUsers.length;
    if (totalTxnSpan) totalTxnSpan.innerText = data.total_transactions || 0;
    if (totalCostSpan) totalCostSpan.innerText = `$${(data.total_cost_usd || 0).toFixed(2)}`;
    
    // Render Clients Table
    if (!usersTableBody) return;
    
    if (registeredUsers.length === 0) {
        usersTableBody.innerHTML = `
            <tr>
                <td colspan="6" style="text-align: center; color: var(--text-muted); padding: 32px 0;">
                    No clients registered under this account yet.
                </td>
            </tr>
        `;
        return;
    }
    
    let rowsHtml = '';
    registeredUsers.forEach(user => {
        const cost = (user.transaction_count_all_time / 1000).toFixed(3);
        const createdDate = new Date(user.created_at).toLocaleDateString(undefined, {
            month: 'short',
            day: 'numeric',
            year: 'numeric'
        });
        
        rowsHtml += `
            <tr>
                <td class="mono">
                    <span class="user-id-truncate" title="Click to copy full ID" onclick="copyToClipboard('${user.user_id}', 'User ID')" style="cursor: pointer; text-decoration: underline;">
                        ${user.user_id.substring(0, 8)}…${user.user_id.substring(user.user_id.length - 8)}
                    </span>
                </td>
                <td>${createdDate}</td>
                <td class="mono">${user.transaction_count_last_24h}</td>
                <td class="mono">${user.transaction_count_all_time}</td>
                <td class="mono" style="font-weight: 600;">$${cost}</td>
                <td style="text-align: right;">
                    <button class="btn btn-outline" style="padding: 6px 12px; font-size: 0.8rem; border-radius: var(--radius-sm);" onclick="openExplorerModal('${user.user_id}')">
                        Inspect Ledger
                    </button>
                </td>
            </tr>
        `;
    });
    usersTableBody.innerHTML = rowsHtml;
}

// Owner action: logout
const logoutBtn = document.getElementById('logoutBtn');
if (logoutBtn) {
    logoutBtn.addEventListener('click', () => {
        localStorage.removeItem('cognov_owner_key');
        currentOwnerKey = "";
        if (loginCard) loginCard.style.display = 'block';
        if (dashboardContent) dashboardContent.style.display = 'none';
        showToast("Logged out successfully", "success");
    });
}

// Owner action: Register new client
if (registerUserBtn) {
    registerUserBtn.addEventListener('click', async () => {
        if (!currentOwnerKey) {
            showToast("Authorization required", "error");
            return;
        }
        
        registerUserBtn.disabled = true;
        registerUserBtn.innerText = "Registering...";
        
        try {
            const res = await apiCall(`/register_user?api_key=${encodeURIComponent(currentOwnerKey)}`, {
                method: 'POST'
            });
            
            // Success response displays credentials card
            if (registerResult) {
                registerResult.style.display = 'block';
                registerResult.innerHTML = `
                    <div class="card glass-panel" style="margin-top: 16px; border-color: var(--success); background: rgba(34, 197, 94, 0.03);">
                        <div style="font-weight: 700; color: var(--text-primary); margin-bottom: 12px; display:flex; align-items:center; gap:8px;">
                            <span style="color:var(--success)">✓</span> Client Registered Successfully
                        </div>
                        <p style="font-size: 0.85rem; margin-bottom: 16px;">Make sure to copy the client credentials below. Owner API key can act as this user's transaction executor.</p>
                        
                        <div class="form-group" style="margin-bottom: 12px;">
                            <label style="font-size:0.75rem;">Client User ID</label>
                            <div style="display:flex; gap:8px;">
                                <input type="text" readonly value="${res.user_id}" id="regUserIdVal" class="mono" style="padding:8px 12px; font-size:0.85rem;">
                                <button class="btn btn-outline" style="padding:8px 12px;" onclick="copyToClipboard('${res.user_id}', 'User ID')">Copy</button>
                            </div>
                        </div>
                    </div>
                `;
            }
            showToast("New client created!", "success");
            loadDashboardData(); // Reload table
        } catch (err) {
            showToast(`Registration failed: ${err.message}`, 'error');
        } finally {
            registerUserBtn.disabled = false;
            registerUserBtn.innerText = "Register new client";
        }
    });
}


// ======================= CLIENT LEDGER INSPECTOR (MODAL) =======================
let activeModalUserId = "";

// Bind modal closing actions
document.addEventListener("DOMContentLoaded", () => {
    const closeBtn = document.getElementById('modalCloseBtn');
    const overlay = document.getElementById('explorerModal');
    
    if (closeBtn) {
        closeBtn.addEventListener('click', closeExplorerModal);
    }
    
    if (overlay) {
        overlay.addEventListener('click', (e) => {
            if (e.target === overlay) closeExplorerModal();
        });
    }
    
    // Esc key bindings
    window.addEventListener('keydown', (e) => {
        if (e.key === "Escape" && overlay && overlay.classList.contains('active')) {
            closeExplorerModal();
        }
    });
});

async function openExplorerModal(userId) {
    activeModalUserId = userId;
    const overlay = document.getElementById('explorerModal');
    const modalTitle = document.getElementById('modalClientTitle');
    
    if (!overlay) return;
    
    overlay.classList.add('active');
    document.body.style.overflow = 'hidden'; // Stop background scroll
    
    if (modalTitle) {
        modalTitle.innerText = `Inspect: Client ${userId.substring(0, 8)}…`;
    }
    
    // Set default tab to 'journal' and load it
    switchExplorerTab('journal');
}

function closeExplorerModal() {
    const overlay = document.getElementById('explorerModal');
    if (overlay) {
        overlay.classList.remove('active');
        document.body.style.overflow = '';
    }
    activeModalUserId = "";
}

// Switch between report views in the inspection modal
async function switchExplorerTab(tabId) {
    const tabs = document.querySelectorAll('.modal-tab-btn');
    tabs.forEach(t => {
        if (t.dataset.tab === tabId) t.classList.add('active');
        else t.classList.remove('active');
    });
    
    const content = document.getElementById('modalTabContent');
    if (!content) return;
    
    content.innerHTML = `
        <div style="text-align: center; padding: 48px 0; color: var(--text-muted);">
            <div class="animate-pulse-subtle">Querying accounting records...</div>
        </div>
    `;
    
    try {
        const endpoint = `/fetch/${activeModalUserId}/${tabId}?api_key=${encodeURIComponent(currentOwnerKey)}`;
        const data = await apiCall(endpoint);
        
        if (tabId === 'journal') {
            renderJournalReport(data.journal, content);
        } else if (tabId === 'trialbalance') {
            renderTrialBalanceReport(data.trial_balance, content);
        } else if (tabId === 'balancesheet') {
            renderBalanceSheetReport(data.balance_sheet, content);
        }
        
    } catch (err) {
        content.innerHTML = `
            <div class="alert alert-error" style="margin: 20px 0;">
                Failed to fetch accounting ledger: ${err.message}
            </div>
        `;
    }
}

// Modal Report Renderers
function renderJournalReport(entries, container) {
    if (!entries || entries.length === 0) {
        container.innerHTML = `<p style="text-align:center; padding:32px; color:var(--text-muted)">No journal entries logged for this user.</p>`;
        return;
    }
    
    let html = `
        <div class="table-wrapper">
            <table>
                <thead>
                    <tr>
                        <th>Date</th>
                        <th>Action</th>
                        <th>Debit (Dr)</th>
                        <th>Credit (Cr)</th>
                        <th style="text-align: right;">Amount</th>
                    </tr>
                </thead>
                <tbody>
    `;
    
    entries.forEach(entry => {
        const dt = new Date(entry.date).toLocaleString(undefined, {
            month: 'short',
            day: 'numeric',
            hour: '2-digit',
            minute: '2-digit'
        });
        
        html += `
            <tr>
                <td style="font-size:0.85rem; color:var(--text-secondary);">${dt}</td>
                <td><span class="badge">${entry.action}</span></td>
                <td style="font-weight: 500;">${entry.debit_account}</td>
                <td style="color:var(--text-secondary);">${entry.credit_account}</td>
                <td class="mono" style="text-align: right; font-weight: 600;">$${entry.amount.toFixed(2)}</td>
            </tr>
        `;
    });
    
    html += `</tbody></table></div>`;
    container.innerHTML = html;
}

function renderTrialBalanceReport(balance, container) {
    if (!balance || balance.length === 0) {
        container.innerHTML = `<p style="text-align:center; padding:32px; color:var(--text-muted)">No accounting balances recorded. Initialize inventory or assets first.</p>`;
        return;
    }
    
    let html = `
        <div class="table-wrapper">
            <table>
                <thead>
                    <tr>
                        <th>Account Name</th>
                        <th style="text-align: right;">Debit Balance ($)</th>
                        <th style="text-align: right;">Credit Balance ($)</th>
                    </tr>
                </thead>
                <tbody>
    `;
    
    let totalDebit = 0;
    let totalCredit = 0;
    
    balance.forEach(row => {
        const dr = parseFloat(row.debit_balance || 0);
        const cr = parseFloat(row.credit_balance || 0);
        totalDebit += dr;
        totalCredit += cr;
        
        html += `
            <tr>
                <td style="font-weight:500;">${row.account_name}</td>
                <td class="mono" style="text-align: right; color: ${dr > 0 ? 'var(--text-primary)' : 'var(--text-muted)'}">${dr > 0 ? '$' + dr.toFixed(2) : '—'}</td>
                <td class="mono" style="text-align: right; color: ${cr > 0 ? 'var(--text-primary)' : 'var(--text-muted)'}">${cr > 0 ? '$' + cr.toFixed(2) : '—'}</td>
            </tr>
        `;
    });
    
    // Ledger total row
    html += `
            <tr style="border-top: 2px solid var(--border-active); font-weight: 700; background: var(--bg-secondary);">
                <td>Total</td>
                <td class="mono" style="text-align: right;">$${totalDebit.toFixed(2)}</td>
                <td class="mono" style="text-align: right;">$${totalCredit.toFixed(2)}</td>
            </tr>
        </tbody>
        </table>
        </div>
    `;
    container.innerHTML = html;
}

function renderBalanceSheetReport(sheet, container) {
    if (!sheet || (!sheet.assets && !sheet.liabilities && !sheet.equity)) {
        container.innerHTML = `<p style="text-align:center; padding:32px; color:var(--text-muted)">No balance sheet generated yet. Enter transaction postings to build ledger values.</p>`;
        return;
    }
    
    const assets = sheet.assets || {};
    const liabilities = sheet.liabilities || {};
    const equity = sheet.equity || {};
    
    let html = `<div style="display: grid; grid-template-columns: 1fr; gap: 24px;">`;
    
    // Left: Assets
    html += `
        <div class="card glass-panel" style="padding:24px;">
            <div class="flex-between" style="border-bottom:1px solid var(--border-subtle); padding-bottom:8px; margin-bottom:12px;">
                <h4 style="font-weight:700;">Assets</h4>
                <span class="mono" style="font-weight:700;">Total Assets: $${(sheet.total_assets || 0).toFixed(2)}</span>
            </div>
            <ul style="list-style:none; display:flex; flex-direction:column; gap:8px;">
    `;
    for (const [acct, val] of Object.entries(assets)) {
        html += `<li class="flex-between" style="font-size:0.9rem;"><span>${acct}</span><span class="mono">$${val.toFixed(2)}</span></li>`;
    }
    if (Object.keys(assets).length === 0) {
        html += `<li style="color:var(--text-muted); font-size:0.9rem;">No assets declared.</li>`;
    }
    html += `</ul></div>`;
    
    // Right: Liabilities & Equity
    html += `
        <div class="card glass-panel" style="padding:24px;">
            <div class="flex-between" style="border-bottom:1px solid var(--border-subtle); padding-bottom:8px; margin-bottom:12px;">
                <h4 style="font-weight:700;">Liabilities & Equity</h4>
                <span class="mono" style="font-weight:700;">Total Liab & Eq: $${(sheet.total_liabilities_equity || 0).toFixed(2)}</span>
            </div>
            
            <p style="font-size:0.8rem; font-weight:700; text-transform:uppercase; color:var(--text-muted); margin-bottom:8px; margin-top:8px;">Liabilities</p>
            <ul style="list-style:none; display:flex; flex-direction:column; gap:8px; margin-bottom:16px;">
    `;
    let totalLiab = 0;
    for (const [acct, val] of Object.entries(liabilities)) {
        totalLiab += val;
        html += `<li class="flex-between" style="font-size:0.9rem;"><span>${acct}</span><span class="mono">$${val.toFixed(2)}</span></li>`;
    }
    if (Object.keys(liabilities).length === 0) {
        html += `<li style="color:var(--text-muted); font-size:0.85rem;">No liabilities declared.</li>`;
    }
    
    html += `
            </ul>
            <p style="font-size:0.8rem; font-weight:700; text-transform:uppercase; color:var(--text-muted); margin-bottom:8px;">Equity</p>
            <ul style="list-style:none; display:flex; flex-direction:column; gap:8px;">
    `;
    let totalEq = 0;
    for (const [acct, val] of Object.entries(equity)) {
        totalEq += val;
        html += `<li class="flex-between" style="font-size:0.9rem;"><span>${acct}</span><span class="mono">$${val.toFixed(2)}</span></li>`;
    }
    if (Object.keys(equity).length === 0) {
        html += `<li style="color:var(--text-muted); font-size:0.85rem;">No equity declared.</li>`;
    }
    
    html += `</ul></div></div>`;
    container.innerHTML = html;
}


// ======================= LIVE API REQUEST TESTER =======================
const PRESET_BODY_DATA = {
    register: `{
  "action": "Register"
}`,
    transaction: `{
  "action": "sales",
  "item": "Laptop",
  "qty": 1,
  "selling_price": 950
}`,
    purchase: `{
  "action": "purchase",
  "item": "Mouse",
  "qty": 5,
  "unit_cost": 12.50
}`,
    initialize: `{
  "action": "initialize",
  "inventory": ["CPU Core"],
  "qty": [10],
  "unit_cost": [220],
  "asset": ["Cash"],
  "value": [8500],
  "liability": [],
  "values": []
}`
};

function updateTesterClientDropdown(users) {
    const dropdown = document.getElementById('testerUserIdSelect');
    if (!dropdown) return;
    
    // Clear dynamic options
    dropdown.innerHTML = '<option value="">-- No User ID (Only for Register) --</option>';
    
    users.forEach(u => {
        const opt = document.createElement('option');
        opt.value = u.user_id;
        opt.innerText = `${u.user_id.substring(0, 8)}… (${new Date(u.created_at).toLocaleDateString()})`;
        dropdown.appendChild(opt);
    });
}

function initApiTester() {
    const presetSelect = document.getElementById('testerPresetSelect');
    const endpointSelect = document.getElementById('testerEndpointSelect');
    const userIdInput = document.getElementById('testerUserIdSelect');
    const bodyTextarea = document.getElementById('testerRequestBody');
    const sendBtn = document.getElementById('testerSendBtn');
    const responseBlock = document.getElementById('testerResponseBlock');
    
    if (!presetSelect || !endpointSelect || !bodyTextarea || !sendBtn || !responseBlock) return;
    
    // Change body template when selecting action presets
    presetSelect.addEventListener('change', () => {
        const val = presetSelect.value;
        if (PRESET_BODY_DATA[val]) {
            bodyTextarea.value = PRESET_BODY_DATA[val];
            if (val === 'register') {
                endpointSelect.value = "/register_user";
            } else {
                endpointSelect.value = "/transaction";
            }
        }
    });
    
    sendBtn.addEventListener('click', async () => {
        const endpoint = endpointSelect.value;
        const bodyText = bodyTextarea.value.trim();
        const selectedUserId = userIdInput.value;
        
        responseBlock.innerHTML = `<span class="animate-pulse-subtle" style="color:var(--text-muted)">Executing POST request to server...</span>`;
        
        let payload;
        try {
            if (bodyText) {
                payload = JSON.parse(bodyText);
            }
        } catch (e) {
            responseBlock.innerHTML = `<span style="color:var(--danger)">JSON Validation Error: ${e.message}</span>`;
            showToast("Invalid JSON in Request Body", "error");
            return;
        }
        
        sendBtn.disabled = true;
        sendBtn.innerText = "Requesting...";
        
        try {
            let res;
            if (endpoint === '/register_user') {
                // Endpoint uses api_key as parameter
                const key = currentOwnerKey || ownerKeyInput.value.trim();
                if (!key) throw new Error("API Key required. Enter Owner Key in dashboard.");
                
                res = await apiCall(`/register_user?api_key=${encodeURIComponent(key)}`, {
                    method: 'POST'
                });
            } else if (endpoint === '/transaction') {
                const key = currentOwnerKey || ownerKeyInput.value.trim();
                if (!key) throw new Error("API Key required. Enter Owner Key in dashboard.");
                if (!selectedUserId && payload?.action !== "Register") {
                    throw new Error("Target Client User ID required to process transaction");
                }
                
                const finalBody = {
                    api_key: key,
                    user_id: selectedUserId || undefined,
                    transaction: payload
                };
                
                res = await apiCall('/transaction', {
                    method: 'POST',
                    body: JSON.stringify(finalBody)
                });
            }
            
            responseBlock.innerHTML = PrismHighlight(JSON.stringify(res, null, 2));
            showToast("API request completed!", "success");
            
            // Refresh table if transaction executed
            if (currentOwnerKey) {
                loadDashboardData();
            }
            
        } catch (err) {
            responseBlock.innerHTML = `<span style="color:var(--danger)">Request Failed:\n${err.message}</span>`;
            showToast(`API Request failed: ${err.message}`, "error");
        } finally {
            sendBtn.disabled = false;
            sendBtn.innerText = "Execute Request";
        }
    });
}

function initDeveloperSignup() {
    const signupBtn = document.getElementById('signUpBtn');
    const entityInput = document.getElementById('signupEntityInput');
    const secretInput = document.getElementById('signupSecretInput');
    const resultContainer = document.getElementById('signupResultContainer');

    if (!signupBtn || !entityInput || !secretInput || !resultContainer) return;

    signupBtn.addEventListener('click', async () => {
        const entity = entityInput.value.trim();
        const secret = secretInput.value.trim() || 'change_me'; // Default standard developer secret in server.py

        if (!entity) {
            showToast("Organization Name is required to generate node credentials.", "error");
            return;
        }

        signupBtn.disabled = true;
        signupBtn.innerText = "Provisioning Node...";
        resultContainer.innerHTML = '';

        try {
            // FastAPI expects scalar params as query params for POST `/admin/generate_owner_api_key`
            const res = await apiCall(`/admin/generate_owner_api_key?entity=${encodeURIComponent(entity)}&master_secret=${encodeURIComponent(secret)}`, {
                method: 'POST'
            });

            if (res && res.api_key) {
                resultContainer.innerHTML = `
                    <div class="credential-display-card" style="border-color: var(--success); background: rgba(34, 197, 94, 0.02);">
                        <div style="font-weight: 700; color: var(--text-primary); margin-bottom: 12px; display:flex; align-items:center; gap:8px;">
                            <span style="color:var(--success)">✓</span> Credentials Generated Successfully
                        </div>
                        <p style="font-size: 0.85rem; margin-bottom: 16px; color: var(--text-secondary);">
                            Your Developer API key is now active. Store it safely. You will use this key to authenticate all API requests.
                        </p>
                        
                        <div class="form-group" style="margin-bottom: 16px;">
                            <label style="font-size:0.75rem;">Your Developer API Key</label>
                            <div style="display:flex; gap:8px;">
                                <input type="text" readonly value="${res.api_key}" id="genApiKeyInput" class="mono" style="padding:10px 14px; font-size:0.85rem;">
                                <button class="btn btn-outline" style="padding:10px 14px;" onclick="copyToClipboard('${res.api_key}', 'API Key')">Copy</button>
                            </div>
                        </div>
                        
                        <button class="btn btn-primary" id="autoLoginBtn" style="width: 100%; font-size: 0.85rem; padding: 10px;">
                            Use Key & Connect Console
                        </button>
                    </div>
                `;

                // Handle autologin clicking action
                const autoLoginBtn = document.getElementById('autoLoginBtn');
                if (autoLoginBtn) {
                    autoLoginBtn.addEventListener('click', () => {
                        if (ownerKeyInput) {
                            ownerKeyInput.value = res.api_key;
                            if (loginBtn) loginBtn.click();
                        }
                    });
                }
                showToast("Developer API Key generated!", "success");
            } else {
                throw new Error("Credentials generation failed: No key returned.");
            }
        } catch (err) {
            console.error(err);
            resultContainer.innerHTML = `
                <div class="alert alert-error" style="margin-top: 16px;">
                    Failed to provision developer credentials. Check that the Target Backend URL is correct and the Master Secret matches. Error: ${err.message}
                </div>
            `;
            showToast("Account creation failed", "error");
        } finally {
            signupBtn.disabled = false;
            signupBtn.innerText = "Generate Credentials";
        }
    });
}

