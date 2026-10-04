import Link from '@docusaurus/Link';
import Layout from '@theme/Layout';
import useBaseUrl from '@docusaurus/useBaseUrl';
import styles from './index.module.css';

const primaryLinks = [
  {label: 'Desktop app', to: '/docs/usage/desktop'},
  {label: 'CLI', to: '/docs/usage/quickstart'},
  {label: 'Audit modes', to: '/docs/usage/audit-modes'},
  {label: 'Video tutorials', to: '/docs/video-tutorials'},
];

const auditOperations = [
  {
    label: '01 / Inspect',
    title: 'Read DICOM metadata',
    text: 'Discover files recursively and parse metadata without loading pixel data.',
  },
  {
    label: '02 / Evaluate',
    title: 'Check for privacy risks',
    text: 'Identify direct PHI fields, pseudonym-pattern failures, and private tags.',
  },
  {
    label: '03 / Record',
    title: 'Save the results',
    text: 'Open an offline HTML report, save JSON or CSV, or view results in MultiQC.',
  },
  {
    label: '04 / Integrate',
    title: 'Automate with the CLI',
    text: 'Use exit codes to continue a workflow, request review, or stop on errors.',
  },
];

const documentationPaths = [
  {
    title: 'Use the desktop app',
    text: 'Run a privacy audit, review findings, and save runs and reports in one project.',
    to: '/docs/usage/desktop',
  },
  {
    title: 'Install dicomqc',
    text: 'Install the PyPI release, optional MultiQC support, or a source checkout.',
    to: '/docs/usage/install',
  },
  {
    title: 'Choose an audit mode',
    text: 'Inspect one DICOM dataset, or compare source DICOM files with their processed copies.',
    to: '/docs/usage/audit-modes',
  },
  {
    title: 'Fix reported problems',
    text: 'Update the pseudonymization process with an external tool and run dicomqc again.',
    to: '/docs/usage/remediation',
  },
  {
    title: 'Review the architecture',
    text: 'See how dicomqc reads metadata, checks it, and writes reports.',
    to: '/docs/technical-details/architecture',
  },
  {
    title: 'Compare prior work',
    text: 'Compare dicomqc with other DICOM quality-control tools.',
    to: '/docs/about/prior-work',
  },
];

export default function Home() {
  const objective = useBaseUrl('/img/dicomqc-objective.svg');

  return (
    <Layout
      title="dicomqc"
      description="dicomqc audits de-identified DICOM metadata for privacy risks">
      <main className={styles.page}>
        <section className={styles.hero}>
          <div className={styles.heroInner}>
            <div className={styles.heroCopy}>
              <p className={styles.kicker}>DICOM metadata quality control</p>
              <div className={styles.brand}>
                <img src={useBaseUrl('/img/dicomqc-symbol.png')} width="176" height="176" alt="" />
                <h1><span className={styles.brandName}>dicom</span><span className={styles.brandQc}>qc</span></h1>
              </div>
              <p className={styles.claim}>
                Check DICOM metadata before sharing research data.
              </p>
              <p className={styles.lede}>
                dicomqc audits de-identified DICOM metadata for privacy risks.
                It flags patient identifiers, unexpected pseudonym formats, and
                private tags, and writes HTML, JSON, CSV, and MultiQC reports.
                Use the desktop app for interactive audits or the CLI for automation.
                It never changes the DICOM files.
              </p>
              <nav className={styles.primaryLinks} aria-label="Primary documentation">
                {primaryLinks.map((link) => (
                  <Link to={link.to} key={link.to}>
                    {link.label}
                    <span aria-hidden="true">&#8594;</span>
                  </Link>
                ))}
              </nav>
            </div>

            <figure className={styles.objectiveFigure}>
              <img
                src={objective}
                alt="Pseudonymized DICOM files are checked by dicomqc, which writes JSON, CSV, and MultiQC reports"
              />
              <figcaption>
                The de-identification tool changes the files; dicomqc checks the result.
              </figcaption>
            </figure>
          </div>
        </section>

        <section className={styles.auditSection} aria-labelledby="audit-surface-title">
          <div className={styles.sectionInner}>
            <picture>
              <source media="(max-width: 760px)" srcSet={useBaseUrl('/img/dicomqc-audit-mobile.svg')} />
              <img className={styles.workflowImage} src={useBaseUrl('/img/dicomqc-audit.svg')}
                alt="dicomqc flags a birth date and private tags in fictional DICOM metadata. An external tool fixes a new copy, then a second audit passes. Pixels are not inspected." />
            </picture>
          </div>
          <div className={styles.sectionInner}>
            <div className={styles.sectionHeading}>
              <p className={styles.sectionLabel}>Current checks</p>
              <h2 id="audit-surface-title">Metadata checks after de-identification</h2>
              <p>
                Run the same checks on files from different providers or
                de-identification tools, and repeat them when a dataset changes.
              </p>
            </div>

            <div className={styles.operationGrid}>
              {auditOperations.map((operation) => (
                <article className={styles.operation} key={operation.title}>
                  <span>{operation.label}</span>
                  <h3>{operation.title}</h3>
                  <p>{operation.text}</p>
                </article>
              ))}
            </div>
          </div>
        </section>

        <section className={styles.boundarySection} aria-labelledby="scope-title">
          <div className={styles.boundaryInner}>
            <div>
              <p className={styles.sectionLabel}>Limits</p>
              <h2 id="scope-title">What dicomqc does not check</h2>
            </div>
            <p>
              dicomqc does not pseudonymize or modify DICOM files, inspect
              pixels or facial features, or certify DICOM PS3.15, BIDS, HIPAA, or
              GDPR compliance. A qualified reviewer must still decide whether the
              data can be shared.
            </p>
          </div>
        </section>

        <section className={styles.docsSection} aria-labelledby="documentation-title">
          <div className={styles.sectionInner}>
            <div className={styles.sectionHeading}>
              <p className={styles.sectionLabel}>Documentation</p>
              <h2 id="documentation-title">Choose a task</h2>
            </div>
            <div className={styles.documentationList}>
              {documentationPaths.map((item) => (
                <Link to={item.to} className={styles.documentationLink} key={item.to}>
                  <span>
                    <strong>{item.title}</strong>
                    <small>{item.text}</small>
                  </span>
                  <span className={styles.linkArrow} aria-hidden="true">&#8594;</span>
                </Link>
              ))}
            </div>
          </div>
        </section>
      </main>
    </Layout>
  );
}
