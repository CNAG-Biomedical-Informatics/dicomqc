import React from 'react';
import {act, cleanup, fireEvent, render, screen, waitFor} from '@testing-library/react';
import {afterEach, beforeEach, describe, expect, it, vi} from 'vitest';
import {App} from './main';
import * as desktop from './desktop';
import type {Job, Results} from './desktop';

vi.mock('./desktop', async importOriginal => ({
  ...await importOriginal<typeof import('./desktop')>(), api: vi.fn(), pick: vi.fn(),
  workspace: vi.fn(), chooseWorkspace: vi.fn(), report: vi.fn(), saveReport: vi.fn(), reveal: vi.fn(), deleteRun: vi.fn(), onDesktopMenu: vi.fn(), syncMenu: vi.fn(),
}));
const job = (overrides: Partial<Job> = {}): Job => ({id: 'first', created: 1700000000, mode: 'scan', example: null,
  status: 'completed', audit_exit_code: 0, summary: {errors: 0, warnings: 0, files_scanned: 5, skipped_files: 0},
  artifacts: ['report.html', 'report.json'], message: null, ...overrides});
const empty: Results = {findings: [], total_findings: 0};
function deferred<T>() {
  let resolve!: (value: T) => void, reject!: (reason: unknown) => void;
  const promise = new Promise<T>((done, fail) => {resolve = done; reject = fail;});
  return {promise, resolve, reject};
}
let history: Job[];
beforeEach(() => {
  vi.resetAllMocks(); localStorage.clear(); history = [];
  vi.mocked(desktop.workspace).mockResolvedValue('/workspace');
  vi.mocked(desktop.onDesktopMenu).mockResolvedValue(() => {});
  vi.mocked(desktop.syncMenu).mockResolvedValue();
  vi.mocked(desktop.report).mockResolvedValue('<h1>Report</h1>');
  vi.mocked(desktop.api).mockImplementation(async (path, method) => {
    if (path.endsWith('/results?offset=0&limit=100')) return empty as never;
    if (method === 'POST') return job({status: 'queued'}) as never;
    return history as never;
  });
});
afterEach(() => {cleanup(); vi.useRealTimers();});
async function start() {render(<App/>); await screen.findByText('● Local engine ready');}
async function runs() {
  await start(); fireEvent.click(screen.getByRole('button', {name: /^Runs/}));
  fireEvent.click(screen.getByRole('button', {name: /Dataset scan/}));
}

