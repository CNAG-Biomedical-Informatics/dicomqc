---
title: Install
---

# Install

dicomqc provides a desktop app and a command-line interface, using the same
Python audit engine.

- **Desktop app:** follow the [desktop source-build instructions](desktop.md#build-from-source).
  Installers have not been published.
- **CLI:** install from [PyPI](https://pypi.org/project/dicomqc/) with Python 3.10
  or newer, as shown below. The PyPI package does not install the desktop app.

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

dicomqc writes standalone HTML reports without extra packages. Install MultiQC
only if you want to combine dicomqc results with other QC reports:

```bash
python -m pip install multiqc
```

See the [scan walkthrough](quickstart.md#view-the-same-scan-in-multiqc)
for the rendering command and its matching report screenshots.

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

For the complete suite, including the optional local API, install
`".[test,api,api-test]"`. The [desktop app](desktop.md) has separate native build
requirements; installing the PyPI package provides the CLI.

## External DICOM tools

DCMTK, Orthanc, and other pseudonymization or remediation tools are not dicomqc
dependencies. Install them separately only when they are part of the local
DICOM transformation workflow. dicomqc itself remains read-only.

Continue with the [Quickstart](quickstart.md) to generate synthetic DICOM data
and run the first audit.
