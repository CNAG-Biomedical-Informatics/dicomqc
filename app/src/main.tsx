import React, {lazy, Suspense, useEffect, useRef, useState} from 'react';
import {createRoot} from 'react-dom/client';
import {FolderOpen, FileText, FilePlus2, Plus, History, Settings, Play, X, Download, RefreshCw, Trash2, Search, PanelLeftClose, PanelLeftOpen, Pencil, FlaskConical, ChevronDown, Check, Ellipsis, BookOpen, Github, Clock3, LoaderCircle} from 'lucide-react';
import {api, auditLabel, currentProject, deleteRun, deleteRuns, newProject, onDesktopMenu, openExternal, openProject, pick, readPolicy, renameRun, report, reveal, saveJobRecord, savePolicyCopy, saveProject, saveReport, syncMenu} from './desktop';
import type {Input, Job, ProjectDraft, ProjectResult, Results} from './desktop';
import {artifactLabel, isExampleInput, isHtml, isMultiqcArtifact, isPreviewable, orderedArtifacts} from './reports';
import {ReportPreview} from './ReportPreview';
import './style.css';

const deletableStatuses = ['completed', 'failed', 'cancelled', 'interrupted'];
const PolicyEditor = lazy(() => import('./PolicyEditor').then(module => ({default: module.PolicyEditor})));
const logo = new URL('../../docs-site/static/img/dicomqc-symbol.png', import.meta.url).href;
const sourceLabels: Record<string, string> = {paths: 'DICOM inputs', source: 'Source folder', candidate: 'Candidate folder', manifest: 'Pairing manifest', policy: 'Project policy'};
const documentationUrl = 'https://cnag-biomedical-informatics.github.io/dicomqc/';
const githubUrl = 'https://github.com/CNAG-Biomedical-Informatics/dicomqc';
const policyTemplate = `version: 1
id: research-policy
rules:
  - id: no-patient-comments
    keyword: PatientComments
    check: absent_or_empty
`;
const exampleScenarios = [
  {id: 'scan', mode: 'scan', label: 'Privacy audit', description: 'Audit synthetic DICOM metadata containing common direct identifiers and privacy findings.'},
  {id: 'compare', mode: 'compare', label: 'Dataset comparison', description: 'Compare synthetic source and pseudonymized datasets for missing files and inconsistent subject linkage.'},
  {id: 'policy', mode: 'scan', label: 'Privacy audit + project policy', description: 'Apply a project-specific YAML policy to failing and corrected synthetic DICOM data.'},
  {id: 'uid', mode: 'scan', label: 'Privacy audit + UID checks', description: 'Check synthetic failing and corrected datasets for invalid or inconsistent DICOM UIDs.'},
  {id: 'vendor', mode: 'scan', label: 'Privacy audit + scanner inventory', description: 'Summarize synthetic scanner equipment, private creators, and private elements without exposing their values.'},
  {id: 'large', mode: 'scan', label: 'Large privacy audit', description: 'Generate a configurable metadata-only cohort with 250 deterministic privacy findings for pagination and review.'},
] as const;
const exampleLabel = (id: string | null) => exampleScenarios.find(value => value.id === id)?.label || id || 'Unknown';
const defaultRunName = (job: Job) => job.mode === 'demo' ? `Example · ${exampleLabel(job.example)}` : job.mode === 'scan' ? 'Privacy audit' : 'Dataset comparison';
const runName = (job: Job) => job.name || defaultRunName(job);
const runSignature = (jobs: Job[]) => JSON.stringify(jobs.map(job => [job.id, job.name, job.status, job.audit_exit_code, job.artifacts]).sort((a, b) => String(a[0]).localeCompare(String(b[0]))));
const runEventLabels: Record<string, string> = {
  queued: 'Audit queued', started: 'Audit started', 'synthetic demo': 'Preparing synthetic data',
  generation: 'Generating synthetic DICOM files', discovery: 'Discovering DICOM files',
  reading: 'Reading and evaluating metadata', relationships: 'Checking dataset relationships',
  reports: 'Writing reports', completed: 'Audit completed', failed: 'Audit failed',
  cancelled: 'Audit cancelled', interrupted: 'Audit interrupted',
};
const progressLabels: Record<string, string> = {
  'synthetic demo': 'Preparing synthetic data', generation: 'Generating synthetic DICOM files',
  discovery: 'Discovering DICOM files', reading: 'Reading and evaluating metadata',
  relationships: 'Checking dataset relationships', reports: 'Writing reports',
};
const duration = (seconds: number) => seconds < 60 ? `${Math.max(0, Math.floor(seconds))}s` : seconds < 3600 ? `${Math.floor(seconds / 60)}m ${Math.floor(seconds % 60)}s` : `${Math.floor(seconds / 3600)}h ${Math.floor((seconds % 3600) / 60)}m`;
const progressDetail = (job: Job) => {
  const elapsed = `Elapsed ${duration(Date.now() / 1000 - job.created)}`;
  if (job.status === 'queued') return `Waiting for the active audit · ${elapsed}`;
  if (!job.progress) return elapsed;
  const {completed, total} = job.progress;
  if (total) return `${completed.toLocaleString()} of ${total.toLocaleString()} (${Math.floor(completed * 100 / total)}%) · ${elapsed}`;
  if (completed) return `${completed.toLocaleString()} files processed · ${elapsed}`;
  return elapsed;
};
const timestamp = (seconds?: number) => seconds === undefined ? 'Not available' : new Date(seconds * 1000).toLocaleString();
const optionState = (value?: boolean) => value === undefined ? 'Not recorded' : value ? 'Enabled' : 'Off';

