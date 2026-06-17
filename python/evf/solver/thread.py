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

"""Solver thread — runs plate solving in a background thread.

Per SPEC_ARCHITECTURE.md §4.2 and impl0.md §Phase 6.
"""

import logging
import threading
import time

from evf.config.manager import ConfigManager
from evf.engine.audio import AudioAlert
from evf.engine.frame_buffer import LatestFrame
from evf.engine.pointing import PointingState
from evf.engine.state import EngineState, InvalidTransitionError, StateMachine
from evf.engine.navigation import angular_separation, sky_position_angle
from evf.solver.solver import PlateSolver
from evf.solver.sync import apply_body_frame_sync

logger = logging.getLogger(__name__)


class SolverThread:
    """Background thread that plate-solves frames from LatestFrame.

    Consumes the most recent frame, solves it, validates the result,
    and updates PointingState. Transitions WARMING_UP → TRACKING on
    first successful solve.
    """

    def __init__(
        self,
        solver: PlateSolver,
        frame_buffer: LatestFrame,
        pointing_state: PointingState,
        state_machine: StateMachine,
        config: ConfigManager,
        audio: AudioAlert | None = None,
    ) -> None:
        self._solver = solver
        self._frame_buffer = frame_buffer
        self._pointing = pointing_state
        self._state_machine = state_machine
        self._config = config
        self._audio = audio
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._consecutive_failures = 0
        self._lock = threading.Lock()
        self._sync_d_body = None  # np.ndarray | None — body-frame sync vector
        # Calibration state
        self._cal_ref_ra: float = 0.0
        self._cal_ref_dec: float = 0.0
        self._cal_ref_roll: float = 0.0
        self._cal_skip = threading.Event()
        self._cal_prev_ra: float = 0.0
        self._cal_prev_dec: float = 0.0
        self._cal_stable_since: float = 0.0  # monotonic timestamp

    def start(self) -> None:
        """Start tracking — transition to WARMING_UP and begin solving."""
        self._stop_event.clear()
        with self._lock:
            self._consecutive_failures = 0
        if self._audio:
            self._audio.reset()
        self._state_machine.transition(EngineState.WARMING_UP)
        self._thread = threading.Thread(
            target=self._run, name="solver", daemon=True
        )
        self._thread.start()

    def stop(self, timeout: float = 5.0) -> None:
        """Stop tracking."""
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=timeout)
            self._thread = None

    @property
    def consecutive_failures(self) -> int:
        with self._lock:
            return self._consecutive_failures

    def set_sync_d_body(self, d_body) -> None:
        """Set or clear the body-frame sync vector applied to solve results."""
        self._sync_d_body = d_body

    def start_calibrate(self, ref_ra: float, ref_dec: float, ref_roll: float) -> None:
        """Enter CALIBRATE state and begin solving to detect finder rotation."""
        self._cal_ref_ra = ref_ra
        self._cal_ref_dec = ref_dec
        self._cal_ref_roll = ref_roll
        self._cal_skip.clear()
        self._cal_prev_ra = ref_ra
        self._cal_prev_dec = ref_dec
        self._cal_stable_since = 0.0
        self._stop_event.clear()
        with self._lock:
            self._consecutive_failures = 0
        if self._audio:
            self._audio.reset()
        self._state_machine.transition(EngineState.CALIBRATE)
        self._thread = threading.Thread(
            target=self._run, name="solver", daemon=True
        )
        self._thread.start()

    def skip_calibrate(self) -> None:
        """Signal the calibration loop to skip and proceed to WARMING_UP."""
        self._cal_skip.set()

    _VALID_STATES = (EngineState.CALIBRATE, EngineState.WARMING_UP, EngineState.TRACKING)
    _AUDIO_FAIL_THRESHOLD = 3  # consecutive failures before audio alert
    _CALIBRATE_MIN_SEP = 0.5  # minimum angular separation (degrees) for calibration
    _CALIBRATE_STABLE_TOL = 0.05  # max frame-to-frame drift (degrees) to count as stable
    _CALIBRATE_STABLE_SECS = 1.0  # seconds of stability required before accepting

    # Solve-rate throttling (#5): minimum wall-clock gap between solve attempts.
    # Prevents hammering the CPU when frames arrive faster than solves complete.
    _MIN_SOLVE_INTERVAL = 0.5  # seconds

    # Stable-TRACKING skip (#7): if the last N solves are all within _STABLE_TOL
    # degrees of each other, the scope isn't moving — drop to a slower rate.
    _STABLE_WINDOW = 4         # number of consecutive solves to check
    _STABLE_TOL_DEG = 0.08    # max RA/Dec spread (degrees) to consider stable
    _STABLE_INTERVAL = 2.5    # seconds between solves when stable
    _STABLE_RESUME_MOVE = 0.3  # movement (degrees) that resets to normal rate

    def _check_calibration(self, ra: float, dec: float, roll: float) -> bool:
        """Check if the scope has moved enough and stabilized to compute finder rotation.

        Waits for the scope to stop moving (consecutive solves within tolerance)
        and then holds for _CALIBRATE_STABLE_SECS before computing. This handles
        jittery motion and stiction on cheap telescope mounts.

        Returns True if calibration is complete (or skipped) and we should
        transition to WARMING_UP.
        """
        if self._cal_skip.is_set():
            logger.info("Calibration skipped — using saved finder_rotation=%.1f",
                        self._config.finder_rotation)
            self._state_machine.transition(EngineState.WARMING_UP)
            return True

        sep = angular_separation(ra, dec, self._cal_ref_ra, self._cal_ref_dec)
        if sep < self._CALIBRATE_MIN_SEP:
            # Not moved enough yet — reset stability tracking
            self._cal_prev_ra = ra
            self._cal_prev_dec = dec
            self._cal_stable_since = 0.0
            return False

        # Check frame-to-frame drift to detect when scope stops moving
        drift = angular_separation(ra, dec, self._cal_prev_ra, self._cal_prev_dec)
        self._cal_prev_ra = ra
        self._cal_prev_dec = dec

        now = time.monotonic()
        if drift > self._CALIBRATE_STABLE_TOL:
            # Still moving — reset stability timer
            self._cal_stable_since = 0.0
            return False

        # Scope is stable (within tolerance)
        if self._cal_stable_since == 0.0:
            self._cal_stable_since = now
            logger.debug("Calibration: scope stable, waiting %.1fs...",
                         self._CALIBRATE_STABLE_SECS)
            return False

        elapsed = now - self._cal_stable_since
        if elapsed < self._CALIBRATE_STABLE_SECS:
            return False

        # Scope has been stable long enough — compute finder rotation
        sky_pa = sky_position_angle(ra, dec, self._cal_ref_ra, self._cal_ref_dec)
        camera_angle = (sky_pa - roll) % 360.0
        # The old center is "behind" us (opposite to push direction)
        finder_rotation = (camera_angle - 180.0) % 360.0

        self._config.finder_rotation = finder_rotation
        logger.info(
            "Calibration complete: sep=%.2f° sky_pa=%.1f° roll=%.1f° "
            "camera_angle=%.1f° finder_rotation=%.1f° (stable %.1fs)",
            sep, sky_pa, roll, camera_angle, finder_rotation, elapsed,
        )
        self._state_machine.transition(EngineState.WARMING_UP)
        return True

    def _run(self) -> None:
        last_frame_id = -1
        first_success = True
        last_solve_time = 0.0          # monotonic; throttle (#5)
        recent_ra: list[float] = []    # stable-TRACKING tracking (#7)
        recent_dec: list[float] = []
        stable = False

        while not self._stop_event.is_set():
            # Exit if state is no longer appropriate (e.g. RECONNECTING, ERROR)
            if self._state_machine.state not in self._VALID_STATES:
                logger.info(
                    "State is %s — solver exiting",
                    self._state_machine.state.value,
                )
                return

            jpeg_bytes, _timestamp, frame_id = self._frame_buffer.get()
            if jpeg_bytes is None or frame_id == last_frame_id:
                time.sleep(0.01)
                continue

            last_frame_id = frame_id

            # --- throttle: enforce minimum gap between solves (#5) ---
            now = time.monotonic()
            in_tracking = self._state_machine.state == EngineState.TRACKING
            min_interval = (
                self._STABLE_INTERVAL if (stable and in_tracking)
                else self._MIN_SOLVE_INTERVAL
            )
            elapsed = now - last_solve_time
            if elapsed < min_interval:
                time.sleep(min(min_interval - elapsed, 0.1))
                continue

            last_solve_time = time.monotonic()
            try:
                t_start = time.monotonic()
                result = self._solver.solve_frame(jpeg_bytes)
                t_total = (time.monotonic() - t_start) * 1000
                logger.info(
                    "Solve frame %d: %.0fms (extract=%.0fms solve=%.0fms) "
                    "centroids=%d RA=%s matches=%s prob=%s",
                    frame_id, t_total,
                    result.get("T_extract", 0),
                    result.get("T_solve", 0),
                    len(result.get("all_centroids") or []),
                    result.get("RA"),
                    result.get("Matches"),
                    result.get("Prob"),
                )
            except Exception as exc:
                logger.error("Solve error: %s", exc)
                self._pointing.clear_centroids()
                with self._lock:
                    self._consecutive_failures += 1
                    new_count = self._consecutive_failures
                if self._audio and new_count == self._AUDIO_FAIL_THRESHOLD:
                    self._audio.on_failure_count_changed(new_count)
                continue

            if self._solver.is_valid(
                result,
                min_matches=self._config.min_matches,
                max_prob=self._config.max_prob,
            ):
                ra, dec = result["RA"], result["Dec"]

                # Calibration check (uses raw plate-solve, before body-frame sync)
                if self._state_machine.state == EngineState.CALIBRATE:
                    self._check_calibration(ra, dec, result["Roll"])

                if self._sync_d_body is not None:
                    ra, dec = apply_body_frame_sync(
                        self._sync_d_body, ra, dec, result["Roll"]
                    )
                self._pointing.update(
                    ra,
                    dec,
                    result["Roll"],
                    result["Matches"],
                    result["Prob"],
                    all_centroids=result.get("all_centroids"),
                    matched_centroids=result.get("matched_centroids"),
                    image_size=result.get("image_size"),
                )
                with self._lock:
                    was_failing = (
                        self._consecutive_failures >= self._AUDIO_FAIL_THRESHOLD
                    )
                    self._consecutive_failures = 0
                if self._audio and was_failing:
                    self._audio.on_failure_count_changed(0)

                # Stable-TRACKING detection (#7): check if scope has stopped moving.
                # Keep a rolling window of recent RA/Dec; if all within tolerance,
                # switch to a slower solve rate to save CPU.
                if in_tracking:
                    recent_ra.append(ra)
                    recent_dec.append(dec)
                    if len(recent_ra) > self._STABLE_WINDOW:
                        recent_ra.pop(0)
                        recent_dec.pop(0)
                    if len(recent_ra) == self._STABLE_WINDOW:
                        ra_spread = max(recent_ra) - min(recent_ra)
                        dec_spread = max(recent_dec) - min(recent_dec)
                        was_stable = stable
                        stable = ra_spread < self._STABLE_TOL_DEG and dec_spread < self._STABLE_TOL_DEG
                        if stable and not was_stable:
                            logger.info("Scope stable — reducing solve rate to %.1fs", self._STABLE_INTERVAL)
                        elif not stable and was_stable:
                            logger.info("Scope moving — resuming normal solve rate")
                else:
                    # Reset stability window when not in TRACKING
                    recent_ra.clear()
                    recent_dec.clear()
                    stable = False

                if first_success and self._state_machine.state == EngineState.WARMING_UP:
                    try:
                        self._state_machine.transition(EngineState.TRACKING)
                    except InvalidTransitionError:
                        logger.info(
                            "Cannot transition to TRACKING — solver exiting"
                        )
                        return
                    first_success = False
                logger.debug(
                    "Solve: RA=%.3f Dec=%.3f M=%d P=%.4f",
                    result["RA"],
                    result["Dec"],
                    result["Matches"],
                    result["Prob"],
                )
            else:
                # Extraction still ran even though the pattern match failed
                # (or wasn't attempted) — keep the "stars seen" overlay live
                # rather than blanking it out every time a solve is rejected.
                self._pointing.update_star_overlay(
                    all_centroids=result.get("all_centroids"),
                    matched_centroids=None,
                    image_size=result.get("image_size"),
                )
                # Solve failure could mean scope moved past recognition threshold;
                # reset stability so we don't back off during recovery.
                recent_ra.clear()
                recent_dec.clear()
                stable = False
                with self._lock:
                    self._consecutive_failures += 1
                    new_count = self._consecutive_failures
                if self._audio and new_count == self._AUDIO_FAIL_THRESHOLD:
                    self._audio.on_failure_count_changed(new_count)
                if result.get("RA") is not None:
                    logger.debug(
                        "Solve rejected: M=%d P=%.4f",
                        result.get("Matches", 0),
                        result.get("Prob", 0),
                    )
