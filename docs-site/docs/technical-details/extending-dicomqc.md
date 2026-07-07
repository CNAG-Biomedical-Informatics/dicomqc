---
title: Extending dicomqc
---

# Extending dicomqc

v0.1 includes stable extension seams without shipping every planned extension.

## Policy DSL

Future policy files should declare audit expectations, not anonymization
actions. For example, a policy may say that `PatientBirthDate` must be absent or
that `PatientID` must match a site-approved pseudonym pattern.

## Plugins

Future plugins should be able to contribute rule packs, reports, backend
implementations, compliance profiles, or vendor fingerprinting modules.

## Standards profiles

DICOM PS3.15 and BIDS support should be implemented as explicit profile packs
with stable rule IDs and source references. v0.1 keeps fields such as
`profile_id`, `rule_id`, and `standard_refs` ready for that work, but does not
claim standards compliance.

## Vendor fingerprinting

Vendor fingerprinting can build on the normalized inventory of manufacturer,
model, software versions, and private creator blocks. The first useful target is
risk evidence that helps reviewers decide which private tags or protocol fields
need manual inspection.