function JobLog({job, saving, onDownload}: {job: Job; saving: boolean; onDownload: () => void}) {
  const events = job.log || [];
  const started = events.find(entry => entry.event === 'started');
  const finished = [...events].reverse().find(entry => ['completed', 'failed', 'cancelled', 'interrupted'].includes(entry.event));
  const parameters = job.parameters;
  const scenario = exampleLabel(job.example);
  const elapsedFrom = started?.at ?? job.created;
  const elapsedTo = finished?.at ?? Date.now() / 1000;
  const processingSeconds = Math.max(0, elapsedTo - elapsedFrom);
  const filesRead = job.summary?.files_scanned ?? job.progress?.completed;
  const throughput = filesRead !== undefined && processingSeconds > 0 ? filesRead / processingSeconds : undefined;
  return <section className="run-log" aria-label="Run log">
    <div className="run-log-heading"><h2>Job record</h2><div><span>{auditLabel(job)}</span><button disabled={saving} onClick={onDownload}><Download size={15}/>{saving ? 'Saving...' : 'Download job record'}</button></div></div>
    <div className="run-log-groups">
      <section><h3>Parameters</h3><dl className="run-facts">
        <div><dt>Audit</dt><dd>{job.mode === 'demo' ? `Synthetic example · ${scenario}` : job.mode === 'scan' ? 'Privacy audit' : 'Dataset comparison'}</dd></div>
        {parameters && Object.entries(parameters.input_counts).map(([key, count]) => <div key={key}><dt>{sourceLabels[key] || key}</dt><dd>{count.toLocaleString()}</dd></div>)}
        {parameters?.example_files !== undefined && <div><dt>Synthetic files</dt><dd>{parameters.example_files.toLocaleString()}</dd></div>}
        {job.policy && <><div><dt>Policy ID</dt><dd>{job.policy.id}</dd></div><div><dt>Policy SHA-256</dt><dd><code>{job.policy.sha256}</code></dd></div></>}
        {(job.mode === 'scan' || job.mode === 'demo') && <><div><dt>UID checks</dt><dd>{optionState(parameters?.options.uid_checks)}</dd></div><div><dt>Scanner inventory</dt><dd>{optionState(parameters?.options.vendor_summary)}</dd></div><div><dt>MultiQC output</dt><dd>{optionState(parameters?.options.multiqc)}</dd></div></>}
      </dl></section>
      <section><h3>Timing</h3><dl className="run-facts">
        <div><dt>Submitted</dt><dd>{timestamp(job.created)}</dd></div>
        <div><dt>Started</dt><dd>{started ? timestamp(started.at) : job.status === 'queued' ? 'Waiting' : 'Not available'}</dd></div>
        <div><dt>Finished</dt><dd>{finished ? timestamp(finished.at) : ['queued', 'running'].includes(job.status) ? 'In progress' : 'Not available'}</dd></div>
        <div><dt>{finished ? 'Processing time' : 'Elapsed'}</dt><dd>{duration(elapsedTo - elapsedFrom)}</dd></div>
      </dl></section>
      <section><h3>Performance</h3><dl className="run-facts">
        <div><dt>Threads</dt><dd>{parameters?.options.threads ?? 'Not recorded'}</dd></div>
        <div><dt>Files read</dt><dd>{filesRead?.toLocaleString() ?? 'Not available'}</dd></div>
        <div><dt>Average throughput</dt><dd>{throughput === undefined ? 'Not available' : `${throughput.toLocaleString(undefined, {maximumFractionDigits: 1})} files/s`}</dd></div>
      </dl></section>
    </div>
    <div className="run-log-heading timeline-heading"><h2>Timeline</h2><span>{events.length} events</span></div>
    {events.length ? <ol>{events.map((entry, index) => {const date = new Date(entry.at * 1000); return <li key={`${entry.at}-${entry.event}-${index}`}><time dateTime={date.toISOString()} title={date.toLocaleString()}>{date.toLocaleTimeString()}</time><span>{runEventLabels[entry.event] || 'Audit event'}</span></li>;})}</ol> : <p className="empty-selection">No activity has been recorded for this run.</p>}
  </section>;
}
type Capabilities = {default_threads: number; max_threads: number; max_concurrent_jobs: number;
  large_demo: {default_files: number; min_files: number; max_files: number; step_files: number}};
const defaultLargeDemo = {default_files: 10_000, min_files: 1_000, max_files: 100_000, step_files: 1_000};
const projectSignature = (mode: string, inputs: Record<string, Input[]>, uid: boolean, vendor: boolean, multiqc: boolean, threads: number, output: string) => JSON.stringify({
  mode,
  inputs: Object.fromEntries(Object.entries(inputs).map(([key, values]) => [key, values.map(value => value.display_path || value.name)])),
  options: {uid_checks: uid, vendor_summary: vendor, multiqc, threads},
  output,
});

