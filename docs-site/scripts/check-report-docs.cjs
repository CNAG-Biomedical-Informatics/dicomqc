// Check the rendered documentation and capture previews outside the repository.
const assert = require('node:assert/strict');
const path = require('node:path');
const {chromium} = require('@playwright/test');

(async () => {
  const base = process.argv[2] || 'http://127.0.0.1:3017/dicomqc';
  const output = process.argv[3] || '/tmp/dicomqc-workspace-design';
  const browser = await chromium.launch({headless: true});
  try {
    const page = await browser.newPage({viewport: {width: 1440, height: 1100}, colorScheme: 'light'});
    for (const width of [1440, 390]) {
      await page.setViewportSize({width, height: 1100});
      await page.goto(base + '/docs/technical-details/architecture');
      const diagram = page.locator('.dicomqcArchitectureFigure img');
      await diagram.scrollIntoViewIfNeeded();
      await diagram.evaluate(img => img.decode());
      assert((await diagram.evaluate(img => img.currentSrc)).endsWith(
        width === 390 ? 'dicomqc-architecture-mobile.svg' : 'dicomqc-architecture.svg'));
      assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
      await page.locator('.dicomqcArchitectureFigure').screenshot({
        path: path.join(output, 'architecture-' + width + '.png'),
      });
    }
    await page.goto(base + '/docs/reference/cli');
    await page.locator('html[data-has-hydrated="true"]').waitFor();
    assert.equal(await page.locator('a[href$="/docs/usage/reports"]').count(), 0, 'Removed Reports page must not appear in navigation');
    assert.equal(await page.locator('article img').count(), 0, 'Report snapshots belong with their analysis');
    // Format-reference links must resolve to the corresponding walkthrough sections.
    const links = await page.locator('article a[href*="#"]').evaluateAll(items => items.map(a => a.href));
    for (const url of links) {
      await page.goto(url);
      const anchor = decodeURIComponent(new URL(url).hash.slice(1));
      assert(await page.evaluate(id => Boolean(document.getElementById(id)), anchor), 'Missing anchor: ' + url);
    }
    await page.goto(base + '/docs/usage/compare');
    await page.locator('html[data-has-hydrated="true"]').waitFor();
    for (const label of ['Example JSON finding', 'Example CSV rows']) {
      const summary = page.locator('summary').filter({hasText: label});
      const details = summary.locator('..');
      assert.equal(await details.getAttribute('open'), null);
      await summary.click();
      await details.locator(label.includes('JSON') ? 'pre' : 'table').waitFor({state: 'visible'});
      assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
      await summary.click();
    }
    for (const width of [1440, 390]) {
      await page.setViewportSize({width, height: 1100});
      for (const [route, expectedImages] of [['quickstart', 4], ['compare', 2], ['policies', 2], ['vendor-summary', 1], ['uid-integrity', 2]]) {
        await page.goto(base + '/docs/usage/' + route);
        await page.locator('html[data-has-hydrated="true"]').waitFor();
        const panels = page.locator('article details').filter({has: page.locator('img')});
        let images = 0;
        for (const panel of await panels.all()) {
          assert.equal(await panel.getAttribute('open'), null);
          await panel.locator('summary').click();
          for (const img of await panel.locator('img').all()) {
            await img.waitFor({state: 'visible'});
            await img.scrollIntoViewIfNeeded();
            await img.evaluate(node => node.decode());
            assert(await img.evaluate(node => node.naturalWidth > 0));
            images++;
          }
          assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
          await panel.locator('summary').click();
        }
        assert.equal(images, expectedImages, route + ' screenshots');
      }
    }
    console.log('Docs passed: architecture, walkthrough links, folded JSON/CSV examples, and eleven report snapshots beside their analyses at desktop/mobile sizes.');
  } finally {
    await browser.close();
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
