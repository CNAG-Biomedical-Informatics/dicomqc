import {beforeEach, expect, it, vi} from 'vitest';
import {invoke, isTauri} from '@tauri-apps/api/core';
import {listen} from '@tauri-apps/api/event';
import {api, chooseWorkspace, deleteRun, onDesktopMenu, pick, report, reveal, saveReport, syncMenu, workspace} from './desktop';

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
it('preserves native dialog and workspace command signatures', async () => {
  await pick(true); expect(invoke).toHaveBeenLastCalledWith('select_input', {directory: true});
  await pick(false); expect(invoke).toHaveBeenLastCalledWith('select_input', {directory: false});
  await workspace(); expect(invoke).toHaveBeenLastCalledWith('workspace');
  await chooseWorkspace(['input']); expect(invoke).toHaveBeenLastCalledWith('choose_workspace', {inputIds: ['input']});
});
it('uses indexed native report commands, not renderer filesystem paths', async () => {
  await report('run', 2); expect(invoke).toHaveBeenLastCalledWith('read_report', {id: 'run', index: 2});
  await saveReport('run', 2); expect(invoke).toHaveBeenLastCalledWith('save_report', {id: 'run', index: 2});
  await reveal('run'); expect(invoke).toHaveBeenLastCalledWith('reveal_run', {id: 'run'});
});
it.each([false, true])('returns native deletion confirmation result %s', async result => {
  vi.mocked(invoke).mockResolvedValueOnce(result);
  await expect(deleteRun('run')).resolves.toBe(result);
  expect(invoke).toHaveBeenCalledWith('delete_run', {id: 'run'});
});
it('does not register or synchronize menus outside native', async () => {
  vi.mocked(isTauri).mockReturnValue(false);
  const stop = await onDesktopMenu(vi.fn()); stop();
  await syncMenu({canRun: false, canFindings: false, canReports: false});
  expect(listen).not.toHaveBeenCalled(); expect(invoke).not.toHaveBeenCalled();
});
it('registers desktop-menu events and synchronizes enabled items with the native contract', async () => {
  const handler = vi.fn(), stop = vi.fn(); vi.mocked(listen).mockResolvedValue(stop);
  expect(await onDesktopMenu(handler)).toBe(stop);
  expect(listen).toHaveBeenCalledWith('desktop-menu', expect.any(Function));
  const callback = vi.mocked(listen).mock.calls[0][1];
  callback({event: 'desktop-menu', id: 1, payload: 'reports'}); expect(handler).toHaveBeenCalledWith('reports');
  await syncMenu({canRun: true, canFindings: true, canReports: false});
  expect(invoke).toHaveBeenCalledWith('sync_menu', {canRun: true, canFindings: true, canReports: false});
});
