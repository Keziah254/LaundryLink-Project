const CACHE_NAME = 'laundrylink-cache-v1';
const urlsToCache = [
  '/',
  '/static/css/style.css',
  '/static/js/main.js', // If you have a main JS file
  '/static/icons/icon-192.png',
  '/static/icons/icon-512.png'
];

// Install event: Cache files
self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then(cache => {
        console.log('Opened cache');
        return cache.addAll(urlsToCache);
      })
  );
});

// Fetch event: Serve from cache, fall back to network
self.addEventListener('fetch', event => {
  event.respondWith(
    caches.match(event.request)
      .then(response => {
        if (response) {
          return response;
        }
        return fetch(event.request);
      }
    )
  );
});