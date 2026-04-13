"""
YAML configuration loading and validation for hfm-download.
"""

import os
import re
import yaml
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

from .exceptions import ConfigValidationError
from .logger import get_logger

logger = get_logger()


# HuggingFace URL patterns for validation
HF_URL_PATTERNS = [
    r'^https?://huggingface\.co/',
    r'^https?://hf-mirror\.com/',
]

HF_URL_REGEX = re.compile('|'.join(HF_URL_PATTERNS))

# Valid subdir key pattern: alphanumeric, hyphen, underscore, dot, forward-slash
SUBDIR_KEY_REGEX = re.compile(r'^[a-zA-Z0-9_./-]+$')


class Config:
    """Configuration container with validation."""
    
    def __init__(self, retry_times: int = 3, timeout: int = 30, workers: int = 1,
                 endpoint: Optional[str] = None):
        self.retry_times = retry_times
        self.timeout = timeout
        self.workers = workers
        self.endpoint = endpoint
        # source mapping: {dest_child_dir: [url1, url2, ...]}
        self.sources: Dict[str, List[str]] = {}
    
    @property
    def cpu_cores(self) -> int:
        """Get CPU core count for fallback."""
        return os.cpu_count() or 1
    
    def get_effective_workers(self) -> int:
        """Get effective worker count (minimum 1, or CPU cores if < 1)."""
        if self.workers < 1:
            return self.cpu_cores
        return self.workers
    
    def __repr__(self):
        return (f"Config(retry_times={self.retry_times}, timeout={self.timeout}, "
                f"workers={self.workers}, endpoint={self.endpoint}, "
                f"sources={list(self.sources.keys())})")


def validate_hf_url(url: str) -> bool:
    """
    Validate if a URL is a valid HuggingFace URL.
    
    Args:
        url: URL to validate
    
    Returns:
        True if valid HuggingFace URL
    """
    return bool(HF_URL_REGEX.match(url.strip()))


def parse_hf_url(url: str) -> Tuple[str, str]:
    """
    Parse a HuggingFace URL and return the model_id and filename.
    
    Args:
        url: HuggingFace URL (original or mirror)
    
    Returns:
        Tuple of (model_id, filename)
    
    Example:
        'https://huggingface.co/bert-base/resolve/main/model.bin'
        -> ('bert-base', 'model.bin')
    """
    url = url.strip()
    
    # Replace huggingface.co with hf-mirror.com if present
    mirror_url = url.replace('https://huggingface.co/', 'https://hf-mirror.com/')
    
    # Parse URL to extract path components
    parsed = urlparse(mirror_url)
    path_parts = [p for p in parsed.path.split('/') if p]
    
    # Supported URL patterns:
    #   /{model_id}/resolve/{version}/{filename}
    #   /{model_id}/resolve/{filename}
    #   /{model_id}/blob/{version}/{filename}     <- blob path, version usually 'main'
    #   /{model_id}/blob/{filename}               <- blob path without version
    #
    # NOTE: model_id may contain hyphens, so resolve/blob are found by search
    try:
        op_index = next(i for i, p in enumerate(path_parts) if p in ('resolve', 'blob'))
    except StopIteration:
        raise ConfigValidationError(
            f"Invalid HuggingFace URL format: {url}. "
            f"Expected: https://huggingface.co/<model>/resolve/<filename> "
            f"or https://huggingface.co/<model>/blob/<filename>"
        )
    
    if op_index == 0:
        raise ConfigValidationError(
            f"Invalid HuggingFace URL format: {url}. "
            f"Model ID is missing."
        )
    
    model_id = path_parts[0]
    filename = path_parts[-1]
    
    return model_id, filename


def extract_mirror_url(url: str, endpoint: Optional[str] = None) -> str:
    """
    Convert original HuggingFace URL to mirror URL.
    
    Args:
        url: Original huggingface.co URL (http or https)
        endpoint: Optional custom mirror endpoint. If provided, replaces
                  huggingface.co with this endpoint. Must be HTTPS URL.
    
    Returns:
        Mirror URL using the endpoint (custom if provided, else hf-mirror.com)
    """
    if endpoint:
        # Use custom endpoint (ensure it ends with / for proper replacement)
        base = endpoint.rstrip('/') + '/'
        url = url.replace('http://huggingface.co/', base)
        url = url.replace('https://huggingface.co/', base)
    else:
        # Default to hf-mirror.com
        url = url.replace('http://huggingface.co/', 'https://hf-mirror.com/')
        url = url.replace('https://huggingface.co/', 'https://hf-mirror.com/')
    return url


