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

    function injectToggle() {
        var footer = document.querySelector('.sidebar-footer');
        if (!footer || document.getElementById('themeToggleBtn')) return;
        var btn = document.createElement('button');
        btn.id = 'themeToggleBtn';
        btn.type = 'button';
        btn.className = 'theme-toggle nav-item';
        btn.setAttribute('aria-label', 'Toggle dark / light mode');
        btn.onclick = window.toggleDashboardTheme;
        btn.innerHTML = buttonHTML(currentTheme());
        // Insert at the TOP of the sidebar footer so it sits above existing
        // footer items (Admin / Logout / Docs link).
        footer.insertBefore(btn, footer.firstChild);
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', injectToggle);
    } else {
        injectToggle();
    }
})();
