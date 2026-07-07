/**
 * PlagSini — Shared Auth & Role-Based Access Control
 * Include this script at the TOP of every page <body> or end of <head>.
 * It will:
 *   1. Check localStorage for staffToken / staffInfo
 *   2. Redirect to /login if not authenticated
 *   3. Verify current page is allowed for user's role/dept
 *   4. Filter sidebar links based on role/dept
 *   5. Hide CRUD elements for non-admin (view-only mode)
 *   6. Add user info + logout + "My Tickets" to sidebar
 */

(function () {
    'use strict';

    // ──────── 1. AUTH CHECK ────────
    const staffToken = localStorage.getItem('staffToken');
    const staffInfo  = JSON.parse(localStorage.getItem('staffInfo') || 'null');

    // Not on login page? Must be authenticated
    if (window.location.pathname !== '/login') {
        if (!staffToken || !staffInfo || !staffInfo.role) {
            localStorage.removeItem('staffToken');
            localStorage.removeItem('staffInfo');
            window.location.href = '/login';
            return; // stop execution
        }
    } else {
        return; // Don't run auth logic on login page itself
    }

    const role = staffInfo.role;       // admin | manager | staff
    const dept = staffInfo.department;  // IT | Finance | Operations | Customer Service | Marketing
    const name = staffInfo.name;
    const isAdmin = (role === 'admin');

    // Expose globally for page-specific logic
    window.STAFF_AUTH = { token: staffToken, info: staffInfo, role, dept, name, isAdmin };

    // ──────── 2. PAGE ACCESS MAP ────────
    // Admin can access everything; all other staff only see Dashboard + own tickets
    const ALL_PAGES = ['/', '/chargers', '/sessions', '/metering', '/faults', '/maintenance', '/invoice', '/settings', '/operations', '/admin', '/my-tickets'];
    const STAFF_PAGES = ['/', '/my-tickets'];  // Non-admin: dashboard + tickets only

    const currentPath = window.location.pathname;

    // Check page access — non-admin can ONLY access Dashboard and My Tickets
    if (!isAdmin) {
        if (!STAFF_PAGES.includes(currentPath)) {
            window.location.href = '/';
            return;
        }
    }

    // ──────── 3. SIDEBAR FILTERING ────────
    // Map of href paths to check against
    const PATH_MAP = {
        '/':           'Dashboard',
        '/chargers':   'Charger Status',
        '/sessions':   'Sessions',
        '/metering':   'Metering',
        '/faults':     'Faults',
        '/maintenance':'Maintenance',
        '/invoice':    'Invoice & Reports',
        '/settings':   'Configuration',
        '/operations': 'OCPP Operations',
    };

    function filterSidebar() {
        const allowedPages = isAdmin ? ALL_PAGES : STAFF_PAGES;
        const sidebar = document.getElementById('sidebar');
        if (!sidebar) return;

        // Filter main menu links
        const navLinks = sidebar.querySelectorAll('.sidebar-nav a.nav-item, .sidebar-nav .nav-item[href]');
        navLinks.forEach(link => {
            const href = link.getAttribute('href');
            if (!href) return;

            // Parse just the path (ignore hash and query params)
            const path = href.split('?')[0].split('#')[0];

            // Staff portal link — hide for everyone (deprecated)
            if (path === '/staff-portal') {
                link.style.display = 'none';
                return;
            }

            // Non-admin: hide ALL pages except Dashboard and My Tickets
            if (!isAdmin) {
                if (!allowedPages.includes(path)) {
                    link.style.display = 'none';
                }
            }
        });

        // Hide entire sections for non-admin
        if (!isAdmin) {
            const navSections = sidebar.querySelectorAll('.nav-section');
            navSections.forEach(section => {
                const title = section.querySelector('.nav-section-title');
                if (!title) return;
                const titleText = title.textContent.trim().toLowerCase();

                // Hide everything except "Overview" section (Dashboard)
                // Administration, Quick Actions, Charger Management, Reports, etc. — all hidden
                if (titleText.includes('administration') ||
                    titleText.includes('quick actions') ||
                    titleText.includes('charger') ||
                    titleText.includes('report') ||
                    titleText.includes('configuration') ||
                    titleText.includes('operations') ||
                    titleText.includes('management')) {
                    section.style.display = 'none';
                }
            });
        }

        // ──────── 4. INJECT USER INFO + LOGOUT + MY TICKETS ────────
        injectSidebarExtras(sidebar);
    }

    function injectSidebarExtras(sidebar) {
        // Role badge colors
        const roleColors = {
            admin:   { bg: '#ff004422', color: '#ff0044', border: '#ff004444', label: '👑 ADMIN' },
            manager: { bg: '#ff880022', color: '#ff8800', border: '#ff880044', label: '📋 MANAGER' },
            staff:   { bg: '#00aaff22', color: '#00aaff', border: '#00aaff44', label: '🎯 STAFF' },
        };
        const rc = roleColors[role] || roleColors.staff;

        // Find or create sidebar-footer
        let footer = sidebar.querySelector('.sidebar-footer');
        if (!footer) {
            footer = document.createElement('div');
            footer.className = 'sidebar-footer';
            sidebar.appendChild(footer);
        }

        // Add "My Tickets" link before footer
        const navArea = sidebar.querySelector('.sidebar-nav');
        if (navArea) {
            // Check if tickets section already exists
            if (!navArea.querySelector('#ticketNavSection')) {
                const ticketSection = document.createElement('div');
                ticketSection.className = 'nav-section';
                ticketSection.id = 'ticketNavSection';
                ticketSection.innerHTML = `
                    <div class="nav-section-title">Support</div>
                    <a href="${isAdmin ? '/admin?tab=tickets' : '/my-tickets'}" class="nav-item${currentPath === '/my-tickets' ? ' active' : ''}" ${!isAdmin ? '' : "onclick=\"localStorage.setItem('adminTab','tickets')\""}>
                        <span class="nav-item-icon">🎫</span>
                        <span class="nav-item-text">My Tickets</span>
                    </a>
                `;
                navArea.appendChild(ticketSection);
            }
        }

        // Inject minimal logout into footer
        footer.innerHTML = `
            <div style="padding:10px 16px;display:flex;align-items:center;justify-content:space-between;">
                <span style="font-size:11px;color:#888;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">${name || 'Staff'}</span>
                <button onclick="window._psLogout()" style="background:none;border:1px solid #333;color:#888;font-size:10px;padding:4px 10px;border-radius:6px;cursor:pointer;transition:all 0.2s;flex-shrink:0;" onmouseover="this.style.borderColor='#ff4444';this.style.color='#ff4444'" onmouseout="this.style.borderColor='#333';this.style.color='#888'">Logout</button>
            </div>
        `;
    }

    // Global logout function
    window._psLogout = function () {
        fetch('/api/staff/logout', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ token: staffToken })
        }).catch(() => {});
        localStorage.removeItem('staffToken');
        localStorage.removeItem('staffInfo');
        localStorage.removeItem('adminToken');
        localStorage.removeItem('adminName');
        window.location.href = '/login';
    };

    // ──────── 5. VIEW-ONLY MODE FOR NON-ADMIN ────────
    function applyViewOnlyMode() {
        if (isAdmin) return; // Admin has full CRUD

        // Add a global CSS class
        document.body.classList.add('ps-view-only');

        // Inject CSS to hide CRUD elements
        const style = document.createElement('style');
        style.textContent = `
            /* Hide CRUD buttons and forms for view-only staff */
            .ps-view-only .admin-only,
            .ps-view-only [data-admin-only],
            .ps-view-only button[onclick*="delete"],
            .ps-view-only button[onclick*="Delete"],
            .ps-view-only button[onclick*="Create"],
            .ps-view-only button[onclick*="create"],
            .ps-view-only button[onclick*="openCreate"],
            .ps-view-only button[onclick*="openEdit"],
            .ps-view-only button[onclick*="toggle"],
            .ps-view-only .btn-danger,
            .ps-view-only .crud-actions {
                display: none !important;
            }

            /* Dim edit-related buttons */
            .ps-view-only input:not([type="search"]):not(.search-input),
            .ps-view-only select:not(.filter-select),
            .ps-view-only textarea {
                pointer-events: none;
                opacity: 0.6;
            }

            /* Show a view-only badge */
            .ps-view-only-badge {
                position: fixed;
                top: 8px;
                right: 16px;
                background: rgba(0,170,255,0.15);
                color: #00aaff;
                border: 1px solid rgba(0,170,255,0.3);
                padding: 4px 14px;
                border-radius: 20px;
                font-size: 11px;
                font-weight: 700;
                letter-spacing: 0.5px;
                z-index: 9999;
                pointer-events: none;
            }
        `;
        document.head.appendChild(style);

        // Add view-only badge
        const badge = document.createElement('div');
        badge.className = 'ps-view-only-badge';
        badge.textContent = '👁 VIEW ONLY';
        document.body.appendChild(badge);
    }

    // ──────── 6. IDLE SESSION TIMEOUT ────────
    // Auto-logout after inactivity to prevent stale-token 401 errors and
    // reduce the risk of an unattended browser being used by someone else.
    // Cross-tab synced via localStorage — activity in any tab resets the
    // countdown across all open PlagSini admin tabs.
    const IDLE_WARN_MS   = 25 * 60 * 1000;   // 25 min → show warning modal
    const IDLE_LOGOUT_MS = 26 * 60 * 1000;   // 26 min → force logout
    const ACTIVITY_KEY   = 'psLastActivity'; // localStorage key, shared across tabs
    const ACTIVITY_EVENTS = ['mousemove', 'mousedown', 'keydown', 'scroll', 'touchstart', 'click'];
    let _idleWarnTimer = null;
    let _idleLogoutTimer = null;
    let _idleModal = null;
    let _idleCountdownTimer = null;

    function _markActive() {
        try { localStorage.setItem(ACTIVITY_KEY, String(Date.now())); } catch (e) {}
        _scheduleIdleChecks();
        _dismissIdleWarning();
    }

    function _scheduleIdleChecks() {
        clearTimeout(_idleWarnTimer);
        clearTimeout(_idleLogoutTimer);
        _idleWarnTimer = setTimeout(_showIdleWarning, IDLE_WARN_MS);
        _idleLogoutTimer = setTimeout(_idleForceLogout, IDLE_LOGOUT_MS);
    }

    function _showIdleWarning() {
        // If any tab had activity more recently than our stored timestamp,
        // that other tab already reset the counter — don't fire the modal.
        try {
            const last = parseInt(localStorage.getItem(ACTIVITY_KEY) || '0', 10);
            if (Date.now() - last < IDLE_WARN_MS - 1000) return;
        } catch (e) {}

        if (_idleModal) return;
        _idleModal = document.createElement('div');
        _idleModal.id = 'psIdleWarning';
        _idleModal.style.cssText = 'position:fixed;inset:0;background:rgba(0,0,0,0.75);z-index:99999;display:flex;align-items:center;justify-content:center;font-family:system-ui,-apple-system,Segoe UI,Roboto,sans-serif;';
        _idleModal.innerHTML = `
            <div style="background:#151b28;border:1px solid #1e2a3a;border-radius:12px;padding:28px 32px;max-width:420px;width:92vw;box-shadow:0 20px 60px rgba(0,0,0,0.6);">
                <div style="display:flex;align-items:center;gap:12px;margin-bottom:16px;">
                    <div style="width:40px;height:40px;border-radius:50%;background:rgba(245,158,11,0.15);display:flex;align-items:center;justify-content:center;font-size:20px;">⏱️</div>
                    <h3 style="margin:0;color:#e4e8ef;font-size:16px;font-weight:600;">Session about to expire</h3>
                </div>
                <p style="color:#8892a4;font-size:13.5px;line-height:1.5;margin:0 0 8px;">
                    You've been inactive for a while. For security, you will be logged out in
                    <b id="psIdleCountdown" style="color:#f59e0b;">60</b> seconds.
                </p>
                <p style="color:#8892a4;font-size:12px;margin:0 0 20px;">
                    Click the button below to stay logged in — this refreshes your session.
                </p>
                <div style="display:flex;gap:10px;justify-content:flex-end;">
                    <button id="psIdleLogout" style="background:transparent;border:1px solid #374151;color:#8892a4;padding:9px 16px;border-radius:8px;font-size:13px;cursor:pointer;">Logout now</button>
                    <button id="psIdleStay" style="background:#00e676;border:none;color:#0b0e14;padding:9px 18px;border-radius:8px;font-size:13px;font-weight:600;cursor:pointer;">Stay logged in</button>
                </div>
            </div>
        `;
        document.body.appendChild(_idleModal);
        document.getElementById('psIdleStay').addEventListener('click', _markActive);
        document.getElementById('psIdleLogout').addEventListener('click', _idleForceLogout);

        // 60-second countdown display in the modal.
        let remaining = 60;
        const countdownEl = document.getElementById('psIdleCountdown');
        _idleCountdownTimer = setInterval(() => {
            remaining -= 1;
            if (countdownEl) countdownEl.textContent = String(Math.max(0, remaining));
            if (remaining <= 0) clearInterval(_idleCountdownTimer);
        }, 1000);
    }

    function _dismissIdleWarning() {
        if (_idleModal) {
            _idleModal.remove();
            _idleModal = null;
        }
        if (_idleCountdownTimer) {
            clearInterval(_idleCountdownTimer);
            _idleCountdownTimer = null;
        }
    }

    function _idleForceLogout() {
        _dismissIdleWarning();
        if (typeof window._psLogout === 'function') {
            window._psLogout();
        } else {
            // Fallback if auth.js's logout helper hasn't loaded yet.
            localStorage.removeItem('staffToken');
            localStorage.removeItem('adminToken');
            window.location.href = '/login';
        }
    }

    // Attach activity listeners once at startup. Passive=true keeps scrolling smooth.
    ACTIVITY_EVENTS.forEach(evt => {
        window.addEventListener(evt, _markActive, { passive: true, capture: true });
    });
    // Cross-tab sync: if another tab records activity, reset our timers too.
    window.addEventListener('storage', (e) => {
        if (e.key === ACTIVITY_KEY) { _scheduleIdleChecks(); _dismissIdleWarning(); }
    });
    // Kick off the first idle window.
    _markActive();

    // ──────── 7. RUN ON DOM READY ────────
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', () => {
            filterSidebar();
            applyViewOnlyMode();
        });
    } else {
        filterSidebar();
        applyViewOnlyMode();
    }

})();
