export function isHtml(name: string): boolean {return name.toLowerCase().endsWith('.html');}

export function artifactLabel(name: string): string {
  const base = name.split('/').pop() || name;
  const format = base.split('.').pop()?.toUpperCase() || 'File';
  if (/^before\./i.test(base)) return `Before correction · ${format}`;
  if (/^after\./i.test(base)) return `After correction · ${format}`;
  if (/_mqc\.html$/i.test(base)) return 'MultiQC content · HTML';
  return `${format} report`;
}

export function orderedArtifacts(names: string[]) {
  const rank = (name: string) => !isHtml(name) ? 4 : /_mqc\.html$/i.test(name) ? 3 : /(^|\/)before\.html$/i.test(name) ? 0 : /(^|\/)after\.html$/i.test(name) ? 2 : 1;
  return names.map((name, index) => ({name, index})).sort((a, b) => rank(a.name) - rank(b.name) || a.index - b.index);
}
