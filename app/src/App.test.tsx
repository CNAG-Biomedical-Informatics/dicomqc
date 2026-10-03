import React from 'react';
import {act, cleanup, fireEvent, render, screen, waitFor} from '@testing-library/react';
import {afterEach, beforeEach, describe, expect, it, vi} from 'vitest';
import {App} from './main';
import * as desktop from './desktop';
import type {Job, Results} from './desktop';

vi.mock('./desktop', async importOriginal => ({
  ...await importOriginal<typeof import('./desktop')>(), api: vi.fn(), pick: vi.fn(),
  readPolicy: vi.fn(), savePolicyCopy: vi.fn(), workspace: vi.fn(), currentProject: vi.fn(), saveProject: vi.fn(), openProject: vi.fn(), newProject: vi.fn(), renameRun: vi.fn(), report: vi.fn(), saveReport: vi.fn(), saveJobRecord: vi.fn(), reveal: vi.fn(), deleteRun: vi.fn(), deleteRuns: vi.fn(), openExternal: vi.fn(), onDesktopMenu: vi.fn(), syncMenu: vi.fn(),
}));
const job = (overrides: Partial<Job> = {}): Job => ({id: 'first', created: 1700000000, mode: 'scan', example: null,
  status: 'completed', audit_exit_code: 0, summary: {errors: 0, warnings: 0, files_scanned: 5, skipped_files: 0},
  artifacts: ['report.html', 'report.json'], message: null, ...overrides});
const empty: Results = {findings: [], total_findings: 0};
const capabilities = {default_threads: 4, max_threads: 12, max_concurrent_jobs: 1,
  large_demo: {default_files: 10_000, min_files: 1_000, max_files: 100_000, step_files: 1_000}};
function deferred<T>() {
  let resolve!: (value: T) => void, reject!: (reason: unknown) => void;
  const promise = new Promise<T>((done, fail) => {resolve = done; reject = fail;});
  return {promise, resolve, reject};
}
let history: Job[], desktopMenu: ((action: string) => void) | null;
beforeEach(() => {
  vi.resetAllMocks(); localStorage.clear(); history = []; desktopMenu = null;
  vi.mocked(desktop.workspace).mockResolvedValue('/workspace');
  vi.mocked(desktop.currentProject).mockResolvedValue({projectPath: null, output: '/workspace', name: 'Untitled', project: {mode: 'scan', inputs: {}, options: {uid_checks: false, vendor_summary: false, multiqc: false, threads: 4}}, missing: []});
  vi.mocked(desktop.onDesktopMenu).mockImplementation(async handler => {desktopMenu = handler; return () => {};});
  vi.mocked(desktop.syncMenu).mockResolvedValue();
  vi.mocked(desktop.report).mockResolvedValue('<h1>Report</h1>');
  vi.mocked(desktop.api).mockImplementation(async (path, method) => {
    if (path === '/api/v1/capabilities') return capabilities as never;
    if (path.endsWith('/results?offset=0&limit=100')) return empty as never;
    if (method === 'POST') return job({status: 'queued'}) as never;
    return history as never;
  });
});
afterEach(() => {cleanup(); vi.useRealTimers();});
async function start() {render(<App/>); await screen.findByText('● Local engine ready');}
function menu(action: string) {if (!desktopMenu) throw new Error('Desktop menu is not registered.'); act(() => desktopMenu?.(action));}
function runButton(name: RegExp): HTMLButtonElement {
  const value = screen.getAllByRole('button', {name}).find(button => button.classList.contains('run-select'));
  if (!value) throw new Error(`Run button ${name} is unavailable.`);
  return value as HTMLButtonElement;
}
async function runs() {
  await start(); fireEvent.click(screen.getByRole('button', {name: /^Runs/}));
  const run = screen.getAllByRole('button', {name: /Privacy audit/}).find(button => button.classList.contains('run-select'));
  if (!run) throw new Error('Privacy audit run is unavailable.');
  fireEvent.click(run);
}

