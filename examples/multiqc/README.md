# MultiQC Example

Generate the built-in synthetic DICOM demo:

```bash
dicomqc demo
```

Render the MultiQC custom-content files if MultiQC is installed:

```bash
multiqc dicomqc-demo/dicomqc --outdir dicomqc-demo --force --config examples/multiqc/multiqc_config.yaml
```

Outputs are written under `dicomqc-demo/`:

- `dicom/`: generated synthetic `.dcm` files
- `dicomqc/report.json`: dicomqc JSON report
- `dicomqc/findings.csv`: dicomqc CSV findings
- `dicomqc/dicomqc_mqc/`: MultiQC custom-content YAML files
- `multiqc_report.html`: rendered MultiQC report, if MultiQC is installed

Generated outputs are ignored by git.
