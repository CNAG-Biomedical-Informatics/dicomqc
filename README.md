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
  <a href="https://cnag-biomedical-informatics.github.io/dicomqc/">Documentation</a> ·
  <a href="https://cnag-biomedical-informatics.github.io/dicomqc/docs/usage/desktop">Desktop app</a> ·
  <a href="https://pypi.org/project/dicomqc/">PyPI</a> ·
  <a href="CHANGELOG.md">Changelog</a> ·
  <a href="LICENSE">Apache-2.0</a>
</p>

---

**dicomqc** audits de-identified DICOM metadata before research release. It
detects privacy risks and compares source and de-identified datasets for file
completeness and pseudonym consistency. Reports are available as HTML, JSON,
CSV, and MultiQC-compatible output.

![How dicomqc audits metadata and writes reports.](https://raw.githubusercontent.com/CNAG-Biomedical-Informatics/dicomqc/main/docs-site/static/img/dicomqc-audit.svg)

> **dicomqc is not an anonymizer.** It never modifies DICOM files. Apply any
> required changes with a dedicated pseudonymization tool, then audit the
> resulting dataset again.

## Use dicomqc

The **Desktop app** is the recommended interface for interactive review. The
**CLI** supports scripted and automated workflows. Both use the same audit
engine.

- [Install the Desktop app or CLI](https://cnag-biomedical-informatics.github.io/dicomqc/docs/usage/install)
- [Use the Desktop app](https://cnag-biomedical-informatics.github.io/dicomqc/docs/usage/desktop)
- [Use the CLI](https://cnag-biomedical-informatics.github.io/dicomqc/docs/usage/cli)
- [Read the complete documentation](https://cnag-biomedical-informatics.github.io/dicomqc/)

## Citation

A manuscript describing **dicomqc** is in preparation. Until publication,
please cite the software using [CITATION.cff](CITATION.cff) and record the
version used in your analysis.

## License

Copyright 2026 Manuel Rueda, CNAG.

dicomqc is distributed under the [Apache License 2.0](LICENSE).
