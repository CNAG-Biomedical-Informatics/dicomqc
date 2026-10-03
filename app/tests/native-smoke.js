(async () => {
  if (window.__dicomqcSmokeStarted) return;
  window.__dicomqcSmokeStarted = true;
  const invoke = (name, args) => window.__TAURI_INTERNALS__.invoke(name, args);
  const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));
  const errors = [];
  window.addEventListener('error', event => errors.push(event.message));
  window.addEventListener('unhandledrejection', event => errors.push(String(event.reason)));
  const wait = async (predicate, label) => {
    const until = Date.now() + 30000;
    while (!predicate()) {
      if (Date.now() > until) throw new Error(`Timed out: ${label}`);
      await sleep(100);
    }
  };
  const button = label => [...document.querySelectorAll('button')].find(node => (node.getAttribute('aria-label') || node.textContent.trim()) === label);
  const click = async label => {
    await wait(() => button(label) && !button(label).disabled, label);
    button(label).click(); await sleep(200);
  };
  const checkpoint = async label => {
    await sleep(250);
    const overflow = [...document.querySelectorAll('button,select,.finding')]
      .filter(node => node.offsetWidth && node.scrollWidth > node.clientWidth + 2).map(node => node.textContent);
    if (document.documentElement.scrollWidth > innerWidth || overflow.length) throw new Error(`Overflow: ${label}: ${overflow}`);
    for (const row of document.querySelectorAll('.run-list button')) {
      const bottom = row.getBoundingClientRect().bottom;
      if ([...row.children].some(child => child.getBoundingClientRect().bottom > bottom + 2)) {
        await invoke('smoke_checkpoint', {label, details: {row: row.getBoundingClientRect().toJSON(), children: [...row.children].map(child => ({text: child.textContent, rect: child.getBoundingClientRect().toJSON()}))}});
        throw new Error(`History text exceeds row: ${label}`);
      }
    }
    if (errors.length) throw new Error(errors.join('; '));
    await invoke('smoke_checkpoint', {label, details: {viewport: [innerWidth, innerHeight], overflow, errors}});
  };
  try {
    await wait(() => document.body.textContent.includes('Local engine ready'), 'engine ready');
    await invoke('plugin:event|emit', {event: 'desktop-menu', payload: 'settings'});
    await wait(() => document.getElementById('settings-heading'), 'native menu navigation');
    const select = document.querySelector('select');
    select.value = 'light'; select.dispatchEvent(new Event('change', {bubbles: true}));
    await click('New audit'); await checkpoint('01-scan');
    await click('Compare datasets'); await checkpoint('02-compare');
    for (const example of ['Scan', 'Compare', 'Policy', 'UID integrity', 'Vendor']) {
      await click('New audit');
      document.querySelector('.examples').open = true;
      await click(example);
      await wait(() => document.querySelector('.findings-heading'), `${example} results`);
      if (document.querySelector('[role="alert"]')) throw new Error('Unexpected error in audit');
      const finding = document.querySelector('.finding');
      if (finding) finding.open = true;
      window.scrollTo(0, 0);
      await checkpoint(`03-${example.toLowerCase().replaceAll(' ', '-')}`);
    }
    await click('Reports');
    await wait(() => document.querySelector('iframe'), 'report preview');
    const frame = document.querySelector('iframe');
    if (frame.getAttribute('sandbox') !== '') throw new Error('Report preview is not isolated');
    await checkpoint('04-report-preview');
    await click('Findings');
    const search = document.querySelector('input[aria-label="Find runs"]');
    const setValue = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set;
    setValue.call(search, 'vendor'); search.dispatchEvent(new Event('input', {bubbles: true}));
    await wait(() => document.querySelectorAll('.run-list button').length === 1, 'filtered history');
    await checkpoint('04-filtered-history');
    setValue.call(search, ''); search.dispatchEvent(new Event('input', {bubbles: true}));
    await wait(() => document.querySelectorAll('.run-list button').length === 5, 'restored history');
    await click('Settings'); window.scrollTo(0, 0);
    const theme = document.querySelector('select');
    theme.value = 'dark'; theme.dispatchEvent(new Event('change', {bubbles: true}));
    await checkpoint('05-settings-dark');
    await invoke('smoke_checkpoint', {label: 'resize', details: {width: 760}});
    await click('New audit'); window.scrollTo(0, 0); await checkpoint('06-narrow-dark');
    await invoke('smoke_finish', {error: null});
  } catch (error) {
    await invoke('smoke_finish', {error: String(error)});
  }
})();
