<div align="center">
  <a href="https://github.com/CNAG-Biomedical-Informatics/dicomqc">
    <img src="https://raw.githubusercontent.com/CNAG-Biomedical-Informatics/dicomqc/main/docs-site/static/img/dicomqc-symbol.png"
         width="200" alt="dicomqc: imaging slices and metadata inspection">
  </a>
  <h1><img src="https://raw.githubusercontent.com/CNAG-Biomedical-Informatics/dicomqc/main/docs-site/static/img/dicomqc-wordmark.svg" width="240" height="64" alt="dicomqc"></h1>
  <p><em>Audit de-identified DICOM metadata for privacy risks</em></p>
</div>

[![Build](https://github.com/CNAG-Biomedical-Informatics/dicomqc/actions/workflows/build-and-test.yml/badge.svg)](https://github.com/CNAG-Biomedical-Informatics/dicomqc/actions/workflows/build-and-test.yml)
[![Documentation](https://github.com/CNAG-Biomedical-Informatics/dicomqc/actions/workflows/documentation.yml/badge.svg)](https://github.com/CNAG-Biomedical-Informatics/dicomqc/actions/workflows/documentation.yml)
[![PyPI](https://img.shields.io/pypi/v/dicomqc.svg)](https://pypi.org/project/dicomqc/)
[![Python](https://img.shields.io/pypi/pyversions/dicomqc.svg)](https://pypi.org/project/dicomqc/)
[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)

<p align="center">
  <a href="https://cnag-biomedical-informatics.github.io/dicomqc/">📚 Documentation</a> ·
  <a href="https://cnag-biomedical-informatics.github.io/dicomqc/docs/usage/desktop">Desktop app</a> ·
  <a href="https://pypi.org/project/dicomqc/">📦 PyPI</a> ·
  <a href="https://cnag-biomedical-informatics.github.io/dicomqc/docs/usage/quickstart">🧪 Try a demo</a> ·
  <a href="CHANGELOG.md">📝 Changelog</a> ·
  <a href="LICENSE">⚖️ Apache-2.0</a>
</p>

---

**dicomqc** audits de-identified DICOM metadata for privacy risks. The desktop
app is the recommended interface; the CLI supports advanced automation and
scripted workflows. Both use the same Python audit engine.

It flags identifying fields, unexpected pseudonym formats, private tags, and
unreadable files. It writes HTML, JSON, CSV, and MultiQC-compatible reports.
Findings omit raw tag values; the optional scanner inventory exports observed
labels and must be reviewed before sharing.

![How dicomqc audits metadata and writes reports.](https://raw.githubusercontent.com/CNAG-Biomedical-Informatics/dicomqc/main/docs-site/static/img/dicomqc-audit.svg)

dicomqc is **not an anonymizer**. It never modifies original DICOM files. If it
reports required changes, apply them with an external pseudonymization or
anonymization tool and rerun the audit.

## Get started

### Desktop app

Select DICOM files or folders and run an
audit. The desktop workspace keeps sources and searchable, renameable run
history beside **Setup**, **Policy**, **Findings**, and **Reports** views. The
Policy workspace creates, edits, and validates YAML project policies while
preserving the original file. Raw DICOM files
remain external and unchanged. **File > Save Project** stores settings, policy
copies, run history, logs, and reports together in a portable `.dicomqc` file.
Example runs and audits of your own data can belong to the same project.
The app manages working storage internally; export individual reports with **Save copy**.
Only one audit runs at a time. Large audits parallelize independent DICOM files;
the metadata-thread count is configurable under **Settings > Processing**.
Each run log records file count, elapsed processing time, average throughput,
and the configured thread count.

**Load example data** runs built-in scan, comparison, policy, UID,
scanner-inventory, and adjustable large-cohort examples without patient data.
The large cohort includes 250 deterministic privacy findings so pagination and
review workflows can be exercised.

![dicomqc desktop workspace with run history and an HTML report preview.](https://raw.githubusercontent.com/CNAG-Biomedical-Informatics/dicomqc/main/docs-site/static/img/desktop-workspace.png)

Download the Desktop app for Windows, macOS, or Linux from
[GitHub Releases](https://github.com/CNAG-Biomedical-Informatics/dicomqc/releases).
See [Install](https://cnag-biomedical-informatics.github.io/dicomqc/docs/usage/install)
for platform-specific instructions and [Desktop usage](https://cnag-biomedical-informatics.github.io/dicomqc/docs/usage/desktop)
for the audit workflow.
The app starts its audit service locally; no remote server is required.

### Command line

Install in a Python environment and try the synthetic demo:

```bash
pip install dicomqc
dicomqc demo
```

For a large dataset, `dicomqc scan study/ --threads 8` uses eight metadata
threads within that single audit. Internally, files are dispatched to batched
worker processes and merged deterministically. The default is four threads, or
fewer on smaller systems; small audits run serially when multiprocessing would
cost more than it saves. The maximum is the logical-processor count available
to dicomqc.

The demo creates `dicomqc-demo/` with synthetic DICOM files and sample reports.
See the [documentation](https://cnag-biomedical-informatics.github.io/dicomqc/)
for installation options, dataset comparisons, reports, and citation guidance.

## Citation

A manuscript describing **dicomqc** is in preparation. Until publication,
please cite the software using [CITATION.cff](CITATION.cff) and record the
version used in your analysis.

## Author

Written by Manuel Rueda. GitHub repository:
<https://github.com/CNAG-Biomedical-Informatics/dicomqc>.

## Copyright and License

Copyright 2026 Manuel Rueda, CNAG.

dicomqc is distributed under the [Apache License 2.0](LICENSE).