export function App() {
  const [page, setPage] = useState<'new' | 'policy' | 'runs' | 'settings'>('new');
  const [tab, setTab] = useState<'findings' | 'reports' | 'log'>('findings');
  const [runQuery, setRunQuery] = useState(''), [navigation, setNavigation] = useState(true);
  const [advanced, setAdvanced] = useState(false), [reportIndex, setReportIndex] = useState<number | null>(null);
  const [examplesOpen, setExamplesOpen] = useState(false);
  const [largeOpen, setLargeOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const [savingRecord, setSavingRecord] = useState(false);
  const savePending = useRef(false);
  const menuHandler = useRef<(action: string) => void>(() => {});
  const workspaceView = useRef<HTMLDivElement>(null);
  useEffect(() => {if (workspaceView.current) workspaceView.current.scrollTop = 0;}, [page, tab]);
  const [mode, setMode] = useState<'scan' | 'compare'>('scan');
  const [inputs, setInputs] = useState<Record<string, Input[]>>({});
  const [policyText, setPolicyText] = useState(''), [policySource, setPolicySource] = useState<string | null>(null);
  const [policyDirty, setPolicyDirty] = useState(false), policyRequest = useRef(0);
  const policyBaseline = useRef('');
  const [uid, setUid] = useState(false), [vendor, setVendor] = useState(false), [multiqc, setMultiqc] = useState(false);
  const [threads, setThreads] = useState(4);
  const [maxThreads, setMaxThreads] = useState(4);
  const [largeFiles, setLargeFiles] = useState(defaultLargeDemo.default_files);
  const [largeDemo, setLargeDemo] = useState(defaultLargeDemo);
  const [jobs, setJobs] = useState<Job[]>([]), [selected, setSelected] = useState<string | null>(null);
  const [savedRuns, setSavedRuns] = useState('[]');
  const [results, setResults] = useState<Results | null>(null), [offset, setOffset] = useState(0);
  const [preview, setPreview] = useState<string | null>(null), [previewError, setPreviewError] = useState(''), [error, setError] = useState('');
  const [busy, setBusy] = useState(false), [ready, setReady] = useState(false), [root, setRoot] = useState('');
  const [projectName, setProjectName] = useState('Untitled'), [projectPath, setProjectPath] = useState<string | null>(null), [savedSignature, setSavedSignature] = useState('');
  const [projectLoaded, setProjectLoaded] = useState(false);
  const [theme, setTheme] = useState(() => {
    try {const value = localStorage.getItem('dicomqc-theme'); return value === 'light' || value === 'dark' ? value : 'system';}
    catch {return 'system';}
  });
  const [connectionError, setConnectionError] = useState('');
  const [resultsError, setResultsError] = useState(false), [retry, setRetry] = useState(0);
  const [switching, setSwitching] = useState(false), [generation, setGeneration] = useState(0);
  const [cancelling, setCancelling] = useState<string | null>(null);
  const [deleting, setDeleting] = useState<string | null>(null);
  const [deletingAll, setDeletingAll] = useState(false);
  const [renaming, setRenaming] = useState<string | null>(null), [renameValue, setRenameValue] = useState('');
  const [runMenu, setRunMenu] = useState<string | null>(null);
  const [reportBusy, setReportBusy] = useState(false), [notice, setNotice] = useState('');
  const epoch = useRef(0), reportRequest = useRef(0), operation = useRef(false);
  const jobsVersion = useRef(0);
  const resultsRequest = useRef(0), selectedRef = useRef(selected);
  selectedRef.current = selected;
  const job = jobs.find(value => value.id === selected);
  const active = jobs.filter(value => ['queued', 'running'].includes(value.status)).length;
  const artifacts = orderedArtifacts(job?.artifacts || []);
  const multiqcArtifacts = (job?.artifacts || []).filter(isMultiqcArtifact);
  const selectedArtifact = reportIndex === null ? undefined : job?.artifacts[reportIndex];
  const visibleJobs = jobs.filter(value => `${runName(value)} ${value.id} ${auditLabel(value)} ${new Date(value.created * 1000).toLocaleString()}`.toLowerCase().includes(runQuery.toLowerCase().trim()));
  const signature = projectSignature(mode, inputs, uid, vendor, multiqc, threads, root);
  const projectDirty = Boolean(savedSignature) && signature !== savedSignature;
  const dirty = projectDirty || policyDirty || runSignature(jobs) !== savedRuns;
  const fail = (value: unknown) => setError(typeof value === 'string' ? value : value instanceof Error ? value.message : 'The operation could not be completed.');
  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    try {localStorage.setItem('dicomqc-theme', theme);} catch { /* Session preferences still work without storage. */ }
  }, [theme]);
  useEffect(() => {
    let alive = true, unlisten: (() => void) | undefined;
    onDesktopMenu(action => {if (alive) menuHandler.current(action);})
      .then(stop => {if (alive) unlisten = stop; else stop();})
      .catch(cause => {if (alive) fail(cause);});
    return () => {alive = false; unlisten?.();};
  }, []);
  useEffect(() => {
    let alive = true;
    Promise.all([currentProject(), api<Capabilities>('/api/v1/capabilities')])
      .then(([value, capabilities]) => {
        if (!alive) return;
        const limit = Math.max(1, capabilities.max_threads);
        setMaxThreads(limit);
        const cohort = capabilities.large_demo || defaultLargeDemo;
        setLargeDemo(cohort);
        setLargeFiles(cohort.default_files);
        applyProject(value, limit);
      })
      .catch(cause => {if (alive) {setProjectLoaded(true); fail(cause);}});
    return () => {alive = false;};
  }, []);
  useEffect(() => {
    let alive = true;
    let timer: ReturnType<typeof setTimeout>;
    const current = epoch.current;
    async function refresh() {
      const version = jobsVersion.current;
      try {
        const values = await api<Job[]>('/api/v1/jobs');
        if (alive && current === epoch.current) {if (version === jobsVersion.current) setJobs(values); setReady(true); setConnectionError('');}
      } catch {if (alive && current === epoch.current) {setReady(false); setConnectionError('Local engine unavailable. Reconnecting...');}}
      finally {if (alive) timer = setTimeout(refresh, 1200);}
    }
    if (!switching && projectLoaded) {
      void refresh();
    }
    return () => {alive = false; clearTimeout(timer);};
  }, [generation, switching, projectLoaded]);
  useEffect(() => {
    let alive = true;
    const current = epoch.current;
    const request = ++resultsRequest.current;
    setResults(null);
    setResultsError(false);
    if (!switching && job?.status === 'completed') api<Results>(`/api/v1/jobs/${job.id}/results?offset=${offset}&limit=100`)
      .then(value => {if (alive && current === epoch.current && request === resultsRequest.current) setResults(value);})
      .catch(() => {if (alive && current === epoch.current && request === resultsRequest.current) setResultsError(true);});
    return () => {alive = false;};
  }, [selected, job?.status, offset, retry, generation, switching]);
  useEffect(() => {
    if (page === 'runs' && tab === 'reports' && !switching && job?.status === 'completed') {
      const first = orderedArtifacts(job.artifacts)[0];
      if (first) selectArtifact(job.id, first.index, first.name);
    }
    return () => {reportRequest.current++;};
  }, [page, tab, selected, job?.status, generation, switching]);

  async function select(key: string, directory: boolean) {
    if (!ready || busy || switching) return;
    const current = epoch.current;
    try {
      const value = await pick(directory);
      if (value && current === epoch.current) setInputs(current => ({...current, [key]: key === 'paths' ? [...(current[key] || []).filter(input => value.display_path && input.display_path ? input.display_path !== value.display_path : input.id !== value.id), value] : [value]}));
    } catch (cause) {fail(cause);}
  }
  async function openPolicy(input?: Input, discardConfirmed = false) {
    if (policySource === input?.id && policyText || policyDirty && !input) {closePreview(); setPage('policy'); return;}
    if (input && policyDirty && !discardConfirmed && !window.confirm('Discard unsaved policy edits?')) return;
    closePreview(); setPage('policy'); setError('');
    if (!input || (policySource === input.id && policyText)) return;
    const request = ++policyRequest.current;
    setBusy(true);
    try {
      const text = await readPolicy(input.id);
      if (request === policyRequest.current) {
        policyBaseline.current = text;
        setPolicyText(text); setPolicySource(input.id); setPolicyDirty(false);
      }
    } catch (cause) {if (request === policyRequest.current) fail(cause);}
    finally {if (request === policyRequest.current) setBusy(false);}
  }
  async function choosePolicy() {
    if (!ready || busy || switching) return;
    if (policyDirty && !window.confirm('Discard unsaved policy edits?')) return;
    try {
      const input = await pick(false);
      if (!input) return;
      setInputs(current => ({...current, policy: [input]}));
      setPolicyText(''); setPolicySource(null); setPolicyDirty(false);
      await openPolicy(input, true);
    } catch (cause) {fail(cause);}
  }
  function createPolicy() {
    if (policyDirty && !window.confirm('Discard unsaved policy edits?')) return;
    policyRequest.current++; closePreview();
    setInputs(current => ({...current, policy: []}));
    policyBaseline.current = policyTemplate;
    setPolicyText(policyTemplate); setPolicySource(null); setPolicyDirty(true); setPage('policy');
  }
  function resetPolicy() {
    if (!window.confirm('Discard policy edits and restore the loaded YAML or starter template?')) return;
    setPolicyText(policyBaseline.current);
    setPolicyDirty(!policySource);
  }
  function removePolicy() {
    if (busy || switching) return;
    if (policyDirty && !window.confirm('Discard unsaved edits and remove the project policy?')) return;
    policyRequest.current++;
    policyBaseline.current = '';
    setInputs(current => ({...current, policy: []}));
    setPolicyText(''); setPolicySource(null); setPolicyDirty(false);
    setError(''); setPage('new');
  }
  async function validatePolicy(text: string) {
    return api<{id: string; sha256: string; rules: number}>('/api/v1/policies/validate', 'POST', {text});
  }
  async function saveEditedPolicy(text: string) {
    const input = await savePolicyCopy(text);
    if (!input) return null;
    setInputs(current => ({...current, policy: [input]}));
    policyBaseline.current = text;
    setPolicySource(input.id); setPolicyDirty(false);
    return input.name;
  }
  async function submit(example?: string) {
    if (operation.current || !ready || policyDirty || (!example && !valid)) return;
    operation.current = true;
    setBusy(true); setError('');
    try {
      const value = await api<Job>('/api/v1/jobs', 'POST', example ? {mode: 'demo', example, options: {multiqc, threads},
        ...(example === 'large' ? {example_files: largeFiles} : {})} : {
        mode, inputs: Object.fromEntries(Object.entries(inputs).filter(([key]) =>
          key === 'policy' || (mode === 'scan' ? key === 'paths' : ['source', 'candidate', 'manifest'].includes(key)))
          .map(([key, values]) => [key, values.map(value => value.id)])),
        options: mode === 'scan' ? {uid_checks: uid, vendor_summary: vendor, multiqc, threads} : {threads},
      });
      jobsVersion.current++; setJobs(current => [value, ...current.filter(job => job.id !== value.id)]); setSelected(value.id); setOffset(0); closePreview(); setRunQuery(''); setTab('findings'); setPage('runs');
    } catch (cause) {fail(cause);} finally {setBusy(false); operation.current = false;}
  }
  function closePreview() {reportRequest.current++; setPreview(null); setPreviewError(''); setReportIndex(null); setReportBusy(false); setNotice('');}
  function selectArtifact(id: string, index: number, name: string) {
    closePreview(); setReportIndex(index);
    if (isPreviewable(name)) void openReport(id, index);
  }
  function showTab(value: 'setup' | 'policy' | 'findings' | 'reports' | 'log') {
    if (value === 'policy') {void openPolicy(inputs.policy?.[0]); return;}
    if ((value === 'findings' && !job) || (value === 'reports' && job?.status !== 'completed')) return;
    if ((value === 'setup' && page === 'new') || (page === 'runs' && tab === value)) return;
    closePreview(); setPage(value === 'setup' ? 'new' : 'runs');
    if (value === 'findings' || value === 'reports' || value === 'log') setTab(value);
  }
  function openRun(value: Job) {
    closePreview(); setRunMenu(null); setSelected(value.id); setOffset(0); setTab('findings'); setPage('runs');
  }
  async function exportReport(id: string, index: number) {
    if (savePending.current) return;
    savePending.current = true; setSaving(true); setError('');
    const current = reportRequest.current;
    try {const saved = await saveReport(id, index); if (current === reportRequest.current) setNotice(saved ? 'Report copy saved.' : '');}
    catch (cause) {if (current === reportRequest.current) fail(cause);}
    finally {savePending.current = false; setSaving(false);}
  }
  async function exportJobRecord(id: string) {
    if (savingRecord) return;
    setSavingRecord(true); setError(''); setNotice('');
    try {const saved = await saveJobRecord(id); setNotice(saved ? 'Job record saved.' : '');}
    catch (cause) {fail(cause);}
    finally {setSavingRecord(false);}
  }
  async function openReport(id: string, index: number) {
    const request = ++reportRequest.current;
    setReportBusy(true); setPreview(null); setPreviewError(''); setError('');
    try {const html = await report(id, index); if (request === reportRequest.current) setPreview(html);}
    catch (cause) {if (request === reportRequest.current) setPreviewError(typeof cause === 'string' ? cause : cause instanceof Error ? cause.message : 'Report preview unavailable.');}
    finally {if (request === reportRequest.current) setReportBusy(false);}
  }
  async function cancelRun(id: string) {
    if (cancelling) return;
    setCancelling(id); setError('');
    try {const value = await api<Job>(`/api/v1/jobs/${id}/cancel`, 'POST'); jobsVersion.current++; setJobs(current => current.map(job => job.id === id ? value : job));}
    catch (cause) {fail(cause);} finally {setCancelling(null);}
  }
  function projectDraft(): ProjectDraft {
    return {
      mode,
      inputs: Object.fromEntries(Object.entries(inputs).map(([key, values]) => [key, values.map(value => value.id)])),
      options: {uid_checks: uid, vendor_summary: vendor, multiqc, threads},
    };
  }
  function applyProject(value: ProjectResult, threadLimit = maxThreads) {
    const restored = value.project.inputs || {};
    const projectThreads = Math.max(1, Math.min(value.project.options.threads, threadLimit));
    epoch.current++; policyRequest.current++; closePreview(); jobsVersion.current++;
    setPolicyText(''); setPolicySource(null); setPolicyDirty(false);
    setMode(value.project.mode); setInputs(restored);
    setUid(value.project.options.uid_checks); setVendor(value.project.options.vendor_summary); setMultiqc(value.project.options.multiqc); setThreads(projectThreads);
    setRoot(value.output); setProjectPath(value.projectPath); setProjectName(value.name); setJobs([]); setSelected(null); setResults(null); setOffset(0); setRunQuery(''); setPage('new');
    setSavedSignature(projectSignature(value.project.mode, restored, value.project.options.uid_checks, value.project.options.vendor_summary, value.project.options.multiqc, projectThreads, value.output));
    setProjectLoaded(true);
    setSavedRuns(runSignature(value.savedJobs || []));
    setNotice(value.missing.length ? `${value.missing.length} saved input ${value.missing.length === 1 ? 'path is' : 'paths are'} unavailable. Select the missing input again before running an audit.` : '');
    setGeneration(current => current + 1);
  }
  async function persistProject(saveAs = false) {
    if (operation.current || !ready) return;
    if (active) {setError('Finish or cancel active audits before saving the project.'); return;}
    if (policyDirty) {setPage('policy'); setError('Save the edited policy as YAML before saving the project.'); return;}
    operation.current = true; setSwitching(true); setError('');
    try {
      const currentSignature = signature;
      const value = await saveProject(projectDraft(), saveAs);
      if (value) {
        setProjectPath(value.projectPath); setProjectName(value.name); setSavedSignature(currentSignature); setNotice('Project saved.');
        setSavedRuns(runSignature(value.savedJobs || jobs));
      }
    } catch (cause) {fail(cause);}
    finally {operation.current = false; setSwitching(false);}
  }
  async function replaceProject(action: 'new' | 'open') {
    if (operation.current || active || !ready) return;
    if (dirty && !window.confirm('Discard unsaved project changes?')) return;
    operation.current = true; setSwitching(true); setError('');
    try {
      const value = action === 'new' ? await newProject() : await openProject();
      if (value) applyProject(value);
    } catch (cause) {fail(cause);}
    finally {operation.current = false; setSwitching(false);}
  }
  async function removeRun(value: Job) {
    if (operation.current || !ready || !deletableStatuses.includes(value.status)) return;
    operation.current = true; setBusy(true); setDeleting(value.id); setError('');
    try {
      if (await deleteRun(value.id)) {
        // A poll started before deletion must not restore its old history snapshot.
        jobsVersion.current++;
        setJobs(current => current.filter(job => job.id !== value.id));
        if (selectedRef.current === value.id) {
          resultsRequest.current++; setSelected(null); setResults(null); setResultsError(false); setOffset(0); closePreview();
        }
      }
    } catch (cause) {fail(cause);}
    finally {operation.current = false; setBusy(false); setDeleting(null);}
  }
  async function removeAllRuns() {
    if (operation.current || !ready || !jobs.some(value => deletableStatuses.includes(value.status))) return;
    operation.current = true; setBusy(true); setDeletingAll(true); setError('');
    try {
      const removed = new Set(await deleteRuns());
      if (removed.size) {
        jobsVersion.current++;
        setJobs(current => current.filter(value => !removed.has(value.id)));
        if (selectedRef.current && removed.has(selectedRef.current)) {
          resultsRequest.current++; setSelected(null); setResults(null); setResultsError(false); setOffset(0); closePreview();
        }
      }
    } catch (cause) {fail(cause);}
    finally {operation.current = false; setBusy(false); setDeletingAll(false);}
  }
  async function commitRename(value: Job) {
    if (operation.current || !ready) return;
    operation.current = true; setError('');
    try {
      const updated = await renameRun(value.id, renameValue);
      jobsVersion.current++; setJobs(current => current.map(item => item.id === value.id ? updated : item)); setRenaming(null); setRenameValue('');
    } catch (cause) {fail(cause);}
    finally {operation.current = false;}
  }
  function inputList(key: string) {
    return <ul className="selections">{(inputs[key] || []).map((value, index) => <li key={value.id}>
      {value.kind === 'directory' ? <FolderOpen size={16}/> : <FileText size={16}/>}
      <span title={value.display_path || value.name}>{value.display_path || value.name}</span>
      <button className="icon" title={`Remove ${value.name}`} aria-label={`Remove ${value.name}`} disabled={busy || switching} onClick={() => {
        if (key === 'policy') {removePolicy(); return;}
        setInputs(current => ({...current, [key]: current[key].filter((_, position) => position !== index)}));
      }}><X size={16}/></button>
    </li>)}</ul>;
  }
  const valid = mode === 'scan' ? Boolean(inputs.paths?.length) : ['source', 'candidate', 'manifest'].every(key => inputs[key]?.length);
  const canRun = valid && ready && !busy && !switching && !policyDirty;
  const canFindings = Boolean(job) && !switching;
  const canReports = job?.status === 'completed' && !switching;
  const canCancel = Boolean(job && ['queued', 'running'].includes(job.status) && ready && !switching && !cancelling);
  useEffect(() => {
    let alive = true;
    syncMenu({canRun, canCancel, canFindings, canReports, dirty}).catch(cause => {if (alive) fail(cause);});
    return () => {alive = false;};
  }, [canRun, canCancel, canFindings, canReports, dirty]);
  const selectedCount = (mode === 'scan' ? inputs.paths?.length || 0 : ['source', 'candidate', 'manifest'].filter(key => inputs[key]?.length).length);
  const tabId = page === 'new' ? 'setup' : page === 'policy' ? 'policy' : page === 'runs' ? tab : null;
  menuHandler.current = action => {
    if (action === 'new-project') void replaceProject('new');
    else if (action === 'open-project') void replaceProject('open');
    else if (action === 'save-project') void persistProject(false);
    else if (action === 'save-project-as') void persistProject(true);
    else if (action === 'new-audit' || action === 'setup') showTab('setup');
    else if (action === 'findings' || action === 'reports' || action === 'log' || action === 'policy') showTab(action);
    else if (action === 'cancel-audit' && canCancel && job) void cancelRun(job.id);
    else if (action === 'report-issue') void openExternal(`${githubUrl}/issues/new`).catch(fail);
    else if (action === 'settings') {closePreview(); setPage('settings');}
    else if (action === 'run-audit') void submit();
    else if ((action === 'add-file' || action === 'add-folder') && ready && !busy && !switching) {
      setMode('scan'); showTab('setup'); void select('paths', action === 'add-folder');
    }
  };
  return <div className="desktop-shell">
    <header className="titlebar"><img src={logo} alt=""/><strong>dicomqc</strong><span>{projectName}{dirty ? ' *' : ''}</span><span className="local-badge">Local project</span></header>
    <div className="toolbar" role="toolbar" aria-label="Workspace actions">
      <button className="icon" aria-label={navigation ? 'Hide navigation' : 'Show navigation'} title={navigation ? 'Hide navigation' : 'Show navigation'} aria-expanded={navigation} aria-controls="workspace-navigation" onClick={() => setNavigation(value => !value)}>{navigation ? <PanelLeftClose size={18}/> : <PanelLeftOpen size={18}/>}</button>
      <button onClick={() => showTab('setup')}><Plus size={17}/>New audit</button>
      <span className="toolbar-context">{page === 'runs' && job ? <>{runName(job)} <small>{job.id.slice(0, 8)}</small></> : mode === 'scan' ? 'Scan a dataset' : 'Compare datasets'}</span>
    </div>
    <div className={`desktop-body ${navigation ? '' : 'navigation-hidden'}`}>
      {navigation && <aside className="workspace-tree" id="workspace-navigation" aria-label="Workspace navigation">
        <div className="tree-scroll">
          <section className="source-tree" aria-label="Selected sources"><h2>Sources</h2>
            {!Object.values(inputs).some(values => values.length) && <p className="tree-empty">No sources selected</p>}
            {Object.entries(inputs).filter(([, values]) => values.length).map(([key, values]) => <div className="source-group" key={key}><h3>{sourceLabels[key]}</h3>{values.map(value =>
              <button className="tree-source" key={value.id} aria-label={`Edit ${sourceLabels[key]}: ${value.name}`} title={value.display_path || value.name} onClick={() => {
                if (key !== 'policy') setMode(key === 'paths' ? 'scan' : 'compare');
                if (key === 'policy') void openPolicy(value);
                else showTab('setup');
              }}>{value.kind === 'directory' ? <FolderOpen size={15}/> : <FileText size={15}/>}<span>{value.name}{value.display_path && <small>{value.display_path}</small>}</span></button>
            )}</div>)}
          </section>
          <section className="history-tree" aria-label="Run history">
            <div className="history-heading"><h2><button className="tree-heading" onClick={() => showTab('findings')}><History size={15}/>Runs <span>{jobs.length}</span></button></h2><button className="icon delete-runs" aria-label="Delete all runs" title="Delete all inactive runs" aria-busy={deletingAll} disabled={!ready || busy || switching || !jobs.some(value => deletableStatuses.includes(value.status))} onClick={() => void removeAllRuns()}><Trash2 size={15}/></button></div>
            <label className="run-search"><Search size={15}/><input aria-label="Find runs" placeholder="Find a run..." value={runQuery} onChange={event => setRunQuery(event.target.value)}/></label>
            <p className="queue-count">{jobs.filter(value => value.status === 'running').length} running · {jobs.filter(value => value.status === 'queued').length} queued</p>
            {!jobs.length && <p className="tree-empty">{ready ? 'No audits yet' : 'Waiting for run history'}</p>}
            {jobs.length > 0 && !visibleJobs.length && <p className="tree-empty">No matching runs</p>}
            <div className="run-list" aria-label="Audit runs">{visibleJobs.map(value => <div className={`run-entry ${selected === value.id ? 'selected' : ''}`} key={value.id}>
              {renaming === value.id ? <form className="sidebar-rename" onSubmit={event => {event.preventDefault(); void commitRename(value);}}>
                <input autoFocus aria-label="Run name" maxLength={80} value={renameValue} onChange={event => setRenameValue(event.target.value)} onKeyDown={event => {if (event.key === 'Escape') {setRenaming(null); setRenameValue('');}}}/>
                <button className="icon" type="submit" aria-label="Save run name" title="Save run name" disabled={!renameValue.trim()}><Check size={15}/></button>
                <button className="icon" type="button" aria-label="Cancel renaming" title="Cancel renaming" onClick={() => {setRenaming(null); setRenameValue('');}}><X size={15}/></button>
              </form> : <><button className="run-select" aria-pressed={selected === value.id} onClick={() => openRun(value)}>
                <strong>{runName(value)}</strong><span className={`run-state ${value.status}`}>{auditLabel(value)}</span>
                <small>{new Date(value.created * 1000).toLocaleString()} · {value.id.slice(0, 8)}</small>
              </button><div className="run-menu-shell" onBlur={event => {if (!event.currentTarget.contains(event.relatedTarget as Node | null)) setRunMenu(null);}}><button className="icon run-menu-trigger" aria-label={`More actions for ${runName(value)}`} title="Run actions" aria-expanded={runMenu === value.id} aria-haspopup="menu" onClick={() => setRunMenu(current => current === value.id ? null : value.id)}><Ellipsis size={17}/></button>
                {runMenu === value.id && <div className="run-context-menu" role="menu"><button role="menuitem" onClick={() => {setRunMenu(null); setRenaming(value.id); setRenameValue(runName(value));}}><Pencil size={15}/>Rename</button>{deletableStatuses.includes(value.status) && <button className="delete-action" role="menuitem" aria-busy={deleting === value.id} disabled={!ready || busy || switching} onClick={() => void removeRun(value)}><Trash2 size={15}/>{deleting === value.id ? 'Deleting...' : 'Delete'}</button>}</div>}
              </div></>}
            </div>)}</div>
          </section>
        </div>
        <nav className="workspace-nav" aria-label="Application">
          <button aria-pressed={page === 'settings'} onClick={() => {closePreview(); setPage('settings');}}><Settings size={16}/>Settings</button>
          <a href={documentationUrl} onClick={event => {event.preventDefault(); void openExternal(event.currentTarget.href).catch(fail);}}><BookOpen size={16}/>Documentation</a>
          <a href={githubUrl} onClick={event => {event.preventDefault(); void openExternal(event.currentTarget.href).catch(fail);}}><Github size={16}/>GitHub</a>
        </nav>
      </aside>}
      <main className="desktop-content">
        <div className="workspace-tabs" role="tablist" aria-label="Workspace views">{(['setup', 'policy', 'findings', 'reports', 'log'] as const).map((value, index, all) =>
          <button key={value} id={`tab-${value}`} role="tab" disabled={value === 'findings' || value === 'log' ? !canFindings : value === 'reports' ? !canReports : false} aria-selected={tabId === value} aria-controls="workspace-panel" tabIndex={tabId === value || (!tabId && index === 0) ? 0 : -1} onClick={() => showTab(value)} onKeyDown={event => {
            const next = event.key === 'ArrowRight' ? (index + 1) % all.length : event.key === 'ArrowLeft' ? (index + all.length - 1) % all.length : event.key === 'Home' ? 0 : event.key === 'End' ? all.length - 1 : -1;
            if (next >= 0) {event.preventDefault(); let target = next; for (let count = 0; count < all.length; count++) {const button = document.getElementById(`tab-${all[target]}`) as HTMLButtonElement; if (!button.disabled) {showTab(all[target]); button.focus(); break;} target = (target + (event.key === 'ArrowLeft' || event.key === 'End' ? all.length - 1 : 1)) % all.length;}}
          }}>{value[0].toUpperCase() + value.slice(1)}{value === 'policy' && policyDirty ? <span aria-hidden="true"> *</span> : null}</button>
        )}</div>
        {error && <div className="error" role="alert"><span>{error}</span><button className="icon" aria-label="Dismiss error" title="Dismiss error" onClick={() => setError('')}><X size={16}/></button></div>}
        {connectionError && <div className="error" role="status">{connectionError}</div>}
        {notice && <p className="notice" role="status">{notice}</p>}
        <div className="workspace-view" ref={workspaceView} id="workspace-panel" role={tabId ? 'tabpanel' : 'region'} aria-labelledby={tabId ? `tab-${tabId}` : 'settings-heading'}>
          {page === 'new' && <div className="setup-pane">
            <div className="pane-heading"><h1>Audit setup</h1></div>
            <div className="mode-tabs audit-mode-selector" role="group" aria-label="Audit mode">
              <button aria-pressed={mode === 'scan'} onClick={() => {setMode('scan'); setLargeOpen(false);}}><FileText size={19}/><span><strong>Privacy audit</strong><small>DICOM dataset</small></span></button>
              <button aria-pressed={mode === 'compare'} onClick={() => {setMode('compare'); setLargeOpen(false);}}><FolderOpen size={19}/><span><strong>Dataset comparison</strong><small>Source and candidate datasets</small></span></button>
            </div>
            <section className="setup-section"><div className="setup-section-heading"><h2>{mode === 'scan' ? 'DICOM inputs' : 'Paired datasets'}</h2><button className="example-trigger" aria-expanded={examplesOpen} aria-controls="example-data-scenarios" onClick={() => setExamplesOpen(value => !value)}><FlaskConical size={16}/>Load example data<ChevronDown className={examplesOpen ? 'expanded' : ''} size={15}/></button></div>
              {examplesOpen && <div className="example-options" id="example-data-scenarios" role="group" aria-label="Example data scenarios">
                <div><strong>Separate example runs</strong><small>Each selection starts one independent {mode === 'scan' ? 'audit' : 'comparison'} using automated test fixtures</small></div>
                <div className="scenario-controls">{(mode === 'scan' ? [['scan', 'large'], ['policy', 'uid', 'vendor']] : [['compare']]).map((ids, group) => <div className="scenario-group" key={group}>{group === 1 && <small>Privacy audit with additional checks or inventory</small>}<div className="scenario-buttons">{exampleScenarios.filter(example => ids.includes(example.id)).map(example =>
                  <button className={`scenario-option ${example.id === 'scan' || example.id === 'compare' ? 'audit-action' : ''}`} key={example.id} aria-label={example.label} aria-describedby={`example-${example.id}-description`} aria-expanded={example.id === 'large' ? largeOpen : undefined} aria-controls={example.id === 'large' ? 'large-cohort-settings' : undefined} disabled={!ready || busy} onClick={() => {if (example.id === 'large') setLargeOpen(value => !value); else {setLargeOpen(false); void submit(example.id);}}}>{example.id !== 'large' && <Play size={13}/>}<span>{example.label}</span><span className="scenario-tooltip" id={`example-${example.id}-description`} role="tooltip">{example.description}</span></button>
                )}</div></div>)}{largeOpen && <div className="large-cohort-settings" id="large-cohort-settings"><label className="large-cohort-size"><span>Large cohort size <output>{largeFiles.toLocaleString()} files</output></span><input aria-label="Large cohort files" type="range" min={largeDemo.min_files} max={largeDemo.max_files} step={largeDemo.step_files} value={largeFiles} onChange={event => setLargeFiles(Number(event.target.value))}/></label><button className="audit-action" disabled={!ready || busy} onClick={() => submit('large')}><Play size={14}/>Run large cohort</button></div>}</div>
              </div>}
              {mode === 'scan' ? <><div className="actions"><button className="recommended-input" title="Scan all DICOM files in a folder and its subfolders" disabled={!ready || busy || switching} onClick={() => select('paths', true)}><FolderOpen size={16}/>Choose DICOM folder</button><button title="Add one DICOM file for an individual check" disabled={!ready || busy || switching} onClick={() => select('paths', false)}><FileText size={16}/>Add single DICOM file</button></div>{!inputs.paths?.length && <p className="empty-selection">No DICOM data selected</p>}{inputList('paths')}</> :
                <div className="input-grid">{[['source', 'Source folder', true], ['candidate', 'Candidate folder', true], ['manifest', 'Pairing manifest · CSV', false]].map(([key, label, directory]) => <div className="input-row" key={String(key)}><div><strong>{label}</strong>{!inputs[String(key)]?.length && <small>Not selected</small>}{inputList(String(key))}</div><button aria-label={`Choose ${label}`} disabled={!ready || busy || switching} onClick={() => select(String(key), Boolean(directory))}><FolderOpen size={16}/>Choose</button></div>)}</div>}
            </section>
<details className="advanced-setup" open={mode === 'compare' || advanced} onToggle={event => {if (mode === 'scan') setAdvanced(event.currentTarget.open);}}>
              <summary hidden={mode !== 'scan'}>Advanced setup{(inputs.policy?.length || policyDirty || uid || vendor) ? <span className="advanced-active">Configured</span> : null}</summary>
            <section className="setup-section policy-setup"><div className="setup-section-heading"><div><h2>Project policy <span>Optional</span></h2><p>Add project-specific metadata requirements to the built-in privacy checks.</p></div><div className="actions"><button disabled={!ready || busy || switching} onClick={createPolicy}><FilePlus2 size={16}/>New policy</button><button disabled={!ready || busy || switching} onClick={() => void choosePolicy()}><FileText size={16}/>Choose YAML</button>{inputs.policy?.[0] && <button onClick={() => void openPolicy(inputs.policy[0])}><Pencil size={16}/>Edit policy</button>}{(inputs.policy?.length || policyDirty) ? <button disabled={busy || switching} title="Continue without a project policy; saved YAML files are kept" onClick={removePolicy}><X size={16}/>Remove policy</button> : null}</div></div>{inputList('policy')}</section>
            <section className="setup-section"><h2>Checks and outputs</h2><div className="setup-summary"><span>{mode === 'scan' ? 'Core audit' : 'Workflow'} <strong>{mode === 'scan' ? 'Privacy metadata' : 'Dataset comparison'}</strong></span><span>Reports <strong>HTML · JSON · CSV{mode === 'scan' && multiqc ? ' · MultiQC' : ''}</strong></span><span>Processing <strong>{threads} {threads === 1 ? 'thread' : 'threads'} · one active audit</strong></span></div>
              {mode === 'scan' && <div className="advanced">
                {mode === 'scan' && <><label className="check"><input type="checkbox" checked={uid} onChange={event => setUid(event.target.checked)}/><span>Check UID syntax and relationships</span></label>
                  <label className="check"><input type="checkbox" checked={vendor} onChange={event => setVendor(event.target.checked)}/><span>Include scanner and private-creator inventory</span></label>
                  {vendor && <p className="privacy-warning">This exports observed labels that may identify people or sites. Review reports before sharing.</p>}</>}
              </div>}
            </section>
            </details>
          </div>}
          {page === 'policy' && ((policyText || policyDirty || policySource) ? <Suspense fallback={<p className="policy-pane" role="status">Loading policy editor...</p>}><PolicyEditor value={policyText} filename={inputs.policy?.[0]?.name} dirty={policyDirty} onChange={value => {setPolicyText(value); setPolicyDirty(true);}} onValidate={validatePolicy} onSave={saveEditedPolicy} onReset={resetPolicy} onRemove={removePolicy}/></Suspense> : <div className="policy-pane empty-policy"><FileText size={30}/><h1>Project policy</h1><p>Create a policy or open an existing YAML file to edit and validate it.</p><div className="actions"><button className="primary" disabled={!ready || busy || switching} onClick={createPolicy}><FilePlus2 size={16}/>New policy</button><button disabled={!ready || busy || switching} onClick={() => void choosePolicy()}><FolderOpen size={16}/>Open YAML</button></div></div>)}
          {page === 'runs' && <div className={`run-pane ${tab === 'reports' ? 'reports-pane' : ''}`}>
            {!job ? <div className="empty"><History size={28}/><h1>{tab === 'reports' ? 'Reports' : tab === 'log' ? 'Log' : 'Findings'}</h1><p>Select a run from history.</p></div> : <>
              <div className="pane-heading result-heading"><div><h1>{auditLabel(job)}</h1><p className="run-identity">{runName(job)} · {new Date(job.created * 1000).toLocaleString()} · {job.id.slice(0, 8)}</p></div>
                <div className="actions">
                  {job.status === 'completed' && <button title="Open run folder" aria-label="Open run folder" onClick={() => reveal(job.id).catch(fail)}><FolderOpen size={16}/><span>Open run folder</span></button>}
                  {['queued', 'running'].includes(job.status) && <button disabled={!ready || cancelling === job.id} onClick={() => cancelRun(job.id)}><X size={16}/>{cancelling === job.id ? 'Cancelling...' : 'Cancel audit'}</button>}
                </div>
              </div>
              {tab === 'findings' && job.summary && <div className="metrics" aria-label="Audit summary"><span><strong>{job.summary.files_scanned}</strong> files read</span><span className="error-count"><strong>{job.summary.errors}</strong> errors</span><span className="warning-count"><strong>{job.summary.warnings}</strong> warnings</span><span className={job.summary.skipped_files ? 'warning-count' : ''}><strong>{job.summary.skipped_files}</strong> skipped files</span></div>}
              {job.mode === 'demo' && <p className="demo-context">Synthetic example{tab === 'findings' && job.artifacts.some(name => /(^|\/)before\.json$/i.test(name)) ? ' · Findings: before correction' : ''}</p>}
              {['queued', 'running'].includes(job.status) && <div className="progress"><p className="progress-status" role="status"><strong>{job.status === 'queued' ? <Clock3 size={16} aria-hidden="true"/> : !job.progress?.total ? <LoaderCircle className="progress-spinner" size={16} aria-label="Audit running"/> : null}{job.status === 'queued' ? 'Audit queued' : job.progress ? progressLabels[job.progress.phase] || 'Audit in progress' : 'Starting audit'}</strong><span>{progressDetail(job)}</span></p>{job.status === 'running' && job.progress?.total ? <progress aria-label="Audit progress" max={job.progress.total} value={Math.min(job.progress.completed, job.progress.total)}/> : null}</div>}
              {job.message && <p className="run-message">{job.message}</p>}
              {tab === 'log' && <JobLog job={job} saving={savingRecord} onDownload={() => void exportJobRecord(job.id)}/>}
              {job.status !== 'completed' && tab === 'reports' && <p className="empty-selection">No completed reports available.</p>}
              {job.status === 'completed' && tab === 'findings' && <>
                {results ? <>
                  <div className="findings-heading"><h2>{results.total_findings ? 'Findings to review' : 'No findings recorded'}</h2><span>{results.total_findings} findings</span></div>
                  {!!job.summary?.skipped_files && <p className="privacy-warning">Some files could not be checked. Review audit coverage before sharing data.</p>}
                  {!results.total_findings && !job.summary?.skipped_files && <p>No findings in the checked metadata. Complete the remaining privacy review before sharing data.</p>}
                  {Array.from(new Set(results.findings.map(f => JSON.stringify([f.rule_id, f.severity, f.message, f.recommendation])))).map(key => {
                    const group = results.findings.filter(f => JSON.stringify([f.rule_id, f.severity, f.message, f.recommendation]) === key);
                    return <details className="finding" key={key}><summary><span className={`severity ${group[0].severity}`}>{group[0].severity}</span><span>{group[0].message}</span><small>{group.length} on this page</small></summary><div className="finding-content"><p>{group[0].recommendation}</p><ul>{group.map((f, i) => <li key={i}><code>{f.path}</code> · {f.keyword}</li>)}</ul></div></details>;
                  })}
                  {results.total_findings > 100 && <div className="pagination"><button disabled={!offset} onClick={() => setOffset(value => Math.max(0, value - 100))}>Previous</button><span>{offset + 1}–{Math.min(offset + 100, results.total_findings)} of {results.total_findings}</span><button disabled={offset + 100 >= results.total_findings} onClick={() => setOffset(value => value + 100)}>Next</button></div>}
                </> : resultsError ? <div role="alert"><p>Findings could not be loaded.</p><button onClick={() => setRetry(value => value + 1)}><RefreshCw size={16}/>Retry findings</button></div> : <p role="status">Loading findings...</p>}
              </>}
              {job.status === 'completed' && tab === 'reports' && <div className="report-workspace">
                <div className="report-files" aria-label="Report files">{[false, true].map(exampleInput => {
                  const items = artifacts.filter(({name}) => isExampleInput(name) === exampleInput);
                  return items.length > 0 && <React.Fragment key={String(exampleInput)}><h2>{exampleInput ? 'Example inputs' : 'Reports'} <span>{items.length}</span></h2>{items.map(({name, index}) =>
                  <button key={name} aria-label={`Select report ${name}`} aria-pressed={reportIndex === index} onClick={() => selectArtifact(job.id, index, name)}><FileText size={16}/><span><strong>{isMultiqcArtifact(name) ? 'MultiQC' : name.split('/').pop()}</strong><small>{isMultiqcArtifact(name) ? `Custom content preview · ${multiqcArtifacts.length} supporting files` : artifactLabel(name)}</small>{!isMultiqcArtifact(name) && <small className="artifact-path">{name.includes('/') ? name.slice(0, name.lastIndexOf('/')) : ''}</small>}</span></button>
                )}</React.Fragment>;
                })}</div>
                <section className="report-preview" aria-label="Selected report">
                  {selectedArtifact !== undefined && reportIndex !== null ? <>
                    <div className="preview-toolbar"><div><strong>{artifactLabel(selectedArtifact)}</strong><small>{selectedArtifact}</small></div><button disabled={saving || busy || switching} aria-label={`Save ${selectedArtifact}`} onClick={() => exportReport(job.id, reportIndex)}><Download size={16}/>{saving ? 'Saving...' : 'Save copy'}</button></div>
                    {reportBusy ? <p className="preview-state" role="status">Loading report...</p> : preview !== null ? isHtml(selectedArtifact) ? <iframe title={isMultiqcArtifact(selectedArtifact) ? 'MultiQC report preview' : 'Audit report preview'} sandbox="" referrerPolicy="no-referrer" srcDoc={preview}/> : <ReportPreview name={selectedArtifact} text={preview}/> : <div className="preview-state"><p role="alert">{previewError || 'Report preview unavailable.'}</p><button onClick={() => openReport(job.id, reportIndex)}><RefreshCw size={16}/>Retry preview</button></div>}
                  </> : <p className="preview-state">No reports available.</p>}
                </section>
              </div>}
            </>}
          </div>}
          {page === 'settings' && <div className="settings-pane"><h1 id="settings-heading">Settings</h1><section className="setup-section"><h2>Appearance</h2><label className="setting">Theme<select value={theme} onChange={event => setTheme(event.target.value)}><option value="system">System</option><option value="light">Light</option><option value="dark">Dark</option></select></label></section>
            <section className="setup-section"><h2>Processing</h2><label className="setting">Metadata threads<input aria-label="Metadata threads" type="number" min="1" max={maxThreads} step="1" value={threads} onChange={event => setThreads(Math.max(1, Math.min(maxThreads, Number(event.target.value) || 1)))}/></label><p>One audit runs at a time. Threads divide independent DICOM files or comparison pairs into bounded batches; additional audits wait in the queue.</p><p>{maxThreads} logical processors are available to dicomqc on this computer.</p></section>
            <section className="setup-section"><h2>Report outputs</h2><label className="check report-output-setting"><input type="checkbox" aria-label="Export MultiQC custom content" checked={multiqc} onChange={event => setMultiqc(event.target.checked)}/><span><strong>Export MultiQC custom content</strong><small>Creates compatible supporting files for scan audits. MultiQC is not required unless you render a complete dashboard externally.</small></span></label></section>
          </div>}
        </div>
        {page === 'new' && <div className="setup-action"><div><strong>{selectedCount} {mode === 'scan' ? 'inputs selected' : 'of 3 required inputs selected'}</strong><small>{policyDirty ? 'Save edited policy before running' : mode === 'scan' ? 'Privacy metadata audit · Files remain unchanged' : 'Source · Candidate · Pairing manifest'}</small></div><button className="primary" disabled={!canRun} onClick={() => submit()}>{active ? <Clock3 size={16}/> : <Play size={16}/>} {active ? 'Queue audit' : mode === 'scan' ? 'Run privacy audit' : 'Run comparison'}</button></div>}
      </main>
    </div>
    <div className="taskbar"><strong>Tasks</strong><span>{active ? `${jobs.filter(value => value.status === 'running').length} running · ${jobs.filter(value => value.status === 'queued').length} queued` : 'No active audits'}</span>{jobs.find(value => value.status === 'running')?.progress && <span className="task-phase">{jobs.find(value => value.status === 'running')?.progress?.phase}</span>}</div>
    <footer className="statusbar"><span className={ready ? 'connection' : ''}>{ready ? '● Local engine ready' : 'Connecting to local engine…'}</span><span>Source files are read-only · Metadata only</span></footer>
  </div>;
}
const container = document.getElementById('root');
if (container) createRoot(container).render(<App/>);
