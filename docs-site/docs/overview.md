---
title: Overview
---

# dicomqc

import useBaseUrl from '@docusaurus/useBaseUrl';

dicomqc audits de-identified DICOM metadata for privacy risks.
It reports patient-identifying fields, unexpected pseudonym
formats, private tags, and files that could not be read. It never changes the
DICOM files.

Use the [desktop app](usage/desktop.md) for file selection, run history, and
report review, or the CLI for scripted workflows. Both use the same audit engine.

<picture>
  <source media="(max-width: 760px)" srcSet={useBaseUrl('/img/dicomqc-audit-mobile.svg')} />
  <img src={useBaseUrl('/img/dicomqc-audit.svg')} alt="A fictional DICOM metadata audit flags a birth date and private tags. After external fixes, a rescan passes. Pixels and sharing still need review." />
</picture>

:::info Project status

dicomqc includes a metadata-only scanner, built-in privacy checks,
offline HTML reports, JSON and CSV reports, and
MultiQC-compatible scan output.
[Dataset comparison](usage/compare.md) checks file completeness and
patient pseudonym consistency between source and de-identified files.
[Project policies](usage/policies.md) add site-specific metadata requirements.
[Scanner inventory](usage/vendor-summary.md) optionally lists declared scanner
and software labels and private creator blocks. These labels may contain
identifying information; review them before sharing.
[UID integrity](usage/uid-integrity.md) checks identifier syntax, role reuse,
and conflicting study/series relationships.

:::

## Use the desktop app

In **Setup**, select files or folders and choose an **Output folder**. Run an
audit, then select **Findings** or **Reports** to review its results. Sources and
searchable run history remain in the sidebar. Each audit has a separate output
subfolder; changing the output folder preserves selected inputs.

**Explore with synthetic data** runs five built-in examples without patient data.
The app and its audit service run locally. See [Desktop app](usage/desktop.md)
for source-build instructions; installers have not been published.

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

A de-identification tool can leave identifying metadata behind or miss files.
Run dicomqc on its output to check for these problems. You can use the same
checks with different tools and data providers.

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
- **Value state** says whether a tag value is present, empty, or absent.
  Findings include this state without copying the raw tag value.
- **Private tag** means a vendor- or organization-defined DICOM data element.
  Private tags are not automatically safe or unsafe; they require review.

## Current checks

The built-in `research-release-v0.1` profile checks for:

- metadata fields containing direct identifiers;
- patient identifiers that do not match the expected pseudonym format;
- private DICOM tags that require review;
- unreadable or skipped input files.

[YAML policies](usage/policies.md) add requirements
for empty fields, required values, approved descriptions, and patient-ID formats.
They do not replace the built-in checks.

Reports identify the file, rule, tag, severity, and recommended action for each
finding. They also include summary counts. Findings omit observed tag values;
see [what stays out of reports](technical-details/architecture.mdx#what-stays-out-of-reports) before sharing.

:::caution Limits

dicomqc does not modify files, inspect pixel data or facial features, or
certify compliance with DICOM PS3.15, BIDS, HIPAA, or GDPR. A qualified reviewer
must still decide whether the data can be shared.

:::

## Find what you need

| Task | Documentation |
| --- | --- |
| Install the CLI | [Install](usage/install.md) |
| Select files and review audits in the desktop app | [Desktop app](usage/desktop.md) |
| Generate the demo and run an audit | [Quickstart](usage/quickstart.md) |
| Compare source and de-identified datasets | [Compare datasets](usage/compare.md) |
| Add project-specific checks | [Project policies](usage/policies.md) |
| Inspect scanner labels and private creator blocks | [Scanner inventory](usage/vendor-summary.md) |
| Check identifiers and study/series relationships | [UID integrity](usage/uid-integrity.md) |
| Audit a large MS MRI collection | [MS MRI workflow](usage/ms-mri-workflow.mdx) |
| Review a scan in HTML or MultiQC | [Scan walkthrough](usage/quickstart.md#open-the-reports) |
| Fix reported problems with external tools | [Remediation](usage/remediation.mdx) |
| Understand the implementation | [Architecture](technical-details/architecture.mdx) |
| Compare related software | [Prior work](about/prior-work.md) |

## Documentation map

- **Use** covers installation, routine audits, reporting, and remediation.
- **Technical Details** explains the implementation and planned features.
- **Reference** lists commands, options, and exit codes.
- **About** records citation guidance, prior work, and the project disclaimer.

Project development and issue tracking take place in the
[dicomqc GitHub repository](https://github.com/CNAG-Biomedical-Informatics/dicomqc).
