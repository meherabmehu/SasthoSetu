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
    localStorage.setItem(TOKEN_KEY, token);
    if (user) localStorage.setItem(USER_KEY, JSON.stringify(user));
  },
  clear() {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(USER_KEY);
    for (const key of Object.keys(localStorage)) {
      if (key.startsWith(CACHE_PREFIX)) localStorage.removeItem(key);
    }
  },
};

/* Cached reads are scoped to the account that fetched them: the same URL
   returns different rows for different users, and a shared device must not
   show one patient the previous patient's screen. */
function cacheKey(path) {
  const user = session.user;
  const scope = user?.id ?? (session.token ? 'session' : 'guest');
  return `${CACHE_PREFIX}${scope}.${path}`;
}

function readCache(path) {
  try {
    const raw = localStorage.getItem(cacheKey(path));
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

function writeCache(path, data) {
  try {
    localStorage.setItem(cacheKey(path), JSON.stringify(data));
  } catch {
    // Storage full or blocked: caching is best-effort, never fatal.
  }
}

export const queue = {
  all() {
    try {
      return JSON.parse(localStorage.getItem(QUEUE_KEY) || '[]');
    } catch {
      return [];
    }
  },
  add(entry) {
    const items = this.all();
    items.push({ ...entry, id: crypto.randomUUID(), queuedAt: Date.now() });
    localStorage.setItem(QUEUE_KEY, JSON.stringify(items));
    window.dispatchEvent(new CustomEvent('queuechange', { detail: { size: items.length } }));
  },
  remove(id) {
    const items = this.all().filter((item) => item.id !== id);
    localStorage.setItem(QUEUE_KEY, JSON.stringify(items));
    window.dispatchEvent(new CustomEvent('queuechange', { detail: { size: items.length } }));
  },
  get size() {
    return this.all().length;
  },
};

async function request(path, { method = 'GET', body, auth = true, queueable = false, cache = false } = {}) {
  const headers = { Accept: 'application/json' };
  if (body !== undefined) headers['Content-Type'] = 'application/json';
  if (auth && session.token) headers.Authorization = `Bearer ${session.token}`;

  try {
    const response = await fetch(`${API_BASE}${path}`, {
      method,
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
    });

    if (response.status === 401 && auth) {
      session.clear();
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

    if (cache && method === 'GET') writeCache(path, data);
    return data;
  } catch (error) {
    if (error instanceof ApiError) throw error;

    // Network-level failure: fall back to cache for reads, queue writes.
    if (method === 'GET' && cache) {
      const cached = readCache(path);
      if (cached) return { ...cached, __fromCache: true };
    }
    if (queueable && method !== 'GET') {
      queue.add({ path, method, body });
      throw new ApiError(i18n.t('status.queued'), 0, { queued: true });
    }
    throw new ApiError(i18n.t('status.offline'), 0, null);
  }
}

export const api = {
  get: (path, options) => request(path, { ...options, method: 'GET' }),
  post: (path, body, options) => request(path, { ...options, method: 'POST', body }),
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
    } catch {
      // Identity lookup is a convenience; the token alone is enough to proceed.
    }
    return session.user;
  },

  register: (payload) => request('/users', { method: 'POST', body: payload, auth: false }),

  logout() {
    session.clear();
    window.dispatchEvent(new CustomEvent('loggedout'));
  },
};

/** Replay queued writes, oldest first. Stops at the first failure. */
export async function flushQueue() {
  const items = queue.all();
  let sent = 0;

  for (const item of items) {
    try {
      await request(item.path, { method: item.method, body: item.body });
      queue.remove(item.id);
      sent += 1;
    } catch (error) {
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

window.addEventListener('online', () => {
  flushQueue().then((sent) => {
    if (sent > 0) {
      window.dispatchEvent(
        new CustomEvent('queueflushed', { detail: { sent } })
      );
    }
  });
});