describe('audit forms', () => {
  it('opens policy and issue reporting from native menus', async () => {
    await start();
    menu('policy');
    expect(screen.getByRole('heading', {name: 'Project policy'})).toBeTruthy();
    vi.mocked(desktop.openExternal).mockResolvedValue();
    menu('report-issue');
    expect(desktop.openExternal).toHaveBeenCalledWith('https://github.com/CNAG-Biomedical-Informatics/dicomqc/issues/new');
    menu('cancel-audit');
    expect(desktop.api).not.toHaveBeenCalledWith(expect.stringContaining('/cancel'), 'POST');
  });
  it('opens the selected job log and cancels only an active selected audit', async () => {
    history = [job({status: 'running'})];
    await runs();
    await waitFor(() => expect(desktop.syncMenu).toHaveBeenLastCalledWith(expect.objectContaining({canCancel: true})));
    menu('log');
    expect(screen.getByRole('heading', {name: 'Job record'})).toBeTruthy();
    vi.mocked(desktop.api).mockResolvedValueOnce(job({status: 'cancelled'}));
    menu('cancel-audit');
    await waitFor(() => expect(desktop.api).toHaveBeenCalledWith('/api/v1/jobs/first/cancel', 'POST'));
    await waitFor(() => expect(desktop.syncMenu).toHaveBeenLastCalledWith(expect.objectContaining({canCancel: false})));
  });
  it('requires inputs, handles picker cancellation, deduplicates and removes inputs', async () => {
    await start(); const run = screen.getByRole('button', {name: 'Run privacy audit'});
    expect((run as HTMLButtonElement).disabled).toBe(true);
    vi.mocked(desktop.pick).mockResolvedValue(null);
    fireEvent.click(screen.getByText('Choose DICOM folder')); await waitFor(() => expect(desktop.pick).toHaveBeenCalledWith(true));
    expect((run as HTMLButtonElement).disabled).toBe(true);
    vi.mocked(desktop.pick).mockResolvedValue({id: 'input', name: 'DICOM', kind: 'directory'});
    fireEvent.click(screen.getByText('Choose DICOM folder')); await screen.findByRole('button', {name: 'Remove DICOM'});
    fireEvent.click(screen.getByText('Choose DICOM folder')); await waitFor(() => expect(desktop.pick).toHaveBeenCalledTimes(3));
    expect(screen.getAllByRole('button', {name: 'Remove DICOM'})).toHaveLength(1);
    fireEvent.click(screen.getByRole('button', {name: 'Remove DICOM'}));
    expect((run as HTMLButtonElement).disabled).toBe(true);
  });
  it('creates a YAML policy, saves a non-destructive copy and uses its input handle', async () => {
    await start();
    vi.mocked(desktop.savePolicyCopy).mockResolvedValue({id: 'policy-copy', name: 'research.yaml', kind: 'file'});
    fireEvent.click(screen.getByRole('button', {name: 'New policy'}));
    expect(await screen.findByRole('textbox', {name: 'Policy editor'})).toBeTruthy();
    expect(screen.getByRole('tab', {name: 'Policy'}).textContent).toContain('*');
    fireEvent.click(screen.getByRole('button', {name: 'Save as and use'}));
    await screen.findByText(/Saved and selected research.yaml/);
    expect(desktop.savePolicyCopy).toHaveBeenCalledWith(expect.stringContaining('version: 1'));
    fireEvent.click(screen.getByRole('tab', {name: 'Setup'}));
    expect(screen.getByRole('button', {name: 'Remove research.yaml'})).toBeTruthy();
    vi.mocked(desktop.pick).mockResolvedValue({id: 'dicom', name: 'DICOM', kind: 'directory'});
    fireEvent.click(screen.getByText('Choose DICOM folder'));
    await screen.findByRole('button', {name: 'Remove DICOM'});
    fireEvent.click(screen.getByRole('button', {name: 'Run privacy audit'}));
    await waitFor(() => expect(desktop.api).toHaveBeenCalledWith('/api/v1/jobs', 'POST', expect.objectContaining({
      inputs: {paths: ['dicom'], policy: ['policy-copy']},
    })));
  });
  it('submits scan options and preserves the native input handle contract', async () => {
    await start(); vi.mocked(desktop.pick).mockResolvedValue({id: 'input', name: 'DICOM', kind: 'directory'});
    fireEvent.click(screen.getByText('Choose DICOM folder')); await screen.findByRole('button', {name: 'Remove DICOM'});
    fireEvent.click(screen.getByText('Advanced setup'));
    fireEvent.click(screen.getByLabelText('Check UID syntax and relationships'));
    fireEvent.click(screen.getByLabelText('Include scanner and private-creator inventory'));
    expect(screen.getByText(/observed labels/)).toBeTruthy();
    fireEvent.click(screen.getByRole('button', {name: 'Run privacy audit'}));
    await waitFor(() => expect(desktop.api).toHaveBeenCalledWith('/api/v1/jobs', 'POST', {
      mode: 'scan', inputs: {paths: ['input']}, options: {uid_checks: true, vendor_summary: true, multiqc: false, threads: 4},
    }));
    await screen.findByText('Audit queued');
    expect(screen.getByText(/Waiting for the active audit/)).toBeTruthy();
  });
  it('requires all compare inputs and excludes scan-only options', async () => {
    await start(); fireEvent.click(screen.getByText('Advanced setup'));
    fireEvent.click(screen.getByLabelText('Check UID syntax and relationships'));
    fireEvent.click(screen.getByRole('button', {name: 'Dataset comparison Source and candidate datasets'}));
    for (const [label, id] of [['Source folder', 'source'], ['Candidate folder', 'candidate'], ['Pairing manifest · CSV', 'manifest']]) {
      expect((screen.getByRole('button', {name: 'Run comparison'}) as HTMLButtonElement).disabled).toBe(true);
      vi.mocked(desktop.pick).mockResolvedValue({id, name: id, kind: 'file'});
      fireEvent.click(screen.getByRole('button', {name: `Choose ${label}`})); await screen.findByRole('button', {name: `Remove ${id}`});
    }
    fireEvent.click(screen.getByRole('button', {name: 'Run comparison'}));
    await waitFor(() => expect(desktop.api).toHaveBeenCalledWith('/api/v1/jobs', 'POST', {
      mode: 'compare', inputs: {source: ['source'], candidate: ['candidate'], manifest: ['manifest']}, options: {threads: 4},
    }));
  });
  it.each(['scan', 'compare', 'policy', 'uid', 'vendor'])('submits the %s example with project report settings', async example => {
    const labels: Record<string, string> = {scan: 'Privacy audit', compare: 'Dataset comparison', policy: 'Privacy audit + project policy', uid: 'Privacy audit + UID checks', vendor: 'Privacy audit + scanner inventory'};
    await start();
    if (example === 'compare') fireEvent.click(screen.getByRole('button', {name: 'Dataset comparison Source and candidate datasets'}));
    fireEvent.click(screen.getByText('Load example data'));
    fireEvent.click(screen.getByRole('button', {name: labels[example]}));
    await waitFor(() => expect(desktop.api).toHaveBeenCalledWith('/api/v1/jobs', 'POST', {mode: 'demo', example, options: {multiqc: false, threads: 4}}));
  });
  it('shows only example data that belongs to the selected audit mode', async () => {
    await start(); fireEvent.click(screen.getByText('Load example data'));
    expect(screen.getByRole('button', {name: 'Privacy audit'})).toBeTruthy();
    expect(screen.queryByRole('button', {name: 'Dataset comparison'})).toBeNull();
    fireEvent.click(screen.getByRole('button', {name: 'Dataset comparison Source and candidate datasets'}));
    expect(screen.getByRole('button', {name: 'Dataset comparison'})).toBeTruthy();
    expect(screen.queryByRole('button', {name: 'Privacy audit'})).toBeNull();
    expect(screen.queryByRole('button', {name: 'Large privacy audit'})).toBeNull();
  });
  it('submits the selected large cohort size', async () => {
    await start(); fireEvent.click(screen.getByText('Load example data'));
    expect(screen.queryByLabelText('Large cohort files')).toBeNull();
    fireEvent.click(screen.getByRole('button', {name: 'Large privacy audit'}));
    const size = screen.getByLabelText('Large cohort files') as HTMLInputElement;
    expect(size.value).toBe('10000'); expect(size.min).toBe('1000'); expect(size.max).toBe('100000');
    fireEvent.change(size, {target: {value: '25000'}});
    expect(screen.getByText('25,000 files')).toBeTruthy();
    fireEvent.click(screen.getByRole('button', {name: 'Run large cohort'}));
    await waitFor(() => expect(desktop.api).toHaveBeenCalledWith('/api/v1/jobs', 'POST', {
      mode: 'demo', example: 'large', example_files: 25_000, options: {multiqc: false, threads: 4},
    }));
  });
  it('applies the MultiQC setting to example data', async () => {
    await start(); fireEvent.click(screen.getByRole('button', {name: 'Settings'}));
    fireEvent.click(screen.getByLabelText('Export MultiQC custom content'));
    fireEvent.click(screen.getByRole('tab', {name: 'Setup'}));
    fireEvent.click(screen.getByRole('button', {name: 'Dataset comparison Source and candidate datasets'}));
    fireEvent.click(screen.getByText('Load example data'));
    fireEvent.click(screen.getByRole('button', {name: 'Dataset comparison'}));
    await waitFor(() => expect(desktop.api).toHaveBeenCalledWith('/api/v1/jobs', 'POST', {
      mode: 'demo', example: 'compare', options: {multiqc: true, threads: 4},
    }));
  });
  it('displays native failures and allows dismissal', async () => {
    await start(); vi.mocked(desktop.pick).mockRejectedValue('Selection failed');
    fireEvent.click(screen.getByText('Add single DICOM file')); expect((await screen.findByRole('alert')).textContent).toContain('Selection failed');
    fireEvent.click(screen.getByLabelText('Dismiss error')); expect(screen.queryByRole('alert')).toBeNull();
  });
  it('labels a submission as queued while another audit is active', async () => {
    history = [job({status: 'running'})]; await start();
    vi.mocked(desktop.pick).mockResolvedValue({id: 'input', name: 'DICOM', kind: 'directory'});
    fireEvent.click(screen.getByText('Choose DICOM folder')); await screen.findByRole('button', {name: 'Remove DICOM'});
    expect(screen.getByRole('button', {name: 'Queue audit'})).toBeTruthy();
  });
});

