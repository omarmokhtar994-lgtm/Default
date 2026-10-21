# © 2026 Omar Mokhtar. All rights reserved.
"""Phase AU: a workbook is a zip file, and a small zip can open to gigabytes (a "zip bomb"). The size limit on an upload
(25 MB) is on the file as sent, so this checks what it would become before any workbook library opens it."""
from __future__ import annotations

import io
import zipfile
from pathlib import Path
from typing import Union

MAX_MEMBERS = 2000
MAX_MEMBER_BYTES = 150 * 1024 * 1024
MAX_TOTAL_BYTES = 250 * 1024 * 1024
MAX_RATIO = 100          # opened size over file size, once it is big enough to matter
RATIO_FROM_BYTES = 20 * 1024 * 1024

PROBLEM = ("That file is far larger once opened than its size says, so it was not read. Upload a normal Excel workbook "
           "(.xlsx).")


def zip_problem(source: Union[str, Path, bytes]) -> str:
    """"" when the zip is a sane size once opened; else what to tell the person. Nothing is extracted. A file that is not
    a readable zip is not a bomb: it is left to the workbook readers, which say what is wrong with it."""
    try:
        handle = zipfile.ZipFile(io.BytesIO(source) if isinstance(source, bytes) else source)
    except (zipfile.BadZipFile, OSError):
        return ""
    with handle:
        infos = handle.infolist()
        total = sum(i.file_size for i in infos)
        packed = sum(i.compress_size for i in infos) or 1
        if (len(infos) > MAX_MEMBERS or total > MAX_TOTAL_BYTES or any(i.file_size > MAX_MEMBER_BYTES for i in infos)
                or (total > RATIO_FROM_BYTES and total / packed > MAX_RATIO)):
            return PROBLEM
    return ""
