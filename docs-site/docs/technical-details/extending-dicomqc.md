---
title: Planned Features
---

# Planned Features

The features on this page are not available in dicomqc v0.1. They describe
possible directions for later releases.

## Policy files

A planned domain-specific language (DSL) would let users define metadata checks
in a configuration file. For example, a policy could require
`PatientBirthDate` to be absent or `PatientID` to match an approved pseudonym
format. The policy would define what dicomqc checks, not how files are modified.

## Plugins

A planned plugin interface would allow separately installed packages to add
checks, report formats, DICOM readers, standards profiles, or vendor-specific
metadata checks.

## Standards profiles

Planned DICOM PS3.15 and BIDS profiles would identify every check with a stable
rule ID and a reference to its source standard. The v0.1 result model already
contains `profile_id`, `rule_id`, and `standard_refs`, but the current built-in
profile does not claim compliance with either standard.

## Vendor fingerprinting

A planned vendor-fingerprinting feature would summarize manufacturer, scanner
model, software version, and private creator blocks. Reviewers could use that
summary to identify private tags and protocol fields that need manual inspection.