describe('runs and reports', () => {
  it('keeps an unsuccessful submission editable and prevents duplicate submissions', async () => {
    await start(); fireEvent.click(screen.getByText('Load example data'));
    const request = deferred<Job>(); vi.mocked(desktop.api).mockReturnValueOnce(request.promise);
    fireEvent.click(screen.getByRole('button', {name: 'Privacy audit'}));
    expect((screen.getByRole('button', {name: 'Privacy audit'}) as HTMLButtonElement).disabled).toBe(true);
    await act(async () => request.resolve(job({status: 'queued'})));
    expect(vi.mocked(desktop.api).mock.calls.filter(([, method]) => method === 'POST')).toHaveLength(1);
    fireEvent.click(screen.getByRole('button', {name: 'New audit'}));
    vi.mocked(desktop.api).mockRejectedValueOnce(new Error('Cannot start audit'));
    fireEvent.click(screen.getByRole('button', {name: 'Privacy audit'}));
    await screen.findByText('Cannot start audit');
    expect((screen.getByRole('button', {name: 'Privacy audit'}) as HTMLButtonElement).disabled).toBe(false);
  });
  it('distinguishes cancelled exports from saved copies and reports failures', async () => {
    history = [job()]; await runs(); fireEvent.click(screen.getByRole('tab', {name: 'Reports'}));
    vi.mocked(desktop.saveReport).mockResolvedValue(false);
    fireEvent.click(screen.getByRole('button', {name: 'Select report report.json'}));
    fireEvent.click(screen.getByLabelText('Save report.json')); await waitFor(() => expect(desktop.saveReport).toHaveBeenCalled());
    expect(screen.queryByText('Report copy saved.')).toBeNull();
    vi.mocked(desktop.report).mockRejectedValue(new Error('Report unavailable'));
    fireEvent.click(screen.getByRole('button', {name: 'Select report report.html'})); await screen.findByText('Report unavailable');
    expect(screen.queryByText('Loading report...')).toBeNull();
  });
  it('explains when a report is too large for the embedded preview', async () => {
    history = [job()];
    vi.mocked(desktop.report).mockRejectedValue('This report is too large for a preview. Save a copy to open it separately.');
    await runs(); fireEvent.click(screen.getByRole('tab', {name: 'Reports'}));
    fireEvent.click(screen.getByRole('button', {name: 'Select report report.json'}));
    expect((await screen.findByRole('alert')).textContent).toBe('This report is too large for a preview. Save a copy to open it separately.');
    expect(screen.getByLabelText('Save report.json')).toBeTruthy();
  });
  it('separates audit errors from worker failures and incomplete audits', () => {
    expect(desktop.auditLabel(job({audit_exit_code: 2}))).toBe('Errors require attention');
    expect(desktop.auditLabel(job({status: 'failed'}))).toBe('Failed');
    expect(desktop.auditLabel(job({audit_exit_code: null}))).toBe('Audit completed');
    expect(desktop.auditLabel(job({summary: {errors: 0, warnings: 0, files_scanned: 2, skipped_files: 1}}))).toBe('Audit incomplete');
  });
  it('shows progress, prevents repeated cancellation, and applies the cancelled response', async () => {
    history = [job({status: 'running', progress: {phase: 'Reading', completed: 2, total: 5}})]; await runs();
    expect(screen.getByRole('progressbar').getAttribute('value')).toBe('2');
    const request = deferred<Job>(); vi.mocked(desktop.api).mockReturnValueOnce(request.promise);
    fireEvent.click(screen.getByText('Cancel audit'));
    expect((screen.getByText('Cancelling...') as HTMLButtonElement).disabled).toBe(true);
    await act(async () => request.resolve(job({status: 'cancelled'})));
    expect(screen.getByRole('heading', {name: 'Cancelled'})).toBeTruthy();
    expect(screen.queryByText('Cancel audit')).toBeNull();
  });
  it('uses a spinner only when running progress has no known total', async () => {
    history = [job({status: 'running', progress: {phase: 'reports', completed: 0, total: null}})];
    await runs();
    expect(screen.getByLabelText('Audit running')).toBeTruthy();
    expect(screen.queryByRole('progressbar')).toBeNull();
    expect(screen.getByText('Writing reports')).toBeTruthy();
    expect(screen.getByText(/Elapsed/)).toBeTruthy();
  });
  it('shows a concise timestamped job log in its own run view', async () => {
    history = [job({log: [
      {at: 1700000000, event: 'queued'}, {at: 1700000001, event: 'started'},
      {at: 1700000002, event: 'reading'}, {at: 1700000003, event: 'completed'},
    ], parameters: {input_counts: {paths: 1, policy: 1}, options: {
      uid_checks: true, vendor_summary: false, multiqc: true, threads: 6,
    }}})];
    await runs();
    fireEvent.click(screen.getByRole('tab', {name: 'Log'}));
    expect(screen.getByRole('heading', {name: 'Job record'})).toBeTruthy();
    expect(screen.getByText('4 events')).toBeTruthy();
    expect(screen.getByText('6')).toBeTruthy();
    expect(screen.getByText('DICOM inputs')).toBeTruthy();
    expect(screen.getByText('Project policy')).toBeTruthy();
    expect(screen.getAllByText('Enabled')).toHaveLength(2);
    expect(screen.getByText('2s')).toBeTruthy();
    expect(screen.getByText('2.5 files/s')).toBeTruthy();
    vi.mocked(desktop.saveJobRecord).mockResolvedValue(true);
    fireEvent.click(screen.getByText('Download job record'));
    await screen.findByText('Job record saved.');
    expect(desktop.saveJobRecord).toHaveBeenCalledWith('first');
    expect(screen.getByText('Audit queued')).toBeTruthy();
    expect(screen.getByText('Reading and evaluating metadata')).toBeTruthy();
    expect(screen.getByText('Audit completed')).toBeTruthy();
    expect(document.querySelectorAll('time')).toHaveLength(4);
  });
  it('retries failed findings, paginates, and resets pagination on another run', async () => {
    history = [job(), job({id: 'second', mode: 'compare'})];
    const finding = {rule_id: 'privacy', severity: 'warning', path: 'file.dcm', keyword: 'PatientName', message: 'Review metadata', recommendation: 'Check identifiers'};
    vi.mocked(desktop.api).mockImplementation(async path => {
      if (path.includes('/results')) throw new Error('Unavailable'); return history as never;
    });
    await runs(); await screen.findByText('Findings could not be loaded.');
    vi.mocked(desktop.api).mockResolvedValue({findings: [finding], total_findings: 101} as never);
    fireEvent.click(screen.getByText('Retry findings')); await screen.findByText('Review metadata');
    fireEvent.click(screen.getByText('Next'));
    await waitFor(() => expect(desktop.api).toHaveBeenCalledWith('/api/v1/jobs/first/results?offset=100&limit=100'));
    await screen.findByText('101–101 of 101');
    fireEvent.click(runButton(/Dataset comparison/));
    await waitFor(() => expect(desktop.api).toHaveBeenCalledWith('/api/v1/jobs/second/results?offset=0&limit=100'));
  });
  it('sandboxes report previews, exports and reveals through native commands', async () => {
    history = [job()]; await runs(); vi.mocked(desktop.report).mockResolvedValue('<h1>Report</h1>');
    vi.mocked(desktop.saveReport).mockResolvedValue(true); vi.mocked(desktop.reveal).mockResolvedValue();
    fireEvent.click(screen.getByRole('tab', {name: 'Reports'}));
    const frame = await screen.findByTitle('Audit report preview'); expect(frame.getAttribute('sandbox')).toBe('');
    expect(frame.getAttribute('srcdoc')).toBe('<h1>Report</h1>');
    fireEvent.click(screen.getByRole('button', {name: 'Select report report.json'}));
    fireEvent.click(screen.getByLabelText('Save report.json')); await screen.findByText('Report copy saved.');
    expect(desktop.saveReport).toHaveBeenCalledWith('first', 1);
    fireEvent.click(screen.getByText('Open run folder')); expect(desktop.reveal).toHaveBeenCalledWith('first');
    fireEvent.click(screen.getByRole('tab', {name: 'Findings'})); expect(screen.queryByTitle('Audit report preview')).toBeNull();
  });
  it('discards a report response after selecting another run', async () => {
    history = [job(), job({id: 'second', mode: 'compare'})]; await runs();
    const request = deferred<string>(); vi.mocked(desktop.report).mockReturnValue(request.promise);
    fireEvent.click(screen.getByRole('tab', {name: 'Reports'}));
    fireEvent.click(runButton(/Dataset comparison/));
    await act(async () => request.resolve('<h1>Wrong run</h1>'));
    expect(screen.queryByTitle('Audit report preview')).toBeNull();
  });
  it('displays failed and interrupted history without reports', async () => {
    history = [job({status: 'failed', message: 'Worker failed.'}), job({id: 'second', mode: 'compare', status: 'interrupted'})];
    await runs(); expect(screen.getByText('Worker failed.')).toBeTruthy(); expect(screen.queryByText('Reports and exports')).toBeNull();
    fireEvent.click(runButton(/Dataset comparison/)); expect(screen.getByRole('heading', {name: 'Interrupted'})).toBeTruthy();
  });
  it('renames a run without changing its immutable identifier', async () => {
    history = [job()]; await runs();
    vi.mocked(desktop.renameRun).mockResolvedValue(job({name: 'MS baseline audit'}));
    fireEvent.click(screen.getByRole('button', {name: 'More actions for Privacy audit'}));
    fireEvent.click(screen.getByRole('menuitem', {name: 'Rename'}));
    fireEvent.change(screen.getByLabelText('Run name'), {target: {value: 'MS baseline audit'}});
    fireEvent.click(screen.getByRole('button', {name: 'Save run name'}));
    await screen.findAllByText('MS baseline audit');
    expect(desktop.renameRun).toHaveBeenCalledWith('first', 'MS baseline audit');
    expect(screen.getAllByText(/first/).length).toBeGreaterThan(0);
  });
});

