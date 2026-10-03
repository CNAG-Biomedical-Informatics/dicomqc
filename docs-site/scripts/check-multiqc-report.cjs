// Capture and check a real MultiQC report generated from the synthetic scan demo.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {pathToFileURL} = require('node:url');
const {chromium} = require('@playwright/test');

(async () => {
  assert(process.argv[2], 'Usage: node scripts/check-multiqc-report.cjs PREVIEW_DIR');
  const root = path.resolve(process.argv[2]);
  const browser = await chromium.launch({headless: true});
  try {
    const page = await browser.newPage({viewport: {width: 1600, height: 1000}, colorScheme: 'light'});
    // No external services are needed to inspect this synthetic report.
    await page.route(/^https?:/, route => route.abort());
    await page.goto(pathToFileURL(path.join(root, 'multiqc/multiqc_report.html')).href);
    const overview = page.locator('.dicomqc-dashboard');
    assert(await overview.isVisible());
    assert((await overview.innerText()).includes('Errors require attention'));
    assert(!(await page.locator('body').innerText()).includes('Release is blocked'));
    await page.locator('#mqc-section-wrapper-dicomqc_00_overview').screenshot({path: path.join(root, 'multiqc-overview.png')});
    for (const [section, filename] of [['dicomqc_01_release_status', 'multiqc-status.png'], ['dicomqc_02_findings', 'multiqc-findings.png']]) {
      await page.locator('#mqc-section-wrapper-' + section).screenshot({path: path.join(root, filename)});
    }
    assert(await page.locator('#dicomqc_findings_table_table th.recommendation').isVisible());
    assert(!(await page.locator('#dicomqc_findings_table_table th.rule_id').isVisible()));
    assert((await page.locator('#dicomqc_release_status_table_table').innerText()).includes('Errors require attention'));
    await overview.locator('summary').click();
    assert((await overview.innerText()).includes('A passing result is not approval to share data'));
    const beforeReport = path.join(root, 'before.json');
    const policy = fs.existsSync(beforeReport) ? JSON.parse(fs.readFileSync(beforeReport, 'utf8')).policy : null;
    if (policy) {
      assert((await overview.innerText()).includes(policy.id));
      assert((await overview.innerText()).includes(policy.sha256));
    }
    await page.locator('html').evaluate(el => el.setAttribute('data-bs-theme', 'dark'));
    await overview.screenshot({path: path.join(root, 'multiqc-dark.png')});
    await page.setViewportSize({width: 390, height: 844});
    const box = await overview.boundingBox();
    assert(box.width <= 390);
    console.log('MultiQC checked: audit vocabulary, visible actions, folded technical columns, scope notes and responsive overview.');
  } finally {
    await browser.close();
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
