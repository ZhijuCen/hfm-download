"""
Tests for YAML configuration loading and validation.
"""

import os
import pytest
from hfm_download.config import load_config, validate_config_for_cwd
from hfm_download.exceptions import ConfigValidationError


class TestLoadConfigBasics:
    """Test basic config loading."""
    
    def test_load_minimal_valid_config(self, tmpdir_with_subdirs, write_config, valid_config_yaml):
        write_config(valid_config_yaml)
        config = load_config()
        assert config.retry_times == 3
        assert config.timeout == 30
        assert config.workers == 1
        assert '.' in config.sources
        assert 'models' in config.sources
        assert 'models/bert' in config.sources
        assert 'datasets/imdb' in config.sources
    
    def test_load_with_custom_retry_timeout_workers(self, tmpdir_with_subdirs, write_config):
        content = """
retry_times: 5
timeout: 60
workers: 8
downloads:
  ".":
    - "https://huggingface.co/bert-base/resolve/main/model.bin"
"""
        write_config(content)
        config = load_config()
        assert config.retry_times == 5
        assert config.timeout == 60
        assert config.workers == 8
        assert config.get_effective_workers() == 8
    
    def test_workers_zero_uses_cpu_cores(self, tmpdir_with_subdirs, write_config):
        content = """
workers: 0
downloads:
  ".":
    - "https://huggingface.co/bert-base/resolve/main/model.bin"
"""
        write_config(content)
        config = load_config()
        import os
        cpu_cores = os.cpu_count() or 1
        assert config.get_effective_workers() == cpu_cores
    
    def test_workers_negative_uses_cpu_cores(self, tmpdir_with_subdirs, write_config):
        content = """
workers: -1
downloads:
  ".":
    - "https://huggingface.co/bert-base/resolve/main/model.bin"
"""
        write_config(content)
        config = load_config()
        import os
        cpu_cores = os.cpu_count() or 1
        assert config.get_effective_workers() == cpu_cores
    
    def test_missing_downloads_section(self, tmpdir, write_config):
        content = """
retry_times: 3
"""
        write_config(content)
        with pytest.raises(ConfigValidationError, match="'downloads' section"):
            load_config()
    
    def test_empty_downloads(self, tmpdir, write_config):
        content = """
downloads:
"""
        write_config(content)
        with pytest.raises(ConfigValidationError, match="dictionary"):
            load_config()
    
    def test_missing_config_file(self, tmpdir):
        with pytest.raises(ConfigValidationError, match='not found'):
            load_config('nonexistent.yaml')
    
    def test_empty_yaml_file(self, tmpdir, write_config):
        write_config('')
        with pytest.raises(ConfigValidationError, match='empty'):
            load_config()


class TestNestedDictRejection:
    """Test that nested dicts in downloads are rejected."""
    
    def test_nested_dict_rejected(self, tmpdir, write_config):
        content = """
downloads:
  models:
    bert:
      - "https://huggingface.co/bert-base/resolve/main/model.bin"
"""
        write_config(content)
        with pytest.raises(ConfigValidationError, match='nested dict'):
            load_config()
    
    def test_deeply_nested_dict_rejected(self, tmpdir, write_config):
        content = """
downloads:
  a:
    b:
      c:
        - "https://huggingface.co/bert-base/resolve/main/model.bin"
"""
        write_config(content)
        with pytest.raises(ConfigValidationError, match='nested dict'):
            load_config()
    
    def test_mixed_flat_and_nested_rejected(self, tmpdir, write_config):
        content = """
downloads:
  ".":
    - "https://huggingface.co/bert-base/resolve/main/model.bin"
  models:
    bert:
      - "https://huggingface.co/bert-base/resolve/main/model.bin"
"""
        write_config(content)
        with pytest.raises(ConfigValidationError, match='nested dict'):
            load_config()


