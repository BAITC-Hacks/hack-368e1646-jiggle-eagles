'use strict';
// Load before CSS so a stored choice is applied before the first painted frame.
(() => {
  const storageKey = 'money-graph.theme';
  const choices = ['system', 'light', 'dark'];
  const system = matchMedia('(prefers-color-scheme: dark)');
  const normalize = value => choices.includes(value) ? value : 'system';
  let preference = 'system';
  try { preference = normalize(localStorage.getItem(storageKey)); }
  catch { /* Optional browser storage may be blocked; System still works. */ }

  function apply() {
    document.documentElement.dataset.theme = preference === 'system' ?
      (system.matches ? 'dark' : 'light') : preference;
    const select = document.getElementById('theme');
    if (select) select.value = preference;
  }
  apply();
  system.addEventListener('change', () => { if (preference === 'system') apply(); });
  window.addEventListener('storage', event => {
    if (event.key === storageKey || event.key === null) {
      preference = normalize(event.newValue);
      apply();
    }
  });
  document.addEventListener('DOMContentLoaded', () => {
    const select = document.getElementById('theme');
    if (!select) return; // The direct-file launch guide has no app controls.
    select.disabled = false;
    select.value = preference;
    select.addEventListener('change', () => {
      preference = normalize(select.value);
      try { localStorage.setItem(storageKey, preference); }
      catch { /* The current page still switches when persistence is unavailable. */ }
      apply();
    });
  }, {once: true});
})();
