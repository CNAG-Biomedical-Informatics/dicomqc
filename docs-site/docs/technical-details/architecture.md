---
title: Architecture
---

# Architecture

DICOMQC separates DICOM parsing from validation and reporting.

```text
DICOM files
        |
        v
Backend
        |
        v
Normalized metadata model
        |
        v
Rule engine
        |
        v
Reports
```

## Backend boundary

The pydicom backend is isolated behind a small protocol:

```python
class DicomBackend:
    def read_metadata(self, path):
        ...
```

Other modules operate on normalized metadata records and do not import pydicom.
This keeps the project open to future backends, including a possible Rust-based
reader.

## Normalized model

Each record contains file-level metadata such as manufacturer, modality, study
UID, and series UID, plus normalized tag records with:

- tag number
- keyword
- VR
- private-tag flag
- redaction-safe value state

Raw values may be used internally by rules, but reports should not expose them.
