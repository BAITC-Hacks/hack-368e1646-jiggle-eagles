// No remote translation service. Catalog values are plain text, never HTML.
const locales = ['en', 'kk', 'ru'];
const formats = {en: 'en-GB', kk: 'kk-KZ', ru: 'ru-RU'};
const storageKey = 'money-graph.locale';
const catalogs = {};
let locale = 'en';

export function normalizeLocale(value) {
  if (typeof value !== 'string') return null;
  const language = value.toLowerCase().replaceAll('_', '-').split('-')[0];
  return language === 'kz' ? 'kk' : locales.includes(language) ? language : null;
}
export function currentLocale() { return locale; }
export function t(key, params = {}) {
  const template = catalogs[locale]?.[key] ?? catalogs.en?.[key] ?? key;
  return template.replace(/\{(\w+)\}/g, (match, name) => Object.hasOwn(params, name) ? String(params[name]) : match);
}
export function number(value, options = {}) {
  // Some Chromium builds omit Kazakh ICU data. Its decimal/group symbols match Russian.
  const format = locale === 'kk' && !Intl.NumberFormat.supportedLocalesOf(['kk-KZ']).length ? 'ru-RU' : formats[locale];
  return new Intl.NumberFormat(format, {maximumFractionDigits: 2, ...options}).format(value);
}
export function date(value) {
  // Source dates have day precision. UTC prevents a local timezone shifting the day.
  if (!Intl.DateTimeFormat.supportedLocalesOf([formats[locale]]).length) {
    const [year, month, day] = value.split('-');
    return t('date.fallback', {year, month: t(`date.month.${Number(month)}`), day: Number(day)});
  }
  return new Intl.DateTimeFormat(formats[locale], {day: '2-digit', month: 'long', year: 'numeric', timeZone: 'UTC'})
    .format(new Date(`${value}T00:00:00Z`));
}
export function timestamp(value) {
  const instant = new Date(value);
  // Run timestamps are instants, displayed in the browser's local timezone.
  const localDay = `${instant.getFullYear()}-${String(instant.getMonth() + 1).padStart(2, '0')}-${String(instant.getDate()).padStart(2, '0')}`;
  const format = Intl.DateTimeFormat.supportedLocalesOf([formats[locale]]).length ? formats[locale] : 'ru-RU';
  const time = new Intl.DateTimeFormat(format, {hour: '2-digit', minute: '2-digit', second: '2-digit'}).format(instant);
  return `${date(localDay)} · ${time}`;
}
export function translatePage() {
  document.documentElement.lang = locale;
  for (const node of document.querySelectorAll('[data-i18n]')) node.textContent = t(node.dataset.i18n);
  for (const attribute of ['aria-label', 'placeholder', 'title']) {
    for (const node of document.querySelectorAll(`[data-i18n-${attribute}]`)) {
      node.setAttribute(attribute, t(node.getAttribute(`data-i18n-${attribute}`)));
    }
  }
}
export function setLocale(value, persist = true) {
  const next = normalizeLocale(value) || 'en';
  if (!catalogs[next]) throw new Error(t('error.catalog'));
  locale = next;
  if (persist) {
    try { localStorage.setItem(storageKey, locale); }
    catch { /* Storage can be disabled; the current page still switches language. */ }
  }
  translatePage();
}
export async function initialize() {
  const results = await Promise.allSettled(locales.map(async language => {
    const response = await fetch(`/locales/${language}.json`);
    if (!response.ok) throw new Error('Language catalog unavailable');
    const data = await response.json();
    if (!data || Array.isArray(data) || typeof data !== 'object' ||
        !Object.values(data).every(value => typeof value === 'string')) throw new Error('Invalid language catalog');
    catalogs[language] = data;
  }));
  if (results[0].status === 'rejected') throw new Error('Could not load language files. Reload to try again.');
  let saved;
  try { saved = normalizeLocale(localStorage.getItem(storageKey)); }
  catch { /* Browser language is the fallback when storage is unavailable. */ }
  const preferred = saved || navigator.languages.map(normalizeLocale).find(Boolean) || 'en';
  setLocale(catalogs[preferred] ? preferred : 'en', false);
  return locales.filter(language => !catalogs[language]);
}
