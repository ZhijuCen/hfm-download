"""
Core download logic with retry mechanism and multi-threading support.
"""

import os
import time
import threading
import urllib.request
import urllib.error
from pathlib import Path
from typing import List, Tuple, Optional, Callable
from concurrent.futures import ThreadPoolExecutor, as_completed

from .config import Config, extract_mirror_url
from .exceptions import (
    DownloadError, RetryableError, NonRetryableError, 
    PathTraversalError
)
from .path_utils import build_dest_path, validate_subdir_exists
from .progress import create_progress_bar
from .logger import get_logger

logger = get_logger()


# HTTP status codes that are retryable
RETRYABLE_STATUS_CODES = {408, 429, 499, 500, 502, 503, 504}

# Errors that are retryable (connection errors)
RETRYABLE_ERRORS = (
    urllib.error.URLError,
    ConnectionError,
    TimeoutError,
    ConnectionResetError,
    ConnectionRefusedError,
)


def is_retryable_error(e: Exception, status_code: Optional[int] = None) -> bool:
    """
    Determine if an error is retryable.
    
    Args:
        e: Exception instance
        status_code: HTTP status code if available
    
    Returns:
        True if the error can be retried
    """
    # Check status code
    if status_code and status_code in RETRYABLE_STATUS_CODES:
        return True
    
    # Check exception type
    if isinstance(e, urllib.error.HTTPError):
        status = e.code
        # Permanent errors (don't retry)
        if status in {401, 403, 404, 410}:
            return False
        # Server errors (retry)
        if status >= 500:
            return True
    
    # Connection errors are retryable
    if isinstance(e, RETRYABLE_ERRORS):
        return True
    
    # Check underlying reason
    if isinstance(e, urllib.error.URLError):
        reason = e.reason
        if isinstance(reason, str):
            # DNS failures, timeouts, connection refused
            retry_keywords = [
                'timed out', 'timeout', 'connection refused',
                'dns', 'reset', 'network unreachable'
            ]
            return any(kw in reason.lower() for kw in retry_keywords)
    
    return False


def download_file(url: str, dest_path: Path, timeout: int = 30,
                   retry_times: int = 3, progress_callback: Optional[Callable] = None) -> bool:
    """
    Download a single file with retry logic.
    
    Args:
        url: Mirror URL to download from
        dest_path: Destination file path
        timeout: Request timeout in seconds
        retry_times: Number of retry attempts
        progress_callback: Optional callback(current, total) for progress updates
    
    Returns:
        True if download succeeded
    
    Raises:
        NonRetryableError: For permanent failures
        RetryableError: After all retries exhausted for temporary failures
    """
    headers = {
        'User-Agent': 'hfm-download/1.0 (HuggingFace Mirror Downloader)'
    }
    
    last_error = None
    
    for attempt in range(retry_times + 1):
        try:
            logger.info(f"Downloading {dest_path.name} (attempt {attempt + 1}/{retry_times + 1})")
            
            request = urllib.request.Request(url, headers=headers)
            
            with urllib.request.urlopen(request, timeout=timeout) as response:
                total_size = int(response.headers.get('Content-Length', 0))
                logger.info(f"File size: {total_size} bytes")
                
                # Create progress bar
                pbar = create_progress_bar(total_size, dest_path.name)
                
                downloaded = 0
                chunk_size = 8192  # 8KB chunks
                
                with open(dest_path, 'wb') as f:
                    while True:
                        chunk = response.read(chunk_size)
                        if not chunk:
                            break
                        
                        f.write(chunk)
                        downloaded += len(chunk)
                        
                        if progress_callback:
                            progress_callback(len(chunk), total_size)
                        else:
                            pbar.update(len(chunk))
                
                pbar.close()
                
                # Verify final size if known
                if total_size > 0 and downloaded != total_size:
                    logger.warning(
                        f"Downloaded size mismatch for {dest_path.name}: "
                        f"expected {total_size}, got {downloaded}"
                    )
                
                logger.info(f"Successfully downloaded {dest_path.name} to {dest_path}")
                return True
                
        except urllib.error.HTTPError as e:
            last_error = e
            status_code = e.code
            
            if not is_retryable_error(e, status_code):
                logger.error(f"Non-retryable HTTP error {status_code}: {url}")
                raise NonRetryableError(
                    f"HTTP {status_code}: {url} - "
                    f"{'Authentication failed' if status_code in {401, 403} else 'Resource not found' if status_code == 404 else 'Server error'}"
                )
            
            if attempt < retry_times:
                logger.warning(f"Retryable error {status_code}, retrying...")
                time.sleep(1)  # Simple delay before retry
            else:
                logger.error(f"Max retries ({retry_times}) exhausted for {url}")
                raise RetryableError(f"Failed after {retry_times} retries: HTTP {status_code}")
                
        except urllib.error.URLError as e:
            last_error = e
            
            if not is_retryable_error(e):
                logger.error(f"Non-retryable URL error: {e.reason}")
                raise NonRetryableError(f"URL error: {e.reason}")
            
            if attempt < retry_times:
                logger.warning(f"Retryable error: {e.reason}, retrying...")
                time.sleep(1)
            else:
                logger.error(f"Max retries ({retry_times}) exhausted for {url}")
                raise RetryableError(f"Failed after {retry_times} retries: {e.reason}")
                
        except Exception as e:
            last_error = e
            
            if is_retryable_error(e):
                if attempt < retry_times:
                    logger.warning(f"Retryable error: {e}, retrying...")
                    time.sleep(1)
                else:
                    raise RetryableError(f"Failed after {retry_times} retries: {e}")
            else:
                raise NonRetryableError(f"Download failed: {e}")
    
    # This shouldn't be reached, but just in case
    raise RetryableError(f"Failed after {retry_times} retries: {last_error}")


