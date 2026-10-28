import os
from pathlib import Path


def data_dir():
    root = Path(os.environ.get("REPOGUARD_HOME", Path.home() / ".repoguard"))
    root.mkdir(parents=True, exist_ok=True)
    return root
