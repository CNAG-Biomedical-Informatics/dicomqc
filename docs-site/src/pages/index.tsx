import Link from '@docusaurus/Link';
import Layout from '@theme/Layout';
import useBaseUrl from '@docusaurus/useBaseUrl';
import styles from './index.module.css';

const primaryLinks = [
  {label: 'Quickstart', to: '/docs/usage/quickstart'},
  {label: 'MS MRI workflow', to: '/docs/usage/ms-mri-workflow'},
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
    title: 'Produce review evidence',
    text: 'Write JSON, CSV, and MultiQC outputs without reporting raw DICOM values.',
  },
  {
    label: '04 / Integrate',
    title: 'Drive pipeline decisions',
    text: 'Use stable exit codes and structured findings in repeatable release workflows.',
  },
];

const documentationPaths = [
  {
    title: 'Run an audit',
    text: 'Install the package, scan a directory, and interpret the result.',
    to: '/docs/usage/quickstart',
  },
  {
    title: 'Plan remediation',
    text: 'Apply findings with an external DICOM transformation tool and audit again.',
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
                Independent metadata audit for DICOM research releases.
              </p>
              <p className={styles.lede}>
                A read-only command-line framework that evaluates candidate DICOM
                data after external pseudonymization or de-identification. It turns
                explicit policy checks into reviewable JSON, CSV, and MultiQC
                evidence.
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
                alt="Candidate DICOM passes through an independent dicomqc metadata audit to produce review evidence"
              />
              <figcaption>
                Transformation and audit remain separate, repeatable steps.
              </figcaption>
            </figure>
          </div>
        </section>

        <section className={styles.auditSection} aria-labelledby="audit-surface-title">
          <div className={styles.sectionInner}>
            <div className={styles.sectionHeading}>
              <p className={styles.sectionLabel}>Current audit surface</p>
              <h2 id="audit-surface-title">A focused metadata control point</h2>
              <p>
                dicomqc evaluates the output of a transformation workflow. Keeping
                that check independent makes release criteria visible, testable,
                and reproducible across tools and data providers.
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
              <p className={styles.sectionLabel}>Scope boundary</p>
              <h2 id="scope-title">Evidence, not transformation</h2>
            </div>
            <p>
              Version 0.1 does not pseudonymize or modify DICOM files, inspect
              pixels or facial features, or certify DICOM PS3.15, BIDS, HIPAA, or
              GDPR compliance. Findings support technical and institutional review;
              they do not replace it.
            </p>
          </div>
        </section>

        <section className={styles.docsSection} aria-labelledby="documentation-title">
          <div className={styles.sectionInner}>
            <div className={styles.sectionHeading}>
              <p className={styles.sectionLabel}>Documentation</p>
              <h2 id="documentation-title">Follow the task at hand</h2>
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
