"""In-memory measurement trend recording for one session.

Thread-safe by a single internal lock: the session worker thread appends
rows while request coroutines start/stop/read. Columns are frozen at start
(the API locks the measurement selection while recording, so row values
always align with them).
"""

import threading
from collections import deque
from typing import Any, Dict, List, Optional, Tuple

MAX_LOG_ROWS = 86400  # 24 h at 1 Hz; a few MB worst case


class TrendRecorder:
    def __init__(self, max_rows: int = MAX_LOG_ROWS):
        self.max_rows = max_rows
        self._lock = threading.Lock()
        self._state = "idle"
        self._started_at: Optional[float] = None
        self._columns: List[Tuple[int, str]] = []
        self._rows: "deque" = deque(maxlen=max_rows)

    @property
    def state(self) -> str:
        with self._lock:
            return self._state

    @property
    def started_at(self) -> Optional[float]:
        with self._lock:
            return self._started_at

    def start(self, columns: List[Tuple[int, str]], started_at: float) -> None:
        """Freeze columns and begin a fresh recording (clears prior rows)."""
        with self._lock:
            self._state = "recording"
            self._started_at = started_at
            self._columns = list(columns)
            self._rows.clear()

    def stop(self) -> None:
        """Stop appending; recorded rows stay available for export."""
        with self._lock:
            self._state = "idle"

    def append(self, timestamp: float, values: List[Optional[float]]) -> None:
        """Record one sample row; a no-op unless recording."""
        with self._lock:
            if self._state == "recording":
                self._rows.append((timestamp, list(values)))

    def status(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "state": self._state,
                "started_at": self._started_at,
                "columns": [{"channel": c, "mtype": m} for c, m in self._columns],
                "row_count": len(self._rows),
                "max_rows": self.max_rows,
            }

    def rows_since(self, since: float = 0.0) -> List[List[Any]]:
        with self._lock:
            return [[ts] + list(values) for ts, values in self._rows if ts > since]
