import Link from '@docusaurus/Link';
import Layout from '@theme/Layout';
import useBaseUrl from '@docusaurus/useBaseUrl';
import styles from './index.module.css';

const primaryLinks = [
  {label: 'Install', to: '/docs/usage/install'},
  {label: 'Quickstart', to: '/docs/usage/quickstart'},
  {label: 'Reports', to: '/docs/usage/reports'},
];

const auditOperations = [
  {
    label: '01 / Inspect',
    title: 'Read DICOM metadata',
    text: 'Discover files recursively and parse metadata without loading pixel data.',
  },
  {
    label: '02 / Evaluate',
    title: 'Apply explicit rules',
    text: 'Identify direct PHI fields, pseudonym-pattern failures, and private tags.',
  },
  {
    label: '03 / Record',
    title: 'Save the results',
    text: 'Write JSON, CSV, and MultiQC reports without copying raw DICOM values.',
  },
  {
    label: '04 / Integrate',
    title: 'Automate the check',
    text: 'Use exit codes to pass, review, or stop a data-processing pipeline.',
  },
];

const documentationPaths = [
  {
    title: 'Install dicomqc',
    text: 'Install the PyPI release, optional MultiQC support, or a source checkout.',
    to: '/docs/usage/install',
  },
  {
    title: 'Run an audit',
    text: 'Generate the demo, scan a directory, and interpret the result.',
    to: '/docs/usage/quickstart',
  },
  {
    title: 'Fix reported problems',
    text: 'Update the pseudonymization process with an external tool and run dicomqc again.',
    to: '/docs/usage/remediation',
  },
  {
    title: 'Review the architecture',
    text: 'Trace metadata through discovery, policy evaluation, and report generation.',
    to: '/docs/technical-details/architecture',
  },
  {
    title: 'Compare prior work',
    text: 'Understand how dicomqc relates to existing de-identification software.',
    to: '/docs/about/prior-work',
  },
];

export default function Home() {
  const objective = useBaseUrl('/img/dicomqc-objective.svg');

  return (
    <Layout
      title="dicomqc"
      description="Independent DICOM metadata quality control for research-release workflows">
      <main className={styles.page}>
        <section className={styles.hero}>
          <div className={styles.heroInner}>
            <div className={styles.heroCopy}>
              <p className={styles.kicker}>DICOM metadata quality control</p>
              <h1>dicomqc</h1>
              <p className={styles.claim}>
                Check DICOM metadata before sharing research data.
              </p>
              <p className={styles.lede}>
                Run dicomqc after pseudonymization or de-identification. It checks
                metadata for patient identifiers, unexpected pseudonym formats, and
                private tags, then writes JSON, CSV, and MultiQC reports. It never
                changes the DICOM files.
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
            <div className={styles.sectionHeading}>
              <p className={styles.sectionLabel}>Current checks</p>
              <h2 id="audit-surface-title">Metadata checks after de-identification</h2>
              <p>
                Use dicomqc on the files produced by any DICOM de-identification
                tool. The same checks can then be repeated for every provider and
                every version of a dataset.
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
              Version 0.1 does not pseudonymize or modify DICOM files, inspect
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
