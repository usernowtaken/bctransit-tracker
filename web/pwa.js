/* PWA installation on Chromium and Apple touch devices. No tracking. */
(() => {
  'use strict';
  const byId = id => document.getElementById(id);
  const installButton = byId('installButton');
  const helpSection = byId('installHelpSection');
  const helpButton = byId('installHelpButton');
  const help = byId('installHelp');
  const ua = navigator.userAgent || '';
  const appleTouch = /iPad|iPhone|iPod/i.test(ua) ||
    (/Mac/i.test(navigator.platform || ua) && navigator.maxTouchPoints > 1);
  const displayMode = window.matchMedia('(display-mode: standalone)');
  const standalone = () => displayMode.matches || navigator.standalone === true;
  let promptEvent = null;
  document.documentElement.classList.toggle('apple-touch', appleTouch);
  function syncInstall() {
    const installed = standalone();
    document.documentElement.classList.toggle('installed-webapp', installed);
    if (installButton) installButton.hidden = installed || !(promptEvent || appleTouch);
    if (helpSection) helpSection.hidden = installed || !appleTouch;
  }
  function openHelp() {
    if (!help || standalone()) return;
    const settings = byId('v34Settings');
    if (settings?.open) settings.close();
    if (!help.open) help.showModal();
  }
  if ('serviceWorker' in navigator && window.isSecureContext) {
    navigator.serviceWorker.register('/sw.js?v=4.0-alpha2').then(registration => {
      // Ask for a newer worker on resume, not every GPS refresh.
      let lastCheck = Date.now();
      const check = () => {
        if (document.visibilityState !== 'visible' || Date.now()-lastCheck < 300000) return;
        lastCheck=Date.now(); registration.update().catch(()=>{});
      };
      document.addEventListener('visibilitychange',check);
      window.addEventListener('pageshow',check);
    }).catch(error => console.info('Offline app shell unavailable:',error));
  }
  window.addEventListener('beforeinstallprompt', event => {
    event.preventDefault(); promptEvent=event; syncInstall();
  });
  installButton?.addEventListener('click', async () => {
    if (standalone()) return;
    if (!promptEvent) { if (appleTouch) openHelp(); return; }
    const event=promptEvent; promptEvent=null; syncInstall();
    try { await event.prompt(); } catch (_) { if (appleTouch) openHelp(); }
  });
  helpButton?.addEventListener('click',openHelp);
  byId('installHelpClose')?.addEventListener('click',()=>help.close());
  window.addEventListener('appinstalled',()=>{promptEvent=null;if(installButton)installButton.hidden=true;if(helpSection)helpSection.hidden=true;});
  if (displayMode.addEventListener) displayMode.addEventListener('change',syncInstall);
  else displayMode.addListener?.(syncInstall);
  syncInstall();
})();
