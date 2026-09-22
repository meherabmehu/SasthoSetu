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
    ['skin.html', 'nav.skin'],
    ['xray.html', 'nav.xray'],
    ['recommend.html', 'nav.doctors'],
    ['appointments.html', 'nav.appointments'],
    ['consultations.html', 'consult.title'],
    ['review.html', 'review.title'],
    ['records.html', 'nav.records'],
    ['hospitals.html', 'nav.hospitals'],
    ['map.html', 'nav.map'],
    ['pharmacy.html', 'nav.pharmacy'],
    ['account.html', 'nav.account'],
    ['notifications.html', 'notif.title'],
  ],
  DOCTOR: [
    ['doctor.html', 'nav.dashboard'],
    ['consultations.html', 'consult.title'],
    ['doctor-schedule.html', 'nav.schedule'],
    ['verify.html', 'nav.verify'],
    ['triage.html', 'nav.triage'],
    ['account.html', 'nav.account'],
    ['notifications.html', 'notif.title'],
  ],
  ADMIN: [
    ['admin.html', 'nav.dashboard'],
    ['hospitals.html', 'nav.hospitals'],
    ['doctors.html', 'nav.doctors'],
    ['verify.html', 'nav.verify'],
    ['account.html', 'nav.account'],
    ['notifications.html', 'notif.title'],
  ],
};

function navFor(user) {
  if (!user) return NAV_BY_ROLE.guest;
  return NAV_BY_ROLE[user.role] || NAV_BY_ROLE.PATIENT;
}

/* Count the reader's unread notifications and show them on the header bell.
 * Failure is silent: the bell is an ambient indicator, and an offline moment
 * or a hiccup must not throw errors onto every page. */
function updateNotificationBadge(badgeEl, userId) {
  api.get(`/notifications/${userId}`)
    .then((items) => {
      const unread = Array.isArray(items)
        ? items.filter((n) => !n.is_read).length
        : 0;
      if (unread > 0) {
        badgeEl.textContent = unread > 9 ? '9+' : String(unread);
        badgeEl.classList.remove('hidden');
        badgeEl.parentElement.setAttribute(
          'aria-label',
          `${i18n.t('notif.title')}: ${unread}`
        );
      } else {
        badgeEl.classList.add('hidden');
      }
    })
    .catch(() => {});
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

  // The bell only appears for someone signed in, and carries the count of
  // unread notifications so the rest of the app's events (a confirmed
  // appointment, a ready prescription) are visible from every page.
  const bell = session.isAuthenticated
    ? `<a href="notifications.html" class="btn btn-ghost btn-sm notif-bell"
         id="notifBell" aria-label="${escapeHtml(i18n.t('notif.title'))}">
         <span aria-hidden="true">🔔</span>
         <span class="notif-badge hidden" id="notifBadge"></span>
       </a>`
    : '';

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
        ${bell}
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

  const badge = header.querySelector('#notifBadge');
  if (badge && session.user?.user_id) {
    updateNotificationBadge(badge, session.user.user_id);
  }

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
    logout.addEventListener('click', async () => {
      // Read before the session is cleared: after signing out there is no
      // role left to decide where to go, and an administrator should not be
      // dropped onto the public site.
      const role = session.user?.role;
      // Awaited: leaving the page before the cached records are deleted
      // would abandon the deletion and leave them readable.
      await api.logout();
      window.location.href = role === 'ADMIN'
        ? 'staff-portal.html'
        : role === 'DOCTOR'
          ? 'doctor-login.html'
          : 'login.html';
    });
  }

  const banner = header.querySelector('#offlineBanner');
  const syncBanner = () => banner.classList.toggle('hidden', navigator.onLine);
  window.addEventListener('online', syncBanner);
  window.addEventListener('offline', syncBanner);
  syncBanner();

  window.addEventListener('unauthorized', () => {
    toast(i18n.t('auth.needLogin'), 'danger');
    // The session is already gone by the time this fires, so the page being
    // viewed is the only clue about which portal to return to.
    const page = window.location.pathname.split('/').pop();
    setTimeout(() => {
      window.location.href = PORTAL_FOR_PAGE[page] || 'login.html';
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

/* Which sign-in page a visitor should be sent to when they are not signed
 * in. Decided from the page they asked for, since a page's own role guard is
 * what knows who belongs there. doctors.html is deliberately absent: it is
 * the patient-facing doctor directory, not the administration list.
 */
const PORTAL_FOR_PAGE = {
  'admin.html': 'staff-portal.html',
  'doctor.html': 'doctor-login.html',
  'doctor-schedule.html': 'doctor-login.html',
};

export function requireAuth(...roles) {
  if (!session.isAuthenticated) {
    const page = window.location.pathname.split('/').pop();
    const portal = PORTAL_FOR_PAGE[page]
      || (roles.includes('ADMIN') && roles.length === 1
        ? 'staff-portal.html'
        : 'login.html');
    window.location.href = `${portal}?next=${encodeURIComponent(page)}`;
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
