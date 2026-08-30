# -*- coding: utf-8 -*-
"""Shared runtime settings for the training and data preparation scripts."""
from __future__ import annotations

import os


def configure_worker_cpus() -> int:
    """Tell joblib how many cores it may use and return that number.

    joblib counts *physical* cores by shelling out to ``wmic`` on Windows.
    That tool was removed from recent Windows builds, so the call fails with
    ``[WinError 2]`` and joblib prints a multi-line traceback in the middle of
    every training run. The count it falls back to - logical cores - is the
    one we want anyway, so state it up front and keep the output readable.

    An existing LOKY_MAX_CPU_COUNT is respected so a machine can be limited
    from the outside.
    """
    existing = os.environ.get("LOKY_MAX_CPU_COUNT")
    if existing:
        try:
            return int(existing)
        except ValueError:
            pass

    cores = os.cpu_count() or 1
    os.environ["LOKY_MAX_CPU_COUNT"] = str(cores)
    return cores
