/* SasthoSetu service worker.
 *
 * Strategy is chosen per request type, because the right trade-off differs:
 *
 *   App shell (HTML, CSS, JS)  cache first, revalidate in background.
 *     On 2G, waiting on the network before painting anything is the difference
 *     between a usable app and an abandoned one.
 *
 *   API reads                  network first, fall back to cache.
 *     Bed counts and appointments must be fresh when a connection exists, but
 *     a stale answer beats a blank screen when it does not.
 *
 *   API writes                 never cached; the app queues them itself.
 */
const VERSION = 'v1';
const SHELL_CACHE = `sasthosetu-shell-${VERSION}`;
const DATA_CACHE = `sasthosetu-data-${VERSION}`;

const SHELL_ASSETS = [
  'index.html',
  'triage.html',
  'doctors.html',
  'recommend.html',
  'doctor-profile.html',
  'review.html',
  'hospitals.html',
  'hospital-detail.html',
  'pharmacy.html',
  'verify.html',
  'appointments.html',
  'records.html',
  'login.html',
  'doctor.html',
  'doctor-schedule.html',
  'admin.html',
  'offline.html',
  'manifest.webmanifest',
  'assets/css/design-system.css',
  'assets/css/layout.css',
  'assets/js/i18n.js',
  'assets/js/api.js',
  'assets/js/ui.js',
  'assets/js/page.js',
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches
      .open(SHELL_CACHE)
      // A single missing asset must not abort the whole install, so each is
      // added independently.
      .then((cache) =>
        Promise.allSettled(SHELL_ASSETS.map((asset) => cache.add(asset)))
      )
      .then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) =>
        Promise.all(
          keys
            .filter((key) => key !== SHELL_CACHE && key !== DATA_CACHE)
            .map((key) => caches.delete(key))
        )
      )
      .then(() => self.clients.claim())
  );
});

function isApiRequest(url) {
  return url.pathname.includes('/api/v1/');
}

self.addEventListener('fetch', (event) => {
  const { request } = event;
  if (request.method !== 'GET') return;

  const url = new URL(request.url);

  if (isApiRequest(url)) {
    event.respondWith(
      fetch(request)
        .then((response) => {
          if (response.ok) {
            const copy = response.clone();
            caches.open(DATA_CACHE).then((cache) => cache.put(request, copy));
          }
          return response;
        })
        .catch(() =>
          caches.match(request).then(
            (cached) =>
              cached ||
              new Response(
                JSON.stringify({ detail: 'Offline', offline: true }),
                { status: 503, headers: { 'Content-Type': 'application/json' } }
              )
          )
        )
    );
    return;
  }

  if (url.origin !== self.location.origin) return;

  event.respondWith(
    caches.match(request).then((cached) => {
      const network = fetch(request)
        .then((response) => {
          if (response.ok) {
            const copy = response.clone();
            caches.open(SHELL_CACHE).then((cache) => cache.put(request, copy));
          }
          return response;
        })
        .catch(() => cached || caches.match('offline.html'));

      return cached || network;
    })
  );
});
