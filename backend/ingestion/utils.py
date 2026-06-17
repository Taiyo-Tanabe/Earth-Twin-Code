"""Shared utilities for data ingestion: write helpers that ensure world-writable permissions
so both the backend container (root) and Airflow container (uid 50000) can read/write files."""
import os
import stat
from pathlib import Path
import pandas as pd


def save_parquet(df: pd.DataFrame, path: Path | str, index: bool = False) -> None:
    """Save DataFrame to parquet and set world-readable/writable permissions."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path, index=index)
    try:
        os.chmod(path, stat.S_IRUSR | stat.S_IWUSR | stat.S_IRGRP | stat.S_IWGRP | stat.S_IROTH | stat.S_IWOTH)
        os.chmod(path.parent, stat.S_IRWXU | stat.S_IRWXG | stat.S_IRWXO)
    except PermissionError:
        pass


def save_csv(df: pd.DataFrame, path: Path | str, index: bool = False, **kwargs) -> None:
    """Save DataFrame to CSV and set world-readable/writable permissions."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=index, **kwargs)
    try:
        os.chmod(path, stat.S_IRUSR | stat.S_IWUSR | stat.S_IRGRP | stat.S_IWGRP | stat.S_IROTH | stat.S_IWOTH)
        os.chmod(path.parent, stat.S_IRWXU | stat.S_IRWXG | stat.S_IRWXO)
    except PermissionError:
        pass


def save_joblib(obj, path: Path | str) -> None:
    """Save object via joblib and set world-readable/writable permissions."""
    import joblib
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(obj, path)
    try:
        os.chmod(path, stat.S_IRUSR | stat.S_IWUSR | stat.S_IRGRP | stat.S_IWGRP | stat.S_IROTH | stat.S_IWOTH)
        os.chmod(path.parent, stat.S_IRWXU | stat.S_IRWXG | stat.S_IRWXO)
    except PermissionError:
        pass
