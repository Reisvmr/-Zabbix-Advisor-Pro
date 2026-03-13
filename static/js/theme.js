/* ── Zabbix Advisor Pro – Theme Manager ── */
;(function () {
  var STORE = 'zab_prefs';

  function load() {
    try { return JSON.parse(localStorage.getItem(STORE)) || {}; } catch { return {}; }
  }
  function save(prefs) {
    localStorage.setItem(STORE, JSON.stringify(prefs));
  }

  var prefs = load();

  /* ─ Apply immediately to avoid FOUC ─ */
  var root = document.documentElement;

  function applyTheme(t) {
    root.setAttribute('data-theme', t || 'dark');
  }
  function applyAccent(a, custom) {
    root.setAttribute('data-accent', a || 'blue');
    if (a === 'custom' && custom) {
      root.style.setProperty('--accent', custom);
    } else {
      root.style.removeProperty('--accent');
    }
  }
  function applyFont(f) {
    root.style.setProperty('--font', f || 'Inter, system-ui, Arial, sans-serif');
    /* Load from Google Fonts if needed */
    var gFonts = { 'Roboto': 'Roboto', 'Open Sans': 'Open+Sans', 'DM Sans': 'DM+Sans' };
    var base = f ? f.replace(/'/g, '').split(',')[0].trim() : '';
    if (gFonts[base] && !document.getElementById('gfont-' + base)) {
      var l = document.createElement('link');
      l.id = 'gfont-' + base;
      l.rel = 'stylesheet';
      l.href = 'https://fonts.googleapis.com/css2?family=' + gFonts[base] + ':wght@400;600;700;800&display=swap';
      document.head.appendChild(l);
    }
  }

  applyTheme(prefs.theme);
  applyAccent(prefs.accent, prefs.accentCustom);
  applyFont(prefs.font);

  /* ─ After DOM ready ─ */
  document.addEventListener('DOMContentLoaded', function () {
    var panel  = document.getElementById('settingsPanel');
    var toggle = document.getElementById('themeToggle');
    var gear   = document.getElementById('themeGear');

    if (!panel) return;

    /* sync UI to current prefs */
    function syncUI() {
      var t = root.getAttribute('data-theme') || 'dark';
      var a = root.getAttribute('data-accent') || 'blue';
      var f = root.style.getPropertyValue('--font').trim() || 'Inter, system-ui, Arial, sans-serif';

      /* toggle icon */
      if (toggle) toggle.textContent = t === 'light' ? '🌙' : '☀️';

      /* theme buttons */
      panel.querySelectorAll('[data-theme-btn]').forEach(function (b) {
        b.classList.toggle('active', b.dataset.themeBtn === t);
      });

      /* accent swatches */
      panel.querySelectorAll('[data-accent-btn]').forEach(function (b) {
        b.classList.toggle('active', b.dataset.accentBtn === a);
      });

      /* font select */
      var sel = document.getElementById('fontSelect');
      if (sel) {
        var fontBase = f.split(',')[0].trim().replace(/'/g, '');
        for (var i = 0; i < sel.options.length; i++) {
          var optBase = sel.options[i].value.replace(/'/g, '').split(',')[0].trim();
          if (optBase === fontBase) { sel.selectedIndex = i; break; }
        }
      }

      /* custom color */
      var pick = document.getElementById('accentCustom');
      if (pick && prefs.accentCustom) pick.value = prefs.accentCustom;
    }

    /* open/close panel */
    if (gear) gear.addEventListener('click', function (e) {
      e.stopPropagation();
      panel.classList.toggle('hidden');
      syncUI();
    });

    document.addEventListener('click', function (e) {
      if (!panel.contains(e.target) && e.target !== gear) {
        panel.classList.add('hidden');
      }
    });

    /* quick toggle dark/light */
    if (toggle) toggle.addEventListener('click', function () {
      var cur = root.getAttribute('data-theme') || 'dark';
      var next = cur === 'dark' ? 'light' : 'dark';
      prefs.theme = next;
      save(prefs);
      applyTheme(next);
      syncUI();
    });

    /* theme buttons inside panel */
    panel.querySelectorAll('[data-theme-btn]').forEach(function (b) {
      b.addEventListener('click', function () {
        prefs.theme = b.dataset.themeBtn;
        save(prefs);
        applyTheme(prefs.theme);
        syncUI();
      });
    });

    /* accent swatches */
    panel.querySelectorAll('[data-accent-btn]').forEach(function (b) {
      b.addEventListener('click', function () {
        prefs.accent = b.dataset.accentBtn;
        delete prefs.accentCustom;
        save(prefs);
        applyAccent(prefs.accent, null);
        syncUI();
      });
    });

    /* custom color */
    var pick = document.getElementById('accentCustom');
    if (pick) {
      pick.addEventListener('input', function () {
        prefs.accent = 'custom';
        prefs.accentCustom = pick.value;
        save(prefs);
        applyAccent('custom', pick.value);
        syncUI();
      });
    }

    /* font select */
    var sel = document.getElementById('fontSelect');
    if (sel) {
      sel.addEventListener('change', function () {
        prefs.font = sel.value;
        save(prefs);
        applyFont(prefs.font);
      });
    }

    syncUI();
  });
})();