def load_config(config_path: Optional[str] = None) -> Config:
    """
    Load configuration from YAML file.
    
    Supported YAML format:
        downloads:
          ".":
            - https://huggingface.co/...
          bert:
            - https://huggingface.co/...
    
    Args:
        config_path: Path to YAML config file. 
                     If None, uses CONFIG_FILE from env or default 'hfm-config.yaml'
    
    Returns:
        Validated Config object
    
    Raises:
        ConfigValidationError: If configuration is invalid
    """
    # Determine config file path
    if not config_path:
        config_path = os.environ.get('HFM_CONFIG_FILE', 'hfm-config.yaml')
    
    config_file = Path(config_path)
    
    if not config_file.exists():
        raise ConfigValidationError(
            f"Configuration file not found: {config_path}. "
            f"Please create a YAML config file or specify a different path with --config."
        )
    
    logger.info(f"Loading configuration from: {config_path}")
    
    # Load YAML
    try:
        with open(config_file, 'r', encoding='utf-8') as f:
            raw_config = yaml.safe_load(f)
    except yaml.YAMLError as e:
        raise ConfigValidationError(f"Failed to parse YAML: {e}")
    
    if not raw_config:
        raise ConfigValidationError("Configuration file is empty")
    
    # Parse into Config object
    config = Config()
    
    # Optional: retry_times
    if 'retry_times' in raw_config:
        config.retry_times = int(raw_config['retry_times'])
        logger.info(f"Retry times: {config.retry_times}")
    
    # Optional: timeout
    if 'timeout' in raw_config:
        config.timeout = int(raw_config['timeout'])
        logger.info(f"Timeout: {config.timeout}s")
    
    # Optional: workers
    if 'workers' in raw_config:
        config.workers = int(raw_config['workers'])
        logger.info(f"Workers: {config.workers} (effective: {config.get_effective_workers()})")
    
    # Optional: endpoint (custom mirror base URL)
    if 'endpoint' in raw_config:
        endpoint = raw_config['endpoint']
        if endpoint is not None:
            # Validate it's a valid HTTPS URL
            endpoint_str = str(endpoint).strip().rstrip('/')
            if endpoint_str:
                parsed = urlparse(endpoint_str)
                if parsed.scheme != 'https' or not parsed.netloc:
                    raise ConfigValidationError(
                        f"Invalid endpoint URL: {endpoint}. "
                        f"Endpoint must be a valid HTTPS URL (e.g., https://mirror.example.com)"
                    )
                config.endpoint = endpoint_str + '/'
                logger.info(f"Custom endpoint: {config.endpoint}")
            else:
                logger.info("Endpoint is empty, using default hf-mirror.com")
    
    if config.endpoint is None:
        logger.info("Using default mirror: https://hf-mirror.com/")
    
    # Look for 'downloads' section
    if 'downloads' not in raw_config:
        raise ConfigValidationError(
            "Configuration must contain a 'downloads' section. "
            "Example:\n"
            "  downloads:\n"
            "    '.':\n"
            "      - https://huggingface.co/..."
        )
    
    downloads_section = raw_config['downloads']
    
    if not isinstance(downloads_section, dict):
        raise ConfigValidationError(
            f"'downloads' must be a dictionary mapping subdirectories to URL lists, "
            f"got {type(downloads_section).__name__}"
        )
    
    for subdir, urls in downloads_section.items():
        # Validate key format (no nested dicts allowed)
        if isinstance(urls, dict):
            raise ConfigValidationError(
                f"downloads['{subdir}'] is a nested dict, which is not supported. "
                f"Use a flat structure with '/' to separate path levels, e.g.: "
                f"downloads:\n  'models/bert':\n    - https://...\n"
                f"Instead of:\n  downloads:\n    models:\n      bert:\n        - https://..."
            )
        
        if not isinstance(urls, list):
            raise ConfigValidationError(
                f"downloads['{subdir}'] must be a list of URLs, "
                f"got {type(urls).__name__}"
            )
        
        # Validate subdir key format (no leading/trailing /, no ..)
        if subdir != '.':
            if not SUBDIR_KEY_REGEX.match(subdir):
                raise ConfigValidationError(
                    f"downloads key '{subdir}' contains invalid characters. "
                    f"Use only letters, numbers, hyphen (-), underscore (_), dot (.), and forward slash (/). "
                    f"No leading/trailing slashes, no '..'."
                )
            if subdir.startswith('/') or subdir.endswith('/'):
                raise ConfigValidationError(
                    f"downloads key '{subdir}' must not start or end with '/'."
                )
            if '..' in subdir:
                raise ConfigValidationError(
                    f"downloads key '{subdir}' must not contain '..' (path traversal not allowed)."
                )
        
        if not urls:
            continue  # Skip empty lists
        
        validated_urls = []
        for url in urls:
            if not isinstance(url, str):
                raise ConfigValidationError(
                    f"Each URL in downloads['{subdir}'] must be a string, "
                    f"got {type(url).__name__}"
                )
            
            url = url.strip()
            if not url:
                continue
            
            if not validate_hf_url(url):
                raise ConfigValidationError(
                    f"Invalid HuggingFace URL in downloads['{subdir}']: {url}"
                )
            
            # Convert to mirror URL using configured endpoint
            mirror_url = extract_mirror_url(url, config.endpoint)
            validated_urls.append(mirror_url)
        
        if validated_urls:
            config.sources[subdir] = validated_urls
            logger.info(f"Loaded {len(validated_urls)} URLs for '{subdir}'")
    
    if not config.sources:
        raise ConfigValidationError(
            "No valid download URLs found in 'downloads' section."
        )
    
    logger.info(f"Configuration loaded successfully: {config}")
    return config


def validate_config_for_cwd(config: Config, cwd: str) -> List[Tuple[str, str]]:
    """
    Validate all paths and URLs in config against current working directory.
    
    Args:
        config: Loaded Config object
        cwd: Current working directory
    
    Returns:
        List of (subdir, filename) tuples for each download task
    
    Raises:
        PathTraversalError: If any path escapes cwd
        ConfigValidationError: If any URL is invalid
    """
    from .path_utils import validate_subdir_exists
    
    tasks = []
    
    for subdir, urls in config.sources.items():
        logger.info(f"Validating subdir '{subdir}' for cwd '{cwd}'")
        
        # Validate subdir exists and is safe
        # Note: '.' is handled specially in validate_subdir_exists (cwd itself)
        try:
            abs_subdir = validate_subdir_exists(subdir, cwd)
        except Exception as e:
            raise ConfigValidationError(f"Invalid subdirectory '{subdir}': {e}")
        
        for url in urls:
            try:
                model_id, filename = parse_hf_url(url)
                tasks.append((subdir, filename, url))
            except ConfigValidationError:
                raise
            except Exception as e:
                raise ConfigValidationError(f"Failed to parse URL '{url}': {e}")
    
    logger.info(f"All {len(tasks)} download tasks validated successfully")
    return tasks
