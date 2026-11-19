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
    ? 'ডেমো/স্যান্ডবক্স: কোনো আসল টাকা, SMS বা IVR পাঠানো হয় না। হাসপাতালের শয্যা ও পূর্বাভাস live যাচাইকৃত তথ্য নয়। AI ফল রোগ নির্ণয় নয়—জরুরি বিপদে এখনই নিকটস্থ হাসপাতালে যান বা ৯৯৯-এ কল করুন।'
    : 'Demo/sandbox: no real money, SMS or IVR is delivered. Bed capacity and forecasts are not verified live data. AI is not a diagnosis; for an emergency, go to the nearest hospital or call 999.';
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
