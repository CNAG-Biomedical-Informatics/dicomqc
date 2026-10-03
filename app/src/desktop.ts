import {invoke, isTauri} from '@tauri-apps/api/core';
import {listen} from '@tauri-apps/api/event';

export type Input = {id: string; name: string; kind: string; display_path?: string};
export type Job = {id: string; created: number; mode: string; example: string | null; status: string;
  audit_exit_code: number | null; summary: {errors: number; warnings: number; files_scanned: number; skipped_files: number} | null;
  artifacts: string[]; message: string | null; progress?: {phase: string; completed: number; total: number | null}};
export type Finding = {rule_id: string; severity: string; path: string; keyword: string; message: string; recommendation: string};
export type Results = {findings: Finding[]; total_findings: number};

export async function api<T>(path: string, method = 'GET', body?: unknown): Promise<T> {
  if (!isTauri()) throw new Error('Launch dicomqc as a native desktop application.');
  return invoke<T>('api_request', {path, method, body: body ?? null});
}
export const pick = (directory: boolean) => invoke<Input | null>('select_input', {directory});
export const workspace = () => invoke<string>('workspace');
export const chooseWorkspace = (inputIds: string[]) => invoke<{path: string; inputs: Record<string, Input>} | null>('choose_workspace', {inputIds});
export const report = (id: string, index: number) => invoke<string>('read_report', {id, index});
export const saveReport = (id: string, index: number) => invoke<boolean>('save_report', {id, index});
export const reveal = (id: string) => invoke<void>('reveal_run', {id});
export const deleteRun = (id: string) => invoke<boolean>('delete_run', {id});
export async function onDesktopMenu(handler: (action: string) => void): Promise<() => void> {
  if (!isTauri()) return () => {};
  return listen<string>('desktop-menu', event => handler(event.payload));
}
export async function syncMenu(state: {canRun: boolean; canFindings: boolean; canReports: boolean}): Promise<void> {
  if (isTauri()) await invoke<void>('sync_menu', state);
}

export function auditLabel(job: Job): string {
  if (job.status !== 'completed') return job.status[0].toUpperCase() + job.status.slice(1);
  if (job.summary?.skipped_files) return 'Audit incomplete';
  return job.audit_exit_code === 2 ? 'Errors require attention' : job.audit_exit_code === 1 ? 'Warnings require review' : job.audit_exit_code === 0 ? 'Checks passed' : 'Audit completed';
}
