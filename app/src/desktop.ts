import {invoke, isTauri} from '@tauri-apps/api/core';
import {listen} from '@tauri-apps/api/event';

export type Input = {id: string; name: string; kind: string; display_path?: string};
export type RunEvent = {at: number; event: string};
export type RunParameters = {input_counts: Record<string, number>; options: {
  uid_checks?: boolean; vendor_summary?: boolean; multiqc?: boolean; threads?: number}; example_files?: number};
export type Job = {id: string; created: number; mode: string; example: string | null; status: string;
  policy?: {id: string; sha256: string};
  name?: string | null;
  audit_exit_code: number | null; summary: {errors: number; warnings: number; files_scanned: number; skipped_files: number} | null;
  artifacts: string[]; message: string | null; progress?: {phase: string; completed: number; total: number | null};
  log?: RunEvent[]; parameters?: RunParameters};
export type Finding = {rule_id: string; severity: string; path: string; keyword: string; message: string; recommendation: string};
export type Results = {findings: Finding[]; total_findings: number};
export type ProjectDraft = {mode: 'scan' | 'compare'; inputs: Record<string, string[]>;
  options: {uid_checks: boolean; vendor_summary: boolean; multiqc: boolean; threads: number}};
export type ProjectResult = {projectPath: string | null; output: string; name: string; savedJobs?: Job[]; project: {mode: 'scan' | 'compare'; inputs: Record<string, Input[]> | null;
  options: {uid_checks: boolean; vendor_summary: boolean; multiqc: boolean; threads: number}}; missing: string[]};

export async function api<T>(path: string, method = 'GET', body?: unknown): Promise<T> {
  if (!isTauri()) throw new Error('Launch dicomqc as a native desktop application.');
  return invoke<T>('api_request', {path, method, body: body ?? null});
}
export const pick = (directory: boolean) => invoke<Input | null>('select_input', {directory});
export const readPolicy = (inputId: string) => invoke<string>('read_policy', {inputId});
export const savePolicyCopy = (text: string) => invoke<Input | null>('save_policy_copy', {text});
export const workspace = () => invoke<string>('workspace');
export const currentProject = () => invoke<ProjectResult>('current_project');
export const saveProject = (draft: ProjectDraft, saveAs = false) => invoke<ProjectResult | null>('save_project', {draft, saveAs});
export const openProject = () => invoke<ProjectResult | null>('open_project');
export const newProject = () => invoke<ProjectResult>('new_project');
export const report = (id: string, index: number) => invoke<string>('read_report', {id, index});
export const saveReport = (id: string, index: number) => invoke<boolean>('save_report', {id, index});
export const saveJobRecord = (id: string) => invoke<boolean>('save_job_record', {id});
export const reveal = (id: string) => invoke<void>('reveal_run', {id});
export const deleteRun = (id: string) => invoke<boolean>('delete_run', {id});
export const deleteRuns = () => invoke<string[]>('delete_runs');
export const openExternal = (url: string) => invoke<void>('open_external', {url});
export const renameRun = (id: string, name: string) => api<Job>(`/api/v1/jobs/${id}`, 'PATCH', {name});
export async function onDesktopMenu(handler: (action: string) => void): Promise<() => void> {
  if (!isTauri()) return () => {};
  return listen<string>('desktop-menu', event => handler(event.payload));
}
export async function syncMenu(state: {canRun: boolean; canCancel: boolean; canFindings: boolean; canReports: boolean; dirty: boolean}): Promise<void> {
  if (isTauri()) await invoke<void>('sync_menu', state);
}

export function auditLabel(job: Job): string {
  if (job.status !== 'completed') return job.status[0].toUpperCase() + job.status.slice(1);
  if (job.summary?.skipped_files) return 'Audit incomplete';
  return job.audit_exit_code === 2 ? 'Errors require attention' : job.audit_exit_code === 1 ? 'Warnings require review' : job.audit_exit_code === 0 ? 'Checks passed' : 'Audit completed';
}
