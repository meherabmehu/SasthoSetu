/* Boilerplate every page repeats: font preload, chrome, footer, i18n. */
import { i18n } from './i18n.js';
import { renderChrome, renderFooter } from './ui.js';

export function bootstrap(active) {
  renderChrome({ active });
  renderFooter();
  i18n.apply();
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
