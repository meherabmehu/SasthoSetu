/* Shared UI helpers: layout chrome, toasts, formatting and severity display. */
import { i18n } from './i18n.js';
import { api, session, queue, flushQueue } from './api.js';

const THEME_KEY = 'sasthosetu.theme';

/* ---------------------------------------------------------------- escaping */

export function escapeHtml(value) {
  if (value === null || value === undefined) return '';
  return String(value)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

/* ------------------------------------------------------------------ theme */

export const theme = {
  get current() {
    return localStorage.getItem(THEME_KEY) || 'light';
  },
  apply(value) {
    document.documentElement.dataset.theme = value;
    localStorage.setItem(THEME_KEY, value);
  },
  toggle() {
    this.apply(this.current === 'dark' ? 'light' : 'dark');
  },
  init() {
    this.apply(this.current);
  },
};

/* ------------------------------------------------------------------ toasts */

let toastRegion;

export function toast(message, variant = '') {
  if (!toastRegion) {
    toastRegion = document.createElement('div');
    toastRegion.className = 'toast-region';
    toastRegion.setAttribute('role', 'status');
    toastRegion.setAttribute('aria-live', 'polite');
    document.body.appendChild(toastRegion);
  }
  const node = document.createElement('div');
  node.className = `toast ${variant ? `toast-${variant}` : ''}`;
  node.textContent = message;
  toastRegion.appendChild(node);
  setTimeout(() => node.remove(), 4500);
}

/* -------------------------------------------------------------- formatting */

export function formatBdt(amount) {
  if (amount === null || amount === undefined) return '-';
  return `৳ ${Number(amount).toLocaleString('en-BD', {
    minimumFractionDigits: 0,
    maximumFractionDigits: 2,
  })}`;
}

export function formatDate(value) {
  if (!value) return '-';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return String(value);
  return date.toLocaleDateString(i18n.lang === 'bn' ? 'bn-BD' : 'en-GB', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  });
}

export function formatDateTime(value) {
  if (!value) return '-';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return String(value);
  return date.toLocaleString(i18n.lang === 'bn' ? 'bn-BD' : 'en-GB', {
    dateStyle: 'medium',
    timeStyle: 'short',
  });
}

/* -------------------------------------------------------------- severity */

export const SEVERITY_LEVELS = {
  SELF_CARE: 1,
  TELECONSULT: 2,
  GP_VISIT: 3,
  SPECIALIST: 4,
  EMERGENCY: 5,
};

// Icons back up the colour so severity survives colour blindness, greyscale
// printing and forced-colours mode.
const SEVERITY_ICONS = { 1: '🏠', 2: '💬', 3: '🩺', 4: '🏥', 5: '🚨' };

export function severityNumber(triageLevel, severityLevel) {
  if (severityLevel) return Number(severityLevel);
  return SEVERITY_LEVELS[triageLevel] || 3;
}

export function severityChip(level) {
  const n = Number(level) || 3;
  return `<span class="severity severity-${n}">
    <span aria-hidden="true">${SEVERITY_ICONS[n]}</span>
    <span>${escapeHtml(i18n.t(`severity.${n}`))}</span>
  </span>`;
}

/* ------------------------------------------------------------------ chrome */

const NAV_BY_ROLE = {
  // Signed out, only what actually works without an account is offered.
  // Listing gated pages here would send a visitor straight to a login bounce.
  guest: [
    ['index.html', 'nav.home'],
    ['verify.html', 'nav.verify'],
  ],
  PATIENT: [
    ['index.html', 'nav.home'],
    ['triage.html', 'nav.triage'],
    ['recommend.html', 'nav.doctors'],
    ['appointments.html', 'nav.appointments'],
    ['review.html', 'review.title'],
    ['records.html', 'nav.records'],
    ['hospitals.html', 'nav.hospitals'],
    ['pharmacy.html', 'nav.pharmacy'],
  ],
  DOCTOR: [
    ['doctor.html', 'nav.dashboard'],
    ['doctor-schedule.html', 'nav.schedule'],
    ['verify.html', 'nav.verify'],
    ['triage.html', 'nav.triage'],
  ],
  ADMIN: [
    ['admin.html', 'nav.dashboard'],
    ['hospitals.html', 'nav.hospitals'],
    ['doctors.html', 'nav.doctors'],
    ['verify.html', 'nav.verify'],
  ],
};

function navFor(user) {
  if (!user) return NAV_BY_ROLE.guest;
  return NAV_BY_ROLE[user.role] || NAV_BY_ROLE.PATIENT;
}

