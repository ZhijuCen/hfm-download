"""
Progress bar implementation using tqdm.
Provides per-file progress tracking compatible with multi-threading.
"""

import threading
from typing import Optional

try:
    from tqdm import tqdm
    TQDM_AVAILABLE = True
except ImportError:
    TQDM_AVAILABLE = False

from .logger import get_logger

logger = get_logger()


class ThreadSafeProgressBar:
    """
    Thread-safe progress bar wrapper.
    Each download task gets its own progress bar instance.
    """
    
    def __init__(self, total: int, desc: str, unit: str = 'B', unit_scale: bool = True):
        """
        Initialize a thread-safe progress bar.
        
        Args:
            total: Total size in bytes
            desc: Description (usually filename)
            unit: Unit for size display
            unit_scale: Whether to scale units (KB, MB, etc.)
        """
        self._lock = threading.Lock()
        self._pbar: Optional[object] = None
        self._total = total
        self._desc = desc
        self._unit = unit
        self._unit_scale = unit_scale
        self._closed = False
        
        if TQDM_AVAILABLE:
            self._pbar = tqdm(
                total=total,
                desc=desc,
                unit=unit,
                unit_scale=unit_scale,
                unit_divisor=1024,
                bar_format='{l_bar}{bar}| {n_fmt}/{total_fmt} [{rate_fmt}, {eta}]',
                colour='green',
                mininterval=0.1,  # Update at most 10 times per second
                maxinterval=1.0,
            )
        else:
            logger.info(f"Downloading {desc}: 0/{total} bytes")
    
    def update(self, amount: int):
        """Update progress by the given amount."""
        with self._lock:
            if self._closed:
                return
            if self._pbar:
                self._pbar.update(amount)
            else:
                # Fallback: log every 10%
                pass  # tqdm not available, minimal output
    
    def set_postfix(self, **kwargs):
        """Set postfix information (e.g., speed)."""
        with self._lock:
            if self._pbar and not self._closed:
                self._pbar.set_postfix(**kwargs)
    
    def close(self):
        """Close the progress bar."""
        with self._lock:
            if self._closed:
                return
            self._closed = True
            if self._pbar:
                self._pbar.close()
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False


class DummyProgressBar:
    """Dummy progress bar for when tqdm is not available."""
    
    def __init__(self, total: int, desc: str, **kwargs):
        self.total = total
        self.desc = desc
        logger.info(f"Download started: {desc} ({total} bytes)")
    
    def update(self, amount: int):
        pass
    
    def set_postfix(self, **kwargs):
        pass
    
    def close(self):
        logger.info(f"Download completed: {self.desc}")
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False


def create_progress_bar(total: int, desc: str, unit: str = 'B', 
                        unit_scale: bool = True, use_tqdm: bool = True):
    """
    Factory function to create appropriate progress bar.
    
    Args:
        total: Total size in bytes
        desc: Description (filename)
        unit: Unit for size display
        unit_scale: Whether to scale units
        use_tqdm: Force tqdm usage (if available)
    
    Returns:
        Progress bar instance
    """
    if use_tqdm and TQDM_AVAILABLE:
        return ThreadSafeProgressBar(total, desc, unit, unit_scale)
    return DummyProgressBar(total, desc)