describe('run deletion', () => {
  it('deletes all inactive runs together and preserves active runs', async () => {
    history = [job(), job({id: 'failed', status: 'failed'}), job({id: 'active', status: 'running'})];
    vi.mocked(desktop.deleteRuns).mockResolvedValue(['first', 'failed']); await runs();
    fireEvent.click(screen.getByRole('button', {name: 'Delete all runs'}));
    await waitFor(() => expect(desktop.deleteRuns).toHaveBeenCalledTimes(1));
    await waitFor(() => expect(screen.getAllByRole('button').filter(button => button.classList.contains('run-select'))).toHaveLength(1));
    const remaining = screen.getAllByRole('button').filter(button => button.classList.contains('run-select'));
    expect(remaining).toHaveLength(1); expect(remaining[0].textContent).toContain('active');
  });
  it('keeps run history when bulk deletion is cancelled', async () => {
    history = [job()]; vi.mocked(desktop.deleteRuns).mockResolvedValue([]); await runs();
    fireEvent.click(screen.getByRole('button', {name: 'Delete all runs'}));
    await waitFor(() => expect(desktop.deleteRuns).toHaveBeenCalledTimes(1));
    expect(runButton(/Privacy audit/)).toBeTruthy();
  });
  it.each(['completed', 'failed', 'cancelled', 'interrupted'])('deletes a %s run after native confirmation', async status => {
    history = [job({status})]; vi.mocked(desktop.deleteRun).mockResolvedValue(true); await runs();
    fireEvent.click(screen.getByRole('button', {name: 'More actions for Privacy audit'}));
    fireEvent.click(screen.getByRole('menuitem', {name: 'Delete'}));
    await screen.findByText('No audits yet'); expect(desktop.deleteRun).toHaveBeenCalledWith('first');
    expect(screen.queryByText('Reports and exports')).toBeNull();
  });
  it.each(['queued', 'running'])('does not offer deletion for %s runs', async status => {
    history = [job({status})]; await runs(); fireEvent.click(screen.getByRole('button', {name: 'More actions for Privacy audit'})); expect(screen.queryByRole('menuitem', {name: 'Delete'})).toBeNull();
  });
  it('prevents duplicate deletion, preserves previews on cancellation, and allows retry after failure', async () => {
    history = [job()]; await runs(); vi.mocked(desktop.report).mockResolvedValue('<h1>Report</h1>');
    fireEvent.click(screen.getByRole('tab', {name: 'Reports'}));
    await screen.findByTitle('Audit report preview');
    const request = deferred<boolean>(); vi.mocked(desktop.deleteRun).mockReturnValueOnce(request.promise);
    fireEvent.click(screen.getByRole('button', {name: 'More actions for Privacy audit'}));
    const button = screen.getByRole('menuitem', {name: 'Delete'});
    fireEvent.click(button); fireEvent.click(button);
    expect((button as HTMLButtonElement).disabled).toBe(true); expect(button.getAttribute('aria-busy')).toBe('true');
    expect(desktop.deleteRun).toHaveBeenCalledTimes(1);
    await act(async () => request.resolve(false)); expect(screen.getByTitle('Audit report preview')).toBeTruthy();
    vi.mocked(desktop.deleteRun).mockRejectedValueOnce(new Error('Deletion failed'));
    fireEvent.click(button); await screen.findByText('Deletion failed'); expect((button as HTMLButtonElement).disabled).toBe(false);
    vi.mocked(desktop.deleteRun).mockResolvedValueOnce(true); fireEvent.click(button);
    await screen.findByText('No audits yet'); expect(screen.queryByTitle('Audit report preview')).toBeNull();
  });
  it('ignores pending poll, findings, and report responses after deletion', async () => {
    vi.useFakeTimers(); history = [job()]; const findings = deferred<Results>(), poll = deferred<Job[]>(), preview = deferred<string>();
    vi.mocked(desktop.api).mockImplementation(async path => path.includes('/results') ? findings.promise as never : history as never);
    render(<App/>); await act(async () => {});
    fireEvent.click(screen.getByRole('button', {name: /^Runs/})); fireEvent.click(runButton(/Privacy audit/));
    vi.mocked(desktop.api).mockReturnValueOnce(poll.promise);
    await act(async () => {await vi.advanceTimersByTimeAsync(1200);});
    vi.mocked(desktop.report).mockReturnValueOnce(preview.promise);
    fireEvent.click(screen.getByRole('tab', {name: 'Reports'}));
    vi.mocked(desktop.deleteRun).mockResolvedValueOnce(true); fireEvent.click(screen.getByRole('button', {name: 'More actions for Privacy audit'})); fireEvent.click(screen.getByRole('menuitem', {name: 'Delete'}));
    await act(async () => {});
    await act(async () => {poll.resolve(history); findings.resolve(empty); preview.resolve('<h1>Stale report</h1>');});
    expect(screen.getByText('No audits yet')).toBeTruthy(); expect(screen.queryByTitle('Audit report preview')).toBeNull();
    expect(screen.queryByText('No findings recorded')).toBeNull();
  });
  it('preserves another selected run when deletion finishes and blocks project saving while pending', async () => {
    history = [job(), job({id: 'second', mode: 'compare'})]; await runs();
    const request = deferred<boolean>(); vi.mocked(desktop.deleteRun).mockReturnValueOnce(request.promise);
    fireEvent.click(screen.getByRole('button', {name: 'More actions for Privacy audit'}));
    fireEvent.click(screen.getByRole('menuitem', {name: 'Delete'}));
    fireEvent.click(screen.getByRole('button', {name: 'Settings'}));
    menu('save-project');
    expect(desktop.saveProject).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole('button', {name: /^Runs/})); fireEvent.click(runButton(/Dataset comparison/));
    await screen.findByText('No findings recorded');
    await act(async () => request.resolve(true));
    expect(screen.queryAllByRole('button', {name: /Privacy audit/}).filter(button => button.classList.contains('run-select'))).toHaveLength(0);
    expect(runButton(/Dataset comparison/).getAttribute('aria-pressed')).toBe('true');
    expect(screen.getByText('No findings recorded')).toBeTruthy();
  });
});

