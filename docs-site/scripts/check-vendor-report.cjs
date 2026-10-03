// Inspect the real vendor demo and capture the inventory beside its walkthrough.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {pathToFileURL} = require('node:url');
const {chromium} = require('@playwright/test');

(async () => {
  const root = path.resolve(process.argv[2] || '/tmp/dicomqc-workspace-design/vendor');
  const browser = await chromium.launch({headless: true});
  try {
    const report = JSON.parse(fs.readFileSync(path.join(root, 'dicomqc/report.json'), 'utf8'));
    assert.equal(report.vendor_summary.private_elements, 5);
    assert.equal(report.vendor_summary.creator_elements, 4);
    assert.equal(report.vendor_summary.unassigned_private_elements, 1);
    const page = await browser.newPage({viewport: {width: 1440, height: 1100}, colorScheme: 'light'});
    const errors = [], network = [];
    page.on('pageerror', error => errors.push(error.message));
    page.on('request', request => { if (/^https?:/.test(request.url())) network.push(request.url()); });
    await page.goto(pathToFileURL(path.join(root, 'dicomqc/report.html')).href);
    const panel = page.locator('#vendor-panel');
    assert.equal(await panel.getAttribute('open'), null);
    assert(await page.getByText('Warnings require review', {exact: true}).isVisible());
    await panel.locator('summary').click();
    const text = await panel.innerText();
    for (const required of ['Example Imaging', 'Research MR', 'ACME_ACQUISITION', 'ACME_PROCESSING', 'No creator', 'Contains observed metadata labels.']) {
      assert(text.includes(required), required);
    }
    assert.equal(await panel.locator('table').count(), 2);
    assert.equal(await panel.locator('tbody tr').count(), 5);
    for (const label of ['SYNTHETIC_PRIVATE_PAYLOAD_DO_NOT_REPORT', 'SYNTHETIC_NESTED_PAYLOAD_DO_NOT_REPORT', 'SYNTHETIC_ORPHAN_PAYLOAD_DO_NOT_REPORT']) {
      assert(!(await page.content()).includes(label), 'Private payload leaked');
    }
    // Capture the inventory panel, not an unrelated mockup or the full long report.
    await panel.screenshot({path: path.join(root, 'html-report-vendor.png')});
    for (const width of [390, 320]) {
      await page.setViewportSize({width, height: 1000});
      assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), 'Inventory overflow');
    }
    await page.emulateMedia({colorScheme: 'dark'});
    await panel.screenshot({path: path.join(root, 'html-report-vendor-dark-mobile.png')});
    await page.emulateMedia({media: 'print'});
    assert.equal(await page.locator('.print-overview .vendor-inventory:visible').count(), 1);
    assert.equal(await panel.isVisible(), false);
    assert.deepEqual(errors, []);
    assert.deepEqual(network, []);
    const multiqc = await browser.newPage({viewport: {width: 1440, height: 1100}, colorScheme: 'light'});
    await multiqc.route(/^https?:/, route => route.abort());
    await multiqc.goto(pathToFileURL(path.join(root, 'multiqc/multiqc_report.html')).href);
    const mqPanel = multiqc.locator('.dicomqc-dashboard .vendor-panel');
    assert.equal(await mqPanel.getAttribute('open'), null);
    await mqPanel.locator('summary').click();
    assert((await mqPanel.innerText()).includes('1 unassigned private elements'));
    assert.equal(await mqPanel.locator('tbody tr').count(), 5);
    await mqPanel.screenshot({path: path.join(root, 'multiqc-vendor.png')});
    await multiqc.setViewportSize({width: 390, height: 1000});
    const panelBox = await mqPanel.boundingBox();
    assert(panelBox.width <= 390);
    assert(await mqPanel.evaluate(el => el.scrollWidth <= el.clientWidth + 1));
    console.log('Vendor HTML and MultiQC passed: scope counts, folded inventory, observed-label warning, payload redaction, mobile, print and offline checks.');
  } finally {
    await browser.close();
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
