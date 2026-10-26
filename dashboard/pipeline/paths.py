"""Shared paths after moving the original scripts into dashboard/pipeline/."""
import os
from pathlib import Path

PIPELINE = Path(__file__).resolve().parent
ROOT = PIPELINE.parents[1]
DASHBOARD = ROOT / 'dashboard'
DATA_ROOT = Path(os.environ.get('IEUM_DATA_ROOT', str(ROOT / 'data'))).expanduser().resolve()
