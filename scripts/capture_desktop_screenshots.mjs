#!/usr/bin/env node
// Capture the real frontend with a fixture-backed native bridge, not OS dialogs.
import {execFileSync} from 'node:child_process';
import {createRequire} from 'node:module';
import {mkdtemp, readFile, rm} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {dirname, join, resolve} from 'node:path';
import {fileURLToPath, pathToFileURL} from 'node:url';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const require = createRequire(join(root, 'app/package.json'));
const {chromium, expect} = require('@playwright/test');
const python = process.env.DICOMQC_DESKTOP_PYTHON || join(root, '.venv', process.platform === 'win32' ? 'Scripts/python.exe' : 'bin/python');
const output = join(root, 'docs-site/static/img');
const temporary = await mkdtemp(join(tmpdir(), 'dicomqc-docs-'));
let browser;
try {
  for (const [name, flag] of [['scan', null], ['compare', '--compare'], ['policy', '--policy-demo'], ['uid', '--uid-demo'], ['vendor', '--vendor-demo']]) {
    execFileSync(python, ['-m', 'dicomqc.cli', 'demo', '--output-dir', join(temporary, name), ...(flag ? [flag] : [])], {cwd: root});
  }
  const reportDir = join(temporary, 'scan/dicomqc');
  const result = JSON.parse(await readFile(join(reportDir, 'report.json'), 'utf8'));
  const reports = await Promise.all(['report.html', 'report.json', 'findings.csv'].map(name => readFile(join(reportDir, name), 'utf8')));
  const comparisonResult = JSON.parse(await readFile(join(temporary, 'compare/before.json'), 'utf8'));
  const comparisonArtifacts = ['before.html', 'after.html', 'before.json', 'before.csv', 'after.json', 'after.csv'];
  const comparisonReports = await Promise.all(comparisonArtifacts.map(name => readFile(join(temporary, 'compare', name), 'utf8')));
  browser = await chromium.launch({headless: true, ...(process.env.CHROMIUM_PATH ? {executablePath: process.env.CHROMIUM_PATH} : {})});
  const page = await browser.newPage({viewport: {width: 1440, height: 960}, deviceScaleFactor: 1, colorScheme: 'light', locale: 'en-GB', timezoneId: 'UTC'});
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  await page.addInitScript(({result, reports, comparisonResult, comparisonReports, comparisonArtifacts}) => {
    if (window !== window.top) return;
    const comparison = new URL(location.href).searchParams.has('comparison');
    if (comparison) { result = comparisonResult; reports = comparisonReports; }
    localStorage.setItem('dicomqc-theme', 'light');
    const job = {id: 'a'.repeat(32), mode: 'demo', example: comparison ? 'compare' : 'scan', name: null,
      created: Date.UTC(2026, 9, 3, 9) / 1000, status: 'completed', audit_exit_code: 2,
      summary: result.summary, artifacts: comparison ? comparisonArtifacts : ['report.html', 'report.json', 'findings.csv'], message: null};
    Object.assign(window, {isTauri: true, __TAURI_INTERNALS__: {
      transformCallback: () => 1, unregisterCallback: () => {},
      invoke: async (command, args = {}) => {
        if (command === 'plugin:event|listen') return 1;
        if (command === 'current_project') return {projectPath: null, name: 'Untitled', output: '/internal/session', savedJobs: [],
          project: {mode: comparison ? 'compare' : 'scan', inputs: {}, options: {threads: 4, uid_checks: false, vendor_summary: false, multiqc: false}}, missing: []};
        if (command === 'read_report') return reports[args.index];
        if (command === 'api_request') {
          if (args.path === '/api/v1/capabilities') return {default_threads: 4, max_threads: 8, max_concurrent_jobs: 1};
          if (args.path.includes('/results')) return {findings: result.findings, total_findings: result.findings.length};
          if (args.path === '/api/v1/jobs') return [job];
        }
        if (['sync_menu', 'plugin:event|unlisten'].includes(command)) return null;
        throw new Error(`Unexpected screenshot command: ${command}`);
      },
    }});
  }, {result, reports, comparisonResult, comparisonReports, comparisonArtifacts});
  await page.route('https://dicomqc.test/**', async route => {
    const pathname = new URL(route.request().url()).pathname;
    const file = resolve(root, 'app/dist', pathname === '/' ? 'index.html' : pathname.slice(1));
    await route.fulfill({body: await readFile(file), contentType: file.endsWith('.js') ? 'text/javascript' : file.endsWith('.css') ? 'text/css' : file.endsWith('.png') ? 'image/png' : 'text/html'});
  });
  await page.goto('https://dicomqc.test/');
  await expect(page.getByText('● Local engine ready')).toBeVisible();
  const capture = async name => {
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    await page.screenshot({path: join(output, name), animations: 'disabled'});
  };
  await page.getByRole('button', {name: 'Load example data'}).click();
  await expect(page.getByRole('button', {name: 'Privacy audit', exact: true})).toBeVisible();
  await capture('desktop-setup.png');
  await page.getByRole('button', {name: 'Load example data'}).click();
  await page.getByText('Advanced setup', {exact: true}).click();
  await expect(page.getByRole('button', {name: 'New policy'})).toBeVisible();
  await capture('desktop-advanced-setup.png');
  await page.locator('.run-select').click();
  await page.getByRole('tab', {name: 'Findings', exact: true}).click();
  await expect(page.getByText('PatientBirthDate', {exact: false}).first()).toBeVisible();
  await capture('desktop-privacy-findings.png');
  await page.getByRole('tab', {name: 'Reports', exact: true}).click();
  await expect(page.getByTitle('Audit report preview')).toBeVisible();
  await expect(page.frameLocator('iframe').getByRole('heading', {name: 'Errors require attention'})).toBeVisible();
  await capture('desktop-workspace.png');
  await page.goto('https://dicomqc.test/?comparison');
  await expect(page.getByText('● Local engine ready')).toBeVisible();
  await expect(page.getByRole('button', {name: 'Run comparison', exact: true})).toBeVisible();
  await capture('desktop-comparison-setup.png');
  await page.locator('.run-select').click();
  await page.getByRole('tab', {name: 'Reports', exact: true}).click();
  await expect(page.frameLocator('iframe').getByRole('heading', {name: 'Errors require attention'})).toBeVisible();
  await capture('desktop-comparison-report.png');
  await page.getByRole('button', {name: /after.html/}).click();
  await expect(page.frameLocator('iframe').getByRole('heading', {name: 'Checks passed'})).toBeVisible();
  await capture('desktop-comparison-after.png');
  expect(errors).toEqual([]);

  // Refresh report screenshots too, so their audit names match the workspace.
  const reportPage = await browser.newPage({viewport: {width: 1440, height: 1000}, colorScheme: 'light'});
  for (const [source, name] of [
    ['scan/dicomqc/report.html', 'scan'], ['compare/before.html', 'before'], ['compare/after.html', 'after'],
    ['policy/before.html', 'policy'], ['policy/after.html', 'policy-after'],
    ['uid/before.html', 'uid'], ['uid/after.html', 'uid-after'], ['vendor/dicomqc/report.html', 'vendor'],
  ]) {
    await reportPage.goto(pathToFileURL(join(temporary, source)).href);
    await reportPage.screenshot({path: join(output, `html-report-${name}.png`), animations: 'disabled'});
  }
  console.log('Desktop and HTML report screenshots updated using synthetic fixtures.');
} finally {
  await browser?.close();
  await rm(temporary, {recursive: true, force: true});
}
