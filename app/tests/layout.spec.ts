import {test, expect} from '@playwright/test';
import {readFile} from 'node:fs/promises';
import {resolve} from 'node:path';

// Fulfill built assets in-process: no web server and no engine credentials.
for (const width of [390, 760, 1440]) for (const theme of ['light', 'dark', 'system']) {
  test(`${width}px ${theme}`, async ({page}, testInfo) => {
    await page.setViewportSize({width, height: 900});
    await page.emulateMedia({colorScheme: 'dark'});
    const errors: string[] = [];
    page.on('pageerror', error => errors.push(error.message));
    await page.addInitScript(({theme}) => {
      if (window !== window.top) return;
      localStorage.setItem('dicomqc-theme', theme);
      const job = {id: 'example', created: 1700000000, mode: 'scan', example: null, status: 'completed',
        audit_exit_code: 2, summary: {errors: 1, warnings: 0, files_scanned: 12, skipped_files: 0},
        artifacts: ['nested/report-with-a-long-filename.html'], message: null};
      Object.assign(window, {isTauri: true, __TAURI_INTERNALS__: {transformCallback: () => 1, unregisterCallback: () => {}, invoke: async (command: string, args: {path?: string}) => {
        if (command === 'plugin:event|listen') return 1;
        if (command === 'select_input') return {id: 'selected', kind: 'directory', name: 'MRI dataset', display_path: '/research/' + 'long-study-directory/'.repeat(5) + 'MRI dataset'};
        if (command === 'workspace') return '/workspace/' + 'long-directory-name/'.repeat(8);
        if (command === 'read_report') return '<h1>Audit report</h1>';
        if (command === 'api_request') return args.path?.includes('/results') ? {total_findings: 1, findings: [{
          rule_id: 'privacy', severity: 'error', message: 'Identifier requires review', recommendation: 'Review metadata',
          path: 'nested/'.repeat(30) + 'file.dcm', keyword: 'PatientName',
        }]} : [job, ...['uid', 'policy', 'vendor', 'compare'].map(example => ({...job, id: example, mode: 'demo', example}))];
        return null;
      }}});
    }, {theme});
    await page.route('https://dicomqc.test/**', async route => {
      const pathname = new URL(route.request().url()).pathname;
      const file = resolve('dist', pathname === '/' ? 'index.html' : pathname.slice(1));
      await route.fulfill({body: await readFile(file), contentType: file.endsWith('.js') ? 'text/javascript' : file.endsWith('.css') ? 'text/css' : file.endsWith('.png') ? 'image/png' : 'text/html'});
    });
    await page.goto('https://dicomqc.test/');
    await expect(page.getByText('● Local engine ready')).toBeVisible();
    expect(await page.locator('.titlebar img').evaluate((img: HTMLImageElement) => img.complete && img.naturalWidth > 0)).toBe(true);
    async function checkLayout(name: string) {
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
      const overflow = await page.locator('button, select, .selections li, .finding').evaluateAll(nodes => nodes
        .filter(node => (node as HTMLElement).offsetWidth > 0 && node.scrollWidth > node.clientWidth + 2)
        .map(node => node.textContent));
      expect(overflow).toEqual([]);
      expect(await page.locator('.run-list button').evaluateAll(rows => rows.every(row => [...row.children].every(child => child.getBoundingClientRect().bottom <= row.getBoundingClientRect().bottom + 2)))).toBe(true);
      await page.screenshot({path: testInfo.outputPath(`${name}.png`), fullPage: true});
    }
    await page.getByRole('button', {name: 'Add folder', exact: true}).click();
    await expect(page.getByRole('button', {name: 'Remove MRI dataset'})).toBeVisible();
    await checkLayout('scan');
    await page.getByRole('button', {name: 'Compare datasets', exact: true}).click(); await checkLayout('compare');
    await page.getByRole('button', {name: /^Runs/}).click();
    await page.getByRole('button', {name: /Dataset scan/}).click();
    await page.getByText('Identifier requires review').click(); await checkLayout('findings');
    await page.getByRole('tab', {name: 'Reports', exact: true}).click();
    await expect(page.getByTitle('Audit report preview')).toHaveAttribute('sandbox', ''); await checkLayout('report');
    await page.getByRole('button', {name: 'Settings', exact: true}).click(); await checkLayout('settings');
    expect(errors).toEqual([]);
  });
}
