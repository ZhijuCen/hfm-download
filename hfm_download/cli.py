"""
Command-line interface for hfm-download.
"""

import argparse
import sys
import os
from pathlib import Path

from .config import load_config, validate_config_for_cwd
from .downloader import download_all
from .exceptions import HfmDownloadError, PathTraversalError, ConfigValidationError
from .logger import setup_logger, get_logger
from . import __version__


# Help text
HELP_TEXT = """
hfm-download - HuggingFace Mirror Downloader

Automatically replace HuggingFace URLs with hf-mirror.com and download
files safely within your current working directory.

Examples:
  hfm-download --help
  hfm-download --config my-config.yaml
  hfm-download --config my-config.yaml --verbose

Configuration YAML format:
  # Optional settings
  retry_times: 3      # Number of retries on failure (default: 3)
  timeout: 30         # Request timeout in seconds (default: 30)
  workers: 0          # Parallel workers (default: 1, 0 = all CPU cores)

  downloads:
    ".":
      - https://huggingface.co/google-bert/bert-base-uncased/blob/main/model.safetensors

    models:
      - https://huggingface.co/google-bert/bert-base-uncased/blob/main/model.safetensors

    "models/bert":
      - https://huggingface.co/google-bert/bert-base-uncased/blob/main/model.safetensors

Notes:
  - Subdirectory must exist in current working directory (except ".")
  - "." means current directory; multi-level keys like "models/bert" are flat (no nesting)
  - All intermediate directories must already exist (mkdir -p models/bert)
  - Invalid URLs or path traversal attempts will fail with clear errors
  - Set workers to 0 to automatically use all CPU cores
"""


EXAMPLE_CONFIG = """
# Example hfm-download configuration file (hfm-config.yaml)

# Optional settings
retry_times: 3
timeout: 30
workers: 0            # 0 = use all CPU cores

# ============================================================================
# DOWNLOAD SECTION
# downloads is a FLAT dictionary. Keys are target directories.
# - '.' means current working directory itself
# - 'models/bert' means subdirectory 'models/bert/' (mkdir -p first)
# - NO NESTED DICTS: use 'models/bert:' not 'models: { bert: ... }'
# ============================================================================

downloads:
  # CASE 1: Download directly into current working directory
  ".":
    - "https://huggingface.co/google-bert/bert-base-uncased/blob/main/model.safetensors"

  # CASE 2: Single-level subdirectory (mkdir -p models first)
  models:
    - "https://huggingface.co/google-bert/bert-base-uncased/blob/main/model.safetensors"

  # CASE 3: Multi-level subdirectory (mkdir -p models/bert first)
  "models/bert":
    - "https://huggingface.co/google-bert/bert-base-uncased/blob/main/model.safetensors"

  # CASE 4: Datasets with multi-level path
  "datasets/imdb":
    - "https://huggingface.co/datasets/stanfordnlp/imdb/blob/main/plain_text/train-00000-of-00001.parquet"
"""


def create_parser() -> argparse.ArgumentParser:
    """Create and configure argument parser."""
    parser = argparse.ArgumentParser(
        prog='hfm-download',
        description=HELP_TEXT,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"""
Configuration File:
  By default, looks for 'hfm-config.yaml' in current directory.
  Set HFM_CONFIG_FILE env var or use --config to specify a different file.

Examples:
  # Download using default config file
  hfm-download
  
  # Download using custom config
  hfm-download --config my-config.yaml
  
  # Verbose output
  hfm-download --config my-config.yaml --verbose

For more information, see the project documentation.
"""
    )
    
    parser.add_argument(
        '--config', '-c',
        type=str,
        default=None,
        help='Path to YAML configuration file (default: hfm-config.yaml or $HFM_CONFIG_FILE)'
    )
    
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Enable verbose (DEBUG) logging'
    )
    
    parser.add_argument(
        '--version',
        action='version',
        version=f'hfm-download {__version__}'
    )
    
    parser.add_argument(
        '--example-config',
        action='store_true',
        help='Print example configuration file and exit'
    )
    
    parser.add_argument(
        '--force', '-f',
        action='store_true',
        help='Overwrite existing files even if already downloaded'
    )
    
    return parser


def main(argv: list = None) -> int:
    """
    Main entry point for hfm-download CLI.
    
    Args:
        argv: Command-line arguments (defaults to sys.argv)
    
    Returns:
        Exit code (0 = success, non-zero = failure)
    """
    parser = create_parser()
    args = parser.parse_args(argv)
    
    # Handle --example-config
    if args.example_config:
        print(EXAMPLE_CONFIG)
        return 0
    
    # Setup logging
    log_level = 10 if args.verbose else 20  # DEBUG if verbose, INFO otherwise
    setup_logger(level=log_level)
    logger = get_logger()
    
    try:
        # Get current working directory
        cwd = os.getcwd()
        logger.info(f"Current working directory: {cwd}")
        
        # Load configuration
        config = load_config(args.config)
        
        # Validate all paths and URLs
        tasks = validate_config_for_cwd(config, cwd)
        
        # Start downloads
        logger.info(f"Starting {len(tasks)} download tasks...")
        force = args.force
        results = download_all(config, cwd, force=force)
        
        # Print summary
        success = [f for f, r in results.items() if r['status'] == 'success']
        skipped = [f for f, r in results.items() if r['status'] == 'skipped']
        failed = [f for f, r in results.items() if r['status'] == 'failed']
        
        print(f"\n{'='*50}")
        print(f"Download Summary")
        print(f"{'='*50}")
        print(f"Total tasks: {len(results)}")
        print(f"Succeeded: {len(success)}")
        print(f"Skipped: {len(skipped)}")
        print(f"Failed: {len(failed)}")
        
        if skipped:
            print(f"\nSkipped files:")
            for filename in skipped:
                print(f"  - {filename}")
        
        if failed:
            print(f"\nFailed files:")
            for filename in failed:
                print(f"  - {filename}: {results[filename]['error']}")
            return 1
        
        return 0
        
    except PathTraversalError as e:
        logger.error(f"Path security violation: {e}")
        print(f"\nERROR: {e}", file=sys.stderr)
        print("Download aborted due to path security violation.", file=sys.stderr)
        return 2
        
    except ConfigValidationError as e:
        logger.error(f"Configuration error: {e}")
        print(f"\nERROR: {e}", file=sys.stderr)
        print("Please fix your configuration file and try again.", file=sys.stderr)
        return 3
        
    except HfmDownloadError as e:
        logger.error(f"Download error: {e}")
        print(f"\nERROR: {e}", file=sys.stderr)
        return 4
        
    except KeyboardInterrupt:
        logger.warning("Download interrupted by user")
        print("\n\nDownload interrupted by user.", file=sys.stderr)
        return 130
        
    except Exception as e:
        logger.exception(f"Unexpected error: {e}")
        print(f"\nERROR: {e}", file=sys.stderr)
        return 99


if __name__ == '__main__':
    sys.exit(main())
