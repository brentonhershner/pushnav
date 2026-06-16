// Copyright (C) 2026 Arun Venkataswamy
//
// This file is part of PushNav.
//
// PushNav is free software: you can redistribute it and/or modify it
// under the terms of the GNU General Public License as published by
// the Free Software Foundation, either version 3 of the License, or
// (at your option) any later version.
//
// PushNav is distributed in the hope that it will be useful, but
// WITHOUT ANY WARRANTY; without even the implied warranty of
// MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU
// General Public License for more details.
//
// You should have received a copy of the GNU General Public License
// along with PushNav. If not, see <https://www.gnu.org/licenses/>.

// ControlManager.swift — Maps protocol control IDs to UVC operations.
//
// Thin mapping layer that builds CONTROL_INFO JSON from probed UVC ranges
// and dispatches SET_CONTROL commands to the appropriate UVC accessors.

import Foundation

class ControlManager {
    private let uvc: UVCController

    init(uvc: UVCController) {
        self.uvc = uvc
    }

    /// Build the CONTROL_INFO JSON dictionary from current UVC state.
    ///
    /// Iterates CAMERA_CONTROLS (CameraConfig.swift) generically — any control
    /// the camera reports as capable becomes a slider in the UI automatically.
    /// Controls forced off via CAMERA_CONTROLS_FORCED_OFF are excluded since
    /// they aren't meant to be user-adjustable.
    func buildControlInfo() -> [String: Any] {
        var controls: [[String: Any]] = []

        for ctrl in CAMERA_CONTROLS {
            guard !CAMERA_CONTROLS_FORCED_OFF.contains(ctrl.id) else { continue }
            guard let range = uvc.ranges[ctrl.id], range.capable else { continue }
            let cur = uvc.getControl(id: ctrl.id) ?? range.cur
            controls.append([
                "id": ctrl.id,
                "label": ctrl.label,
                "type": "int",
                "min": range.min,
                "max": range.max,
                "step": range.res,
                "cur": cur,
                "unit": ctrl.unitLabel,
            ])
        }

        return ["controls": controls]
    }

    /// Apply a SET_CONTROL command. Returns true if the control was recognized and applied.
    func applySetControl(id: String, value: Int) -> Bool {
        guard CAMERA_CONTROLS.contains(where: { $0.id == id }) else {
            fputs("WARNING: Unknown control ID: \(id)\n", stderr)
            return false
        }
        let applied = uvc.setControl(id: id, value: value)
        print("SET_CONTROL: \(id) = \(value) → actual = \(uvc.getControl(id: id) ?? -1)")
        return applied
    }
}