export function renderChrome({ active = '' } = {}) {
  theme.init();

  const user = session.user;
  const links = navFor(user)
    .map(([href, key]) => {
      const current = href === active;
      return `<a href="${href}" class="navlink${current ? ' navlink-active' : ''}"
        ${current ? 'aria-current="page"' : ''} data-i18n="${key}">${escapeHtml(i18n.t(key))}</a>`;
    })
    .join('');

  const authArea = session.isAuthenticated
    ? `<button class="btn btn-ghost btn-sm" id="logoutBtn" data-i18n="nav.logout">${escapeHtml(i18n.t('nav.logout'))}</button>`
    : `<a href="login.html" class="btn btn-sm" data-i18n="nav.login">${escapeHtml(i18n.t('nav.login'))}</a>`;

  const header = document.createElement('header');
  header.className = 'site-header no-print';
  header.innerHTML = `
    <a class="skip-link" href="#main">Skip to content</a>
    <div class="header-inner container">
      <a class="brand" href="index.html">
        <span class="brand-mark" aria-hidden="true">✚</span>
        <span class="brand-text">
          <strong data-i18n="app.name">${escapeHtml(i18n.t('app.name'))}</strong>
          <small data-i18n="app.tagline">${escapeHtml(i18n.t('app.tagline'))}</small>
        </span>
      </a>
      <button class="nav-toggle btn btn-ghost btn-sm" id="navToggle"
        aria-expanded="false" aria-controls="primaryNav" aria-label="Menu">☰</button>
      <nav class="primary-nav" id="primaryNav" aria-label="Primary">${links}</nav>
      <div class="header-actions">
        <button class="btn btn-ghost btn-sm" id="langBtn" aria-label="Change language">
          ${i18n.lang === 'bn' ? 'EN' : 'বাং'}
        </button>
        <button class="btn btn-ghost btn-sm" id="themeBtn" aria-label="Toggle dark mode">
          ${theme.current === 'dark' ? '☀' : '☾'}
        </button>
        ${authArea}
      </div>
    </div>
    <div class="offline-banner hidden" id="offlineBanner" role="status">
      ${escapeHtml(i18n.t('status.offline'))}
    </div>`;

  document.body.prepend(header);

  header.querySelector('#langBtn').addEventListener('click', () => {
    i18n.toggle();
    window.location.reload();
  });
  header.querySelector('#themeBtn').addEventListener('click', () => {
    theme.toggle();
    header.querySelector('#themeBtn').textContent =
      theme.current === 'dark' ? '☀' : '☾';
  });
  header.querySelector('#navToggle').addEventListener('click', (event) => {
    const nav = header.querySelector('#primaryNav');
    const open = nav.classList.toggle('open');
    event.currentTarget.setAttribute('aria-expanded', String(open));
  });
  const logout = header.querySelector('#logoutBtn');
  if (logout) {
    logout.addEventListener('click', () => {
      api.logout();
      window.location.href = 'login.html';
    });
  }

  const banner = header.querySelector('#offlineBanner');
  const syncBanner = () => banner.classList.toggle('hidden', navigator.onLine);
  window.addEventListener('online', syncBanner);
  window.addEventListener('offline', syncBanner);
  syncBanner();

  window.addEventListener('unauthorized', () => {
    toast(i18n.t('auth.needLogin'), 'danger');
    setTimeout(() => {
      window.location.href = 'login.html';
    }, 1200);
  });

  window.addEventListener('queueflushed', (event) => {
    toast(`${event.detail.sent} ${i18n.t('status.saved')}`, 'success');
  });

  if (navigator.onLine && queue.size > 0) flushQueue();

  i18n.apply();
  return header;
}

export function renderFooter() {
  const footer = document.createElement('footer');
  footer.className = 'site-footer no-print';
  footer.innerHTML = `
    <div class="container">
      <p class="small muted mb-0">
        <strong data-i18n="app.name">${escapeHtml(i18n.t('app.name'))}</strong> ·
        <span data-i18n="disclaimer">${escapeHtml(i18n.t('disclaimer'))}</span>
      </p>
      <p class="tiny subtle mb-0">
        <span data-i18n="emergency.call">${escapeHtml(i18n.t('emergency.call'))}</span>
      </p>
    </div>`;
  document.body.appendChild(footer);
  return footer;
}

/* ------------------------------------------------------------- guards etc */

export function requireAuth(...roles) {
  if (!session.isAuthenticated) {
    window.location.href = `login.html?next=${encodeURIComponent(
      window.location.pathname.split('/').pop()
    )}`;
    return false;
  }
  if (roles.length && !session.hasRole(...roles)) {
    document.body.innerHTML =
      `<div class="container"><div class="alert alert-danger mt-4">
        ${escapeHtml(i18n.t('auth.needLogin'))}</div></div>`;
    return false;
  }
  return true;
}

export function skeletonList(count = 3) {
  return Array.from({ length: count })
    .map(
      () => `<div class="card"><div class="skeleton" style="height:16px;width:60%"></div>
      <div class="skeleton mt-4" style="height:12px;width:90%"></div></div>`
    )
    .join('');
}

export function emptyState(messageKey = 'status.none', icon = '🔍') {
  return `<div class="empty">
    <div class="empty-icon" aria-hidden="true">${icon}</div>
    <p class="mb-0">${escapeHtml(i18n.t(messageKey))}</p>
  </div>`;
}

export function errorState(message) {
  return `<div class="alert alert-danger">${escapeHtml(message)}</div>`;
}

export function setBusy(button, busy, label) {
  if (!button) return;
  button.disabled = busy;
  if (busy) {
    button.dataset.originalLabel = button.innerHTML;
    button.innerHTML = `<span class="spinner" aria-hidden="true"></span> ${escapeHtml(
      label || i18n.t('status.loading')
    )}`;
  } else if (button.dataset.originalLabel) {
    button.innerHTML = button.dataset.originalLabel;
  }
}