describe('settings and connection', () => {
  it('contains preferences without duplicating project-file or About commands', async () => {
    await start(); fireEvent.click(screen.getByRole('button', {name: 'Settings'}));
    for (const name of ['Appearance', 'Processing', 'Report outputs']) expect(screen.getByRole('heading', {name})).toBeTruthy();
    expect(screen.queryByText('Choose output folder')).toBeNull();
    expect(screen.getByText(/One audit runs at a time/)).toBeTruthy();
    const threads = screen.getByLabelText('Metadata threads') as HTMLInputElement;
    expect(threads.value).toBe('4'); expect(threads.max).toBe('12');
    expect(screen.getByText(/12 logical processors/)).toBeTruthy();
    expect(screen.queryByRole('heading', {name: 'Project file'})).toBeNull();
    expect(screen.queryByRole('heading', {name: 'About dicomqc'})).toBeNull();
    expect(screen.getByRole('link', {name: 'Documentation'}).getAttribute('href')).toBe('https://cnag-biomedical-informatics.github.io/dicomqc/');
    expect(screen.getByRole('link', {name: 'GitHub'}).getAttribute('href')).toBe('https://github.com/CNAG-Biomedical-Informatics/dicomqc');
  });
  it('uses the selected metadata thread count for the next audit', async () => {
    await start(); fireEvent.click(screen.getByRole('button', {name: 'Settings'}));
    fireEvent.change(screen.getByLabelText('Metadata threads'), {target: {value: '8'}});
    fireEvent.click(screen.getByRole('tab', {name: 'Setup'}));
    vi.mocked(desktop.pick).mockResolvedValue({id: 'input', name: 'DICOM', kind: 'directory'});
    fireEvent.click(screen.getByText('Choose DICOM folder')); await screen.findByRole('button', {name: 'Remove DICOM'});
    fireEvent.click(screen.getByRole('button', {name: 'Run privacy audit'}));
    await waitFor(() => expect(desktop.api).toHaveBeenCalledWith('/api/v1/jobs', 'POST', expect.objectContaining({
      options: expect.objectContaining({threads: 8}),
    })));
  });
  it('restores project settings and reports missing external inputs', async () => {
    vi.mocked(desktop.currentProject).mockResolvedValue({projectPath: '/projects/MS.dicomqc', output: '/outputs/MS', name: 'MS', project: {mode: 'scan', inputs: {paths: [{id: 'restored', name: 'MRI', kind: 'directory', display_path: '/data/MRI'}]}, options: {uid_checks: true, vendor_summary: false, multiqc: true, threads: 8}}, missing: ['/data/missing']});
    await start();
    expect(screen.getAllByText('MS').length).toBeGreaterThan(0);
    expect(screen.getByRole('button', {name: 'Remove MRI'})).toBeTruthy();
    expect((screen.getByLabelText('Check UID syntax and relationships') as HTMLInputElement).checked).toBe(true);
    expect(screen.getByRole('status').textContent).toContain('1 saved input path is unavailable');
    fireEvent.click(screen.getByRole('button', {name: 'Settings'}));
    expect((screen.getByLabelText('Export MultiQC custom content') as HTMLInputElement).checked).toBe(true);
    expect((screen.getByLabelText('Metadata threads') as HTMLInputElement).value).toBe('8');
  });
  it('does not overlap slow history polls', async () => {
    vi.useFakeTimers(); const pending = deferred<Job[]>();
    vi.mocked(desktop.api).mockImplementation(path => path === '/api/v1/capabilities' ? Promise.resolve(capabilities) as never : pending.promise as never);
    render(<App/>); await act(async () => {await vi.advanceTimersByTimeAsync(5000);});
    expect(desktop.api).toHaveBeenCalledTimes(2);
    await act(async () => pending.resolve([]));
    await act(async () => {await vi.advanceTimersByTimeAsync(1200);}); expect(desktop.api).toHaveBeenCalledTimes(3);
  });
  it('persists light, dark, and system preferences', async () => {
    localStorage.setItem('dicomqc-theme', 'invalid'); await start(); fireEvent.click(screen.getByRole('button', {name: 'Settings'}));
    expect(document.documentElement.dataset.theme).toBe('system');
    for (const value of ['light', 'dark', 'system']) {
      fireEvent.change(screen.getByLabelText('Theme'), {target: {value}});
      expect(document.documentElement.dataset.theme).toBe(value); expect(localStorage.getItem('dicomqc-theme')).toBe(value);
    }
  });
  it('blocks project snapshots while work is active', async () => {
    history = [job({status: 'queued'})]; await start(); fireEvent.click(screen.getByRole('button', {name: 'Settings'}));
    menu('save-project');
    expect(desktop.saveProject).not.toHaveBeenCalled();
    expect(screen.getByRole('alert').textContent).toContain('Finish or cancel active audits');
  });
  it('saves a project file without changing the output folder or input handles', async () => {
    await start(); vi.mocked(desktop.pick).mockResolvedValue({id: 'old', name: 'Old input', kind: 'directory'});
    fireEvent.click(screen.getByText('Choose DICOM folder')); await screen.findByRole('button', {name: 'Remove Old input'});
    vi.mocked(desktop.saveProject).mockResolvedValue({projectPath: '/projects/MS.dicomqc', output: '/workspace', name: 'MS', project: {mode: 'scan', inputs: null, options: {uid_checks: false, vendor_summary: false, multiqc: false, threads: 4}}, missing: []});
    menu('save-project-as');
    await waitFor(() => expect(desktop.saveProject).toHaveBeenCalled());
    expect(desktop.saveProject).toHaveBeenCalledWith(expect.objectContaining({inputs: {paths: ['old']}}), true);
    fireEvent.click(screen.getByRole('button', {name: 'New audit'}));
    fireEvent.click(screen.getByRole('button', {name: 'Run privacy audit'}));
    await waitFor(() => expect(desktop.api).toHaveBeenCalledWith('/api/v1/jobs', 'POST', expect.objectContaining({inputs: {paths: ['old']}})));
  });
  it('marks run-history changes as unsaved and clears them after a project snapshot', async () => {
    history = [job()];
    await start();
    await waitFor(() => expect(desktop.syncMenu).toHaveBeenLastCalledWith(expect.objectContaining({dirty: true})));
    vi.mocked(desktop.saveProject).mockResolvedValue({projectPath: '/Study.dicomqc', name: 'Study', output: '/workspace', savedJobs: history, project: {mode: 'scan', inputs: null, options: {threads: 4, uid_checks: false, vendor_summary: false, multiqc: false}}, missing: []});
    menu('save-project');
    await screen.findByText('Project saved.');
    await waitFor(() => expect(desktop.syncMenu).toHaveBeenLastCalledWith(expect.objectContaining({dirty: false})));
  });
  it.each(['cancel', 'failure'])('retains selected inputs when project saving ends in %s', async outcome => {
    await start();
    vi.mocked(desktop.pick).mockResolvedValue({id: 'old', name: 'MRI input', kind: 'directory'});
    fireEvent.click(screen.getByText('Choose DICOM folder'));
    await screen.findByRole('button', {name: 'Remove MRI input'});
    if (outcome === 'cancel') vi.mocked(desktop.saveProject).mockResolvedValue(null);
    else vi.mocked(desktop.saveProject).mockRejectedValue(new Error('Choose a writable project file.'));
    menu('save-project-as');
    await screen.findByText('● Local engine ready');
    expect(screen.getByRole('button', {name: 'Edit DICOM inputs: MRI input'})).toBeTruthy();
    fireEvent.click(screen.getByRole('button', {name: 'New audit'}));
    expect(screen.getByRole('button', {name: 'Remove MRI input'})).toBeTruthy();
    await waitFor(() => expect((screen.getByRole('button', {name: 'Run privacy audit'}) as HTMLButtonElement).disabled).toBe(false));
    if (outcome === 'failure') expect((await screen.findByRole('alert')).textContent).toContain('writable project file');
  });
  it('marks connection loss and recovers on the next poll', async () => {
    await start(); vi.useFakeTimers();
    // Remount so the polling timer is controlled by this test.
    cleanup(); render(<App/>); await act(async () => {});
    vi.mocked(desktop.api).mockRejectedValueOnce(new Error('offline'));
    await act(async () => {await vi.advanceTimersByTimeAsync(1200);});
    expect(screen.getByText('Local engine unavailable. Reconnecting...')).toBeTruthy();
    expect(screen.queryByText('● Local engine ready')).toBeNull();
    await act(async () => {await vi.advanceTimersByTimeAsync(1200);});
    expect(screen.getByText('● Local engine ready')).toBeTruthy();
    expect(screen.queryByText('Local engine unavailable. Reconnecting...')).toBeNull();
  });
});