describe('audit forms', () => {
  it('requires inputs, handles picker cancellation, deduplicates and removes inputs', async () => {
    await start(); const run = screen.getByRole('button', {name: 'Run audit'});
    expect((run as HTMLButtonElement).disabled).toBe(true);
    vi.mocked(desktop.pick).mockResolvedValue(null);
    fireEvent.click(screen.getByText('Add folder')); await waitFor(() => expect(desktop.pick).toHaveBeenCalledWith(true));
    expect((run as HTMLButtonElement).disabled).toBe(true);
    vi.mocked(desktop.pick).mockResolvedValue({id: 'input', name: 'DICOM', kind: 'directory'});
    fireEvent.click(screen.getByText('Add folder')); await screen.findByRole('button', {name: 'Remove DICOM'});
    fireEvent.click(screen.getByText('Add folder')); await waitFor(() => expect(desktop.pick).toHaveBeenCalledTimes(3));
    expect(screen.getAllByRole('button', {name: 'Remove DICOM'})).toHaveLength(1);
    fireEvent.click(screen.getByRole('button', {name: 'Remove DICOM'}));
    expect((run as HTMLButtonElement).disabled).toBe(true);
  });
  it('submits scan options and preserves the native input handle contract', async () => {
    await start(); vi.mocked(desktop.pick).mockResolvedValue({id: 'input', name: 'DICOM', kind: 'directory'});
    fireEvent.click(screen.getByText('Add folder')); await screen.findByRole('button', {name: 'Remove DICOM'});
    fireEvent.click(screen.getByText('Advanced checks and outputs'));
    fireEvent.click(screen.getByLabelText('Check UID syntax and relationships'));
    fireEvent.click(screen.getByLabelText('Include scanner and private-creator inventory'));
    expect(screen.getByText(/observed labels/)).toBeTruthy();
    fireEvent.click(screen.getByRole('button', {name: 'Run audit'}));
    await waitFor(() => expect(desktop.api).toHaveBeenCalledWith('/api/v1/jobs', 'POST', {
      mode: 'scan', inputs: {paths: ['input']}, options: {uid_checks: true, vendor_summary: true, multiqc: false},
    }));
    await screen.findByText('Queued - waiting for the active audit');
  });
  it('requires all compare inputs and excludes scan-only options', async () => {
    await start(); fireEvent.click(screen.getByText('Advanced checks and outputs'));
    fireEvent.click(screen.getByLabelText('Check UID syntax and relationships'));
    fireEvent.click(screen.getByText('Compare datasets'));
    for (const [label, id] of [['Source folder', 'source'], ['Candidate folder', 'candidate'], ['Pairing manifest · CSV', 'manifest']]) {
      expect((screen.getByRole('button', {name: 'Run audit'}) as HTMLButtonElement).disabled).toBe(true);
      vi.mocked(desktop.pick).mockResolvedValue({id, name: id, kind: 'file'});
      fireEvent.click(screen.getByRole('button', {name: `Choose ${label}`})); await screen.findByRole('button', {name: `Remove ${id}`});
    }
    fireEvent.click(screen.getByRole('button', {name: 'Run audit'}));
    await waitFor(() => expect(desktop.api).toHaveBeenCalledWith('/api/v1/jobs', 'POST', {
      mode: 'compare', inputs: {source: ['source'], candidate: ['candidate'], manifest: ['manifest']}, options: {},
    }));
  });
  it.each(['scan', 'compare', 'policy', 'uid', 'vendor'])('submits the %s example without external options', async example => {
    await start(); fireEvent.click(screen.getByText('Explore with synthetic data'));
    fireEvent.click(screen.getByRole('button', {name: example === 'uid' ? 'UID integrity' : example[0].toUpperCase() + example.slice(1)}));
    await waitFor(() => expect(desktop.api).toHaveBeenCalledWith('/api/v1/jobs', 'POST', {mode: 'demo', example}));
  });
  it('displays native failures and allows dismissal', async () => {
    await start(); vi.mocked(desktop.pick).mockRejectedValue('Selection failed');
    fireEvent.click(screen.getByText('Add file')); expect((await screen.findByRole('alert')).textContent).toContain('Selection failed');
    fireEvent.click(screen.getByLabelText('Dismiss error')); expect(screen.queryByRole('alert')).toBeNull();
  });
});

describe('runs and reports', () => {
  it('keeps an unsuccessful submission editable and prevents duplicate submissions', async () => {
    await start(); fireEvent.click(screen.getByText('Explore with synthetic data'));
    const request = deferred<Job>(); vi.mocked(desktop.api).mockReturnValueOnce(request.promise);
    fireEvent.click(screen.getByRole('button', {name: 'Scan'}));
    expect((screen.getByRole('button', {name: 'Scan'}) as HTMLButtonElement).disabled).toBe(true);
    await act(async () => request.resolve(job({status: 'queued'})));
    expect(vi.mocked(desktop.api).mock.calls.filter(([, method]) => method === 'POST')).toHaveLength(1);
    fireEvent.click(screen.getByRole('button', {name: 'New audit'}));
    vi.mocked(desktop.api).mockRejectedValueOnce(new Error('Cannot start audit'));
    fireEvent.click(screen.getByText('Explore with synthetic data'));
    fireEvent.click(screen.getByRole('button', {name: 'Scan'}));
    await screen.findByText('Cannot start audit');
    expect((screen.getByRole('button', {name: 'Scan'}) as HTMLButtonElement).disabled).toBe(false);
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
    fireEvent.click(screen.getByRole('button', {name: /Dataset comparison/}));
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
    fireEvent.click(screen.getByRole('button', {name: /Dataset comparison/}));
    await act(async () => request.resolve('<h1>Wrong run</h1>'));
    expect(screen.queryByTitle('Audit report preview')).toBeNull();
  });
  it('displays failed and interrupted history without reports', async () => {
    history = [job({status: 'failed', message: 'Worker failed.'}), job({id: 'second', mode: 'compare', status: 'interrupted'})];
    await runs(); expect(screen.getByText('Worker failed.')).toBeTruthy(); expect(screen.queryByText('Reports and exports')).toBeNull();
    fireEvent.click(screen.getByRole('button', {name: /Dataset comparison/})); expect(screen.getByRole('heading', {name: 'Interrupted'})).toBeTruthy();
  });
});

