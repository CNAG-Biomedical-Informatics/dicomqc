import Link from '@docusaurus/Link';
import Layout from '@theme/Layout';
import useBaseUrl from '@docusaurus/useBaseUrl';
import styles from './index.module.css';

const guideLinks = [
  {
    label: '01',
    title: 'Quickstart',
    text: 'Install dicomqc, scan a study directory, and read the exit codes.',
    to: '/docs/usage/quickstart',
  },
  {
    label: '02',
    title: 'MS MRI workflow',
    text: 'Place dicomqc after pseudonymization and before research release.',
    to: '/docs/usage/ms-mri-workflow',
  },
  {
    label: '03',
    title: 'Reports',
    text: 'Use redaction-safe JSON, CSV, and MultiQC companion evidence.',
    to: '/docs/usage/reports',
  },
  {
    label: '04',
    title: 'Architecture',
    text: 'Review the scanner, rules, report writers, and extension roadmap.',
    to: '/docs/technical-details/architecture',
  },
];

const capabilities = [
  {
    label: 'Inspect',
    title: 'Read metadata only',
    text: 'Scan DICOM files without loading pixel data and normalize release-relevant tags.',
  },
  {
    label: 'Audit',
    title: 'Apply explicit policies',
    text: 'Flag direct PHI fields, risky pseudonym fields, and private tags as structured findings.',
  },
  {
    label: 'Report',
    title: 'Keep evidence reproducible',
    text: 'Write JSON, CSV, and MultiQC-compatible outputs that avoid raw DICOM values.',
  },
  {
    label: 'Improve',
    title: 'Feed the remediation loop',
    text: 'Use findings to update an external pseudonymization workflow, then rerun the audit.',
  },
];

export default function Home() {
  const logo = useBaseUrl('/img/dicomqc-logo.png');
  const auditFlow = useBaseUrl('/img/dicomqc-audit-flow.svg');

  return (
    <Layout
      title="dicomqc"
      description="Policy-driven DICOM metadata quality control for de-identification and research-release readiness">
      <main className={styles.page}>
        <section className={styles.hero}>
          <div className={styles.heroInner}>
            <div className={styles.copy}>
              <img className={styles.logo} src={logo} alt="dicomqc" />
              <p className={styles.kicker}>DICOM metadata audit</p>
              <h1>Policy-driven QC for research-ready DICOM releases</h1>
              <p className={styles.lede}>
                dicomqc validates pseudonymized DICOM datasets before release,
                producing redaction-safe evidence for de-identification review,
                private-tag handling, and MultiQC project reports.
              </p>
              <div className={styles.actions}>
                <Link className="button button--primary button--lg" to="/docs/usage/quickstart">
                  Quick start
                </Link>
                <Link className="button button--secondary button--lg" to="/docs/overview">
                  Overview
                </Link>
              </div>
            </div>

            <div className={styles.contractPreview} aria-label="Example dicomqc scan command">
              <div className={styles.previewTitle}>Release audit</div>
              <pre><code><span>dicomqc scan</span> work/candidate_release_mri/{`\n`}  <span>--json</span> reports/dicomqc/report.json{`\n`}  <span>--csv</span> reports/dicomqc/findings.csv{`\n`}  <span>--multiqc</span> reports/dicomqc/dicomqc_mqc</code></pre>
              <div className={styles.resolution}>
                <div><span>Input</span><strong>DICOM</strong></div>
                <div><span>Mode</span><strong>read-only</strong></div>
                <div><span>Evidence</span><strong>redacted</strong></div>
              </div>
            </div>
          </div>
        </section>

        <section className={styles.workflow} aria-label="DICOM release audit workflow">
          <div className={styles.workflowInner}>
            <img
              className={styles.workflowImage}
              src={auditFlow}
              alt="Raw DICOM files are pseudonymized externally, audited by dicomqc, and reported as release evidence"
            />
            <div className={styles.mobileFlow}>
              <div><span>Raw</span><strong>Preserve source DICOM</strong></div>
              <div><span>Anon</span><strong>Run external pseudonymization</strong></div>
              <div><span>QC</span><strong>Audit metadata with dicomqc</strong></div>
              <div><span>Report</span><strong>Archive JSON, CSV, and MultiQC evidence</strong></div>
            </div>
            <p>dicomqc audits the candidate release; it does not modify the original imaging data.</p>
          </div>
        </section>

        <section className={styles.sections} aria-label="dicomqc capabilities">
          <div className={styles.grid}>
            {capabilities.map((item) => (
              <article className={styles.card} key={item.title}>
                <span>{item.label}</span>
                <h2>{item.title}</h2>
                <p>{item.text}</p>
              </article>
            ))}
          </div>
        </section>

        <section className={styles.sections} aria-label="Documentation paths">
          <p className={styles.sectionLabel}>Start here</p>
          <div className={styles.grid}>
            {guideLinks.map((guide) => (
              <Link className={styles.card} to={guide.to} key={guide.title}>
                <span>{guide.label}</span>
                <h2>{guide.title}</h2>
                <p>{guide.text}</p>
              </Link>
            ))}
          </div>
        </section>
      </main>
    </Layout>
  );
}
