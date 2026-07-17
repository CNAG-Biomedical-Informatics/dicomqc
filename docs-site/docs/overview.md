---
title: Overview
---

# dicomqc

<div class="dicomqcLead">
  <p>
    <strong>dicomqc</strong> is a policy-driven, standards-aware audit
    framework for validating DICOM metadata de-identification and
    research-release readiness.
  </p>
</div>

dicomqc validates DICOM metadata after pseudonymization or anonymization. It is
an independent audit layer for research-release readiness, not another DICOM
anonymizer.

<div class="dicomqcCardGrid">
  <div class="dicomqcCard">
    <span>Input</span>
    <h3>DICOM files and studies</h3>
    <p>Scan one file, one study directory, or a recursive release candidate.</p>
  </div>
  <div class="dicomqcCard">
    <span>Scope</span>
    <h3>Metadata-only audit</h3>
    <p>Read release-relevant tags without loading pixel data or modifying files.</p>
  </div>
  <div class="dicomqcCard">
    <span>Rules</span>
    <h3>PHI and private-tag checks</h3>
    <p>Detect direct PHI fields, risky pseudonym fields, and private DICOM tags.</p>
  </div>
  <div class="dicomqcCard">
    <span>Evidence</span>
    <h3>JSON, CSV, and MultiQC</h3>
    <p>Produce reproducible audit artifacts for automated research workflows.</p>
  </div>
</div>

v0.1 is intentionally conservative. It provides a usable metadata scanner and
rule engine, while leaving standards-specific profiles and plugin discovery for
later releases.

## What dicomqc does not do

<div class="dicomqcNote">
  <p>
    dicomqc never modifies original DICOM files. It also does not claim DICOM
    PS3.15, BIDS, HIPAA, or GDPR compliance in v0.1. Those standards are future
    profile targets that require audited rule packs.
  </p>
</div>

When dicomqc reports required changes, apply them with an external
pseudonymization or anonymization workflow and rerun the audit. See
[Remediation](usage/remediation.md) for practical examples.

For the initial large-scale multiple sclerosis MRI use case, see
[MS MRI Workflow](usage/ms-mri-workflow.md).
