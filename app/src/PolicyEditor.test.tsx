import {act, cleanup, fireEvent, render, screen} from '@testing-library/react';
import {EditorView} from '@codemirror/view';
import {afterEach, expect, it, vi} from 'vitest';
import {errorLine, PolicyEditor} from './PolicyEditor';

afterEach(cleanup);

it('edits, validates and saves exact YAML text', async () => {
  const onChange = vi.fn();
  const onValidate = vi.fn().mockResolvedValue({id: 'research-policy', rules: 1});
  const onSave = vi.fn().mockResolvedValue('reviewed.yaml');
  const source = 'version: 1\nid: research-policy\nrules: []\n';
  const props = {value: source, filename: 'policy.yaml', dirty: false, onChange, onValidate, onSave, onReset: vi.fn(), onRemove: vi.fn()};
  const {rerender} = render(<PolicyEditor {...props}/>);
  expect(document.querySelector('.cm-lineNumbers')).toBeTruthy();
  fireEvent.click(screen.getByRole('button', {name: 'Remove policy'}));
  expect(props.onRemove).toHaveBeenCalledOnce();
  expect(screen.getByRole('button', {name: 'Reset YAML'}).hasAttribute('disabled')).toBe(true);
  const editor = EditorView.findFromDOM(screen.getByRole('textbox', {name: 'Policy editor'}))!;
  const edited = source.replace('rules: []', 'rules:\n  - id: comments');
  act(() => editor.dispatch({changes: {from: 0, to: editor.state.doc.length, insert: edited}}));
  expect(onChange).toHaveBeenCalledWith(edited);
  rerender(<PolicyEditor {...props} value={edited} dirty/>);
  fireEvent.click(screen.getByRole('button', {name: 'Reset YAML'}));
  expect(props.onReset).toHaveBeenCalledOnce();
  rerender(<PolicyEditor {...props}/>);
  expect(editor.state.doc.toString()).toBe(source);
  rerender(<PolicyEditor {...props} value={edited} dirty/>);
  fireEvent.click(screen.getByRole('button', {name: 'Validate'}));
  expect((await screen.findByRole('status')).textContent).toContain('research-policy is valid with 1 rule');
  expect(onValidate).toHaveBeenCalledWith(edited);
  fireEvent.click(screen.getByRole('button', {name: 'Save as and use'}));
  expect((await screen.findByRole('status')).textContent).toContain('Saved and selected reviewed.yaml');
  expect(onSave).toHaveBeenCalledWith(edited);
});

it('marks and navigates to a backend YAML diagnostic', async () => {
  render(<PolicyEditor value={'version: 1\nrules: [\n'} dirty onChange={vi.fn()} onSave={vi.fn()} onReset={vi.fn()} onRemove={vi.fn()}
    onValidate={vi.fn().mockRejectedValue(new Error('Policy file must contain valid UTF-8 YAML at line 2, column 9.'))}/>);
  fireEvent.click(screen.getByRole('button', {name: 'Validate'}));
  expect((await screen.findByRole('alert')).textContent).toContain('line 2');
  fireEvent.click(screen.getByRole('button', {name: 'Go to line 2'}));
  const editor = EditorView.findFromDOM(screen.getByRole('textbox', {name: 'Policy editor'}))!;
  expect(editor.state.doc.lineAt(editor.state.selection.main.head).number).toBe(2);
  expect(errorLine('Policy rule IDs must be unique.')).toBeUndefined();
});
