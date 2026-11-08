/* Minimal PWA install support, no extra dependencies or tracking. */
(() => {
  'use strict';
  const installButton = document.getElementById('installButton');
  let promptEvent = null;
  const standalone = () => window.matchMedia('(display-mode: standalone)').matches ||
      window.navigator.standalone === true;
  if ('serviceWorker' in navigator && window.isSecureContext) {
    navigator.serviceWorker.register('/sw.js?v=3.2.0').catch((error) =>
      console.info('Offline app shell unavailable:', error));
  }
  window.addEventListener('beforeinstallprompt', (event) => {
    event.preventDefault();
    promptEvent = event;
    if (installButton && !standalone()) installButton.hidden = false;
  });
  if (installButton) {
    installButton.addEventListener('click', async () => {
      if (!promptEvent) return;
      const event = promptEvent;
      promptEvent = null;
      installButton.hidden = true;
      try { await event.prompt(); } catch (_) { /* Chrome install UI may be unavailable. */ }
    });
  }
  window.addEventListener('appinstalled', () => {
    promptEvent = null;
    if (installButton) installButton.hidden = true;
  });
})();
