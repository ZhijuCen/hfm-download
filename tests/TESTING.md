# Testing Guide

## Running Tests

```bash
# Install dependencies
uv venv .venv && uv pip install -e . pytest

# Activate virtual environment
source .venv/bin/activate

# Run all tests with verbose output
pytest tests/ -v

# Run specific test file
pytest tests/test_config.py -v

# Run with coverage
pytest tests/ -v --tb=short

# Run tests matching a keyword
pytest tests/ -k "mirror" -v
```

## Test Structure

```
tests/
├── __init__.py           # Package marker
├── conftest.py           # Shared pytest fixtures
├── test_config.py        # URL parsing and mirror replacement
├── test_path_utils.py    # Path safety validation
├── test_config_loading.py # YAML config loading and validation
├── test_cli.py           # CLI entry points
└── TESTING.md            # This file
```

## Fixtures (conftest.py)

| Fixture | Description |
|---------|-------------|
| `tmpdir` | Temp directory, changes CWD, auto-cleanup |
| `tmpdir_with_subdirs` | Same as `tmpdir` but pre-creates `models/`, `datasets/`, `models/bert/`, `datasets/imdb/` |
| `valid_config_yaml` | Minimal valid YAML with `.`, `models`, `models/bert`, `datasets/imdb` keys |
| `write_config` | Factory: writes YAML content to file, returns path |

## Test Cases

### URL Parsing (`test_config.py`)

| Test | Description |
|------|-------------|
| `test_valid_huggingface_co` | Standard huggingface.co URL accepted |
| `test_valid_hf_mirror` | Already-mirrored URL accepted |
| `test_invalid_random_url` | Non-HF URLs rejected |
| `test_basic_replacement` | `huggingface.co` → `hf-mirror.com` |
| `test_blob_format` | `/blob/main/` URLs parsed correctly |
| `test_resolve_format` | `/resolve/` URLs parsed correctly |
| `test_mixed_hyphen_model_id` | Model IDs with hyphens parsed correctly |

### Path Safety (`test_path_utils.py`)

| Test | Description |
|------|-------------|
| `test_relative_path_within_cwd` | Normal relative paths work |
| `test_dot_current_dir` | `.` resolves to cwd |
| `test_absolute_path_outside_cwd_blocked` | Absolute paths outside cwd blocked |
| `test_path_traversal_blocked_single_level` | `../etc` blocked |
| `test_path_traversal_blocked_multi_level` | `models/../../../etc` blocked |
| `test_symlink_traversal_blocked` | Symlinks escaping cwd blocked |
| `test_missing_intermediate_dir_blocked` | `models/bert` where `models/` missing blocked |
| `test_traversal_in_subdir_key_blocked` | `../etc` as subdir key blocked |

### Config Loading (`test_config_loading.py`)

| Test | Description |
|------|-------------|
| `test_load_minimal_valid_config` | Full valid config loads correctly |
| `test_workers_zero_uses_cpu_cores` | `workers: 0` resolves to CPU count |
| `test_nested_dict_rejected` | Nested YAML dicts rejected with clear error |
| `test_missing_downloads_section` | Missing `downloads:` key caught |
| `test_invalid_url_rejected` | Non-HF URLs cause error |
| `test_leading_slash_rejected` | Keys starting with `/` rejected |
| `test_missing_subdir_raises` | Non-existent subdirectory caught |

### CLI (`test_cli.py`)

| Test | Description |
|------|-------------|
| `test_example_config_flag` | `--example-config` prints valid YAML |
| `test_has_nested_dict_rejection_comment` | Example config documents flat-structure rule |

## Expected Behavior

### Valid Config Flow

```
YAML loaded → Key format validated → Subdir existence checked → Tasks built
```

### Invalid Config Errors

| Error | Cause | Message includes |
|-------|-------|-----------------|
| `ConfigValidationError` | Missing `downloads:` | `"'downloads' section"` |
| `ConfigValidationError` | Nested dict | `"nested dict"` |
| `ConfigValidationError` | Invalid URL | `"Invalid HuggingFace URL"` |
| `ConfigValidationError` | Invalid key format | `"must not start or end with"` |
| `ConfigValidationError` | Subdir doesn't exist | `"does not exist"` |
| `ConfigValidationError` | Missing intermediate dir | `"Intermediate directory"` |
| `PathTraversalError` | Path escapes cwd | `"escapes current working directory"` |

## Adding New Tests

1. Add test function to the appropriate file
2. Use `tmpdir` or `tmpdir_with_subdirs` fixtures
3. Use `write_config` fixture to create config files
4. Assert expected outcomes with clear error messages
5. Run `pytest tests/ -v` to verify
