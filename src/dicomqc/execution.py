"""Input/output validation shared by CLI and local jobs."""

from pathlib import Path

from dicomqc.rules.policy import Policy, load_policy


def validate_audit_inputs(mode: str, inputs: dict[str, list[Path]]) -> list[Path]:
    """Validate API input roles using the same comparison roots as the CLI."""
    for role in ("policy", "manifest"):
        if role in inputs and not inputs[role][0].is_file():
            raise ValueError("Policy and manifest inputs must be regular files.")
    if mode == "compare":
        from dicomqc.compare import comparison_roots
        roots = list(comparison_roots(inputs["source"][0], inputs["candidate"][0]))
        manifest = inputs["manifest"][0]
        if any(root in manifest.parents for root in roots):
            raise ValueError("Keep the pairing manifest outside both input directories.")
        return roots
    return inputs.get("paths", [])


def _validate_multiqc_output(bundle: Path, inputs: list[Path], outputs: list[Path]) -> None:
    bundle = bundle.resolve()
    inputs = [root.resolve() for root in inputs]
    outputs = [output.resolve() for output in outputs]
    if any(bundle == root or root in bundle.parents or bundle in root.parents for root in inputs):
        raise ValueError("Keep the MultiQC output directory separate from the DICOM inputs.")
    if any(bundle == output or bundle in output.parents or output in bundle.parents for output in outputs):
        raise ValueError("Keep other reports outside the MultiQC output directory.")


def _load_requested_policy(
    path: Path | None, inputs: list[Path], outputs: list[Path], multiqc: Path | None = None,
) -> Policy | None:
    if path is None:
        return None
    policy_path = path.resolve()
    inputs = [root.resolve() for root in inputs]
    if any(policy_path == root or root in policy_path.parents
           or (root.is_file() and policy_path.exists() and root.samefile(policy_path))
           for root in inputs):
        raise ValueError("Keep the policy outside the DICOM inputs.")
    protected_outputs = list(outputs)
    if multiqc is not None:
        bundle = multiqc.resolve()
        if policy_path == bundle or bundle in policy_path.parents:
            raise ValueError("Keep the policy outside the MultiQC output directory.")
        for pattern in ("*_mqc.yaml", "*_mqc.html"):
            protected_outputs.extend(bundle.glob(pattern))
    if any(output.resolve() == policy_path
           or (output.is_file() and policy_path.exists() and output.samefile(policy_path))
           for output in protected_outputs):
        raise ValueError("Report output must not overwrite or remove the policy.")
    return load_policy(policy_path)
