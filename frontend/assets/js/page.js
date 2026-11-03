/* Boilerplate every page repeats: font preload, chrome, footer, i18n. */
import { i18n } from './i18n.js';
import { renderChrome, renderFooter } from './ui.js';

export function bootstrap(active) {
  renderChrome({ active });
  renderFooter();
  i18n.apply();
  const demo = document.createElement('aside');
  demo.className = 'container alert alert-warning';
  demo.setAttribute('role', 'note');
  demo.textContent = i18n.lang === 'bn'
    ? 'ডেমো সংস্করণ: পেমেন্টে আসল টাকা কাটা হয় না। হাসপাতালের শয্যা ও পূর্বাভাস যাচাইকৃত live তথ্য নয়। AI ফল চিকিৎসকের বিকল্প নয়।'
    : 'Demo: payments move no real money. Bed capacity and forecasts are not verified live data. AI results require a clinician.';
  document.querySelector('main')?.prepend(demo);
  registerServiceWorker();
}

function registerServiceWorker() {
  // Requires a secure context; skipped silently when opened over plain http
  // from a file server during development.
  if (!('serviceWorker' in navigator)) return;
  if (!window.isSecureContext) return;
  navigator.serviceWorker.register('service-worker.js').catch(() => {
    // Offline support is an enhancement; failing to register must not break
    // the page.
  });
}
