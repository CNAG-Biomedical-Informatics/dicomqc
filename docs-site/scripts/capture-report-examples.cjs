// Capture the reports beside their documented synthetic input/analysis examples.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {pathToFileURL} = require('node:url');
const {chromium} = require('@playwright/test');

(async () => {
  const root = path.resolve(process.argv[2] || '/tmp/dicomqc-workspace-design');
  const browser = await chromium.launch({headless: true});
  try {
    const page = await browser.newPage({viewport: {width: 1440, height: 1000}, colorScheme: 'light'});
    const examples = [
      ['scan/dicomqc/report', 'html-report-scan.png', 3, 1, 4],
      ['policy/before', 'html-report-policy.png', 1, 3, 0],
      ['policy/after', 'html-report-policy-after.png', 1, 0, 0],
    ];
    for (const [name, filename, files, errors, warnings] of examples) {
      const report = JSON.parse(fs.readFileSync(path.join(root, name + '.json'), 'utf8'));
      assert.equal(report.summary.files_scanned, files);
      assert.equal(report.summary.errors, errors);
      assert.equal(report.summary.warnings, warnings);
      await page.goto(pathToFileURL(path.join(root, name + '.html')).href);
      assert(await page.getByText('Synthetic demo', {exact: true}).isVisible());
      assert(await page.getByText(errors ? 'Errors require attention' : 'Checks passed', {exact: true}).isVisible());
      assert.equal(await page.locator('#overview-panel').getAttribute('open'), null);
      await page.screenshot({path: path.join(root, filename), fullPage: true});
    }
    console.log('Captured actual scan and policy reports; counts match the documented examples.');
  } finally {
    await browser.close();
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
