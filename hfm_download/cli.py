"""
Command-line interface for hfm-download.
"""

import argparse
import sys
import os
from pathlib import Path
from typing import List

import yaml

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


def create_root_parser() -> argparse.ArgumentParser:
    """Create the root argument parser with global options."""
    parser = argparse.ArgumentParser(
        prog='hfm-download',
        description=HELP_TEXT,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    
    parser.add_argument(
        '--version',
        action='version',
        version=f'hfm-download {__version__}'
    )
    
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Enable verbose (DEBUG) logging'
    )
    
    return parser


def create_subparsers(parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
    """Create and configure subcommand parsers."""
    subparsers = parser.add_subparsers(
        dest='command',
        help='Available commands'
    )
    
    # =========================================================================
    # init subcommand
    # =========================================================================
    init_parser = subparsers.add_parser(
        'init',
        help='Initialize a new configuration file',
        description='Create a new hfm-config.yaml file with default settings.'
    )
    
    init_parser.add_argument(
        'filename',
        nargs='?',
        default='hfm-config.yaml',
        help='Path to the configuration file (default: hfm-config.yaml)'
    )
    
    init_parser.add_argument(
        '--levels', '-l',
        type=int,
        default=0,
        help='Number of directory levels to explore (default: 0, meaning no limit)'
    )
    
    init_parser.add_argument(
        '--all-dir',
        action='store_true',
        help='Include all directories found in current working directory'
    )
    
    init_parser.add_argument(
        '--dirs',
        nargs='+',
        metavar='DIR',
        help='Specific directories to include (space-separated)'
    )
    
    # =========================================================================
    # run subcommand
    # =========================================================================
    run_parser = subparsers.add_parser(
        'run',
        help='Run downloads from a configuration file',
        description='Download files according to the configuration file.'
    )
    
    run_parser.add_argument(
        'config',
        help='Path to YAML configuration file'
    )
    
    run_parser.add_argument(
        '--force', '-f',
        action='store_true',
        help='Overwrite existing files even if already downloaded'
    )
    
    run_parser.add_argument(
        '--endpoint',
        type=str,
        help='Override the HuggingFace endpoint URL'
    )
    
    run_parser.add_argument(
        '--workers',
        type=int,
        help='Number of parallel workers (default: from config, 0 = all CPU cores)'
    )
    
    run_parser.add_argument(
        '--timeout',
        type=int,
        help='Request timeout in seconds (default: from config)'
    )
    
    run_parser.add_argument(
        '--retry-times',
        type=int,
        help='Number of retries on failure (default: from config)'
    )
    
    return subparsers


def create_parser() -> argparse.ArgumentParser:
    """Create and configure the full argument parser with subcommands."""
    parser = create_root_parser()
    create_subparsers(parser)
    return parser


def _generate_downloads_keys(levels: int, all_dir: bool, dirs: List[str]) -> List[str]:
    """
    Generate list of downloads keys based on levels and flags.
    
    Args:
        levels: Number of directory levels to generate
        all_dir: If True, generate placeholder dir structure
        dirs: List of specific directory paths to generate intermediates for
        
    Returns:
        List of directory keys for the downloads section
    """
    keys = ["."]
    
    if levels == 0:
        # Only current directory
        return keys
    
    if levels >= 1:
        # Generate placeholder subdirectories
        # For levels=1: "dir1", "dir2"
        # For levels=2 with all_dir: "dir1", "dir1/subdir1", "dir2", "dir2/subdir1"
        # etc.
        placeholder_tops = ["dir1", "dir2", "dir3"]
        
        if all_dir:
            # Generate full placeholder tree up to 'levels' depth
            for top in placeholder_tops:
                keys.append(top)
                # Build path incrementally: dir1, dir1/subdir1, dir1/subdir1/subdir1, etc.
                for depth in range(1, levels):
                    keys.append(top + "/".join([""] + ["subdir1"] * depth))
        else:
            # Not all_dir - just single level placeholders
            for i in range(1, min(levels + 1, 4)):  # up to dir3
                keys.append(f"dir{i}")
    
    # Handle explicit --dirs
    if dirs:
        for d in dirs:
            # Normalize path: remove leading ./ and split
            clean_d = os.path.normpath(d).lstrip("./")
            parts = clean_d.split("/")
            
            # Generate all intermediate levels up to 'levels' depth
            for i in range(1, min(len(parts), levels) + 1):
                intermediate = "/".join(parts[:i])
                if intermediate not in keys:
                    keys.append(intermediate)
    
    return keys


def _init_main(args: argparse.Namespace) -> int:
    """
    Main entry point for the 'init' subcommand.
    
    Args:
        args: Parsed command-line arguments
        
    Returns:
        Exit code (0 = success, non-zero = failure)
    """
    # Validation: levels > 1 requires either --all-dir or --dirs
    if args.levels > 1 and not args.all_dir and not args.dirs:
        print("error: --levels > 1 requires either --all-dir or --dirs", file=sys.stderr)
        return 1
    
    # Generate the downloads keys
    keys = _generate_downloads_keys(args.levels, args.all_dir, args.dirs)
    
    # Build the config scaffold
    config_scaffold = {
        'workers': 1,
        'timeout': 30,
        'retry_times': 3,
        'downloads': {}
    }
    
    for key in keys:
        config_scaffold['downloads'][key] = []  # empty list, user fills in URLs
    
    # Write to file
    filename = args.filename
    with open(filename, 'w', encoding='utf-8') as f:
        yaml.dump(config_scaffold, f, default_flow_style=False, sort_keys=False)
    
    print(f"Created {filename}")
    return 0


def _run_main(args: argparse.Namespace) -> int:
    """
    Main entry point for the 'run' subcommand.
    
    Args:
        args: Parsed command-line arguments
        
    Returns:
        Exit code (0 = success, non-zero = failure)
    """
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
        
        # Override config values from CLI args (only if the CLI arg is not None)
        if args.endpoint is not None:
            config.endpoint = args.endpoint
        if args.workers is not None:
            config.workers = args.workers
        if args.timeout is not None:
            config.timeout = args.timeout
        if args.retry_times is not None:
            config.retry_times = args.retry_times
        
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
                print(f"  - {filename}: already exists (use --force to overwrite)")
        
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
    
    # Setup logging using global --verbose
    log_level = 10 if args.verbose else 20
    setup_logger(level=log_level)
    
    if args.command == 'init':
        return _init_main(args)
    elif args.command == 'run':
        return _run_main(args)
    else:
        parser.print_help()
        return 0


if __name__ == '__main__':
    sys.exit(main())
