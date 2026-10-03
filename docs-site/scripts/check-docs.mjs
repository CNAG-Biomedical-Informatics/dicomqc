import {existsSync, readFileSync} from 'node:fs';
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
requireText(home, 'Check DICOM metadata before sharing research data.', 'src/pages/index.tsx');
requireText(home, 'dicomqc does not pseudonymize', 'src/pages/index.tsx');

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
requireText(architecture, 'What stays out of reports', 'docs/technical-details/architecture.mdx');

const overview = read('docs/overview.md');
requireText(overview, 'Project status', 'docs/overview.md');
requireText(overview, 'Run from the command line', 'docs/overview.md');
requireText(overview, 'Why audit after de-identification?', 'docs/overview.md');
requireText(overview, '## Terminology', 'docs/overview.md');

const plannedFeatures = read('docs/technical-details/extending-dicomqc.md');
requireText(plannedFeatures, '# Planned Features', 'docs/technical-details/extending-dicomqc.md');
requireText(
  plannedFeatures,
  '## Broader standards coverage',
  'docs/technical-details/extending-dicomqc.md',
);

const install = read('docs/usage/install.md');
requireText(install, 'python -m pip install dicomqc', 'docs/usage/install.md');
requireText(install, 'python -m pip install multiqc', 'docs/usage/install.md');
requireText(install, 'python -m pip install -e ".[test]"', 'docs/usage/install.md');

const quickstart = read('docs/usage/quickstart.md');
requireText(quickstart, '[Install](install.md)', 'docs/usage/quickstart.md');
requireText(quickstart, '/img/html-report-scan.png', 'docs/usage/quickstart.md');
requireText(quickstart, '/img/multiqc-dicomqc-module.png', 'docs/usage/quickstart.md');
const comparison = read('docs/usage/compare.md');
requireText(comparison, '/img/html-report-before.png', 'docs/usage/compare.md');
requireText(comparison, '/img/html-report-after.png', 'docs/usage/compare.md');
requireText(comparison, 'Example JSON finding', 'docs/usage/compare.md');
requireText(comparison, 'Example CSV rows', 'docs/usage/compare.md');
const policies = read('docs/usage/policies.md');
requireText(policies, '/img/html-report-policy.png', 'docs/usage/policies.md');
requireText(policies, '/img/html-report-policy-after.png', 'docs/usage/policies.md');
const vendor = read('docs/usage/vendor-summary.md');
const uid = read('docs/usage/uid-integrity.md');
requireText(uid, '/img/html-report-uid.png', 'docs/usage/uid-integrity.md');
requireText(uid, '/img/html-report-uid-after.png', 'docs/usage/uid-integrity.md');
requireText(uid, '--uid-checks', 'docs/usage/uid-integrity.md');
requireText(vendor, '/img/html-report-vendor.png', 'docs/usage/vendor-summary.md');
requireText(vendor, '--vendor-summary', 'docs/usage/vendor-summary.md');
if (existsSync(join(root, 'docs/usage/reports.md'))) {
  throw new Error('Report documentation belongs with the walkthroughs and CLI reference');
}
for (const location of ['docusaurus.config.ts', 'sidebars.ts', 'src/pages/index.tsx']) {
  if (read(location).includes('usage/reports')) {
    throw new Error(location + ' must not link to the removed Reports page');
  }
}
requireText(quickstart, '### Review the HTML report', 'docs/usage/quickstart.md');
requireText(read('docs/reference/cli.md'), '## Output formats', 'docs/reference/cli.md');

const msMriWorkflow = read('docs/usage/ms-mri-workflow.mdx');
requireText(
  msMriWorkflow,
  "useBaseUrl('/img/dicomqc-ms-mri-workflow.svg')",
  'docs/usage/ms-mri-workflow.mdx',
);
requireText(
  msMriWorkflow,
  "useBaseUrl('/img/dicomqc-ms-mri-workflow-mobile.svg')",
  'docs/usage/ms-mri-workflow.mdx',
);

const remediation = read('docs/usage/remediation.mdx');
requireText(
  remediation,
  "useBaseUrl('/img/dicomqc-remediation-loop.svg')",
  'docs/usage/remediation.mdx',
);
requireText(
  remediation,
  "useBaseUrl('/img/dicomqc-remediation-loop-mobile.svg')",
  'docs/usage/remediation.mdx',
);

const homeStyles = read('src/pages/index.module.css');
requireText(homeStyles, '.objectiveFigure {', 'src/pages/index.module.css');
requireText(homeStyles, 'display: none;', 'src/pages/index.module.css');

requireAccessibleSvg('static/img/dicomqc-objective.svg');
requireAccessibleSvg('static/img/dicomqc-audit.svg');
requireAccessibleSvg('static/img/dicomqc-audit-mobile.svg');
for (const [content, location] of [[home, 'src/pages/index.tsx'], [overview, 'docs/overview.md']]) {
  requireText(content, "useBaseUrl('/img/dicomqc-audit-mobile.svg')", location);
  requireText(content, 'media="(max-width: 760px)"', location);
}
requireAccessibleSvg('static/img/dicomqc-architecture.svg');
requireAccessibleSvg('static/img/dicomqc-architecture-mobile.svg');
requireAccessibleSvg('static/img/dicomqc-ms-mri-workflow.svg');
requireAccessibleSvg('static/img/dicomqc-ms-mri-workflow-mobile.svg');
requireAccessibleSvg('static/img/dicomqc-remediation-loop.svg');
requireAccessibleSvg('static/img/dicomqc-remediation-loop-mobile.svg');

console.log('Documentation smoke checks passed.');
