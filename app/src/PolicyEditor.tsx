import {useEffect, useRef, useState} from 'react';
import {basicSetup} from 'codemirror';
import {indentWithTab} from '@codemirror/commands';
import {yaml} from '@codemirror/lang-yaml';
import {indentUnit, HighlightStyle, syntaxHighlighting} from '@codemirror/language';
import {setDiagnostics} from '@codemirror/lint';
import {openSearchPanel} from '@codemirror/search';
import {Compartment, EditorState} from '@codemirror/state';
import {EditorView, keymap} from '@codemirror/view';
import {tags} from '@lezer/highlight';
import {Check, RotateCcw, Save, Search, X} from 'lucide-react';

export function errorLine(message: string): number | undefined {
  const found = message.match(/\bline\s*:?\s*(\d+)/i);
  const line = Number(found?.[1]);
  return line > 0 ? line : undefined;
}

export function PolicyEditor({value, filename, dirty, onChange, onValidate, onSave, onReset, onRemove}: {
  value: string;
  filename?: string;
  dirty: boolean;
  onReset: () => void;
  onRemove: () => void;
  onChange: (value: string) => void;
  onValidate: (value: string) => Promise<{id: string; rules: number}>;
  onSave: (value: string) => Promise<string | null>;
}) {
  const host = useRef<HTMLDivElement>(null);
  const editor = useRef<EditorView>(null);
  const change = useRef(onChange);
  change.current = onChange;
  const editable = useRef(new Compartment());
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState('');
  const [notice, setNotice] = useState('');
  const [line, setLine] = useState<number>();

  function createState(doc: string) {
    return EditorState.create({doc, extensions: [
      basicSetup,
      yaml(),
      indentUnit.of('  '),
      keymap.of([indentWithTab]),
      editable.current.of(EditorView.editable.of(true)),
      syntaxHighlighting(HighlightStyle.define([
        {tag: [tags.propertyName, tags.attributeName], color: 'var(--accent)'},
        {tag: tags.string, color: 'var(--success)'},
        {tag: [tags.number, tags.bool, tags.null], color: 'var(--warning)'},
        {tag: tags.comment, color: 'var(--muted)', fontStyle: 'italic'},
      ])),
      EditorView.contentAttributes.of({'aria-label': 'Policy editor', 'aria-multiline': 'true', role: 'textbox'}),
      EditorView.updateListener.of(update => {
        if (update.docChanged) {
          change.current(update.state.doc.toString());
          setProblem(''); setNotice(''); setLine(undefined);
        }
      }),
    ]});
  }

  useEffect(() => {
    const view = new EditorView({state: createState(value), parent: host.current!});
    editor.current = view;
    return () => {view.destroy(); editor.current = null;};
  }, []);
  useEffect(() => {
    if (editor.current) editor.current.dispatch(setDiagnostics(editor.current.state, []));
    if (editor.current && editor.current.state.doc.toString() !== value) {
      editor.current.setState(createState(value));
      setProblem(''); setNotice(''); setLine(undefined);
    }
  }, [value]);
  useEffect(() => {
    editor.current?.dispatch({effects: editable.current.reconfigure(EditorView.editable.of(!busy))});
  }, [busy]);

  async function action(save: boolean) {
    if (busy) return;
    setBusy(true); setProblem(''); setNotice(''); setLine(undefined);
    if (editor.current) editor.current.dispatch(setDiagnostics(editor.current.state, []));
    try {
      if (save) {
        const saved = await onSave(value);
        if (saved) setNotice(`Saved and selected ${saved}.`);
      } else {
        const policy = await onValidate(value);
        setNotice(`Policy ${policy.id} is valid with ${policy.rules} ${policy.rules === 1 ? 'rule' : 'rules'}.`);
      }
    } catch (reason) {
      const message = reason instanceof Error ? reason.message : String(reason);
      setProblem(message);
      const at = errorLine(message);
      if (editor.current && at && at <= editor.current.state.doc.lines) {
        setLine(at);
        const location = editor.current.state.doc.line(at);
        editor.current.dispatch(setDiagnostics(editor.current.state, [{from: location.from, to: location.to, severity: 'error', message}]));
      }
    } finally {
      setBusy(false);
    }
  }

  return <section className="policy-pane">
    <div className="pane-heading"><div><h1>Project policy</h1><p>{filename || 'New policy'}</p></div><span className="editor-state">{dirty ? 'Unsaved edits' : 'Selected policy'}</span></div>
    <p>Define project-specific DICOM metadata requirements. Saving creates a new YAML file and never overwrites the original.</p>
    <div className="policy-actions">
      <button disabled={busy || !value.trim()} onClick={() => void action(false)}><Check size={16}/>{busy ? 'Working...' : 'Validate'}</button>
      <button className="primary" disabled={busy || !value.trim()} onClick={() => void action(true)}><Save size={16}/>Save as and use</button>
      <button disabled={busy} onClick={() => editor.current && openSearchPanel(editor.current)}><Search size={16}/>Find</button>
      <button disabled={busy || !dirty} title="Reset YAML to the loaded or last-saved policy, or the starter template" onClick={onReset}><RotateCcw size={16}/>Reset YAML</button>
      <button disabled={busy} title="Continue without a project policy; saved YAML files are kept" onClick={onRemove}><X size={16}/>Remove policy</button>
    </div>
    {problem && <div className="policy-error" role="alert"><strong>Policy could not be validated or saved</strong><pre>{problem}</pre>{line && <button onClick={() => {
      if (!editor.current) return;
      const at = editor.current.state.doc.line(line).from;
      editor.current.dispatch({selection: {anchor: at}, scrollIntoView: true});
      editor.current.focus();
    }}>Go to line {line}</button>}</div>}
    {notice && <p className="policy-notice" role="status">{notice}</p>}
    <div ref={host} className="policy-code-editor"/>
    <p className="editor-help">YAML · two-space indentation · Ctrl/Cmd+F to find · Ctrl/Cmd+Z to undo. Validation uses the dicomqc policy engine.</p>
  </section>;
}
