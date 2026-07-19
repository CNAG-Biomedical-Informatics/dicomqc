import {readFileSync} from 'node:fs';
import {fileURLToPath} from 'node:url';
import {dirname, join} from 'node:path';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');

function read(relativePath) {
  return readFileSync(join(root, relativePath), 'utf8');
}

function requireText(content, expected, location) {
  if (!content.includes(expected)) {
    throw new Error(`${location} must contain ${JSON.stringify(expected)}`);
  }
}

function requireAccessibleSvg(relativePath) {
  const svg = read(relativePath);
  requireText(svg, '<title', relativePath);
  requireText(svg, '<desc', relativePath);
  requireText(svg, 'role="img"', relativePath);
}

const home = read('src/pages/index.tsx');
requireText(home, "useBaseUrl('/img/dicomqc-objective.svg')", 'src/pages/index.tsx');
requireText(home, 'Independent metadata audit for DICOM research releases.', 'src/pages/index.tsx');
requireText(home, 'Version 0.1 does not pseudonymize', 'src/pages/index.tsx');

if (home.includes('dicomqc-logo.png')) {
  throw new Error('The landing page should use the lowercase wordmark, not the legacy logo image');
}

const architecture = read('docs/technical-details/architecture.mdx');
requireText(
  architecture,
  "useBaseUrl('/img/dicomqc-architecture.svg')",
  'docs/technical-details/architecture.mdx',
);
requireText(
  architecture,
  "useBaseUrl('/img/dicomqc-architecture-mobile.svg')",
  'docs/technical-details/architecture.mdx',
);
requireText(architecture, 'Metadata and reporting boundary', 'docs/technical-details/architecture.mdx');

const overview = read('docs/overview.md');
requireText(overview, 'Project status', 'docs/overview.md');
requireText(overview, 'Primary interface', 'docs/overview.md');
requireText(overview, 'Why audit after de-identification?', 'docs/overview.md');

const homeStyles = read('src/pages/index.module.css');
requireText(homeStyles, '.objectiveFigure {', 'src/pages/index.module.css');
requireText(homeStyles, 'display: none;', 'src/pages/index.module.css');

requireAccessibleSvg('static/img/dicomqc-objective.svg');
requireAccessibleSvg('static/img/dicomqc-architecture.svg');
requireAccessibleSvg('static/img/dicomqc-architecture-mobile.svg');

console.log('Documentation smoke checks passed.');
