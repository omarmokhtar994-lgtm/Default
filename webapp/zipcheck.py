# © 2026 Omar Mokhtar. All rights reserved.
"""Phase AU: a workbook is a zip file, and a small zip can open to gigabytes (a "zip bomb"). The size limit on an upload
(25 MB) is on the file as sent, so this checks what it would become before any workbook library opens it."""
from __future__ import annotations

import io
import zipfile
from pathlib import Path
from typing import Optional, Union

MAX_MEMBERS = 2000
MAX_MEMBER_BYTES = 150 * 1024 * 1024
MAX_TOTAL_BYTES = 250 * 1024 * 1024
MAX_RATIO = 100          # opened size over file size, once it is big enough to matter
RATIO_FROM_BYTES = 20 * 1024 * 1024
# A schedule workbook is opened whole by the web process (every cell becomes an object), and the largest real one in this repository is 4.5 MB opened
# (1.7 MB a member): five times that is the limit for an upload that becomes a run. The limits above stay for the volumes and people files, whose
# readers go row by row and may hold 400,000 rows. (Audit 2026-11-11.)
RUN_LIMITS = {"member_limit": 25 * 1024 * 1024, "total_limit": 40 * 1024 * 1024}

PROBLEM = ("That file is far larger once opened than its size says, so it was not read. Upload a normal Excel workbook "
           "(.xlsx).")


def zip_problem(source: Union[str, Path, bytes], member_limit: Optional[int] = None, total_limit: Optional[int] = None) -> str:
    """"" when the zip is a sane size once opened; else what to tell the person. Nothing is extracted. A file that is not
    a readable zip is not a bomb: it is left to the workbook readers, which say what is wrong with it. ``member_limit`` and ``total_limit``
    replace the defaults (``RUN_LIMITS`` for a schedule workbook)."""
    member_limit = MAX_MEMBER_BYTES if member_limit is None else member_limit
    total_limit = MAX_TOTAL_BYTES if total_limit is None else total_limit
    try:
        handle = zipfile.ZipFile(io.BytesIO(source) if isinstance(source, bytes) else source)
    except (zipfile.BadZipFile, OSError):
        return ""
    with handle:
        infos = handle.infolist()
        total = sum(i.file_size for i in infos)
        packed = sum(i.compress_size for i in infos) or 1
        if (len(infos) > MAX_MEMBERS or total > total_limit or any(i.file_size > member_limit for i in infos)
                or (total > RATIO_FROM_BYTES and total / packed > MAX_RATIO)):
            return PROBLEM
    return ""
