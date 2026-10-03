import React, {useEffect, useRef, useState} from 'react';
import {createRoot} from 'react-dom/client';
import {FolderOpen, FileText, Plus, History, Settings, ArrowRight, X, Download, RefreshCw, Trash2, Search, PanelLeftClose, PanelLeftOpen} from 'lucide-react';
import {api, auditLabel, chooseWorkspace, deleteRun, onDesktopMenu, pick, report, reveal, saveReport, syncMenu, workspace} from './desktop';
import type {Input, Job, Results} from './desktop';
import {artifactLabel, isHtml, orderedArtifacts} from './reports';
import './style.css';

const deletableStatuses = ['completed', 'failed', 'cancelled', 'interrupted'];
const logo = new URL('../src-tauri/icons/128x128.png', import.meta.url).href;
const sourceLabels: Record<string, string> = {paths: 'DICOM inputs', source: 'Source folder', candidate: 'Candidate folder', manifest: 'Pairing manifest', policy: 'Project policy'};
const runName = (job: Job) => job.mode === 'demo' ? `Example · ${job.example === 'uid' ? 'UID integrity' : job.example}` : job.mode === 'scan' ? 'Dataset scan' : 'Dataset comparison';

export function App() {
  const [page, setPage] = useState<'new' | 'runs' | 'settings'>('new');
  const [tab, setTab] = useState<'findings' | 'reports'>('findings');
  const [runQuery, setRunQuery] = useState(''), [navigation, setNavigation] = useState(true);
  const [advanced, setAdvanced] = useState(false), [reportIndex, setReportIndex] = useState<number | null>(null);
  const [saving, setSaving] = useState(false);
  const savePending = useRef(false);
  const menuHandler = useRef<(action: string) => void>(() => {});
  const workspaceView = useRef<HTMLDivElement>(null);
  useEffect(() => {if (workspaceView.current) workspaceView.current.scrollTop = 0;}, [page, tab]);
  const [mode, setMode] = useState<'scan' | 'compare'>('scan');
  const [inputs, setInputs] = useState<Record<string, Input[]>>({});
  const [uid, setUid] = useState(false), [vendor, setVendor] = useState(false), [multiqc, setMultiqc] = useState(false);
  const [jobs, setJobs] = useState<Job[]>([]), [selected, setSelected] = useState<string | null>(null);
  const [results, setResults] = useState<Results | null>(null), [offset, setOffset] = useState(0);
  const [preview, setPreview] = useState<string | null>(null), [error, setError] = useState('');
  const [busy, setBusy] = useState(false), [ready, setReady] = useState(false), [root, setRoot] = useState('');
  const [theme, setTheme] = useState(() => {
    try {const value = localStorage.getItem('dicomqc-theme'); return value === 'light' || value === 'dark' ? value : 'system';}
    catch {return 'system';}
  });
  const [connectionError, setConnectionError] = useState('');
  const [resultsError, setResultsError] = useState(false), [retry, setRetry] = useState(0);
  const [switching, setSwitching] = useState(false), [generation, setGeneration] = useState(0);
  const [cancelling, setCancelling] = useState<string | null>(null);
  const [deleting, setDeleting] = useState<string | null>(null);
  const [reportBusy, setReportBusy] = useState(false), [notice, setNotice] = useState('');
  const epoch = useRef(0), reportRequest = useRef(0), operation = useRef(false);
  const jobsVersion = useRef(0);
  const resultsRequest = useRef(0), selectedRef = useRef(selected);
  selectedRef.current = selected;
  const job = jobs.find(value => value.id === selected);
  const active = jobs.filter(value => ['queued', 'running'].includes(value.status)).length;
  const artifacts = orderedArtifacts(job?.artifacts || []);
  const selectedArtifact = reportIndex === null ? undefined : job?.artifacts[reportIndex];
  const visibleJobs = jobs.filter(value => `${runName(value)} ${value.id} ${auditLabel(value)} ${new Date(value.created * 1000).toLocaleString()}`.toLowerCase().includes(runQuery.toLowerCase().trim()));
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
    if (!switching) {
      void refresh();
      workspace().then(value => {if (alive && current === epoch.current) setRoot(value);}).catch(cause => {if (alive) fail(cause);});
    }
    return () => {alive = false; clearTimeout(timer);};
  }, [generation, switching]);
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
  async function submit(example?: string) {
    if (operation.current || !ready || (!example && !valid)) return;
    operation.current = true;
    setBusy(true); setError('');
    try {
      const value = await api<Job>('/api/v1/jobs', 'POST', example ? {mode: 'demo', example} : {
        mode, inputs: Object.fromEntries(Object.entries(inputs).filter(([key]) =>
          key === 'policy' || (mode === 'scan' ? key === 'paths' : ['source', 'candidate', 'manifest'].includes(key)))
          .map(([key, values]) => [key, values.map(value => value.id)])),
        options: mode === 'scan' ? {uid_checks: uid, vendor_summary: vendor, multiqc} : {},
      });
      jobsVersion.current++; setJobs(current => [value, ...current.filter(job => job.id !== value.id)]); setSelected(value.id); setOffset(0); closePreview(); setRunQuery(''); setTab('findings'); setPage('runs');
    } catch (cause) {fail(cause);} finally {setBusy(false); operation.current = false;}
  }
  function closePreview() {reportRequest.current++; setPreview(null); setReportIndex(null); setReportBusy(false); setNotice('');}
  function selectArtifact(id: string, index: number, name: string) {
    closePreview(); setReportIndex(index);
    if (isHtml(name)) void openReport(id, index);
  }
  function showTab(value: 'setup' | 'findings' | 'reports') {
    if ((value === 'findings' && !job) || (value === 'reports' && job?.status !== 'completed')) return;
    if ((value === 'setup' && page === 'new') || (page === 'runs' && tab === value)) return;
    closePreview(); setPage(value === 'setup' ? 'new' : 'runs');
    if (value !== 'setup') setTab(value);
  }
  function openRun(value: Job) {
    closePreview(); setSelected(value.id); setOffset(0); setTab('findings'); setPage('runs');
  }
  async function exportReport(id: string, index: number) {
    if (savePending.current) return;
    savePending.current = true; setSaving(true); setError('');
    const current = reportRequest.current;
    try {const saved = await saveReport(id, index); if (current === reportRequest.current) setNotice(saved ? 'Report copy saved.' : '');}
    catch (cause) {if (current === reportRequest.current) fail(cause);}
    finally {savePending.current = false; setSaving(false);}
  }
  async function openReport(id: string, index: number) {
    const request = ++reportRequest.current;
    setReportBusy(true); setPreview(null); setError('');
    try {const html = await report(id, index); if (request === reportRequest.current) setPreview(html);}
    catch (cause) {if (request === reportRequest.current) fail(cause);}
    finally {if (request === reportRequest.current) setReportBusy(false);}
  }
  async function cancelRun(id: string) {
    if (cancelling) return;
    setCancelling(id); setError('');
    try {const value = await api<Job>(`/api/v1/jobs/${id}/cancel`, 'POST'); jobsVersion.current++; setJobs(current => current.map(job => job.id === id ? value : job));}
    catch (cause) {fail(cause);} finally {setCancelling(null);}
  }
  async function switchWorkspace() {
    if (operation.current || active || !ready) return;
    operation.current = true; epoch.current++; closePreview(); setSwitching(true); setReady(false); setError('');
    try {
      const value = await chooseWorkspace(Object.values(inputs).flat().map(input => input.id));
      if (value) {
        setRoot(value.path);
        setInputs(current => Object.fromEntries(Object.entries(current).map(([key, values]) => [key, values.map(input => value.inputs[input.id])])));
        setJobs([]); setSelected(null); setResults(null); setOffset(0); setRunQuery('');
      }
    } catch (cause) {fail(cause);}
    finally {operation.current = false; setSwitching(false); setGeneration(value => value + 1);}
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
  function inputList(key: string) {
    return <ul className="selections">{(inputs[key] || []).map((value, index) => <li key={value.id}>
      {value.kind === 'directory' ? <FolderOpen size={16}/> : <FileText size={16}/>}
      <span title={value.display_path || value.name}>{value.display_path || value.name}</span>
      <button className="icon" title={`Remove ${value.name}`} aria-label={`Remove ${value.name}`} disabled={busy || switching} onClick={() =>
        setInputs(current => ({...current, [key]: current[key].filter((_, position) => position !== index)}))}><X size={16}/></button>
    </li>)}</ul>;
  }
  const valid = mode === 'scan' ? Boolean(inputs.paths?.length) : ['source', 'candidate', 'manifest'].every(key => inputs[key]?.length);
  const canRun = valid && ready && !busy && !switching;
  const canFindings = Boolean(job) && !switching;
  const canReports = job?.status === 'completed' && !switching;
  useEffect(() => {
    let alive = true;
    syncMenu({canRun, canFindings, canReports}).catch(cause => {if (alive) fail(cause);});
    return () => {alive = false;};
  }, [canRun, canFindings, canReports]);
  const selectedCount = (mode === 'scan' ? inputs.paths?.length || 0 : ['source', 'candidate', 'manifest'].filter(key => inputs[key]?.length).length);
  const tabId = page === 'new' ? 'setup' : page === 'runs' ? tab : null;
  menuHandler.current = action => {
    if (action === 'new-audit' || action === 'setup') showTab('setup');
    else if (action === 'findings' || action === 'reports') showTab(action);
    else if (action === 'settings') {closePreview(); setPage('settings');}
    else if (action === 'run-audit') void submit();
    else if ((action === 'add-file' || action === 'add-folder') && ready && !busy && !switching) {
      setMode('scan'); showTab('setup'); void select('paths', action === 'add-folder');
    }
  };
  return <div className="desktop-shell">
    <header className="titlebar"><img src={logo} alt=""/><strong>dicomqc</strong><span>DICOM metadata audit</span><span className="local-badge">Local workspace</span></header>
    <div className="toolbar" role="toolbar" aria-label="Workspace actions">
      <button className="icon" aria-label={navigation ? 'Hide navigation' : 'Show navigation'} title={navigation ? 'Hide navigation' : 'Show navigation'} aria-expanded={navigation} aria-controls="workspace-navigation" onClick={() => setNavigation(value => !value)}>{navigation ? <PanelLeftClose size={18}/> : <PanelLeftOpen size={18}/>}</button>
      <button onClick={() => showTab('setup')}><Plus size={17}/>New audit</button>
      <span className="toolbar-context">{page === 'runs' && job ? <>{runName(job)} <small>{job.id.slice(0, 8)}</small></> : mode === 'scan' ? 'Scan a dataset' : 'Compare datasets'}</span>
      <button className="icon settings-button" title="Settings" aria-label="Settings" aria-pressed={page === 'settings'} onClick={() => {closePreview(); setPage('settings');}}><Settings size={18}/></button>
    </div>
    <div className={`desktop-body ${navigation ? '' : 'navigation-hidden'}`}>
      {navigation && <aside className="workspace-tree" id="workspace-navigation" aria-label="Workspace navigation">
        <div className="tree-scroll">
          <section className="source-tree" aria-label="Selected sources"><h2>Sources</h2>
            {!Object.values(inputs).some(values => values.length) && <p className="tree-empty">No sources selected</p>}
            {Object.entries(inputs).filter(([, values]) => values.length).map(([key, values]) => <div className="source-group" key={key}><h3>{sourceLabels[key]}</h3>{values.map(value =>
              <button className="tree-source" key={value.id} aria-label={`Edit ${sourceLabels[key]}: ${value.name}`} title={value.display_path || value.name} onClick={() => {
                if (key !== 'policy') setMode(key === 'paths' ? 'scan' : 'compare');
                if (key === 'policy') setAdvanced(true);
                showTab('setup');
              }}>{value.kind === 'directory' ? <FolderOpen size={15}/> : <FileText size={15}/>}<span>{value.name}{value.display_path && <small>{value.display_path}</small>}</span></button>
            )}</div>)}
          </section>
          <section className="history-tree" aria-label="Run history">
            <h2><button className="tree-heading" onClick={() => showTab('findings')}><History size={15}/>Runs <span>{jobs.length}</span></button></h2>
            <label className="run-search"><Search size={15}/><input aria-label="Find runs" placeholder="Find a run..." value={runQuery} onChange={event => setRunQuery(event.target.value)}/></label>
            <p className="queue-count">{jobs.filter(value => value.status === 'running').length} running · {jobs.filter(value => value.status === 'queued').length} queued</p>
            {!jobs.length && <p className="tree-empty">{ready ? 'No audits yet' : 'Waiting for run history'}</p>}
            {jobs.length > 0 && !visibleJobs.length && <p className="tree-empty">No matching runs</p>}
            <div className="run-list" aria-label="Audit runs">{visibleJobs.map(value => <button key={value.id} aria-pressed={selected === value.id} onClick={() => openRun(value)}>
              <strong>{runName(value)}</strong><span className={`run-state ${value.status}`}>{auditLabel(value)}</span>
              <small>{new Date(value.created * 1000).toLocaleString()} · {value.id.slice(0, 8)}</small>
            </button>)}</div>
          </section>
        </div>
        <div className="tree-footer"><FolderOpen size={15}/><span title={root}>{root.split(/[\\/]/).filter(Boolean).pop() || 'Workspace'}</span></div>
      </aside>}
      <main className="desktop-content">
        <div className="workspace-tabs" role="tablist" aria-label="Workspace views">{(['setup', 'findings', 'reports'] as const).map((value, index, all) =>
          <button key={value} id={`tab-${value}`} role="tab" disabled={value === 'findings' ? !canFindings : value === 'reports' ? !canReports : false} aria-selected={tabId === value} aria-controls="workspace-panel" tabIndex={tabId === value || (!tabId && index === 0) ? 0 : -1} onClick={() => showTab(value)} onKeyDown={event => {
            const next = event.key === 'ArrowRight' ? (index + 1) % all.length : event.key === 'ArrowLeft' ? (index + all.length - 1) % all.length : event.key === 'Home' ? 0 : event.key === 'End' ? all.length - 1 : -1;
            if (next >= 0) {event.preventDefault(); let target = next; for (let count = 0; count < all.length; count++) {const button = document.getElementById(`tab-${all[target]}`) as HTMLButtonElement; if (!button.disabled) {showTab(all[target]); button.focus(); break;} target = (target + (event.key === 'ArrowLeft' || event.key === 'End' ? all.length - 1 : 1)) % all.length;}}
          }}>{value[0].toUpperCase() + value.slice(1)}</button>
        )}</div>
        {error && <div className="error" role="alert"><span>{error}</span><button className="icon" aria-label="Dismiss error" title="Dismiss error" onClick={() => setError('')}><X size={16}/></button></div>}
        {connectionError && <div className="error" role="status">{connectionError}</div>}
        {notice && <p className="notice" role="status">{notice}</p>}
        <div className="workspace-view" ref={workspaceView} id="workspace-panel" role={tabId ? 'tabpanel' : 'region'} aria-labelledby={tabId ? `tab-${tabId}` : 'settings-heading'}>
          {page === 'new' && <div className="setup-pane">
            <div className="pane-heading"><h1>Audit setup</h1><div className="mode-tabs" role="group" aria-label="Audit mode"><button aria-pressed={mode === 'scan'} onClick={() => setMode('scan')}>Scan a dataset</button><button aria-pressed={mode === 'compare'} onClick={() => setMode('compare')}>Compare datasets</button></div></div>
            <section className="setup-section"><h2>{mode === 'scan' ? 'DICOM inputs' : 'Paired datasets'}</h2>
              {mode === 'scan' ? <><div className="actions"><button disabled={!ready || busy || switching} onClick={() => select('paths', true)}><FolderOpen size={16}/>Add folder</button><button disabled={!ready || busy || switching} onClick={() => select('paths', false)}><FileText size={16}/>Add file</button></div>{!inputs.paths?.length && <p className="empty-selection">No files or folders selected</p>}{inputList('paths')}</> :
                <div className="input-grid">{[['source', 'Source folder', true], ['candidate', 'Candidate folder', true], ['manifest', 'Pairing manifest · CSV', false]].map(([key, label, directory]) => <div className="input-row" key={String(key)}><div><strong>{label}</strong>{!inputs[String(key)]?.length && <small>Not selected</small>}{inputList(String(key))}</div><button aria-label={`Choose ${label}`} disabled={!ready || busy || switching} onClick={() => select(String(key), Boolean(directory))}><FolderOpen size={16}/>Choose</button></div>)}</div>}
            </section>
            <section className="setup-section"><h2>Checks and outputs</h2><div className="setup-summary"><span>Privacy checks <strong>On</strong></span><span>Reports <strong>HTML · JSON · CSV</strong></span></div>
              <details open={advanced} onToggle={event => setAdvanced(event.currentTarget.open)}><summary>Advanced checks and outputs</summary><div className="advanced">
                <div className="input-row"><div><strong>Project policy · YAML</strong>{inputList('policy')}</div><button disabled={!ready || busy || switching} onClick={() => select('policy', false)}><FileText size={16}/>Choose policy</button></div>
                {mode === 'scan' && <><label className="check"><input type="checkbox" checked={uid} onChange={event => setUid(event.target.checked)}/><span>Check UID syntax and relationships</span></label>
                  <label className="check"><input type="checkbox" checked={vendor} onChange={event => setVendor(event.target.checked)}/><span>Include scanner and private-creator inventory</span></label>
                  {vendor && <p className="privacy-warning">This exports observed labels that may identify people or sites. Review reports before sharing.</p>}
                  <label className="check"><input type="checkbox" checked={multiqc} onChange={event => setMultiqc(event.target.checked)}/><span>Also create MultiQC custom content</span></label></>}
              </div></details>
              <div className="output-location"><strong>Output folder</strong><code>{root || 'Loading...'}</code><button disabled={active > 0 || busy || switching || !ready} onClick={switchWorkspace}><FolderOpen size={16}/>{switching ? 'Changing output folder...' : 'Choose output folder'}</button></div>
            </section>
            <details className="examples"><summary>Explore with synthetic data</summary><div className="actions">{['scan', 'compare', 'policy', 'uid', 'vendor'].map(example => <button key={example} disabled={!ready || busy} onClick={() => submit(example)}>{example === 'uid' ? 'UID integrity' : example[0].toUpperCase() + example.slice(1)}</button>)}</div></details>
          </div>}
          {page === 'runs' && <div className={`run-pane ${tab === 'reports' ? 'reports-pane' : ''}`}>
            {!job ? <div className="empty"><History size={28}/><h1>{tab === 'reports' ? 'Reports' : 'Findings'}</h1><p>Select a run from history.</p></div> : <>
              <div className="pane-heading result-heading"><div><h1>{auditLabel(job)}</h1><p>{runName(job)} · {new Date(job.created * 1000).toLocaleString()} · {job.id.slice(0, 8)}</p></div>
                <div className="actions">
                  {job.status === 'completed' && <button title="Open run folder" aria-label="Open run folder" onClick={() => reveal(job.id).catch(fail)}><FolderOpen size={16}/><span>Open run folder</span></button>}
                  {deletableStatuses.includes(job.status) && <button className="icon" aria-label="Delete run" title={deleting === job.id ? 'Deleting run...' : 'Delete run'} aria-busy={deleting === job.id} disabled={!ready || busy || switching} onClick={() => removeRun(job)}><Trash2 size={17}/></button>}
                  {['queued', 'running'].includes(job.status) && <button disabled={!ready || cancelling === job.id} onClick={() => cancelRun(job.id)}><X size={16}/>{cancelling === job.id ? 'Cancelling...' : 'Cancel audit'}</button>}
                </div>
              </div>
              {tab === 'findings' && job.summary && <div className="metrics" aria-label="Audit summary"><span><strong>{job.summary.files_scanned}</strong> files read</span><span className="error-count"><strong>{job.summary.errors}</strong> errors</span><span className="warning-count"><strong>{job.summary.warnings}</strong> warnings</span><span className={job.summary.skipped_files ? 'warning-count' : ''}><strong>{job.summary.skipped_files}</strong> skipped files</span></div>}
              {job.mode === 'demo' && <p className="demo-context">Synthetic example{tab === 'findings' && job.artifacts.some(name => /(^|\/)before\.json$/i.test(name)) ? ' · Findings: before correction' : ''}</p>}
              {['queued', 'running'].includes(job.status) && <div className="progress"><p role="status">{job.status === 'queued' ? 'Queued - waiting for the active audit' : job.progress ? `${job.progress.phase} · ${job.progress.completed}${job.progress.total != null ? ` / ${job.progress.total}` : ''}` : 'Starting audit...'}</p><progress aria-label="Audit progress" max={job.progress?.total || 1} value={job.progress?.total ? Math.min(job.progress.completed, job.progress.total) : undefined}/></div>}
              {job.message && <p className="run-message">{job.message}</p>}
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
                <div className="report-files" aria-label="Report files"><h2>Files <span>{artifacts.length}</span></h2>{artifacts.map(({name, index}) =>
                  <button key={name} aria-label={`Select report ${name}`} aria-pressed={reportIndex === index} onClick={() => selectArtifact(job.id, index, name)}><FileText size={16}/><span><strong>{name.split('/').pop()}</strong><small>{artifactLabel(name)}</small><small className="artifact-path">{name.includes('/') ? name.slice(0, name.lastIndexOf('/')) : ''}</small></span></button>
                )}</div>
                <section className="report-preview" aria-label="Selected report">
                  {selectedArtifact !== undefined && reportIndex !== null ? <>
                    <div className="preview-toolbar"><div><strong>{artifactLabel(selectedArtifact)}</strong><small>{selectedArtifact}</small></div><button disabled={saving || busy || switching} aria-label={`Save ${selectedArtifact}`} onClick={() => exportReport(job.id, reportIndex)}><Download size={16}/>{saving ? 'Saving...' : 'Save copy'}</button></div>
                    {reportBusy ? <p className="preview-state" role="status">Loading report...</p> : preview !== null ? <iframe title="Audit report preview" sandbox="" referrerPolicy="no-referrer" srcDoc={preview}/> : isHtml(selectedArtifact) ? <div className="preview-state"><p>Report preview unavailable.</p><button onClick={() => openReport(job.id, reportIndex)}><RefreshCw size={16}/>Retry preview</button></div> : <div className="preview-state"><FileText size={28}/><h2>{artifactLabel(selectedArtifact)}</h2><p>{selectedArtifact}</p></div>}
                  </> : <p className="preview-state">No reports available.</p>}
                </section>
              </div>}
            </>}
          </div>}
          {page === 'settings' && <div className="settings-pane"><h1 id="settings-heading">Settings</h1><section className="setup-section"><h2>Appearance</h2><label className="setting">Theme<select value={theme} onChange={event => setTheme(event.target.value)}><option value="system">System</option><option value="light">Light</option><option value="dark">Dark</option></select></label></section>
            <section className="setup-section"><h2>Output folder</h2><code className="workspace-path">{root}</code><button disabled={active > 0 || busy || switching || !ready} onClick={switchWorkspace}><FolderOpen size={16}/>{switching ? 'Changing output folder...' : 'Choose output folder'}</button>{active > 0 && <p>Wait for active audits or cancel them before changing the output folder.</p>}</section>
            <section className="setup-section"><h2>About dicomqc</h2><p>Version 0.2.0 · Local API · One audit at a time</p><p>Audit DICOM metadata for privacy risks. This application does not de-identify files or certify that data is safe to share.</p></section>
          </div>}
        </div>
        {page === 'new' && <div className="setup-action"><div><strong>{selectedCount} {mode === 'scan' ? 'inputs selected' : 'of 3 required inputs selected'}</strong><small>{mode === 'scan' ? 'Metadata only · Files remain unchanged' : 'Source · Candidate · Pairing manifest'}</small></div><button className="primary" disabled={!valid || !ready || busy || switching} onClick={() => submit()}>Run audit<ArrowRight size={17}/></button></div>}
      </main>
    </div>
    <div className="taskbar"><strong>Tasks</strong><span>{active ? `${jobs.filter(value => value.status === 'running').length} running · ${jobs.filter(value => value.status === 'queued').length} queued` : 'No active audits'}</span>{jobs.find(value => value.status === 'running')?.progress && <span className="task-phase">{jobs.find(value => value.status === 'running')?.progress?.phase}</span>}</div>
    <footer className="statusbar"><span className={ready ? 'connection' : ''}>{ready ? '● Local engine ready' : 'Connecting to local engine…'}</span><span>Source files are read-only · Metadata only</span></footer>
  </div>;
}
const container = document.getElementById('root');
if (container) createRoot(container).render(<App/>);
