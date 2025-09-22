self.addEventListener('push', function (event) {
  let data = {};
  try { data = event.data.json(); } catch (e) { /* ignore */ }
  const title = data.title || 'Neues Handelssignal';
  const body = data.body || (data.symbol ? `${data.action} ${data.symbol}` : 'Signal');
  const options = {
    body,
    data,
    icon: data.icon || '/icon.png',
    badge: data.badge || '/icon.png',
  };
  event.waitUntil(self.registration.showNotification(title, options));
});

self.addEventListener('notificationclick', function (event) {
  event.notification.close();
  event.waitUntil(clients.openWindow('/'));
});

