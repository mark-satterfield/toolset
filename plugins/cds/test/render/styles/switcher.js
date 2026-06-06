/* ============================================================
 * switcher.js — Customizable Design System
 * Theme + mode resolution script from
 * foundations/implementation.md §9 (root data-theme / data-mode).
 * Standalone file the galleries can inline. DO NOT EDIT —
 * regenerate from the reference.
 * ============================================================ */

/* ---- Render-blocking initializer (inline in <head> before paint) ----
 *  placed in <head>, or inline the
 * IIFE body below to avoid a flash of the wrong mode. */
(function () {
  var STORAGE_KEY = 'site-mode';
  var stored = null;
  try { stored = localStorage.getItem(STORAGE_KEY); } catch (e) {}
  var mode = stored || 'system';
  document.documentElement.setAttribute('data-mode', mode);
})();

/* ---- Runtime controller ---- */
(function (global) {
  var STORAGE_KEY = 'site-mode';

  function setMode(mode) {
    document.documentElement.setAttribute('data-mode', mode);
    try {
      if (mode === 'system') {
        localStorage.removeItem(STORAGE_KEY);
      } else {
        localStorage.setItem(STORAGE_KEY, mode);
      }
    } catch (e) {}
  }

  function getMode() {
    return document.documentElement.getAttribute('data-mode') || 'system';
  }

  /* Theme is applied per-section by adding a theme class to a wrapper
   * element. setTheme toggles the document-root data-theme marker for
   * galleries that switch the whole page's default theme. */
  function setTheme(theme) {
    if (theme) {
      document.documentElement.setAttribute('data-theme', theme);
    } else {
      document.documentElement.removeAttribute('data-theme');
    }
  }

  function getTheme() {
    return document.documentElement.getAttribute('data-theme') || null;
  }

  var systemQuery = window.matchMedia('(prefers-color-scheme: dark)');
  systemQuery.addEventListener('change', function () {
    if (getMode() === 'system') {
      // CSS @media rule handles the visual flip automatically.
      window.dispatchEvent(new CustomEvent('site-mode-resolved'));
    }
  });

  global.CDSThemeSwitcher = {
    setMode: setMode,
    getMode: getMode,
    setTheme: setTheme,
    getTheme: getTheme
  };
})(typeof window !== 'undefined' ? window : this);
