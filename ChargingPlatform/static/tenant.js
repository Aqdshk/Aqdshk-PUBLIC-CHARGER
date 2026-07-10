// ── Dashboard tenant switcher ──────────────────────────────────────────────
// Small dropdown injected into the sidebar (below the theme toggle) that
// lets an admin scope the whole dashboard to a single fleet operator, or
// view a combined "All Tenants" roll-up for reconciliation reporting.
//
// Selection persists in localStorage (`dashboard_tenant`) and is exposed:
//   window.currentTenant() → 'all' | 'perodua' | 'czero-tng' | ...
//   window.addEventListener('tenantChange', e => { e.detail.tenant })
//
// Pages that filter server-side just read window.currentTenant() and append
// `?tenant=<value>` (skip when value === 'all') to their /api/... calls.
(function () {
    var KEY = 'dashboard_tenant';

    // Hardcoded for now — swap for GET /api/admin/tenants once we build the
    // tenants management page. Keys must match chargers.tenant column values.
    var TENANTS = [
        { value: 'all',       label: 'All Tenants',        badge: '', hint: 'Combined view — used for reconciliation & totals' },
        { value: 'czero-tng', label: 'CZero TNG Public',   badge: 'TNG',     hint: 'Walk-up + TNG payment flow' },
        { value: 'perodua',   label: 'Perodua Public',     badge: 'P2',      hint: 'Perodua P2 Superapp fleet' },
    ];

    function currentValue() {
        var v = null;
        try { v = localStorage.getItem(KEY); } catch (e) {}
        if (!v) return 'all';
        if (!TENANTS.some(function (t) { return t.value === v; })) return 'all';
        return v;
    }

    // Public accessor for page scripts
    window.currentTenant = currentValue;

    function setTenant(v) {
        try { localStorage.setItem(KEY, v); } catch (e) {}
        updateButton(v);
        // Notify listeners on the same page
        window.dispatchEvent(new CustomEvent('tenantChange', { detail: { tenant: v } }));
        // Cross-tab sync: other open tabs pick this up via the 'storage' event
        // (handled below in the listener) and refresh their views.
    }

    function tenantByValue(v) {
        for (var i = 0; i < TENANTS.length; i++) if (TENANTS[i].value === v) return TENANTS[i];
        return TENANTS[0];
    }

    function buttonHTML(v) {
        var t = tenantByValue(v);
        return ''
            + '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
            +     'stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
            + '  <path d="M3 21h18M5 21V7l7-4 7 4v14M9 9h1M9 13h1M9 17h1M14 9h1M14 13h1M14 17h1"/>'
            + '</svg>'
            + '<span class="tenant-toggle-label">'
            +   '<span class="tenant-toggle-name">' + t.label + '</span>'
            +   (t.badge ? '<span class="tenant-toggle-badge">' + t.badge + '</span>' : '')
            + '</span>'
            + '<svg class="tenant-toggle-caret" width="12" height="12" viewBox="0 0 24 24" fill="none" '
            +     'stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
            + '  <polyline points="18 15 12 9 6 15"/>'
            + '</svg>';
    }

    function updateButton(v) {
        var btn = document.getElementById('tenantToggleBtn');
        if (btn) btn.innerHTML = buttonHTML(v);
    }

    function closeMenu() {
        var menu = document.getElementById('tenantToggleMenu');
        if (menu) menu.remove();
        document.removeEventListener('click', outsideClick, true);
    }

    function outsideClick(e) {
        var menu = document.getElementById('tenantToggleMenu');
        var btn  = document.getElementById('tenantToggleBtn');
        if (!menu) return;
        if (btn && btn.contains(e.target)) return;
        if (menu.contains(e.target)) return;
        closeMenu();
    }

    function openMenu(anchor) {
        if (document.getElementById('tenantToggleMenu')) { closeMenu(); return; }

        var current = currentValue();
        var menu = document.createElement('div');
        menu.id = 'tenantToggleMenu';
        menu.className = 'tenant-menu';

        TENANTS.forEach(function (t) {
            var row = document.createElement('button');
            row.type = 'button';
            row.className = 'tenant-menu-row' + (t.value === current ? ' is-active' : '');
            row.innerHTML = ''
                + '<span class="tenant-menu-main">'
                +   '<span class="tenant-menu-label">' + t.label + '</span>'
                +   (t.hint ? '<span class="tenant-menu-hint">' + t.hint + '</span>' : '')
                + '</span>'
                + (t.badge ? '<span class="tenant-menu-badge">' + t.badge + '</span>' : '')
                + (t.value === current
                    ? '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
                    +     'stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>'
                    : '');
            row.onclick = function () { setTenant(t.value); closeMenu(); };
            menu.appendChild(row);
        });

        // Position: fixed to the anchor's location (above the toggle button)
        var rect = anchor.getBoundingClientRect();
        menu.style.left   = Math.round(rect.left) + 'px';
        menu.style.bottom = Math.round(window.innerHeight - rect.top + 8) + 'px';
        menu.style.width  = Math.round(rect.width) + 'px';

        document.body.appendChild(menu);
        setTimeout(function () {
            document.addEventListener('click', outsideClick, true);
        }, 0);
    }

    function buildButton() {
        var btn = document.createElement('button');
        btn.id = 'tenantToggleBtn';
        btn.type = 'button';
        btn.className = 'tenant-toggle nav-item';
        btn.setAttribute('aria-label', 'Switch tenant');
        btn.onclick = function () { openMenu(btn); };
        btn.innerHTML = buttonHTML(currentValue());
        return btn;
    }

    function injectSwitcher() {
        if (document.getElementById('tenantToggleBtn')) return;
        var sidebar = document.querySelector('.sidebar');
        if (!sidebar) return;
        // Insert BEFORE the theme toggle wrapper so tenant sits above light mode.
        var themeWrap = document.getElementById('themeToggleWrap');
        var footer    = document.querySelector('.sidebar-footer');
        var wrap = document.createElement('div');
        wrap.id = 'tenantToggleWrap';
        wrap.className = 'tenant-toggle-wrap';
        wrap.appendChild(buildButton());
        var anchor = themeWrap || footer;
        if (anchor && anchor.parentNode === sidebar) {
            sidebar.insertBefore(wrap, anchor);
        } else {
            sidebar.appendChild(wrap);
        }
    }

    function startWatcher() {
        var sidebar = document.querySelector('.sidebar');
        if (!sidebar || !window.MutationObserver) return;
        var obs = new MutationObserver(function () {
            if (!document.getElementById('tenantToggleBtn')) injectSwitcher();
        });
        obs.observe(sidebar, { childList: true, subtree: true });
    }

    // Cross-tab sync: when another tab changes the tenant, refresh this tab's
    // button + fire the same event so page scripts can re-fetch.
    window.addEventListener('storage', function (e) {
        if (e.key !== KEY) return;
        var v = currentValue();
        updateButton(v);
        window.dispatchEvent(new CustomEvent('tenantChange', { detail: { tenant: v } }));
    });

    function boot() {
        injectSwitcher();
        startWatcher();
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', boot);
    } else {
        boot();
    }
})();
