"""Private subprocess entry point; calls the engine, never the CLI parser."""

from __future__ import annotations

import logging
import hashlib
import os
from pathlib import Path
import sys
import time
import warnings

from dicomqc.api.storage import read_json, validate_identity, write_json
from dicomqc.compare import compare_datasets
from dicomqc.execution import _load_requested_policy, validate_audit_inputs
from dicomqc.reports import write_csv, write_html, write_json as report_json, write_multiqc
from dicomqc.reports.json import result_to_dict
from dicomqc.scanner import scan_paths
from dicomqc.parallel import DEFAULT_THREADS


def execute(directory: Path) -> None:
    request = read_json(directory / "request.json")
    def workspace():
        validate_identity(request["workspace"])
        validate_identity(request["directory"])

    workspace()
    refs = {key: [validate_identity(value) for value in values] for key, values in request["inputs"].items()}
    paths = validate_audit_inputs(request["mode"], refs)
    options = request["options"]
    stage = directory / "pending"
    stage.mkdir(mode=0o700)
    events = []
    last_phase = None
    last_progress_write = 0.0

    def progress(event):
        nonlocal last_phase, last_progress_write
        workspace()
        now = time.time()
        phase_changed = event["phase"] != last_phase
        finished = event.get("total") is not None and event.get("completed") == event["total"]
        if phase_changed:
            events.append({"at": now, "event": event["phase"]})
            write_json(directory / "events.json", events)
            last_phase = event["phase"]
        if phase_changed or finished or now - last_progress_write >= 0.2:
            write_json(directory / "progress.json", event)
            last_progress_write = now

    if request["mode"] == "demo":
        from dicomqc.demo import run_demo, run_comparison_demo, run_large_demo, run_policy_demo, run_uid_demo, run_vendor_demo
        demos = {"scan": run_demo, "compare": run_comparison_demo, "policy": run_policy_demo,
                 "uid": run_uid_demo, "vendor": run_vendor_demo, "large": run_large_demo}
        progress({"phase": "synthetic demo", "completed": 0, "total": None})
        demo_options = {"multiqc": options.get("multiqc", False),
                        "threads": options.get("threads", DEFAULT_THREADS)}
        if request["example"] == "large" and request.get("example_files") is not None:
            demo_options["count"] = request["example_files"]
        if request["example"] == "large":
            demo_options["progress"] = progress
        demos[request["example"]](stage / "example", **demo_options)
        candidates = sorted((stage / "example").rglob("*.json"))
        payload = read_json(next(path for path in candidates if path.name in {"before.json", "report.json"}))
        code = 2 if payload["summary"]["errors"] or payload["summary"]["skipped_files"] else int(bool(payload["summary"]["warnings"]))
    else:
        protected = [stage / name for name in ("report.html", "report.json", "findings.csv")]
        if any(directory == root or root in directory.parents or directory in root.parents for root in paths):
            raise ValueError("Keep run outputs separate from the inputs.")
        policy = _load_requested_policy(refs.get("policy", [None])[0], paths, protected)
        if policy is not None:
            source = refs["policy"][0].read_bytes()
            if hashlib.sha256(source).hexdigest() != policy.sha256:
                raise ValueError("The project policy changed during the audit.")
            (stage / "project-policy.yaml").write_bytes(source)
        progress({"phase": "discovery", "completed": 0, "total": None})
        if request["mode"] == "compare":
            result = compare_datasets(*paths, refs["manifest"][0], policy=policy,
                                      threads=options.get("threads", DEFAULT_THREADS), progress=progress)
        else:
            result = scan_paths(paths, policy=policy, uid_checks=options["uid_checks"],
                                vendor_summary=options["vendor_summary"],
                                threads=options.get("threads", DEFAULT_THREADS), progress=progress)
        progress({"phase": "reports", "completed": 0, "total": None})
        report_json(result, stage / "report.json")
        write_csv(result, stage / "findings.csv")
        write_html(result, stage / "report.html")
        if options["multiqc"]:
            write_multiqc(result, stage / "multiqc")
        payload, code = result_to_dict(result), result.exit_code()
    # JSON exports retain documented CLI semantics; live responses never return raw record context.
    workspace()
    payload.pop("records", None)
    write_json(stage / "review.json", payload)
    artifacts = [str(path.relative_to(stage)).replace(os.sep, "/") for path in sorted(stage.rglob("*"))
                 if path.is_file() and path.suffix in {".html", ".json", ".csv", ".yaml"} and path.name != "review.json"]
    workspace()
    stage.rename(directory / "reports")
    write_json(directory / "completion.json", {"audit_exit_code": code, "artifacts": artifacts,
                                             "summary": payload["summary"], "policy": payload.get("policy")})


def main(directory: str) -> int:
    # Never let pydicom diagnostics or tracebacks disclose values in desktop logs.
    logging.disable(logging.CRITICAL)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        try:
            execute(Path(directory))
        except Exception:
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1]))
