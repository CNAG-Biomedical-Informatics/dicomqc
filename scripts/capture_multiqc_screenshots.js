#!/usr/bin/env node

const path = require('path');

const repoRoot = path.resolve(__dirname, '..');
const {chromium} = require(path.join(repoRoot, 'docs-site', 'node_modules', '@playwright', 'test'));
const reportPath = path.join(repoRoot, 'examples', 'multiqc', 'output', 'multiqc_report.html');
const outputDir = path.join(repoRoot, 'docs-site', 'static', 'img');

const chromiumExecutable = process.env.CHROMIUM || '/usr/bin/chromium-browser';

async function capture(page, selector, filename) {
  const locator = page.locator(selector).first();
  await locator.waitFor({state: 'visible', timeout: 15000});
  await locator.screenshot({
    path: path.join(outputDir, filename),
    animations: 'disabled',
  });
}

(async () => {
  const browser = await chromium.launch({
    executablePath: chromiumExecutable,
    headless: true,
    args: ['--no-sandbox', '--disable-dev-shm-usage'],
  });
  const page = await browser.newPage({
    viewport: {width: 1800, height: 1200},
    deviceScaleFactor: 1,
  });
  await page.goto(`file://${reportPath}`, {waitUntil: 'networkidle'});
  await page.waitForSelector('#mqc-module-section-dicomqc', {state: 'visible'});

  await capture(page, '#mqc-module-section-dicomqc', 'multiqc-dicomqc-module.png');
  await capture(page, '#mqc-section-wrapper-dicomqc_01_release_status', 'multiqc-dicomqc-release-status.png');
  await capture(page, '#mqc-section-wrapper-dicomqc_02_findings', 'multiqc-dicomqc-findings.png');

  await browser.close();
})();
