/* API client, session handling and the offline write queue.
 *
 * Connectivity in much of Bangladesh is intermittent, so a failed write is
 * treated as normal rather than exceptional: safe requests are queued in
 * localStorage and replayed when the connection returns, and reads fall back
 * to the last cached response so a patient is never left with a blank screen.
 */
import { i18n } from './i18n.js';

const TOKEN_KEY = 'sasthosetu.token';
const USER_KEY = 'sasthosetu.user';
const QUEUE_KEY = 'sasthosetu.queue';
const CACHE_PREFIX = 'sasthosetu.cache.';
const STORAGE_PREFIX = 'sasthosetu.private.v2.';
const TAB_ID = sessionStorage.getItem('sasthosetu.tab') || crypto.randomUUID();
sessionStorage.setItem('sasthosetu.tab', TAB_ID);
const MAX_AGE = 24 * 60 * 60 * 1000;
// Discard the old unencrypted, unowned data rather than migrating identities.
localStorage.removeItem(QUEUE_KEY);
for (const key of Object.keys(localStorage)) {
  if (key.startsWith(CACHE_PREFIX)) localStorage.removeItem(key);
}

function identity() {
  const user = session.user;
  return user?.user_id || user?.id || null;
}
function privateKey(kind) {
  const owner = identity();
  return owner && session.token ? `${STORAGE_PREFIX}${owner}.${TAB_ID}.${kind}` : null;
}
async function encryptionKey() {
  const name = 'sasthosetu.crypto.' + TAB_ID;
  let raw = sessionStorage.getItem(name);
  if (!raw) {
    raw = JSON.stringify(Array.from(crypto.getRandomValues(new Uint8Array(32))));
    sessionStorage.setItem(name, raw);
  }
  return crypto.subtle.importKey('raw', new Uint8Array(JSON.parse(raw)), 'AES-GCM', false,
    ['encrypt', 'decrypt']);
}
async function seal(data) {
  const iv = crypto.getRandomValues(new Uint8Array(12));
  const bytes = new TextEncoder().encode(JSON.stringify(data));
  const cipher = await crypto.subtle.encrypt({ name: 'AES-GCM', iv }, await encryptionKey(), bytes);
  return { iv: Array.from(iv), cipher: Array.from(new Uint8Array(cipher)) };
}
async function unseal(data) {
  const bytes = await crypto.subtle.decrypt({ name: 'AES-GCM', iv: new Uint8Array(data.iv) },
    await encryptionKey(), new Uint8Array(data.cipher));
  return JSON.parse(new TextDecoder().decode(bytes));
}
function discardPrivateData() {
  for (const key of Object.keys(localStorage)) {
    if (key.startsWith(STORAGE_PREFIX) || key.startsWith(CACHE_PREFIX)) localStorage.removeItem(key);
  }
  sessionStorage.removeItem('sasthosetu.crypto.' + TAB_ID);
  localStorage.removeItem(QUEUE_KEY);
}


function resolveBase() {
  // An explicit override always wins, which is how a deployment points the
  // static bundle at an API on another host.
  const override = localStorage.getItem('sasthosetu.apiBase');
  if (override) return override;

  const meta = document.querySelector('meta[name="api-base"]');
  if (meta?.content) return meta.content;

  const { origin, protocol, hostname, port } = window.location;

  // Opened straight from disk: nothing to infer from, use the local API.
  if (protocol === 'file:') return 'http://127.0.0.1:8000/api/v1';

  // Served by the API itself, or behind a reverse proxy on a standard port:
  // the API lives at the same origin.
  if (port === '' || port === '80' || port === '443' || port === '8000') {
    return `${origin}/api/v1`;
  }

  // Any other port is a separate static dev server, so the API is the
  // conventional :8000 on the same host.
  return `${protocol}//${hostname}:8000/api/v1`;
}

export const API_BASE = resolveBase();

export class ApiError extends Error {
  constructor(message, status, body) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.body = body;
  }
}

