# DICOMQC - Project Specification

## Vision

Develop an open-source tool for **quality control and validation of
DICOM metadata**, with a primary focus on verifying pseudonymization and
ensuring datasets are ready for research release.

This project is **not another anonymizer**.

Instead, it should independently verify that anonymization has been
correctly performed and generate reproducible reports suitable for
research pipelines.

------------------------------------------------------------------------

# Objectives

The software should:

-   Scan one or more DICOM studies.
-   Read metadata without loading pixel data whenever possible.
-   Detect personally identifiable information (PHI).
-   Validate anonymization policies.
-   Detect vendor-specific private tags.
-   Produce human-readable and machine-readable reports.
-   Integrate well into automated workflows.

The tool should never modify the original DICOM files.

------------------------------------------------------------------------

# Philosophy

Use existing, mature DICOM parsers instead of implementing a parser from
scratch.

The parser is an implementation detail.

The value of this project lies in:

-   metadata normalization
-   validation
-   reporting
-   policy engine
-   workflow integration

------------------------------------------------------------------------

# Initial Technology Stack

## Language

Python

## DICOM backend

pydicom

The backend must remain isolated behind an abstraction layer so that a
future Rust implementation (using dicom-rs) can replace it without
affecting the rest of the codebase.

Example:

``` python
class DicomBackend:
    def read_metadata(self, path):
        ...
```

------------------------------------------------------------------------

# Architecture

``` text
DICOM files
        │
        ▼
Backend (pydicom)
        │
        ▼
Normalized metadata model
        │
        ▼
Rule engine
        │
        ▼
Risk analysis
        │
        ▼
Reports
```

------------------------------------------------------------------------

# Project Structure

``` text
dicomqc/
    backend/
        pydicom_backend.py
    model/
        metadata.py
    rules/
        builtin.py
        policy.py
    reports/
        html.py
        json.py
        csv.py
    cli.py

tests/
docs/
```

------------------------------------------------------------------------

# Metadata Model

The backend should expose a normalized representation.

``` python
MetadataRecord(
    path="...",
    patient_id="...",
    study_uid="...",
    series_uid="...",
    manufacturer="SIEMENS",
    tags={
        "(0010,0010)": {
            "keyword": "PatientName",
            "vr": "PN",
            "value": "SUBJ001"
        }
    }
)
```

No other module should directly depend on pydicom.

------------------------------------------------------------------------

# Rule Engine

Rules operate on normalized metadata.

Each rule returns:

-   severity
-   message
-   affected tag
-   recommendation

Future policies should be configurable in YAML, for example:

``` yaml
PatientName:
  action: remove

PatientBirthDate:
  action: remove

PatientSex:
  action: keep
```

------------------------------------------------------------------------

# Reports

Produce:

-   HTML
-   JSON
-   CSV

Each finding should include:

-   file
-   tag
-   severity
-   explanation
-   recommendation

Summary example:

``` text
Files scanned: 432

Errors: 2
Warnings: 5

Passed: 425
Failed: 7
```

------------------------------------------------------------------------

# CLI

Basic:

``` bash
dicomqc scan study/
```

Future:

``` bash
dicomqc scan study/ \
    --policy policy.yaml \
    --html report.html \
    --json report.json \
    --csv report.csv
```

Exit codes:

-   0 = success
-   1 = warnings
-   2 = validation failure

------------------------------------------------------------------------

# Initial Validation Rules

Validate at least:

-   PatientName
-   PatientID
-   PatientBirthDate
-   PatientAddress
-   PatientTelephoneNumbers
-   InstitutionAddress
-   ReferringPhysicianName
-   OperatorsName
-   AccessionNumber

Also report:

-   private tags
-   manufacturer
-   modality
-   study UID
-   series UID

------------------------------------------------------------------------

# Design Principles

-   Modular
-   Strong typing
-   Testable
-   Backend-independent
-   Easily extensible
-   No hidden side effects

------------------------------------------------------------------------

# Non-Goals (Version 1)

Do **not**:

-   anonymize files
-   edit DICOM metadata
-   convert to NIfTI
-   process pixel data
-   perform face detection
-   implement DICOM networking

This project is strictly a metadata validation and QC framework.

------------------------------------------------------------------------

# Long-Term Roadmap

## Version 1

-   Python
-   pydicom backend
-   CLI
-   JSON reports
-   HTML reports
-   Built-in validation rules

## Version 2

-   YAML policies
-   Plugin system
-   Vendor-specific rule packs
-   Risk scoring

## Version 3

-   Optional Rust backend using dicom-rs
-   Faster scanning
-   Python bindings to Rust core

------------------------------------------------------------------------

# Guiding Principle

Become the equivalent of **FastQC** for DICOM metadata:

-   simple to use
-   reproducible
-   scriptable
-   CI-friendly
-   focused on validation rather than modification
