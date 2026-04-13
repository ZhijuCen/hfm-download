"""
Pytest fixtures for hfm-download tests.
"""

import os
import tempfile
import pytest
from pathlib import Path


@pytest.fixture
def tmpdir():
    """Create a temporary directory and change to it, cleanup after."""
    with tempfile.TemporaryDirectory() as td:
        old_cwd = os.getcwd()
        os.chdir(td)
        yield Path(td)
        os.chdir(old_cwd)


@pytest.fixture
def tmpdir_with_subdirs(tmpdir):
    """Create a temp dir with common subdirectory structure."""
    subdirs = ['models', 'datasets', 'models/bert', 'datasets/imdb']
    for d in subdirs:
        (tmpdir / d).mkdir(parents=True, exist_ok=True)
    return tmpdir


@pytest.fixture
def valid_config_yaml():
    """Return a minimal valid config YAML content string."""
    return """
downloads:
  ".":
    - "https://huggingface.co/google-bert/bert-base-uncased/blob/main/model.safetensors"
  models:
    - "https://huggingface.co/google-bert/bert-base-uncased/blob/main/model.safetensors"
  "models/bert":
    - "https://huggingface.co/google-bert/bert-base-uncased/blob/main/model.safetensors"
  "datasets/imdb":
    - "https://huggingface.co/datasets/stanfordnlp/imdb/blob/main/plain_text/train-00000-of-00001.parquet"
"""


@pytest.fixture
def write_config(tmpdir):
    """Factory fixture: write YAML content to a file and return path."""
    def _write(content, filename='hfm-config.yaml'):
        p = tmpdir / filename
        p.write_text(content)
        return p
    return _write