export const session = {
  get token() {
    return localStorage.getItem(TOKEN_KEY);
  },
  get user() {
    try {
      return JSON.parse(localStorage.getItem(USER_KEY) || 'null');
    } catch {
      return null;
    }
  },
  get isAuthenticated() {
    return Boolean(this.token);
  },
  hasRole(...roles) {
    const user = this.user;
    return Boolean(user && roles.includes(user.role));
  },
  save(token, user) {
    if (this.token !== token) discardPrivateData();
    localStorage.setItem(TOKEN_KEY, token);
    if (user) localStorage.setItem(USER_KEY, JSON.stringify(user));
    else localStorage.removeItem(USER_KEY);
  },
  clear() {
    discardPrivateData();
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(USER_KEY);
    for (const key of Object.keys(localStorage)) {
      if (key.startsWith(CACHE_PREFIX)) localStorage.removeItem(key);
    }
    // Resolves once the cached responses are gone. Callers that are about to
    // navigate must await it, or the browser tears the page down first and
    // the deletion never completes.
    return clearCachedResponses();
  },
};

/* The service worker keeps a copy of every successful API read so the app
 * still shows something useful without a connection. Those copies include
 * prescriptions, appointments and triage history, and removing the token
 * does not remove them: the next person to use the phone could read the
 * previous patient's records straight out of the cache.
 *
 * Signing out therefore has to discard the data cache as well. The shell
 * cache is left alone - it holds only the pages themselves, and throwing it
 * away would mean re-downloading the whole app on a connection that may not
 * be there.
 */
function clearCachedResponses() {
  if (!('caches' in window)) return Promise.resolve();
  return caches
    .keys()
    .then((names) =>
      Promise.all(
        names
          .filter((name) => name.includes('data'))
          .map((name) => caches.delete(name))
      )
    )
    .catch(() => {
      /* A browser that refuses cache access has nothing stored to leak. */
    });
}

/* Cached reads are scoped to the account that fetched them: the same URL
   returns different rows for different users, and a shared device must not
   show one patient the previous patient's screen. */
async function readCache(path) {
  const key = privateKey('cache.' + path);
  const token = session.token;
  try {
    const raw = key && localStorage.getItem(key);
    if (!raw) return null;
    const entry = await unseal(JSON.parse(raw));
    if (session.token !== token || Date.now() - entry.time > MAX_AGE) return null;
    return entry.data;
  } catch { return null; }
}

async function writeCache(path, data, token) {
  const key = privateKey('cache.' + path);
  if (!key || token !== session.token) return;
  try {
    const entry = await seal({ time: Date.now(), data });
    if (token === session.token) localStorage.setItem(key, JSON.stringify(entry));
  } catch { /* Storage is best effort. */ }
}

export const queue = {
  records() {
    try { return JSON.parse(localStorage.getItem(privateKey('queue')) || '[]'); }
    catch { return []; }
  },
  async all() {
    const token = session.token;
    const items = [];
    for (const record of this.records()) {
      try {
        const item = await unseal(record);
        if (item.owner === identity() && Date.now() - item.queuedAt <= MAX_AGE) items.push(item);
      } catch { /* A different tab or expired key cannot decrypt the entry. */ }
    }
    return token === session.token ? items : [];
  },
  async add(entry, token) {
    const key = privateKey('queue');
    if (!key || token !== session.token) throw new Error('Session changed');
    const item = { ...entry, owner: identity(), id: crypto.randomUUID(), queuedAt: Date.now() };
    const encrypted = await seal(item);
    if (token !== session.token) throw new Error('Session changed');
    const items = this.records();
    items.push({ ...encrypted, id: item.id });
    localStorage.setItem(key, JSON.stringify(items));
    window.dispatchEvent(new CustomEvent('queuechange', { detail: { size: items.length } }));
  },
  remove(id) {
    const key = privateKey('queue');
    if (!key) return;
    const items = this.records().filter((item) => item.id !== id);
    localStorage.setItem(key, JSON.stringify(items));
    window.dispatchEvent(new CustomEvent('queuechange', { detail: { size: items.length } }));
  },
  get size() { return this.records().length; },
};

