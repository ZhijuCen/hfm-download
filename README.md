# hfm-download

HuggingFace Mirror Downloader - Download models from hf-mirror.com with safety constraints.

## Features

- **Automatic Mirror Replacement**: Transforms `huggingface.co` URLs to `hf-mirror.com`
- **Path Safety**: All downloads strictly bounded within current working directory
- **Multi-threaded**: Configurable parallel downloads
- **Retry Logic**: Smart retry for temporary network failures
- **Progress Bars**: Per-file progress display with tqdm
- **YAML Configuration**: Simple YAML-based configuration

## Installation

```bash
pip install -e .
```

Or install dependencies only:
```bash
pip install pyyaml tqdm
```

## Quick Start

1. Create a YAML config file (e.g., `hfm-config.yaml`):

```yaml
# Optional settings
retry_times: 3
timeout: 30
workers: 0  # 0 = use all CPU cores

# Download section (required)
downloads:
  # Download directly into current working directory:
  ".":
    - "https://huggingface.co/google-bert/bert-base-uncased/blob/main/model.safetensors"

  # Download into subdirectory (mkdir -p bert first):
  bert:
    - "https://huggingface.co/google-bert/bert-base-uncased/blob/main/model.safetensors"
```

2. Create the subdirectory (skip if using `"."` to download to current dir):
```bash
mkdir -p bert
```

3. Run:
```bash
python -m hfm-download --config hfm-config.yaml
```

## Usage

```bash
# Show help
python -m hfm-download --help

# Use default config (hfm-config.yaml)
python -m hfm-download

# Use custom config
python -m hfm-download --config my-config.yaml

# Verbose output
python -m hfm-download --config my-config.yaml --verbose

# Generate example config
python -m hfm-download --example-config
```

## Configuration

### YAML Structure

| Key | Required | Default | Description |
|-----|----------|---------|-------------|
| `retry_times` | No | 3 | Number of retries on failure |
| `timeout` | No | 30 | Request timeout (seconds) |
| `workers` | No | 1 | Parallel workers (0 = all CPU cores) |
| `downloads` | Yes | - | Dict mapping target dirs to URL lists |

### `downloads` Section

The `downloads` key is a **flat** dictionary where:
- **Key** = target directory; `.` means current dir; `/`-separated paths for multi-level (e.g. `models/bert`)
- **Value** = list of HuggingFace URLs to download
- **No nested dicts** — use `models/bert:` as a flat key, NOT `models: { bert: ... }`

```yaml
downloads:
  ".":                            # Current directory (no subfolder)
    - "https://huggingface.co/google-bert/bert-base-uncased/blob/main/model.safetensors"

  models:                        # Subdirectory 'models/'
    - "https://huggingface.co/google-bert/bert-base-uncased/blob/main/model.safetensors"

  "models/bert":                  # Multi-level: 'models/bert/' (mkdir -p first)
    - "https://huggingface.co/google-bert/bert-base-uncased/blob/main/model.safetensors"

  "datasets/imdb":               # Multi-level: 'datasets/imdb/'
    - "https://huggingface.co/datasets/stanfordnlp/imdb/blob/main/plain_text/train-00000-of-00001.parquet"
```

> **`.` as key**: always quote it in YAML (`"."` or `'.'`).
> **Multi-level paths**: run `mkdir -p datasets/imdb models/bert` first — all intermediate directories must exist.

### Typical Scenarios

**Scenario A: Working directory IS the model folder (no subdirectory needed)**

```yaml
# Current dir: ~/models/bert-base/
downloads:
  ".":
    - "https://huggingface.co/google-bert/bert-base-uncased/blob/main/model.safetensors"
```

**Scenario B: Models and datasets in separate subdirectories**

```yaml
# Current dir: ~/hf/
# mkdir -p models datasets/imdb
downloads:
  models:
    - "https://huggingface.co/google-bert/bert-base-uncased/blob/main/model.safetensors"

  "datasets/imdb":
    - "https://huggingface.co/datasets/stanfordnlp/imdb/blob/main/plain_text/train-00000-of-00001.parquet"
```

**Scenario C: Fine-grained multi-level organization**

```yaml
# Current dir: ~/hf/
# mkdir -p models/google models/openai datasets/imdb
downloads:
  models:
    - "https://huggingface.co/google-bert/bert-base-uncased/blob/main/model.safetensors"

  "models/google":
    - "https://huggingface.co/google-bert/bert-base-uncased/blob/main/model.safetensors"

  "datasets/imdb":
    - "https://huggingface.co/datasets/stanfordnlp/imdb/blob/main/plain_text/train-00000-of-00001.parquet"
```

### Path Safety

- Downloads are **only** allowed within current working directory
- Path traversal (`..`) is blocked
- Non-existent subdirectories cause errors (no auto-create)
- All intermediate directories for multi-level paths must exist
- Absolute paths are rejected

## Architecture

```
hfm_download/
├── __init__.py          # Package init
├── __main__.py          # Entry point
├── cli.py               # CLI argument parsing
├── config.py            # YAML config loading/validation
├── downloader.py        # Core download logic
├── exceptions.py        # Custom exceptions
├── logger.py            # Logging setup
├── path_utils.py        # Path safety validation
└── progress.py          # Progress bar (tqdm wrapper)
```

## License

MIT
