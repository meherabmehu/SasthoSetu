/* Boilerplate every page repeats: font preload, chrome, footer, i18n. */
import { i18n } from './i18n.js';
import { renderChrome, renderFooter } from './ui.js';

export function bootstrap(active) {
  renderChrome({ active });
  renderFooter();
  i18n.apply();
}
