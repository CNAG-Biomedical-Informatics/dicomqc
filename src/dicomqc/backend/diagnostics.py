"""Read metadata without disclosing parser diagnostics containing tag values."""

import logging
from pathlib import Path
import re
import threading
import warnings

from dicomqc.backend.base import DicomBackend, DicomReadError
from dicomqc.model.metadata import MetadataRecord


class _HideParserDetails(logging.Filter):
    def __init__(self) -> None:
        super().__init__()
        self.thread = threading.get_ident()

    def filter(self, record: logging.LogRecord) -> bool:
        return record.thread != self.thread


def read_metadata_safely(reader: DicomBackend, path: Path, *, allow_uid_warnings: bool = False) -> MetadataRecord:
    logger = logging.getLogger("pydicom")
    log_filter = _HideParserDetails()
    logger.addFilter(log_filter)
    try:
        with warnings.catch_warnings(record=True) as diagnostics:
            warnings.simplefilter("always")
            record = reader.read_metadata(path)
        # UI validation warnings are expected when auditing malformed UIDs.
        # Other parser warnings still make coverage incomplete. Do not change
        # pydicom's global validation settings or print original diagnostics.
        for diagnostic in diagnostics:
            message = str(diagnostic.message)
            uid_warning = message.startswith("Invalid value for VR UI:") or bool(re.match(
                r"The value length \([0-9]+\) exceeds the maximum length of 64 allowed for VR UI\.", message,
            ))
            if not (allow_uid_warnings and uid_warning):
                raise DicomReadError("DICOM parser reported a warning.")
        return record
    except DicomReadError:
        raise DicomReadError("Cannot read DICOM metadata.") from None
    finally:
        logger.removeFilter(log_filter)
