import Link from '@docusaurus/Link';
import Layout from '@theme/Layout';

export default function Home() {
  return (
    <Layout
      title="DICOMQC"
      description="Quality control and validation of DICOM metadata for research release">
      <main className="dicomqcHome">
        <section className="dicomqcHero">
          <p className="dicomqcKicker">DICOM metadata audit</p>
          <h1>DICOMQC</h1>
          <p>
            A policy-driven, standards-aware audit framework for validating DICOM
            de-identification and research-release readiness.
          </p>
          <div className="dicomqcActions">
            <Link className="button button--primary" to="/docs/usage/quickstart">
              Quick Start
            </Link>
            <Link className="button button--secondary" to="/docs/technical-details/architecture">
              Architecture
            </Link>
          </div>
        </section>
      </main>
    </Layout>
  );
}
