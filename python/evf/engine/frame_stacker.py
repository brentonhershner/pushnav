# Copyright (C) 2026 Arun Venkataswamy
#
# This file is part of PushNav.
#
# PushNav is free software: you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# PushNav is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with PushNav. If not, see <https://www.gnu.org/licenses/>.

"""Frame stacker — mean-stacks N consecutive frames before passing to the solver.

Runs as a background thread between the raw LatestFrame (camera output) and a
separate solver LatestFrame.  When stack_count == 1 the frame is forwarded
directly with no copy cost.  Higher counts increase effective exposure time and
improve SNR for faint-star plate solving at the cost of latency.
"""

import io
import logging
import threading
import time

import numpy as np
from PIL import Image

from evf.engine.frame_buffer import LatestFrame

logger = logging.getLogger(__name__)


class FrameStacker:
    """Background thread that mean-stacks frames from *source* into *output*.

    stack_count=1 is a zero-copy passthrough.  stack_count=N accumulates N
    frames in a ring buffer, then writes the mean as a grayscale JPEG.
    """

    def __init__(
        self,
        source: LatestFrame,
        output: LatestFrame,
        stack_count: int = 1,
    ) -> None:
        self._source = source
        self._output = output
        self._lock = threading.Lock()
        self._stack_count = max(1, int(stack_count))
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()

    @property
    def stack_count(self) -> int:
        with self._lock:
            return self._stack_count

    @stack_count.setter
    def stack_count(self, n: int) -> None:
        with self._lock:
            self._stack_count = max(1, int(n))
            # Signal ring reset via a sentinel; the run loop checks this.
            self._reset_ring = True

    def start(self) -> None:
        self._stop.clear()
        self._reset_ring = False
        self._thread = threading.Thread(
            target=self._run, name="frame-stacker", daemon=True
        )
        self._thread.start()

    def stop(self, timeout: float = 2.0) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=timeout)
            self._thread = None

    def _run(self) -> None:
        last_id = -1
        ring: list[np.ndarray] = []
        current_n = self._stack_count

        while not self._stop.is_set():
            jpeg, ts, fid = self._source.get()
            if jpeg is None or fid == last_id:
                time.sleep(0.005)
                continue
            last_id = fid

            with self._lock:
                n = self._stack_count
                reset = getattr(self, "_reset_ring", False)
                if reset:
                    self._reset_ring = False

            if n != current_n or reset:
                ring.clear()
                current_n = n

            # Passthrough when stacking is disabled
            if n == 1:
                self._output.set(jpeg, ts, fid)
                continue

            # Decode to grayscale float32
            try:
                arr = np.array(
                    Image.open(io.BytesIO(jpeg)).convert("L"), dtype=np.float32
                )
            except Exception as exc:
                logger.debug("FrameStacker: decode error: %s", exc)
                continue

            ring.append(arr)
            if len(ring) > n:
                ring.pop(0)

            if len(ring) < n:
                continue

            # Mean-stack and re-encode as grayscale JPEG
            stacked = np.mean(ring, axis=0).clip(0, 255).astype(np.uint8)
            img = Image.fromarray(stacked, mode="L")
            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=92)
            self._output.set(buf.getvalue(), ts, fid)
