// ── Dashboard theme switcher ───────────────────────────────────────────────
// Reads the saved preference from localStorage and sets data-theme on <html>
// *synchronously* before paint (avoids a flash of the wrong theme). On
// DOMContentLoaded it injects a small Dark/Light toggle into .sidebar-footer
// above the Admin/Logout block, present on every dashboard page.
//
// Persists to localStorage key `dashboard_theme` so the choice carries
// across navigation between dashboard pages.
(function () {
    var KEY = 'dashboard_theme';
    var saved = null;
    try { saved = localStorage.getItem(KEY); } catch (e) {}
    if (saved !== 'light' && saved !== 'dark') saved = 'dark';
    document.documentElement.setAttribute('data-theme', saved);

    function setTheme(t) {
        document.documentElement.setAttribute('data-theme', t);
        try { localStorage.setItem(KEY, t); } catch (e) {}
        updateButton(t);
    }

    function currentTheme() {
        return document.documentElement.getAttribute('data-theme') || 'dark';
    }

    window.toggleDashboardTheme = function () {
        setTheme(currentTheme() === 'dark' ? 'light' : 'dark');
    };

    function buttonHTML(t) {
        // Sun icon when currently dark (tap to go light); moon when light.
        var dark = t === 'dark';
        var icon = dark
            ? '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M4.93 19.07l1.41-1.41M17.66 6.34l1.41-1.41"/></svg>'
            : '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/></svg>';
        return icon + '<span class="theme-toggle-label">' + (dark ? 'Light mode' : 'Dark mode') + '</span>';
    }

    function updateButton(t) {
        var btn = document.getElementById('themeToggleBtn');
        if (btn) btn.innerHTML = buttonHTML(t);
    }

    function buildButton() {
        var btn = document.createElement('button');
        btn.id = 'themeToggleBtn';
        btn.type = 'button';
        btn.className = 'theme-toggle nav-item';
        btn.setAttribute('aria-label', 'Toggle dark / light mode');
        btn.onclick = window.toggleDashboardTheme;
        btn.innerHTML = buttonHTML(currentTheme());
        return btn;
    }

    function injectToggle() {
        if (document.getElementById('themeToggleBtn')) return;
        var footer = document.querySelector('.sidebar-footer');
        var sidebar = document.querySelector('.sidebar');
        if (!sidebar) return;
        // Wrap in a small container styled like the footer so the button
        // visually sits above the Admin/Logout area. Insert as a SIBLING
        // before .sidebar-footer (NOT inside it) — auth.js wipes the
        // footer's innerHTML when it injects the staff name + logout, which
        // was eating any button placed inside.
        var wrap = document.createElement('div');
        wrap.id = 'themeToggleWrap';
        wrap.className = 'theme-toggle-wrap';
        wrap.appendChild(buildButton());
        if (footer) {
            sidebar.insertBefore(wrap, footer);
        } else {
            sidebar.appendChild(wrap);
        }
    }

    // Watch the sidebar for re-renders (auth.js runs after DOMContentLoaded
    // and rewrites the footer). If our toggle disappears, put it back.
    function startWatcher() {
        var sidebar = document.querySelector('.sidebar');
        if (!sidebar || !window.MutationObserver) return;
        var obs = new MutationObserver(function () {
            if (!document.getElementById('themeToggleBtn')) injectToggle();
        });
        obs.observe(sidebar, { childList: true, subtree: true });
    }

    function boot() {
        injectToggle();
        startWatcher();
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', boot);
    } else {
        boot();
    }
})();
