import {beforeEach, expect, it, vi} from 'vitest';
import {invoke, isTauri} from '@tauri-apps/api/core';
import {listen} from '@tauri-apps/api/event';
import {api, currentProject, deleteRun, deleteRuns, newProject, onDesktopMenu, openExternal, openProject, pick, readPolicy, renameRun, report, reveal, saveJobRecord, savePolicyCopy, saveProject, saveReport, syncMenu, workspace} from './desktop';

vi.mock('@tauri-apps/api/core', () => ({invoke: vi.fn(), isTauri: vi.fn()}));
vi.mock('@tauri-apps/api/event', () => ({listen: vi.fn()}));
beforeEach(() => {vi.resetAllMocks(); vi.mocked(isTauri).mockReturnValue(true);});
it('keeps API transport inside the native bridge', async () => {
  await api('/api/v1/jobs');
  expect(invoke).toHaveBeenLastCalledWith('api_request', {path: '/api/v1/jobs', method: 'GET', body: null});
  await api('/api/v1/jobs', 'POST', {mode: 'demo', example: 'uid'});
  expect(invoke).toHaveBeenLastCalledWith('api_request', {path: '/api/v1/jobs', method: 'POST', body: {mode: 'demo', example: 'uid'}});
});
it('rejects non-native API use', async () => {
  vi.mocked(isTauri).mockReturnValue(false);
  await expect(api('/api/v1/jobs')).rejects.toThrow('native desktop');
  expect(invoke).not.toHaveBeenCalled();
});
it('preserves native dialog and project command signatures', async () => {
  await pick(true); expect(invoke).toHaveBeenLastCalledWith('select_input', {directory: true});
  await pick(false); expect(invoke).toHaveBeenLastCalledWith('select_input', {directory: false});
  await readPolicy('policy'); expect(invoke).toHaveBeenLastCalledWith('read_policy', {inputId: 'policy'});
  await savePolicyCopy('version: 1'); expect(invoke).toHaveBeenLastCalledWith('save_policy_copy', {text: 'version: 1'});
  await workspace(); expect(invoke).toHaveBeenLastCalledWith('workspace');
  await currentProject(); expect(invoke).toHaveBeenLastCalledWith('current_project');
  const draft = {mode: 'scan' as const, inputs: {paths: ['input']}, options: {uid_checks: false, vendor_summary: false, multiqc: false, threads: 4}};
  await saveProject(draft, true); expect(invoke).toHaveBeenLastCalledWith('save_project', {draft, saveAs: true});
  await openProject(); expect(invoke).toHaveBeenLastCalledWith('open_project');
  await newProject(); expect(invoke).toHaveBeenLastCalledWith('new_project');
  await renameRun('a'.repeat(32), 'Baseline'); expect(invoke).toHaveBeenLastCalledWith('api_request', {path: `/api/v1/jobs/${'a'.repeat(32)}`, method: 'PATCH', body: {name: 'Baseline'}});
});
it('uses indexed native report commands, not renderer filesystem paths', async () => {
  await report('run', 2); expect(invoke).toHaveBeenLastCalledWith('read_report', {id: 'run', index: 2});
  await saveReport('run', 2); expect(invoke).toHaveBeenLastCalledWith('save_report', {id: 'run', index: 2});
  await saveJobRecord('run'); expect(invoke).toHaveBeenLastCalledWith('save_job_record', {id: 'run'});
  await reveal('run'); expect(invoke).toHaveBeenLastCalledWith('reveal_run', {id: 'run'});
});
it.each([false, true])('returns native deletion confirmation result %s', async result => {
  vi.mocked(invoke).mockResolvedValueOnce(result);
  await expect(deleteRun('run')).resolves.toBe(result);
  expect(invoke).toHaveBeenCalledWith('delete_run', {id: 'run'});
});
it('returns the run identifiers deleted by native bulk confirmation', async () => {
  vi.mocked(invoke).mockResolvedValueOnce(['first', 'second']);
  await expect(deleteRuns()).resolves.toEqual(['first', 'second']);
  expect(invoke).toHaveBeenCalledWith('delete_runs');
});
it('opens external links through the native allowlist', async () => {
  await openExternal('https://github.com/CNAG-Biomedical-Informatics/dicomqc');
  expect(invoke).toHaveBeenCalledWith('open_external', {url: 'https://github.com/CNAG-Biomedical-Informatics/dicomqc'});
});
it('does not register or synchronize menus outside native', async () => {
  vi.mocked(isTauri).mockReturnValue(false);
  const stop = await onDesktopMenu(vi.fn()); stop();
  await syncMenu({canRun: false, canCancel: false, canFindings: false, canReports: false, dirty: false});
  expect(listen).not.toHaveBeenCalled(); expect(invoke).not.toHaveBeenCalled();
});
it('registers desktop-menu events and synchronizes enabled items with the native contract', async () => {
  const handler = vi.fn(), stop = vi.fn(); vi.mocked(listen).mockResolvedValue(stop);
  expect(await onDesktopMenu(handler)).toBe(stop);
  expect(listen).toHaveBeenCalledWith('desktop-menu', expect.any(Function));
  const callback = vi.mocked(listen).mock.calls[0][1];
  callback({event: 'desktop-menu', id: 1, payload: 'reports'}); expect(handler).toHaveBeenCalledWith('reports');
  await syncMenu({canRun: true, canCancel: true, canFindings: true, canReports: false, dirty: true});
  expect(invoke).toHaveBeenCalledWith('sync_menu', {canRun: true, canCancel: true, canFindings: true, canReports: false, dirty: true});
});
