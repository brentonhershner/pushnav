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

"""Plate solver — tetra3 wrapper for single-frame plate solving.

Per SPEC_ARCHITECTURE.md §8 and impl0.md §Phase 6.
"""

import io
import logging
import time
from pathlib import Path

from PIL import Image
from tetra3 import get_centroids_from_image

from evf.paths import database_path

logger = logging.getLogger(__name__)

# MUST use Path object — string triggers tetra3's internal path resolution
# which won't find our database (see CLAUDE.md).
_DATABASE_PATH = database_path()

# Centroid extraction parameters (passed to get_centroids_from_image).
_CENTROID_PARAMS = dict(
    sigma=3,        # PiFinder uses 8 on raw 12-bit data; UVC JPEG output has
                    # lower local SNR after ISP gamma compression so we need a
                    # lower threshold — 3 finds real stars while the plate-solve
                    # pattern matcher rejects any false centroids
    filtsize=15,
    max_area=2000,  # Allow bright extended stars (M45, Capella); was 500
)

# Solve parameters proven in prototyping (impl0.md §6.2, solve_hip8.py).
#
# FOV is for the Arducam IMX462 (1/2.8" sensor, 2.9µm pixels, 1920×1080
# native) with a 25mm f/2.0 lens. Whether the UVC driver downscales or
# center-crops to deliver 1280×720 is firmware-dependent:
#   - Downscale: FOV unchanged at 2·atan(5.57mm / 50mm) ≈ 12.7°
#   - Center-crop: FOV narrows to 2·atan(3.71mm / 50mm) ≈ 8.5°
# fov_max_error=4.0 brackets both cases so the solver works regardless.
# The original 8.86° was correct for the old OV9281 camera (1/4", 3µm).
_SOLVE_PARAMS = dict(
    fov_estimate=12.0,  # degrees — IMX462 + 25mm, full-sensor downscale
    fov_max_error=4.0,  # wide to cover crop vs downscale uncertainty
    match_radius=0.01,
    pattern_checking_stars=30,
    match_threshold=0.1,
    solve_timeout=1000,  # ms — cap failed solves to ~1s instead of 6-10s
)


class PlateSolver:
    """Load tetra3 database once and solve frames on demand."""

    def __init__(self, database_path: Path | None = None) -> None:
        import tetra3

        db_path = database_path or _DATABASE_PATH
        t0 = time.monotonic()
        self._t3 = tetra3.Tetra3(load_database=db_path)
        elapsed = time.monotonic() - t0
        logger.info("tetra3 database loaded in %.2fs: %s", elapsed, db_path)

    # Downsample factor for centroid extraction: 2 = ½ linear = ¼ pixel count = ~4× faster.
    # Centroids are scaled back to original-resolution space so the overlay and
    # tetra3 pattern matching both see consistent pixel scales.
    _SOLVE_DOWNSAMPLE = 2

    def solve_frame(self, image_bytes: bytes) -> dict:
        """Solve a single image frame. Returns tetra3 result dict.

        Splits into centroid extraction + solve so we can return both
        all detected centroids and matched centroids for star overlay.
        Centroid extraction runs on a ½-resolution copy for speed; coordinates
        are scaled back up so everything is in the original-resolution space.
        """
        img = Image.open(io.BytesIO(image_bytes)).convert("L")
        orig_h, orig_w = img.height, img.width

        # Half-resolution copy for fast centroid extraction
        ds = self._SOLVE_DOWNSAMPLE
        small = img.resize((orig_w // ds, orig_h // ds), Image.BILINEAR)

        t0 = time.monotonic()
        centroids_small = get_centroids_from_image(small, **_CENTROID_PARAMS)
        t_extract = (time.monotonic() - t0) * 1000

        # Scale back to original resolution so overlay SVG viewBox aligns
        centroids = centroids_small * ds if len(centroids_small) else centroids_small

        result = self._t3.solve_from_centroids(
            centroids,
            (orig_h, orig_w),
            return_matches=True,
            **_SOLVE_PARAMS,
        )
        # Negate Roll: tetra3's image-vector convention (i=boresight, j=right, k=up)
        # produces Roll with opposite sign to our body-frame formulas.
        # Empirically verified across 7 targets: std drops from 1.04° to 0.14°.
        if result.get("Roll") is not None:
            result["Roll"] = (360.0 - result["Roll"]) % 360.0

        result["T_extract"] = t_extract
        result["all_centroids"] = centroids.tolist()  # Nx2 (y, x) in original space
        result["image_size"] = (orig_h, orig_w)
        return result

    @staticmethod
    def is_valid(
        result: dict, min_matches: int = 8, max_prob: float = 0.2
    ) -> bool:
        """Check if a solve result meets quality thresholds."""
        if result.get("RA") is None:
            return False
        if result.get("Matches", 0) < min_matches:
            return False
        if result.get("Prob", 1.0) > max_prob:
            return False
        return True
