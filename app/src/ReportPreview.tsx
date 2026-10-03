import {useEffect, useMemo, useState} from 'react';
import Papa from 'papaparse';
import {JsonView} from 'react-json-view-lite';
import {ArrowDown, ArrowUp, ArrowUpDown, ChevronLeft, ChevronRight, Search} from 'lucide-react';
import 'react-json-view-lite/dist/index.css';
import './report-preview.css';

type SortState = {column: number; direction: 'ascending' | 'descending'} | null;
const collator = new Intl.Collator(undefined, {numeric: true, sensitivity: 'base'});
const expandSummary = (level: number) => level < 2;
const jsonStyles = {
  container: 'json-tree', basicChildStyle: 'json-child', label: 'json-label', clickableLabel: 'json-clickable',
  nullValue: 'json-null', undefinedValue: 'json-null', numberValue: 'json-number', stringValue: 'json-string',
  booleanValue: 'json-boolean', otherValue: 'json-value', punctuation: 'json-punctuation', expandIcon: 'json-expand',
  collapseIcon: 'json-collapse', collapsedContent: 'json-collapsed', childFieldsContainer: 'json-children',
};

function JsonReport({text}: {text: string}) {
  const parsed = useMemo(() => {
    try {return {value: JSON.parse(text) as unknown, error: ''};}
    catch {return {value: null, error: 'This report does not contain valid JSON.'};}
  }, [text]);
  if (parsed.error) return <p className="preview-state" role="alert">{parsed.error}</p>;
  if (parsed.value === null || typeof parsed.value !== 'object') return <pre className="scalar-json">{JSON.stringify(parsed.value, null, 2)}</pre>;
  return <div className="structured-preview json-preview" aria-label="JSON report contents"><JsonView data={parsed.value as object} style={jsonStyles} shouldExpandNode={expandSummary} clickToExpandNode/></div>;
}

function CsvReport({text}: {text: string}) {
  const [page, setPage] = useState(0);
  const [pageSize, setPageSize] = useState(100);
  const [query, setQuery] = useState('');
  const [sort, setSort] = useState<SortState>(null);
  const parsed = useMemo(() => Papa.parse<string[]>(text, {skipEmptyLines: 'greedy'}), [text]);
  useEffect(() => setPage(0), [text, pageSize, query, sort?.column, sort?.direction]);
  if (!parsed.data.length) return <p className="preview-state">The CSV report is empty.</p>;
  const header = parsed.data[0];
  const rows = parsed.data.slice(1);
  const columnCount = Math.max(header.length, ...rows.map(row => row.length));
  const filtered = query.trim() ? rows.filter(row => row.some(cell => cell.toLocaleLowerCase().includes(query.trim().toLocaleLowerCase()))) : rows;
  const sorted = sort ? [...filtered].sort((left, right) => {
    const compared = collator.compare(left[sort.column] ?? '', right[sort.column] ?? '');
    return sort.direction === 'ascending' ? compared : -compared;
  }) : filtered;
  const pages = Math.max(1, Math.ceil(sorted.length / pageSize));
  const currentPage = Math.min(page, pages - 1);
  const visible = sorted.slice(currentPage * pageSize, (currentPage + 1) * pageSize);
  const changeSort = (column: number) => setSort(current => current?.column !== column ? {column, direction: 'ascending'} : current.direction === 'ascending' ? {column, direction: 'descending'} : null);
  return <div className="structured-preview csv-preview" aria-label="CSV report contents">
    <div className="data-preview-toolbar"><label className="data-filter"><Search size={14}/><input aria-label="Filter CSV rows" placeholder="Filter rows..." value={query} onChange={event => setQuery(event.target.value)}/></label><label>Rows per page<select aria-label="Rows per page" value={pageSize} onChange={event => setPageSize(Number(event.target.value))}>{[25, 50, 100, 250].map(value => <option key={value} value={value}>{value}</option>)}</select></label></div>
    <div className="data-table-wrap"><table><thead><tr>{Array.from({length: columnCount}, (_, index) => <th key={index} scope="col" aria-sort={sort?.column === index ? sort.direction : 'none'}><button onClick={() => changeSort(index)}>{header[index] || `Column ${index + 1}`}{sort?.column !== index ? <ArrowUpDown size={13}/> : sort.direction === 'ascending' ? <ArrowUp size={13}/> : <ArrowDown size={13}/>}</button></th>)}</tr></thead>
      <tbody>{visible.map((row, rowIndex) => <tr key={currentPage * pageSize + rowIndex}>{Array.from({length: columnCount}, (_, columnIndex) => <td key={columnIndex}>{row[columnIndex] ?? ''}</td>)}</tr>)}{!visible.length && <tr><td className="empty-table" colSpan={columnCount}>No matching rows</td></tr>}</tbody></table></div>
    <div className="data-preview-footer"><span>{sorted.length ? `${currentPage * pageSize + 1}-${Math.min((currentPage + 1) * pageSize, sorted.length)} of ${sorted.length} rows` : '0 rows'}{query && rows.length !== sorted.length ? ` · ${rows.length} total` : ''}{parsed.errors.length ? ` · ${parsed.errors.length} parse warnings` : ''}</span>
      <div><span>Page {currentPage + 1} of {pages}</span><button className="icon" aria-label="Previous CSV page" title="Previous page" disabled={currentPage === 0} onClick={() => setPage(value => Math.max(0, value - 1))}><ChevronLeft size={15}/></button><button className="icon" aria-label="Next CSV page" title="Next page" disabled={currentPage + 1 >= pages} onClick={() => setPage(value => Math.min(pages - 1, value + 1))}><ChevronRight size={15}/></button></div>
    </div>
  </div>;
}

export function ReportPreview({name, text}: {name: string; text: string}) {
  if (/\.ya?ml$/i.test(name)) return <pre className="scalar-json" aria-label="YAML policy contents">{text}</pre>;
  if (name.toLowerCase().endsWith('.json')) return <JsonReport text={text}/>;
  if (name.toLowerCase().endsWith('.csv')) return <CsvReport text={text}/>;
  return <p className="preview-state">Preview is unavailable for this report format.</p>;
}