async function request(path, { method = 'GET', body, auth = true, queueable = false, cache = false } = {}) {
  const requestToken = session.token;
  const headers = { Accept: 'application/json' };
  if (body !== undefined) headers['Content-Type'] = 'application/json';
  if (auth && requestToken) headers.Authorization = `Bearer ${requestToken}`;

  try {
    const response = await fetch(`${API_BASE}${path}`, {
      method,
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
    });

    if (auth && requestToken !== session.token) throw new ApiError('Session changed', 409, null);
    if (response.status === 401 && auth) {
      // An expired session ends the same way a deliberate sign-out does, so
      // the cached records have to go with it.
      await session.clear();
      window.dispatchEvent(new CustomEvent('unauthorized'));
      throw new ApiError(i18n.t('auth.needLogin'), 401, null);
    }

    const text = await response.text();
    const data = text ? JSON.parse(text) : null;

    if (!response.ok) {
      const detail = data?.detail;
      const message = Array.isArray(detail)
        ? detail.map((d) => d.msg).join(', ')
        : detail || `${i18n.t('status.error')} (${response.status})`;
      throw new ApiError(message, response.status, data);
    }

    if (cache && method === 'GET') await writeCache(path, data, requestToken);
    return data;
  } catch (error) {
    if (error instanceof ApiError) throw error;

    if (auth && requestToken !== session.token) throw new ApiError('Session changed', 409, null);
    // Network-level failure: fall back to cache for reads, queue writes.
    if (method === 'GET' && cache) {
      const cached = await readCache(path);
      if (cached) return Array.isArray(cached) ? cached : { ...cached, __fromCache: true };
    }
    if (queueable && method !== 'GET') {
      await queue.add({ path, method, body }, requestToken);
      throw new ApiError(i18n.t('status.queued'), 0, { queued: true });
    }
    throw new ApiError(i18n.t('status.offline'), 0, null);
  }
}

export const api = {
  get: (path, options) => request(path, { ...options, method: 'GET' }),
  post: (path, body, options) => request(path, { ...options, method: 'POST', body }),
  put: (path, body, options) => request(path, { ...options, method: 'PUT', body }),
  patch: (path, body, options) => request(path, { ...options, method: 'PATCH', body }),
  delete: (path, options) => request(path, { ...options, method: 'DELETE' }),

  async login(email, password) {
    const data = await request('/auth/login', {
      method: 'POST',
      body: { email, password },
      auth: false,
    });
    session.save(data.access_token, null);
    try {
      const me = await request('/auth/me');
      session.save(data.access_token, me);
    } catch (error) {
      // Never continue under a previous account's cached identity.
      await session.clear();
      throw error;
    }
    return session.user;
  },

  register: (payload) => request('/users', { method: 'POST', body: payload, auth: false }),

  async logout() {
    try { await request('/auth/logout', { method: 'POST', body: {} }); } catch { /* Offline sign-out still clears this device. */ }
    await session.clear();
    window.dispatchEvent(new CustomEvent('loggedout'));
  },
};

/** Replay queued writes, oldest first. Stops at the first failure. */
let flushing;
export function flushQueue() {
  if (!flushing) {
    const replay = () => replayQueue();
    const lock = privateKey('queue');
    flushing = (navigator.locks && lock ? navigator.locks.request(lock, replay) : replay())
      .finally(() => { flushing = null; });
  }
  return flushing;
}
async function replayQueue() {
  const token = session.token;
  const items = await queue.all();
  let sent = 0;

  for (const item of items) {
    if (!token || token !== session.token || item.owner !== identity()) break;
    try {
      await request(item.path, { method: item.method, body: item.body });
      if (token !== session.token) break;
      queue.remove(item.id);
      sent += 1;
    } catch (error) {
      if (token !== session.token || error.status === 401) break;
      if (error.status && error.status >= 400 && error.status < 500) {
        // A rejected request will never succeed on retry; drop it rather
        // than blocking everything queued behind it.
        queue.remove(item.id);
        continue;
      }
      break;
    }
  }
  return sent;
}

window.addEventListener('storage', (event) => {
  if (event.key === TOKEN_KEY) {
    discardPrivateData();
    clearCachedResponses();
    window.dispatchEvent(new CustomEvent('unauthorized'));
  }
});

window.addEventListener('online', () => {
  flushQueue().then((sent) => {
    if (sent > 0) {
      window.dispatchEvent(
        new CustomEvent('queueflushed', { detail: { sent } })
      );
    }
  });
});
