# MultiQC Example

This example generates synthetic DICOM files, runs dicomqc with MultiQC
custom-content output, and optionally renders a MultiQC HTML report.

From the repository root:

```bash
bash examples/multiqc/run_example.sh
```

Outputs are written under `examples/multiqc/output/`:

- `dicom/`: generated synthetic `.dcm` files
- `dicomqc/report.json`: dicomqc JSON report
- `dicomqc/findings.csv`: dicomqc CSV findings
- `dicomqc/dicomqc_mqc/`: MultiQC custom-content YAML files
- `multiqc_report.html`: rendered MultiQC report, if `multiqc` is installed

Generated outputs are ignored by git.
