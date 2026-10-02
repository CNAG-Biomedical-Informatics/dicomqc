---
title: Overview
---

# dicomqc

import useBaseUrl from '@docusaurus/useBaseUrl';

dicomqc audits de-identified DICOM metadata for privacy risks.
It reports patient-identifying fields, unexpected pseudonym
formats, private tags, and files that could not be read. It never changes the
DICOM files.

<picture>
  <source media="(max-width: 760px)" srcSet={useBaseUrl('/img/dicomqc-audit-mobile.svg')} />
  <img src={useBaseUrl('/img/dicomqc-audit.svg')} alt="A fictional DICOM metadata audit flags a birth date and private tags. After external fixes, a rescan passes. Pixels and sharing still need review." />
</picture>

:::info Project status

This documentation covers **v0.2.0**. It includes a metadata-only scanner,
built-in privacy checks, offline HTML reports, JSON and CSV reports, and
MultiQC-compatible scan output.
The new [dataset comparison](usage/compare.md) checks file completeness and
patient pseudonym consistency between source and de-identified files.
Standards-specific checks and plugins are planned for later releases.

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
  Reports include this state without copying the raw tag value.
- **Private tag** means a vendor- or organization-defined DICOM data element.
  Private tags are not automatically safe or unsafe; they require review.

## Current checks

The built-in `research-release-v0.1` profile checks for:

- metadata fields containing direct identifiers;
- patient identifiers that do not match the expected pseudonym format;
- private DICOM tags that require review;
- unreadable or skipped input files.

Reports identify the file, rule, tag, severity, and recommended action for each
finding. They also include summary counts. Raw DICOM tag values are omitted.

:::caution Limits

dicomqc v0.2 does not modify files, inspect pixel data or facial features, or
certify compliance with DICOM PS3.15, BIDS, HIPAA, or GDPR. A qualified reviewer
must still decide whether the data can be shared.

:::

## Find what you need

| Task | Documentation |
| --- | --- |
| Install the CLI | [Install](usage/install.md) |
| Generate the demo and run an audit | [Quickstart](usage/quickstart.md) |
| Compare source and de-identified datasets | [Compare datasets](usage/compare.md) |
| Audit a large MS MRI collection | [MS MRI workflow](usage/ms-mri-workflow.mdx) |
| Read reports and view them in MultiQC | [Reports](usage/reports.md) |
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
