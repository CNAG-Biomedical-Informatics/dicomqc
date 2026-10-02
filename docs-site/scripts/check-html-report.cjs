// Run against a comparison demo; --states also checks optional synthetic stress fixtures.
const assert = require('node:assert/strict');
const path = require('node:path');
const {pathToFileURL} = require('node:url');
const {chromium} = require('@playwright/test');

(async () => {
  assert(process.argv[2], 'Usage: node scripts/check-html-report.cjs COMPARISON_DEMO_DIR [--states]');
  const root = path.resolve(process.argv[2]);
  const url = name => pathToFileURL(path.join(root, `${name}.html`)).href;
  const browser = await chromium.launch({headless: true});
  try {
    const page = await browser.newPage({viewport: {width: 1440, height: 1000}});
    const errors = [], external = [];
    page.on('pageerror', error => errors.push(error.message));
    page.on('console', message => { if (message.type() === 'error') errors.push(message.text()); });
    page.on('request', request => { if (/^https?:/.test(request.url())) external.push(request.url()); });
    const issues = page.locator('.issue:visible');
    const occurrences = page.locator('.occurrences tbody tr:visible');
    await page.goto(url('before'));
    assert(!(await page.locator('#controls').isVisible()));
    assert(!(await page.locator('#overview-panel .supporting-content').isVisible()));
    await page.locator('#overview-panel > summary').click();
    assert.equal(await issues.count(), 2);
    assert.equal(await occurrences.count(), 0);
    assert.equal(await page.locator('.occurrences tbody tr').count(), 3);
    assert.equal(await page.locator('#overview-panel figure.chart').count(), 2);
    const charts = await page.locator('#overview-panel .insights').innerText();
    await page.locator('#expand').click();
    assert.equal(await occurrences.count(), 3);
    await page.locator('#expand').click();
    assert.equal(await occurrences.count(), 0);
    const bar = page.locator('#overview-panel').getByRole('button', {name: 'Patient identifiers 2', exact: true});
    await bar.focus();
    await page.keyboard.press('Enter');
    assert.equal(await issues.count(), 1);
    assert.equal(await bar.getAttribute('aria-pressed'), 'true');
    assert.equal(await page.locator('#category').inputValue(), 'Patient identifiers');
    await page.locator('#search').fill('pair-000001');
    assert.equal(await occurrences.count(), 1);
    assert((await occurrences.first().innerText()).includes('pair-000001'));
    assert((await issues.first().locator('summary').innerText()).includes('1 finding in 1 reference'));
    await page.locator('#search').fill('missing');
    assert(await page.locator('#no-matches').isVisible());
    await page.locator('#reset').click();
    assert.equal(await issues.count(), 2);
    assert.equal(await occurrences.count(), 0);
    await page.locator('#search').fill('inconsistent_pseudonym');
    assert.equal(await issues.count(), 1);
    assert.equal(await occurrences.count(), 2);
    await page.locator('#severity').selectOption('warning');
    assert(await page.locator('#no-matches').isVisible());
    assert.equal(await page.locator('#overview-panel .insights').innerText(), charts);
    await page.emulateMedia({media: 'print'});
    assert.equal(await issues.count(), 2);
    assert.equal(await page.locator('.print-copy tbody tr:visible').count(), 3);
    assert(!(await page.locator('#print').isVisible()));
    await page.emulateMedia({media: 'screen'});
    await page.locator('#reset').click();
    await page.locator('#overview-panel > summary').click();
    await page.locator('#filter-panel > summary').click();
    await page.locator('h1').click();
    await page.evaluate(() => window.scrollTo(0, 0));
    await page.screenshot({path: path.join(root, 'html-desktop.png'), fullPage: true});
    await page.setViewportSize({width: 390, height: 844});
    assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
    await page.locator('.occurrences summary').first().click();
    assert.equal(await occurrences.count(), 1);
    assert.equal(await page.getByRole('table').count(), 1);
    await page.screenshot({path: path.join(root, 'html-mobile.png'), fullPage: true});
    await page.emulateMedia({colorScheme: 'dark'});
    await page.screenshot({path: path.join(root, 'html-dark.png'), fullPage: true});
    await page.getByRole('link', {name: 'After corrections', exact: true}).click();
    assert.equal(page.url(), url('after'));
    assert(await page.getByText('Checks passed', {exact: true}).isVisible());
    assert.equal(await page.locator('.issue').count(), 0);
    assert.equal(await page.locator('#overview-panel figure.chart').count(), 1);
    assert(await page.locator('.empty-state').isVisible());
    assert(!(await page.locator('#controls').isVisible()));
    assert(await page.locator('#print').isVisible());
    await page.getByRole('link', {name: 'Before corrections', exact: true}).click();
    assert.equal(page.url(), url('before'));
    const noJS = await browser.newPage({javaScriptEnabled: false});
    await noJS.goto(url('before'));
    assert.equal(await noJS.locator('.issue:visible').count(), 2);
    assert(!(await noJS.locator('#controls').isVisible()));
    assert(await noJS.locator('.category-bar').first().isDisabled());
    await noJS.locator('.occurrences summary').first().click();
    assert.equal(await noJS.locator('.occurrences tbody tr:visible').count(), 1);
    await noJS.emulateMedia({media: 'print'});
    assert.equal(await noJS.locator('.print-copy tbody tr:visible').count(), 3);
    if (process.argv.includes('--states')) {
      for (const [state, status] of [['empty', 'No readable files'], ['unreadable', 'Errors require attention'], ['pass', 'Checks passed'], ['warning', 'Warnings require review'], ['large', 'Errors require attention']]) {
        await page.goto(url(state));
        assert(await page.getByText(status, {exact: true}).isVisible());
        for (const width of [320, 650, 900, 1440]) {
          await page.setViewportSize({width, height: 1000});
          assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), `${state} overflow at ${width}`);
        }
        if (state === 'large') {
          assert.equal(await issues.count(), 1);
          assert.equal(await page.locator('.occurrences tbody tr').count(), 250);
          assert.equal(await occurrences.count(), 0);
          await page.locator('#filter-panel > summary').click();
          await page.locator('#search').fill('study-0249');
          assert.equal(await occurrences.count(), 1);
          await page.setViewportSize({width: 320, height: 900});
          assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
          await page.emulateMedia({media: 'print'});
          assert.equal(await page.locator('.print-copy tbody tr:visible').count(), 250);
          await page.emulateMedia({media: 'screen'});
          await page.setViewportSize({width: 1440, height: 1000});
          await page.locator('#reset').click();
        }
        await page.emulateMedia({colorScheme: 'light'});
        await page.screenshot({path: path.join(root, `state-${state}.png`), fullPage: true});
      }
      await page.goto(url('before'));
      await page.emulateMedia({media: 'print'});
      await page.pdf({path: path.join(root, 'print-preview.pdf'), format: 'A4', printBackground: true});
    }
    assert.deepEqual(errors, []);
    assert.deepEqual(external, []);
    console.log('Grouped workspace passed: grouping, occurrence filters, keyboard controls, print, mobile, no-JS, navigation and offline checks.');
  } finally {
    await browser.close();
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
