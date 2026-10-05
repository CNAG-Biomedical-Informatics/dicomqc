"""Exercise an installed distribution from a directory outside the checkout."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from importlib.metadata import version
from pathlib import Path

import dicomqc


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--expected-version", required=True)
    expected = parser.parse_args().expected_version
    assert dicomqc.__version__ == version("dicomqc") == expected
    checkout = Path(__file__).resolve().parents[1]
    assert checkout not in Path(dicomqc.__file__).resolve().parents, "Smoke test imported checkout code"
    with tempfile.TemporaryDirectory(prefix="dicomqc-package-smoke-") as temporary:
        root = Path(temporary)

        def cli(*args: str, expected_exit: int = 0) -> str:
            result = subprocess.run(
                [sys.executable, "-m", "dicomqc.cli", *args], cwd=root,
                capture_output=True, text=True, check=False,
            )
            assert result.returncode == expected_exit, (args, result.stdout, result.stderr)
            return result.stdout

        assert cli("--version").strip() == f"dicomqc {expected}"
        cli("demo", "--output-dir", "scan-demo")
        assert (root / "scan-demo/dicomqc/dicomqc_mqc/dicomqc_summary_mqc.yaml").is_file()
        assert "Privacy audit" in (root / "scan-demo/dicomqc/report.html").read_text(encoding="utf-8")
        cli("demo", "--compare", "--output-dir", "comparison-demo")
        for name, errors in (("before", 3), ("after", 0)):
            report = root / f"comparison-demo/{name}.json"
            assert json.loads(report.read_text(encoding="utf-8"))["summary"]["errors"] == errors
            assert report.with_suffix(".csv").is_file()
            assert "Dataset comparison" in report.with_suffix(".html").read_text(encoding="utf-8")
        for directory, code in (("candidate", 2), ("corrected", 0)):
            cli("compare", "comparison-demo/source", f"comparison-demo/{directory}",
                "--manifest", "comparison-demo/pairs.csv", "--json", f"{directory}.json",
                "--csv", f"{directory}.csv", "--html", f"{directory}.html", expected_exit=code)
            assert (root / f"{directory}.html").is_file()
        cli("demo", "--compare", "--output-dir", "comparison-demo", "--force")
        cli("demo", "--policy-demo", "--output-dir", "policy-demo")
        for phase, errors in (("before", 3), ("after", 0)):
            payload = json.loads((root / f"policy-demo/{phase}.json").read_text(encoding="utf-8"))
            assert payload["summary"]["errors"] == errors
            assert payload["policy"]["id"] == "research-demo"
            assert len(payload["policy"]["sha256"]) == 64
        cli("scan", "policy-demo/corrected", "--policy", "policy-demo/policy.yaml",
            "--html", "policy-scan.html")
        cli("demo", "--vendor-demo", "--output-dir", "vendor-demo")
        vendor = json.loads((root / "vendor-demo/dicomqc/report.json").read_text(encoding="utf-8"))
        assert vendor["summary"]["warnings"] == 3
        assert vendor["vendor_summary"]["unassigned_private_elements"] == 1
        assert vendor["vendor_summary"]["private_elements"] == 5
        cli("demo", "--uid-demo", "--output-dir", "uid-demo")
        for phase, errors in (("before", 7), ("after", 0)):
            payload = json.loads((root / f"uid-demo/{phase}.json").read_text(encoding="utf-8"))
            assert payload["summary"]["errors"] == errors
            assert payload["uid_checks"]["files_checked"] == 4
        cli("scan", "uid-demo/corrected", "--uid-checks", "--html", "uid.html")
    print(f"Installed dicomqc {expected}: scan, comparison, policy, vendor and UID demos passed.")


if __name__ == "__main__":
    main()
