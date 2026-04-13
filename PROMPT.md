---
guidance: true
---
# hfm-download · User Requirements Prompt

> This prompt captures the intended behavior and specification for `hfm-download`,
> a HuggingFace mirror downloader. Use it as a reference when building or modifying the tool.

---

## Core Functionality

- **Name**: `hfm-download`
- **Entry point**: `python -m hfm-download`
- **Purpose**: Automatically replace HuggingFace model URLs with `https://hf-mirror.com/`
  and download files safely into the current working directory.
- **Dependencies**: Python standard library + `pyyaml`, `tqdm`

---

## YAML Configuration Format

```yaml
# Optional settings (all optional)
retry_times: 3      # default: 3
timeout: 30          # default: 30, in seconds
workers: 0           # default: 1; 0 means auto-detect CPU cores

# Required: download section
downloads:
  ".":                          # current working directory itself
    - "https://huggingface.co/google-bert/bert-base-uncased/blob/main/model.safetensors"

  models:                       # subdirectory 'models/'
    - "https://huggingface.co/google-bert/bert-base-uncased/blob/main/model.safetensors"

  "models/bert":                # multi-level path 'models/bert/' — flat key, no nesting
    - "https://huggingface.co/google-bert/bert-base-uncased/blob/main/model.safetensors"

  "datasets/imdb":              # multi-level path 'datasets/imdb/'
    - "https://huggingface.co/datasets/stanfordnlp/imdb/blob/main/plain_text/train-00000-of-00001.parquet"
```

### Rules

| Rule | Detail |
|------|--------|
| **Flat structure only** | `downloads` must be a **flat dict**. `models/bert:` as a flat key. **NOT** `models: { bert: ... }` |
| **`.` means current dir** | No subfolder; files land directly in CWD. Always quote in YAML: `"."` or `'.'` |
| **Multi-level paths** | Use `/`-separated flat keys: `"datasets/imdb"`. All intermediate directories must already exist (`mkdir -p datasets/imdb`) |
| **No auto-create** | Subdirectories must exist before running. Tool does not create them. |
| **URL types** | Both `/resolve/` and `/blob/` paths are supported. `http://` and `https://` both accepted. |

---

## Path Safety (Critical)

All download destinations are **strictly bounded within the current working directory**.
The tool must enforce:

1. **Path traversal blocking** — `..` in any path component is rejected
2. **Absolute path blocking** — Absolute paths outside CWD are rejected
3. **Symlink traversal blocking** — Symbolic links that resolve outside CWD are rejected
4. **Intermediate directory check** — For `models/bert`, both `models/` and `models/bert/` must exist
5. **Empty key blocking** — Empty string `""` as a subdirectory key is rejected

---

## URL Handling

- **Mirror replacement**: `https://huggingface.co/` → `https://hf-mirror.com/`
- **Supported path patterns**:
  - `/<model_id>/resolve/main/<filename>`
  - `/<model_id>/resolve/<version>/<filename>`
  - `/<model_id>/blob/main/<filename>`
  - `/<model_id>/blob/<version>/<filename>`
- Model IDs may contain hyphens (e.g. `google-bert`, `bert-base-uncased`)

---

## Error Classification

| Error Type | Examples | Behavior |
|-----------|----------|----------|
| **Retryable** | timeout, connection reset, DNS failure, 429, 500–504 | Retry up to `retry_times` |
| **Non-retryable** | 401, 403, 404, invalid URL, path traversal | Fail immediately with clear message |

---

## Multi-threading

| Config value | Behavior |
|-------------|----------|
| `workers >= 1` | Use exactly that many threads |
| `workers < 1` or `workers == 0` | Use all available CPU cores |

---

## Progress Display

Each file gets its **own independent progress bar**, showing:
- File name
- Downloaded / Total bytes
- Download speed
- Estimated time remaining

Progress bars must not interfere with each other across threads.

---

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | All downloads succeeded |
| 1 | Some downloads failed |
| 2 | Path security violation (traversal detected) |
| 3 | Configuration error (invalid YAML, missing `downloads:`, nested dict, etc.) |
| 4 | Download error (unrecoverable) |
| 130 | Interrupted by user |

---

## Validation Checklist (on config load)

- [ ] `downloads` key exists and is a dict (not `None` / not a nested structure)
- [ ] Each key under `downloads` is a valid subdir name (no leading/trailing `/`, no `..`)
- [ ] Each value under `downloads` is a list of strings
- [ ] Each URL is a valid HuggingFace URL
- [ ] All subdirectories (except `.`) exist in CWD
- [ ] All intermediate directories for multi-level paths exist
