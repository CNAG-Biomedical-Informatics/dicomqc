// Real UID-demo reports: offline controls, coverage, privacy, and screenshots.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {pathToFileURL} = require('node:url');
const {chromium} = require('@playwright/test');

(async () => {
  const root = path.resolve(process.argv[2] || '/tmp/dicomqc-workspace-design/uid');
  const browser = await chromium.launch({headless: true});
  try {
    const page = await browser.newPage({viewport: {width: 1440, height: 1000}, colorScheme: 'light'});
    const errors = [], network = [];
    page.on('pageerror', error => errors.push(error.message));
    page.on('request', request => { if (/^https?:/.test(request.url())) network.push(request.url()); });
    await page.goto(pathToFileURL(path.join(root, 'before.html')).href);
    assert.equal(await page.locator('.issue[data-category="UID integrity"]').count(), 4);
    assert(await page.getByText('Errors require attention', {exact: true}).isVisible());
    assert.equal(await page.locator('#overview-panel').getAttribute('open'), null);
    assert.equal(await page.locator('#filter-panel').getAttribute('open'), null);
    await page.screenshot({path: path.join(root, 'html-report-uid.png'), fullPage: true});
    await page.locator('#overview-panel > summary').click();
    assert((await page.locator('#overview-panel .uid-coverage').innerText()).includes('3 of 4 files'));
    assert.equal(await page.locator('#overview-panel .uid-coverage tbody tr').count(), 3);
    await page.locator('#overview-panel > summary').click();
    await page.locator('#filter-panel > summary').click();
    await page.locator('#category').selectOption('UID integrity');
    assert.equal(await page.locator('.issue:visible').count(), 4);
    await page.locator('#severity').selectOption('warning');
    assert.equal(await page.locator('.issue:visible').count(), 0);
    await page.locator('#reset').click();
    await page.locator('#filter-panel > summary').click();
    for (const width of [390, 320]) {
      await page.setViewportSize({width, height: 844});
      await page.locator('#overview-panel > summary').click();
      assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
      await page.locator('#overview-panel > summary').click();
    }
    await page.emulateMedia({media: 'print'});
    assert(await page.locator('.print-overview .uid-coverage').isVisible());
    await page.emulateMedia({media: 'screen'});
    await page.getByRole('link', {name: 'After corrections', exact: true}).click();
    assert(await page.getByText('Checks passed', {exact: true}).isVisible());
    assert.equal(await page.locator('.issue').count(), 0);
    await page.locator('#overview-panel > summary').click();
    assert((await page.locator('#overview-panel .uid-coverage').innerText()).includes('4 of 4 files'));
    await page.setViewportSize({width: 1440, height: 1000});
    await page.screenshot({path: path.join(root, 'html-report-uid-after.png'), fullPage: true});
    const noJS = await browser.newPage({javaScriptEnabled: false, viewport: {width: 390, height: 844}});
    await noJS.goto(pathToFileURL(path.join(root, 'before.html')).href);
    assert.equal(await noJS.locator('.issue').count(), 4);
    await noJS.locator('#overview-panel > summary').click();
    assert(await noJS.locator('#overview-panel .uid-coverage').isVisible());
    for (const phase of ['before', 'after']) {
      assert(!fs.readFileSync(path.join(root, phase + '.html'), 'utf8').includes('1.2.826.0.1.3680043.10.54321'));
    }
    assert.deepEqual(errors, []);
    assert.deepEqual(network, []);
    // MultiQC embeds exactly the same value-free coverage and status wording.
    await page.goto(pathToFileURL(path.join(root, 'multiqc/multiqc_report.html')).href);
    const dashboard = page.locator('.dicomqc-dashboard');
    assert(await dashboard.getByText('Errors require attention', {exact: true}).isVisible());
    await dashboard.locator('summary').filter({hasText: 'Audit scope and report notes'}).click();
    assert((await dashboard.locator('.uid-coverage').innerText()).includes('3 of 4 files'));
    await dashboard.screenshot({path: path.join(root, 'multiqc-uid.png')});
    console.log('UID reports passed: findings, folded details, coverage, filters, mobile, print, no-JS, redaction, offline and MultiQC alignment.');
  } finally {
    await browser.close();
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
