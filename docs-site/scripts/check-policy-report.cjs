// Capture real policy-demo reports and exercise policy-specific review controls.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {pathToFileURL} = require('node:url');
const {chromium} = require('@playwright/test');

(async () => {
  const root = path.resolve(process.argv[2] || '/tmp/dicomqc-workspace-design/policy');
  const browser = await chromium.launch({headless: true});
  try {
    const page = await browser.newPage({viewport: {width: 1440, height: 1000}, colorScheme: 'light'});
    const errors = [], network = [];
    page.on('pageerror', error => errors.push(error.message));
    page.on('request', request => { if (/^https?:/.test(request.url())) network.push(request.url()); });
    await page.goto(pathToFileURL(path.join(root, 'before.html')).href);
    assert.equal(await page.locator('.issue').count(), 3);
    assert.equal(await page.locator('.issue[data-category="Project policy"]').count(), 3);
    assert(await page.getByText('Errors require attention', {exact: true}).isVisible());
    assert.equal(await page.locator('#overview-panel').getAttribute('open'), null);
    assert.equal(await page.locator('#filter-panel').getAttribute('open'), null);
    await page.screenshot({path: path.join(root, 'html-policy.png'), fullPage: true});
    await page.locator('#overview-panel > summary').click();
    assert(await page.locator('#overview-panel').getByText('research-demo', {exact: true}).isVisible());
    assert((await page.locator('#overview-panel').innerText()).includes('Policy SHA-256'));
    await page.locator('#overview-panel > summary').click();
    await page.locator('#filter-panel > summary').click();
    await page.locator('#category').selectOption('Project policy');
    assert.equal(await page.locator('.issue:visible').count(), 3);
    await page.locator('#search').fill('PatientComments');
    assert.equal(await page.locator('.issue:visible').count(), 1);
    await page.locator('#reset').click();
    await page.locator('#filter-panel > summary').click();
    for (const width of [390, 320]) {
      await page.setViewportSize({width, height: 844});
      await page.locator('#overview-panel > summary').click();
      assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
      await page.locator('#overview-panel > summary').click();
    }
    await page.emulateMedia({colorScheme: 'dark'});
    await page.screenshot({path: path.join(root, 'html-policy-dark-mobile.png'), fullPage: true});
    await page.getByRole('link', {name: 'After corrections', exact: true}).click();
    assert(await page.getByText('Checks passed', {exact: true}).isVisible());
    assert.equal(await page.locator('.issue').count(), 0);
    await page.locator('#overview-panel > summary').click();
    assert(await page.locator('#overview-panel').getByText('research-demo', {exact: true}).isVisible());
    await page.locator('#overview-panel > summary').click();
    await page.setViewportSize({width: 1440, height: 1000});
    await page.emulateMedia({colorScheme: 'light'});
    await page.screenshot({path: path.join(root, 'html-policy-after.png'), fullPage: true});
    for (const phase of ['before', 'after']) {
      const html = fs.readFileSync(path.join(root, phase + '.html'), 'utf8');
      for (const sensitive of ['Example Patient', 'Synthetic identifying comment', 'T2w']) {
        assert(!html.includes(sensitive), 'Report leaked a tag value or configured allowlist');
      }
    }
    assert.deepEqual(errors, []);
    assert.deepEqual(network, []);
    console.log('Policy reports passed: groups, provenance, filters, mobile, before/after, redaction and offline checks.');
  } finally {
    await browser.close();
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
