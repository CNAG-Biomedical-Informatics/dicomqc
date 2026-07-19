---
title: Overview
---

# dicomqc

dicomqc is a policy-driven audit framework for evaluating DICOM metadata after
pseudonymization or de-identification. It provides an independent quality-control
step between an external transformation workflow and a proposed research
release.

:::info Project status

The current package is **v0.1.0** and is available from
[PyPI](https://pypi.org/project/dicomqc/). This release implements a
metadata-only scanner, one built-in research-release profile, JSON and CSV
reports, and MultiQC-compatible output. Standards-specific rule packs and a
plugin system remain planned work.

:::

## Primary interface

The command-line interface is the primary user interface. A minimal audit reads
a file or directory recursively and prints a summary:

```bash
dicomqc scan candidate_release/
```

Use `--json`, `--csv`, and `--multiqc` to retain machine-readable evidence. Exit
codes distinguish a pass (`0`), findings requiring review (`1`), and errors or
skipped files (`2`). See the [CLI reference](reference/cli.md) for all options.

## Why audit after de-identification?

De-identification software transforms DICOM data. A successful tool invocation
does not, by itself, show which release criteria were evaluated, whether files
were skipped, or what evidence should accompany the dataset. dicomqc keeps that
assessment separate so the same policy can be applied repeatedly across tools,
providers, and release iterations.

This separation also creates a practical remediation loop:

1. Preserve source DICOM under the project data-governance controls.
2. Pseudonymize or de-identify a working copy with an external tool.
3. Audit the candidate output with dicomqc.
4. Review findings and update the transformation configuration.
5. Rerun the audit and archive the final evidence with the release record.

## Current checks

The built-in `research-release-v0.1` profile evaluates:

- direct PHI-bearing metadata fields;
- whether configured patient identifiers resemble pseudonyms;
- private DICOM tags that require review;
- unreadable or skipped input files.

Reports include structured finding metadata, value states, file context, and
aggregate counts. They do not serialize raw DICOM tag values.

:::caution Interpretation boundary

dicomqc does not modify files, inspect pixel data or facial features, or certify
DICOM PS3.15, BIDS, HIPAA, or GDPR compliance in v0.1. Its output supports
technical and institutional review; it does not replace either.

:::

## Start by task

| Task | Documentation |
| --- | --- |
| Install the CLI | [Install](usage/install.md) |
| Generate the demo and run an audit | [Quickstart](usage/quickstart.md) |
| Audit a large MS MRI collection | [MS MRI workflow](usage/ms-mri-workflow.mdx) |
| Interpret and aggregate outputs | [Reports](usage/reports.md) |
| Apply findings with external tools | [Remediation](usage/remediation.mdx) |
| Understand implementation boundaries | [Architecture](technical-details/architecture.mdx) |
| Compare related software | [Prior work](about/prior-work.md) |

## Documentation map

- **Use** covers installation, routine audits, reporting, and remediation.
- **Technical Details** documents the current architecture and planned extension
  points.
- **Reference** defines the command-line contract.
- **About** records citation guidance, prior work, and the project disclaimer.

Project development and issue tracking take place in the
[dicomqc GitHub repository](https://github.com/CNAG-Biomedical-Informatics/dicomqc).
