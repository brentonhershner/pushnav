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

// CameraConfig.swift — single source of truth for camera identification.
//
// All VID/PID values, model names, and AVFoundation matching strings live here.
// Update this file when switching to a different camera module.

// MARK: - USB identity (used by UVCController for IOKit device lookup)

/// USB Vendor ID — Sonix Technology (shared by many Arducam UVC modules)
let CAMERA_VID: Int = 0x0C45  // 3141 decimal

/// USB Product ID — update this when switching camera modules.
/// Arducam IMX462: 0x6366
/// Arducam OV9281: 0x6366  (same USB bridge, different sensor)
let CAMERA_PID: Int = 0x6366  // 25446 decimal

// MARK: - Human-readable identity (used in logs and HELLO message)

/// Display name sent to the Python engine in the HELLO handshake.
let CAMERA_MODEL: String = "arducam-imx462"

/// Human-readable label used in error messages.
let CAMERA_LABEL: String = "Arducam IMX462"

// MARK: - AVFoundation matching
//
// AVFoundation enumerates USB UVC cameras with localizedName strings that vary
// by driver and macOS version ("USB Camera", "USB 2.0 Camera", or a descriptive
// name like "Arducam OV9281").  We match in priority order:
//   1. Exact or partial localizedName match (fastest, most specific)
//   2. modelID substring match — AVFoundation formats VID as decimal in
//      "VendorID_<decimal>" so 0x0C45 → "VendorID_3141".
//   3. Single external camera fallback — if only one external USB camera is
//      present we assume it's ours (safe for a single-camera astronomy rig).

/// Substrings checked against AVFoundation device.localizedName (case-sensitive).
/// List the most specific names first.
let CAMERA_NAME_SUBSTRINGS: [String] = [
    "Arducam IMX462",
    "Arducam OV9281",
    "Arducam",
    "IMX462",
]

/// Substrings checked against AVFoundation device.modelID.
/// AVFoundation encodes VID as decimal: 0x0C45 → "VendorID_3141".
let CAMERA_MODEL_ID_SUBSTRINGS: [String] = [
    "VendorID_3141",   // 0x0C45 decimal — Sonix Technology
]

// MARK: - UVC controls
//
// Single declarative list of every camera control PushNav exposes. Each entry
// becomes one slider in the UI (CameraControls.tsx renders the protocol's
// CONTROL_INFO list generically — no UI code changes needed when this list
// changes). To add/remove a control for a future camera swap, edit only here.
//
// Selector values are from the USB Video Class 1.5 spec, Processing Unit and
// Camera Terminal control selector tables.

enum UVCUnit {
    case cameraTerminal
    case processingUnit
}

struct UVCControlDef {
    let id: String        // protocol control id, sent over the wire
    let label: String     // UI display label
    let selector: UInt8   // UVC control selector
    let unit: UVCUnit     // which UVC unit ID this selector targets
    let size: Int         // GET/SET payload size in bytes
    let unitLabel: String // UI unit suffix shown next to the value
}

let CAMERA_CONTROLS: [UVCControlDef] = [
    UVCControlDef(id: "exposure", label: "Exposure", selector: 0x04,
                  unit: .cameraTerminal, size: 4, unitLabel: "100us"),
    UVCControlDef(id: "gain", label: "Gain", selector: 0x04,
                  unit: .processingUnit, size: 2, unitLabel: "raw"),
    UVCControlDef(id: "brightness", label: "Brightness", selector: 0x02,
                  unit: .processingUnit, size: 2, unitLabel: "raw"),
    UVCControlDef(id: "contrast", label: "Contrast", selector: 0x03,
                  unit: .processingUnit, size: 2, unitLabel: "raw"),
    UVCControlDef(id: "gamma", label: "Gamma", selector: 0x09,
                  unit: .processingUnit, size: 2, unitLabel: "raw"),
    UVCControlDef(id: "sharpness", label: "Sharpness", selector: 0x0A,
                  unit: .processingUnit, size: 2, unitLabel: "raw"),
    UVCControlDef(id: "backlight_compensation", label: "Backlight Comp", selector: 0x01,
                  unit: .processingUnit, size: 2, unitLabel: "raw"),
]

/// Controls forced to a fixed value at startup rather than left as sliders.
/// Backlight compensation actively re-brightens scenes it judges "too dark" —
/// exactly the opposite of what a faint-star capture needs — so it's always
/// disabled rather than exposed as a tunable.
let CAMERA_CONTROLS_FORCED_OFF: [String] = ["backlight_compensation"]
