---
title: Install
---

# Install

dicomqc requires Python 3.10 or newer. Install the published package from
[PyPI](https://pypi.org/project/dicomqc/) for normal use.

## Install from PyPI

Create an isolated environment so dicomqc and its dependencies do not alter the
system Python installation:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install dicomqc
```

Verify the installed command and version:

```bash
dicomqc --version
```

Upgrade an existing installation with:

```bash
python -m pip install --upgrade dicomqc
```

## Optional MultiQC installation

dicomqc can write MultiQC-compatible custom content without MultiQC being
installed. Install MultiQC when an interactive HTML report is required:

```bash
python -m pip install multiqc
```

See [Reports](reports.md) for report-generation commands and the example
configuration.

## Install from source

From a repository checkout, install dicomqc and its runtime dependencies in
editable mode:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e .
```

Contributors who need pytest and coverage tooling can install the `test`
optional dependency group:

```bash
python -m pip install -e ".[test]"
```

The `test` extra is not needed for normal use.

## External DICOM tools

DCMTK, Orthanc, and other pseudonymization or remediation tools are not dicomqc
dependencies. Install them separately only when they are part of the local
DICOM transformation workflow. dicomqc itself remains read-only.

Continue with the [Quickstart](quickstart.md) to generate synthetic DICOM data
and run the first audit.
