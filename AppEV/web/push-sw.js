/**
 * PlagSini EV — PWA Push Notification Service Worker
 * Handles background Web Push events from the server.
 *
 * NOTE: We deliberately DON'T call skipWaiting() / clients.claim() here.
 * On iOS Safari, the controllerchange event from claim() races with
 * Flutter's own auto-generated flutter_service_worker.js (registered by
 * flutter_bootstrap.js at the same scope), and Safari ends up in an
 * infinite reload loop. Letting this SW activate naturally on the next
 * page load avoids the conflict.
 */

// Handle incoming push event
self.addEventListener('push', function(event) {
  let data = { title: 'PlagSini EV', body: 'Anda mempunyai notifikasi baru', url: '/', tag: 'plagsini' };

  if (event.data) {
    try {
      data = Object.assign(data, JSON.parse(event.data.text()));
    } catch (_) {}
  }

  const options = {
    body:  data.body,
    icon:  data.icon  || '/icons/Icon-192.png',
    badge: data.badge || '/icons/Icon-192.png',
    tag:   data.tag   || 'plagsini-ev',
    data:  { url: data.url || '/' },
    vibrate: [200, 100, 200],
    requireInteraction: false,
  };

  event.waitUntil(self.registration.showNotification(data.title, options));
});

// Handle notification click — open or focus app
self.addEventListener('notificationclick', function(event) {
  event.notification.close();
  const url = (event.notification.data && event.notification.data.url) || '/';

  event.waitUntil(
    clients.matchAll({ type: 'window', includeUncontrolled: true }).then(function(clientList) {
      for (const client of clientList) {
        if (client.url.includes(self.location.origin) && 'focus' in client) {
          return client.focus();
        }
      }
      if (clients.openWindow) return clients.openWindow(url);
    })
  );
});
