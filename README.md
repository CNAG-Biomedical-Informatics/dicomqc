<div align="center">
  <a href="https://github.com/CNAG-Biomedical-Informatics/dicomqc">
    <img src="https://raw.githubusercontent.com/CNAG-Biomedical-Informatics/dicomqc/main/docs-site/static/img/dicomqc-logo.png"
         width="300" alt="dicomqc">
  </a>
  <p><em>Audit de-identified DICOM metadata for privacy risks</em></p>
</div>

[![Build](https://github.com/CNAG-Biomedical-Informatics/dicomqc/actions/workflows/build-and-test.yml/badge.svg)](https://github.com/CNAG-Biomedical-Informatics/dicomqc/actions/workflows/build-and-test.yml)
[![Documentation](https://github.com/CNAG-Biomedical-Informatics/dicomqc/actions/workflows/documentation.yml/badge.svg)](https://github.com/CNAG-Biomedical-Informatics/dicomqc/actions/workflows/documentation.yml)
[![PyPI](https://img.shields.io/pypi/v/dicomqc.svg)](https://pypi.org/project/dicomqc/)
[![Python](https://img.shields.io/pypi/pyversions/dicomqc.svg)](https://pypi.org/project/dicomqc/)
[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)

<p align="center">
  <a href="https://cnag-biomedical-informatics.github.io/dicomqc/">📚 Documentation</a> ·
  <a href="https://pypi.org/project/dicomqc/">📦 PyPI</a> ·
  <a href="https://cnag-biomedical-informatics.github.io/dicomqc/docs/usage/quickstart">🧪 Try a demo</a> ·
  <a href="CHANGELOG.md">📝 Changelog</a> ·
  <a href="LICENSE">⚖️ Apache-2.0</a>
</p>

---

**dicomqc** audits de-identified DICOM metadata for privacy risks.

It flags identifying fields, unexpected pseudonym formats, private tags, and
unreadable files. It writes JSON, CSV, and MultiQC-compatible reports without
copying raw DICOM tag values.

![How dicomqc audits metadata and writes reports.](docs-site/static/img/dicomqc-audit.svg)

dicomqc is **not an anonymizer**. It never modifies original DICOM files. If it
reports required changes, apply them with an external pseudonymization or
anonymization tool and rerun the audit.

## Get started

Install in a Python environment and try the synthetic demo:

```bash
pip install dicomqc
dicomqc demo
```

The demo creates `dicomqc-demo/` with synthetic DICOM files and sample reports.
See the [documentation](https://cnag-biomedical-informatics.github.io/dicomqc/)
for installation options, dataset comparisons, reports, and citation guidance.

## Author

Written by Manuel Rueda. GitHub repository:
<https://github.com/CNAG-Biomedical-Informatics/dicomqc>.

## Copyright and License

Copyright 2026 Manuel Rueda, CNAG.

dicomqc is distributed under the [Apache License 2.0](LICENSE).
