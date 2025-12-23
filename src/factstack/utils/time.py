"""Time utilities for FactStack."""

import time
from datetime import datetime
from typing import Optional
from contextlib import contextmanager


def get_timestamp() -> str:
    """Get current timestamp in ISO format."""
    return datetime.now().isoformat()


def get_timestamp_for_filename() -> str:
    """Get timestamp suitable for filenames."""
    return datetime.now().strftime("%Y%m%d_%H%M%S")


@contextmanager
def timer():
    """Context manager to measure elapsed time in milliseconds."""
    class TimerResult:
        def __init__(self):
            self.start_time: float = 0
            self.end_time: float = 0
            self.elapsed_ms: float = 0
    
    result = TimerResult()
    result.start_time = time.time()
    try:
        yield result
    finally:
        result.end_time = time.time()
        result.elapsed_ms = (result.end_time - result.start_time) * 1000


def format_duration(ms: float) -> str:
    """Format duration in human-readable format."""
    if ms < 1000:
        return f"{ms:.1f}ms"
    elif ms < 60000:
        return f"{ms/1000:.2f}s"
    else:
        minutes = int(ms // 60000)
        seconds = (ms % 60000) / 1000
        return f"{minutes}m {seconds:.1f}s"
