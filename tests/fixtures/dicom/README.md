# Synthetic DICOM Fixtures

This directory is reserved for synthetic DICOM fixtures used during dicomqc
development.

Generated `.dcm` files are intentionally ignored by git. Recreate them with:

```bash
python scripts/make_dicom_fixtures.py
```

The generator writes:

- `raw_phi.dcm`: contains obvious synthetic PHI-like metadata
- `pseudonymized.dcm`: contains research-style pseudonyms
- `private_tags.dcm`: contains a vendor-style private creator tag

Do not place real clinical DICOM files in this repository.