describe('run deletion', () => {
  it.each(['completed', 'failed', 'cancelled', 'interrupted'])('deletes a %s run after native confirmation', async status => {
    history = [job({status})]; vi.mocked(desktop.deleteRun).mockResolvedValue(true); await runs();
    fireEvent.click(screen.getByRole('button', {name: 'Delete run'}));
    await screen.findByText('No audits yet'); expect(desktop.deleteRun).toHaveBeenCalledWith('first');
    expect(screen.queryByText('Reports and exports')).toBeNull();
  });
  it.each(['queued', 'running'])('does not offer deletion for %s runs', async status => {
    history = [job({status})]; await runs(); expect(screen.queryByRole('button', {name: 'Delete run'})).toBeNull();
  });
  it('prevents duplicate deletion, preserves previews on cancellation, and allows retry after failure', async () => {
    history = [job()]; await runs(); vi.mocked(desktop.report).mockResolvedValue('<h1>Report</h1>');
    fireEvent.click(screen.getByRole('tab', {name: 'Reports'}));
    await screen.findByTitle('Audit report preview');
    const request = deferred<boolean>(); vi.mocked(desktop.deleteRun).mockReturnValueOnce(request.promise);
    const button = screen.getByRole('button', {name: 'Delete run'});
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
    fireEvent.click(screen.getByRole('button', {name: /^Runs/})); fireEvent.click(screen.getByRole('button', {name: /Dataset scan/}));
    vi.mocked(desktop.api).mockReturnValueOnce(poll.promise);
    await act(async () => {await vi.advanceTimersByTimeAsync(1200);});
    vi.mocked(desktop.report).mockReturnValueOnce(preview.promise);
    fireEvent.click(screen.getByRole('tab', {name: 'Reports'}));
    vi.mocked(desktop.deleteRun).mockResolvedValueOnce(true); fireEvent.click(screen.getByRole('button', {name: 'Delete run'}));
    await act(async () => {});
    await act(async () => {poll.resolve(history); findings.resolve(empty); preview.resolve('<h1>Stale report</h1>');});
    expect(screen.getByText('No audits yet')).toBeTruthy(); expect(screen.queryByTitle('Audit report preview')).toBeNull();
    expect(screen.queryByText('No findings recorded')).toBeNull();
  });
  it('preserves another selected run when deletion finishes and blocks workspace switching while pending', async () => {
    history = [job(), job({id: 'second', mode: 'compare'})]; await runs();
    const request = deferred<boolean>(); vi.mocked(desktop.deleteRun).mockReturnValueOnce(request.promise);
    fireEvent.click(screen.getByRole('button', {name: 'Delete run'}));
    fireEvent.click(screen.getByRole('button', {name: 'Settings'}));
    expect((screen.getByText('Choose output folder') as HTMLButtonElement).disabled).toBe(true);
    fireEvent.click(screen.getByRole('button', {name: /^Runs/})); fireEvent.click(screen.getByRole('button', {name: /Dataset comparison/}));
    await screen.findByText('No findings recorded');
    await act(async () => request.resolve(true));
    expect(screen.queryByRole('button', {name: /Dataset scan/})).toBeNull();
    expect(screen.getByRole('button', {name: /Dataset comparison/}).getAttribute('aria-pressed')).toBe('true');
    expect(screen.getByText('No findings recorded')).toBeTruthy();
  });
});

