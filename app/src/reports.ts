export function isHtml(name: string): boolean {return name.toLowerCase().endsWith('.html');}

export function isPreviewable(name: string): boolean {return /\.(html|json|csv|ya?ml)$/i.test(name);}

export function isExampleInput(name: string): boolean {
  return name === 'example/policy.yaml' || name === 'example/pairs.csv';
}

export function isMultiqcArtifact(name: string): boolean {
  return /(^|\/)[^/]*_mqc\//i.test(name);
}

export function artifactLabel(name: string): string {
  const base = name.split('/').pop() || name;
  const format = base.split('.').pop()?.toUpperCase() || 'File';
  if (name === 'example/policy.yaml') return 'Example policy · YAML';
  if (name === 'project-policy.yaml') return 'Project policy · YAML';
  if (name === 'example/pairs.csv') return 'Pairing manifest · CSV';
  if (/^before\./i.test(base)) return `Before correction · ${format}`;
  if (/^after\./i.test(base)) return `After correction · ${format}`;
  if (/_mqc\.html$/i.test(base)) return 'MultiQC report · HTML';
  return `${format} report`;
}

export function orderedArtifacts(names: string[]) {
  const rank = (name: string) => /_mqc\.html$/i.test(name) ? 5 : !isHtml(name) ? 4 : /(^|\/)before\.html$/i.test(name) ? 0 : /(^|\/)after\.html$/i.test(name) ? 2 : 1;
  const indexed = names.map((name, index) => ({name, index}));
  const reports = indexed.filter(({name}) => !isMultiqcArtifact(name));
  const multiqc = indexed.find(({name}) => isMultiqcArtifact(name) && /_mqc\.html$/i.test(name));
  if (multiqc) reports.push(multiqc);
  return reports.sort((a, b) => rank(a.name) - rank(b.name) || a.index - b.index);
}
