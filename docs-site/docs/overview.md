---
title: Overview
---

# dicomqc

dicomqc checks DICOM metadata after files have been pseudonymized or
de-identified. It reports patient-identifying fields, unexpected pseudonym
formats, private tags, and files that could not be read. It never changes the
DICOM files.

:::info Project status

The current package is **v0.1.0** and is available from
[PyPI](https://pypi.org/project/dicomqc/). It includes a metadata-only scanner,
one built-in set of checks, JSON and CSV reports, and MultiQC-compatible output.
Checks based directly on specific standards and support for plugins are planned,
but are not included in this release.

:::

## Run from the command line

Give `dicomqc scan` one DICOM file or a directory. Directories are scanned
recursively:

```bash
dicomqc scan candidate_release/
```

Use `--json`, `--csv`, and `--multiqc` to save reports. Exit codes distinguish a
pass (`0`), warnings that require review (`1`), and errors or unreadable files
(`2`). See the [CLI reference](reference/cli.md) for all options.

## Why audit after de-identification?

Completing a de-identification command does not prove that every file was
processed or that the result meets the project's rules. dicomqc performs a
separate check, so one set of rules can be applied to output from different
tools and data providers.

The recommended process is:

1. Preserve the source DICOM files under restricted access.
2. Pseudonymize or de-identify a working copy with an external tool.
3. Check the resulting files with dicomqc.
4. Review the findings and correct the external tool's configuration.
5. Generate the files again, rerun dicomqc, and retain the final reports.

## Terminology

- **De-identification** is the broader process of reducing the risk that a
  person can be identified from the data.
- **Pseudonymization** replaces direct identifiers with a code. The data can
  still be linked to a person by someone who holds the separate linkage file.
- **PHI/PII** means identifying or sensitive personal information. Although PHI
  is a term from US health-privacy law, dicomqc uses it in rule names for
  identifiable DICOM metadata.
- **Redaction-safe report** means that dicomqc reports whether a tag value is
  present, empty, or absent without copying the raw value into the report.
- **Private tag** means a vendor- or organization-defined DICOM data element.
  Private tags are not automatically safe or unsafe; they require review.

## Current checks

The built-in `research-release-v0.1` profile evaluates:

- direct PHI-bearing metadata fields;
- whether configured patient identifiers resemble pseudonyms;
- private DICOM tags that require review;
- unreadable or skipped input files.

Reports identify the file, rule, tag, severity, and recommended action for each
finding. They also include summary counts. Raw DICOM tag values are omitted.

:::caution Limits

dicomqc v0.1 does not modify files, inspect pixel data or facial features, or
certify compliance with DICOM PS3.15, BIDS, HIPAA, or GDPR. A qualified reviewer
must still decide whether the data can be shared.

:::

## Start by task

| Task | Documentation |
| --- | --- |
| Install the CLI | [Install](usage/install.md) |
| Generate the demo and run an audit | [Quickstart](usage/quickstart.md) |
| Audit a large MS MRI collection | [MS MRI workflow](usage/ms-mri-workflow.mdx) |
| Interpret and aggregate outputs | [Reports](usage/reports.md) |
| Apply findings with external tools | [Remediation](usage/remediation.mdx) |
| Understand the implementation | [Architecture](technical-details/architecture.mdx) |
| Compare related software | [Prior work](about/prior-work.md) |

## Documentation map

- **Use** covers installation, routine audits, reporting, and remediation.
- **Technical Details** documents the current architecture and planned extension
  points.
- **Reference** defines the command-line contract.
- **About** records citation guidance, prior work, and the project disclaimer.

Project development and issue tracking take place in the
[dicomqc GitHub repository](https://github.com/CNAG-Biomedical-Informatics/dicomqc).
