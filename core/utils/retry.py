from __future__ import annotations

import random
import time
from typing import Callable, TypeVar, Optional, Tuple

T = TypeVar("T")

def retry(
    fn: Callable[[], T],
    attempts: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 8.0,
    jitter: float = 0.25,
    on_error: Optional[Callable[[int, Exception], None]] = None,
    retry_on: Tuple[type, ...] = (Exception,),
) -> T:
    """Simple retry with exponential backoff + jitter."""
    last_exc: Exception | None = None
    for i in range(1, max(1, attempts) + 1):
        try:
            return fn()
        except retry_on as e:  # type: ignore[misc]
            last_exc = e
            if on_error:
                on_error(i, e)
            if i >= attempts:
                break
            delay = min(max_delay, base_delay * (2 ** (i - 1)))
            delay = delay * (1.0 + random.uniform(-jitter, jitter))
            time.sleep(max(0.0, delay))
    assert last_exc is not None
    raise last_exc
