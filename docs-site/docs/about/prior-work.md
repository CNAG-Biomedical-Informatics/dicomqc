---
title: Prior Work
---

# Prior Work

DICOMQC should improve on existing DICOM metadata QC efforts rather than overlap
with them. Related projects identified during initial repository discovery
include:

| Project | Focus | Relationship to DICOMQC |
| --- | --- | --- |
| [`SPMIC-UoN/xnat-dicomqc`](https://github.com/SPMIC-UoN/xnat-dicomqc) | XNAT container script for simple configurable tag-based QC on scan DICOMs. | DICOMQC should remain usable outside XNAT and provide a typed Python API, reproducible reports, and future policy/profile extensibility. |
| [`IUSCA/SQAN`](https://github.com/IUSCA/SQAN) | Scalable Quality Assurance for Neuroimaging: DICOM metadata ETL, logging, and web portal-based QC verification. | DICOMQC should stay lightweight and pipeline-friendly while focusing on de-identification validation and research-release audit evidence. |

## Positioning

DICOMQC is not intended to be a replacement for site QC platforms, XNAT-based
workflows, anonymizers, or BIDS validators. Its core value should be an
independent, backend-neutral audit layer that can answer:

- whether a declared DICOM metadata release policy passed
- which tags created release risk
- what evidence can be archived without exposing raw PHI
- which standards-aware profiles or institutional policies were applied

This page should be updated as more related tools are identified.