class TestUrlValidation:
    """Test URL validation in config."""
    
    def test_invalid_url_rejected(self, tmpdir, write_config):
        content = """
downloads:
  ".":
    - "https://example.com/model.bin"
"""
        write_config(content)
        with pytest.raises(ConfigValidationError, match='Invalid HuggingFace URL'):
            load_config()
    
    def test_non_string_url_rejected(self, tmpdir, write_config):
        content = """
downloads:
  ".":
    - 12345
"""
        write_config(content)
        with pytest.raises(ConfigValidationError, match='must be a string'):
            load_config()
    
    def test_non_list_value_rejected(self, tmpdir, write_config):
        content = """
downloads:
  ".": "just a string"
"""
        write_config(content)
        with pytest.raises(ConfigValidationError, match='must be a list'):
            load_config()
    
    def test_empty_url_list_ok(self, tmpdir, write_config):
        content = """
downloads:
  ".":
    - "https://huggingface.co/bert-base/resolve/main/model.bin"
  empty: []
"""
        write_config(content)
        config = load_config()
        assert 'empty' not in config.sources  # empty lists are skipped


class TestSubdirKeyValidation:
    """Test subdirectory key format validation."""
    
    def test_leading_slash_rejected(self, tmpdir, write_config):
        content = """
downloads:
  "/models":
    - "https://huggingface.co/bert-base/resolve/main/model.bin"
"""
        write_config(content)
        with pytest.raises(ConfigValidationError, match='must not start or end with'):
            load_config()
    
    def test_trailing_slash_rejected(self, tmpdir, write_config):
        content = """
downloads:
  "models/":
    - "https://huggingface.co/bert-base/resolve/main/model.bin"
"""
        write_config(content)
        with pytest.raises(ConfigValidationError, match='must not start or end with'):
            load_config()
    
    def test_double_dot_rejected(self, tmpdir, write_config):
        content = """
downloads:
  "models/..":
    - "https://huggingface.co/bert-base/resolve/main/model.bin"
"""
        write_config(content)
        with pytest.raises(ConfigValidationError, match='path traversal'):
            load_config()


class TestValidateConfigForCwd:
    """Test config validation against current working directory."""
    
    def test_all_valid_tasks(self, tmpdir_with_subdirs, write_config, valid_config_yaml):
        write_config(valid_config_yaml)
        config = load_config()
        tasks = validate_config_for_cwd(config, str(tmpdir_with_subdirs))
        
        assert len(tasks) == 4
        subdirs = [t[0] for t in tasks]
        assert '.' in subdirs
        assert 'models' in subdirs
        assert 'models/bert' in subdirs
        assert 'datasets/imdb' in subdirs
    
    def test_missing_subdir_raises(self, tmpdir, write_config):
        content = """
downloads:
  nonexistent:
    - "https://huggingface.co/bert-base/resolve/main/model.bin"
"""
        write_config(content)
        config = load_config()
        with pytest.raises(ConfigValidationError, match='does not exist'):
            validate_config_for_cwd(config, str(tmpdir))
    
    def test_missing_intermediate_dir_raises(self, tmpdir, write_config):
        (tmpdir / 'models').mkdir()  # only models exists, not models/bert
        content = """
downloads:
  "models/bert":
    - "https://huggingface.co/bert-base/resolve/main/model.bin"
"""
        write_config(content)
        config = load_config()
        with pytest.raises(ConfigValidationError, match='Intermediate directory'):
            validate_config_for_cwd(config, str(tmpdir))
    
    def test_tasks_contain_correct_info(self, tmpdir_with_subdirs, write_config):
        content = """
downloads:
  ".":
    - "https://huggingface.co/google-bert/bert-base-uncased/blob/main/model.safetensors"
  "models/bert":
    - "https://huggingface.co/google-bert/bert-base-uncased/blob/main/config.json"
"""
        write_config(content)
        config = load_config()
        tasks = validate_config_for_cwd(config, str(tmpdir_with_subdirs))
        
        task_dict = {subdir: (fname, url) for subdir, fname, url in tasks}
        
        assert task_dict['.'][0] == 'model.safetensors'
        assert 'hf-mirror.com' in task_dict['.'][1]
        assert task_dict['models/bert'][0] == 'config.json'
