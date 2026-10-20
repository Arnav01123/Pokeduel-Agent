"""Shared paths and agent loading for the arena scripts."""
import importlib.util
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
ARENA = ROOT / 'arena'
def load(path, name):
    spec = importlib.util.spec_from_file_location(name, str(path))
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m