describe('settings and connection', () => {
  it.each(['success', 'failure'])('ignores late findings %s while workspace selection is pending and refetches after cancellation', async outcome => {
    history = [job()];
    const pendingResults = deferred<Results>(), pendingWorkspace = deferred<Awaited<ReturnType<typeof desktop.chooseWorkspace>>>();
    vi.mocked(desktop.api).mockImplementation(async path => path.includes('/results') ? pendingResults.promise as never : history as never);
    await runs();
    await screen.findByText('Loading findings...');
    vi.mocked(desktop.chooseWorkspace).mockReturnValue(pendingWorkspace.promise);
    fireEvent.click(screen.getByRole('button', {name: 'Settings'}));
    fireEvent.click(screen.getByText('Choose output folder'));
    await screen.findByText('Changing output folder...');
    await act(async () => {
      if (outcome === 'success') pendingResults.resolve(empty);
      else pendingResults.reject(new Error('Old workspace failure'));
    });
    fireEvent.click(screen.getByRole('button', {name: /^Runs/}));
    expect(screen.queryByText('No findings recorded')).toBeNull();
    expect(screen.queryByText('Findings could not be loaded.')).toBeNull();
    expect(vi.mocked(desktop.api).mock.calls.filter(([path]) => path.includes('/results'))).toHaveLength(1);
    vi.mocked(desktop.api).mockImplementation(async path => path.includes('/results') ? empty as never : history as never);
    await act(async () => pendingWorkspace.resolve(null));
    await screen.findByText('No findings recorded');
    expect(vi.mocked(desktop.api).mock.calls.filter(([path]) => path.includes('/results'))).toHaveLength(2);
  });
  it('does not let old workspace findings replace results in the new workspace', async () => {
    history = [job()]; const oldResults = deferred<Results>();
    vi.mocked(desktop.api).mockImplementation(async path => path.includes('/results') ? oldResults.promise as never : history as never);
    await runs(); await screen.findByText('Loading findings...');
    vi.mocked(desktop.chooseWorkspace).mockResolvedValue({path: '/new', inputs: {}});
    vi.mocked(desktop.workspace).mockResolvedValue('/new');
    vi.mocked(desktop.api).mockImplementation(async path => path.includes('/results') ? empty as never : history as never);
    fireEvent.click(screen.getByRole('button', {name: 'Settings'})); fireEvent.click(screen.getByText('Choose output folder'));
    await screen.findByText('/new'); await screen.findByText('● Local engine ready');
    fireEvent.click(screen.getByRole('button', {name: /^Runs/}));
    fireEvent.click(screen.getByRole('button', {name: /Dataset scan/})); await screen.findByText('No findings recorded');
    await act(async () => oldResults.resolve({total_findings: 1, findings: [{rule_id: 'old', severity: 'error', path: 'old', keyword: 'old', message: 'Stale finding', recommendation: 'old'}]}));
    expect(screen.queryByText('Stale finding')).toBeNull(); expect(screen.getByText('No findings recorded')).toBeTruthy();
  });
  it('ignores history and picker responses from the previous workspace', async () => {
    await start(); vi.useFakeTimers(); cleanup(); render(<App/>); await act(async () => {});
    const oldHistory = deferred<Job[]>(), oldInput = deferred<desktop.Input | null>();
    vi.mocked(desktop.api).mockReturnValueOnce(oldHistory.promise);
    await act(async () => {await vi.advanceTimersByTimeAsync(1200);});
    vi.mocked(desktop.pick).mockReturnValueOnce(oldInput.promise);
    fireEvent.click(screen.getByText('Add folder'));
    vi.mocked(desktop.chooseWorkspace).mockResolvedValue({path: '/new', inputs: {}}); vi.mocked(desktop.workspace).mockResolvedValue('/new');
    fireEvent.click(screen.getByRole('button', {name: 'Settings'})); fireEvent.click(screen.getByText('Choose output folder'));
    await act(async () => {});
    await act(async () => {oldHistory.resolve([job()]); oldInput.resolve({id: 'stale', name: 'Stale input', kind: 'directory'});});
    fireEvent.click(screen.getByRole('button', {name: 'New audit'})); expect(screen.queryByText('Stale input')).toBeNull();
    fireEvent.click(screen.getByRole('button', {name: /^Runs/})); expect(screen.getByText('No audits yet')).toBeTruthy();
    expect(screen.queryByText('Dataset scan')).toBeNull();
  });
  it('does not overlap slow history polls', async () => {
    vi.useFakeTimers(); const pending = deferred<Job[]>(); vi.mocked(desktop.api).mockReturnValueOnce(pending.promise);
    render(<App/>); await act(async () => {await vi.advanceTimersByTimeAsync(5000);});
    expect(desktop.api).toHaveBeenCalledTimes(1);
    await act(async () => pending.resolve([]));
    await act(async () => {await vi.advanceTimersByTimeAsync(1200);}); expect(desktop.api).toHaveBeenCalledTimes(2);
  });
  it('persists light, dark, and system preferences', async () => {
    localStorage.setItem('dicomqc-theme', 'invalid'); await start(); fireEvent.click(screen.getByRole('button', {name: 'Settings'}));
    expect(document.documentElement.dataset.theme).toBe('system');
    for (const value of ['light', 'dark', 'system']) {
      fireEvent.change(screen.getByLabelText('Theme'), {target: {value}});
      expect(document.documentElement.dataset.theme).toBe(value); expect(localStorage.getItem('dicomqc-theme')).toBe(value);
    }
  });
  it('blocks workspace switching while work is active', async () => {
    history = [job({status: 'queued'})]; await start(); fireEvent.click(screen.getByRole('button', {name: 'Settings'}));
    expect((screen.getByText('Choose output folder') as HTMLButtonElement).disabled).toBe(true);
  });
  it('preserves inputs with renewed handles when choosing an output folder from setup', async () => {
    await start(); vi.mocked(desktop.pick).mockResolvedValue({id: 'old', name: 'Old input', kind: 'directory'});
    fireEvent.click(screen.getByText('Add folder')); await screen.findByRole('button', {name: 'Remove Old input'});
    vi.mocked(desktop.chooseWorkspace).mockResolvedValue({path: '/new', inputs: {old: {id: 'renewed', name: 'Old input', kind: 'directory'}}}); vi.mocked(desktop.workspace).mockResolvedValue('/new');
    fireEvent.click(screen.getByText('Choose output folder'));
    await screen.findByText('/new'); await screen.findByText('● Local engine ready');
    expect(desktop.chooseWorkspace).toHaveBeenCalledWith(['old']);
    expect(screen.getByRole('button', {name: 'Remove Old input'})).toBeTruthy();
    expect((screen.getByRole('button', {name: 'Run audit'}) as HTMLButtonElement).disabled).toBe(false);
    fireEvent.click(screen.getByRole('button', {name: 'Run audit'}));
    await waitFor(() => expect(desktop.api).toHaveBeenCalledWith('/api/v1/jobs', 'POST', expect.objectContaining({inputs: {paths: ['renewed']}})));
  });
  it.each(['cancel', 'failure'])('retains selected inputs when output selection ends in %s', async outcome => {
    await start();
    vi.mocked(desktop.pick).mockResolvedValue({id: 'old', name: 'MRI input', kind: 'directory'});
    fireEvent.click(screen.getByText('Add folder'));
    await screen.findByRole('button', {name: 'Remove MRI input'});
    if (outcome === 'cancel') vi.mocked(desktop.chooseWorkspace).mockResolvedValue(null);
    else vi.mocked(desktop.chooseWorkspace).mockRejectedValue(new Error('Choose a separate output folder.'));
    fireEvent.click(screen.getByText('Choose output folder'));
    await screen.findByText('● Local engine ready');
    expect(screen.getByRole('button', {name: 'Remove MRI input'})).toBeTruthy();
    expect((screen.getByRole('button', {name: 'Run audit'}) as HTMLButtonElement).disabled).toBe(false);
    if (outcome === 'failure') expect(screen.getByRole('alert').textContent).toContain('separate output folder');
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
