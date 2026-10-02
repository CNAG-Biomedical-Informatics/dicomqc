---
title: Reports
---

# Reports

dicomqc v0.1 writes JSON, CSV, and MultiQC custom-content reports.

```bash
dicomqc scan study/ --json report.json --csv findings.csv --multiqc
```

## Redaction

Reports omit raw DICOM tag values. Findings and the tag list
show whether a value is absent, empty, or present, but not the observed value.

File paths and other report details may still identify people or datasets.
Review reports before sharing them.

## JSON

The JSON report includes:

- tool metadata
- selected profile
- summary counts
- scanned files and their metadata
- findings
- skipped files

## CSV

The CSV report contains one row per finding with:

- path
- rule ID
- profile ID
- severity
- tag and keyword
- value state
- message
- recommendation

## MultiQC

`--multiqc` writes a `dicomqc_mqc/` directory by default:

```bash
dicomqc scan study/ --multiqc
multiqc .
```

The directory contains small `*_mqc.yaml` custom-content files. MultiQC renders
these as dicomqc general statistics, a compact audit-status table, and a
findings table without raw tag values. Keep the JSON and CSV files as the audit
records. Use MultiQC to view the results alongside other QC reports.

Use a custom output directory when needed:

```bash
dicomqc scan study/ --multiqc reports/dicomqc_mqc
```

## Example Report

The CLI includes a reproducible demo that generates synthetic DICOM files and
writes dicomqc reports without raw tag values:

```bash
dicomqc demo --output-dir dicomqc-demo --force
```

If MultiQC is installed, render the custom-content bundle:

```bash
multiqc dicomqc-demo/dicomqc --outdir dicomqc-demo --force --config examples/multiqc/multiqc_config.yaml
```

The rendered report is written to:

```text
dicomqc-demo/multiqc_report.html
```

### Screenshots

![dicomqc sections rendered in a MultiQC report.](/img/multiqc-dicomqc-module.png)

![dicomqc release status table rendered in MultiQC.](/img/multiqc-dicomqc-release-status.png)

![dicomqc findings table rendered in MultiQC.](/img/multiqc-dicomqc-findings.png)
