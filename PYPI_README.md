<div align="center">
  <img src="https://raw.githubusercontent.com/CNAG-Biomedical-Informatics/dicomqc/main/docs-site/static/img/dicomqc-symbol.png"
       width="160" alt="dicomqc: imaging slices and metadata inspection">
  <h1>dicomqc</h1>
  <p><em>Audit de-identified DICOM metadata for privacy risks</em></p>
</div>

[![PyPI](https://img.shields.io/pypi/v/dicomqc.svg)](https://pypi.org/project/dicomqc/)
[![Python](https://img.shields.io/pypi/pyversions/dicomqc.svg)](https://pypi.org/project/dicomqc/)
[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://github.com/CNAG-Biomedical-Informatics/dicomqc/blob/main/LICENSE)

**dicomqc** is a read-only command-line tool for auditing de-identified DICOM
metadata. It flags identifying fields, unexpected pseudonym formats, private
tags, unreadable files, and consistency problems between source and processed
datasets. Reports are available as HTML, JSON, CSV, and MultiQC-compatible
output.

dicomqc does not anonymize files or modify the input dataset. Apply required
changes with a DICOM anonymization or pseudonymization tool, then rerun the
audit.

## Install

dicomqc requires Python 3.10 or newer. Install it in an isolated environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install dicomqc
```

## Try the synthetic demo

```bash
dicomqc demo
```

The command creates `dicomqc-demo/` with synthetic DICOM files and example
HTML, JSON, CSV, and MultiQC input files. Findings are intentional, so the demo
reports a non-zero audit result.

## Audit a dataset

```bash
dicomqc scan candidate-dicom/ --html audit.html --json audit.json --csv findings.csv
```

Use a project policy for site-specific metadata rules:

```bash
dicomqc scan candidate-dicom/ --policy policy.yaml --html audit.html
```

For large collections, `--threads` controls parallel metadata readers within a
single audit:

```bash
dicomqc scan candidate-dicom/ --threads 8 --html audit.html
```

## Compare source and processed datasets

```bash
dicomqc compare source-dicom/ candidate-dicom/ \
  --manifest pairs.csv \
  --html comparison.html \
  --json comparison.json \
  --csv comparison.csv
```

The pairing manifest has `source,candidate` columns containing paths relative
to their respective dataset directories. Comparison checks file coverage and
patient pseudonym consistency, then applies privacy checks to readable paired
candidate files.

## MultiQC

Install MultiQC separately when you want to combine dicomqc with other QC
results:

```bash
python -m pip install multiqc
dicomqc demo
multiqc dicomqc-demo/dicomqc --outdir dicomqc-demo --force
```

## Documentation and Desktop

See the [documentation](https://cnag-biomedical-informatics.github.io/dicomqc/)
for audit modes, policy syntax, report interpretation, and remediation
workflows. A Desktop application for Windows, macOS, and Linux is available
from [GitHub Releases](https://github.com/CNAG-Biomedical-Informatics/dicomqc/releases).

Please cite the software using
[CITATION.cff](https://github.com/CNAG-Biomedical-Informatics/dicomqc/blob/main/CITATION.cff)
and record the version used in your analysis.