class DownloadWorker(threading.Thread):
    """Worker thread for downloading files."""
    
    def __init__(self, task_queue: List[Tuple[str, str, str]], config: Config, cwd: str,
                 results: dict, lock: threading.Lock, progress_lock: threading.Lock):
        """
        Initialize download worker.
        
        Args:
            task_queue: List of (subdir, filename, url) tuples
            config: Configuration object
            cwd: Current working directory
            results: Shared results dictionary
            lock: Lock for results dictionary
            progress_lock: Lock for progress updates
        """
        super().__init__(daemon=True)
        self.tasks = task_queue
        self.config = config
        self.cwd = cwd
        self.results = results
        self.lock = lock
        self.progress_lock = progress_lock
    
    def run(self):
        """Execute download tasks."""
        for subdir, filename, url in self.tasks:
            thread_name = threading.current_thread().name
            
            try:
                logger.info(f"[{thread_name}] Starting download: {filename}")
                
                # Build and validate destination path
                abs_subdir = validate_subdir_exists(subdir, self.cwd)
                dest_path = build_dest_path(abs_subdir, filename, self.cwd)
                
                # Download with retry
                success = download_file(
                    url=url,
                    dest_path=dest_path,
                    timeout=self.config.timeout,
                    retry_times=self.config.retry_times
                )
                
                with self.lock:
                    self.results[filename] = {'status': 'success', 'path': str(dest_path)}
                    
            except NonRetryableError as e:
                logger.error(f"[{thread_name}] Failed permanently: {filename} - {e}")
                with self.lock:
                    self.results[filename] = {'status': 'failed', 'error': str(e)}
                    
            except RetryableError as e:
                logger.error(f"[{thread_name}] Failed after retries: {filename} - {e}")
                with self.lock:
                    self.results[filename] = {'status': 'failed', 'error': str(e)}
                    
            except Exception as e:
                logger.error(f"[{thread_name}] Unexpected error: {filename} - {e}")
                with self.lock:
                    self.results[filename] = {'status': 'failed', 'error': str(e)}


def download_all(config: Config, cwd: str) -> dict:
    """
    Download all files specified in configuration using multi-threading.
    
    Args:
        config: Validated Config object
        cwd: Current working directory
    
    Returns:
        Dictionary mapping filenames to download results
    """
    # Get all download tasks
    tasks: List[Tuple[str, str, str]] = []  # (subdir, filename, url)
    
    for subdir, urls in config.sources.items():
        for url in urls:
            from .config import parse_hf_url
            _, filename = parse_hf_url(url)
            tasks.append((subdir, filename, url))
    
    logger.info(f"Starting download of {len(tasks)} files with {config.get_effective_workers()} workers")
    
    # Shared results
    results = {}
    results_lock = threading.Lock()
    progress_lock = threading.Lock()
    
    # Distribute tasks across workers
    effective_workers = config.get_effective_workers()
    tasks_per_worker = len(tasks) // effective_workers
    extra_tasks = len(tasks) % effective_workers
    
    worker_tasks = []
    start = 0
    
    for i in range(effective_workers):
        count = tasks_per_worker + (1 if i < extra_tasks else 0)
        worker_tasks.append(tasks[start:start + count])
        start += count
    
    # Start worker threads
    workers = []
    for i, task_list in enumerate(worker_tasks):
        if task_list:  # Only start workers with tasks
            worker = DownloadWorker(
                task_queue=task_list,
                config=config,
                cwd=cwd,
                results=results,
                lock=results_lock,
                progress_lock=progress_lock
            )
            worker.start()
            workers.append(worker)
    
    # Wait for all workers to complete
    for worker in workers:
        worker.join()
    
    # Summarize results
    success_count = sum(1 for r in results.values() if r['status'] == 'success')
    fail_count = len(results) - success_count
    
    logger.info(f"Download complete: {success_count} succeeded, {fail_count} failed")
    
    if fail_count > 0:
        logger.warning("Failed downloads:")
        for filename, result in results.items():
            if result['status'] == 'failed':
                logger.warning(f"  - {filename}: {result['error']}")
    
    return results
