# Prevent Android V4L2 control-device probing from blocking legacy audio routing

Target branch: **legacy**. Prepared against `a271f010b0f2ed413e193e779e38daa77070c974`.

## Problem

Some Qualcomm Android kernels expose camera request-manager, camera-sync and VIDC codec interfaces as `/dev/video*`. These host interfaces can be visible inside the Linux environment, but they are not ordinary V4L2 capture devices.

On the affected device, WirePlumber's V4L2 monitor tries to activate them. The request-manager and sync devices return EALREADY during SPA listener initialization. PipeWire 1.6.9 ignores that listener error and returns an unbound client-device proxy, leaving WirePlumber 0.5.18 waiting for activation. The event dispatcher then cannot finish audio linking: the desktop and `anland-speaker` are present, but application playback has no link to Android.

The same shared PipeWire/WirePlumber failure path applies to legacy KDE, GNOME, Niri and Gamescope producers.

## Changes

- Add a shared WirePlumber 0.5 rule matching the sysfs identities of Qualcomm `cam-req-mgr`, `cam-sync` and `vidc` devices before initialization.
- Keep ordinary V4L2 devices, libcamera and Anland's directly created PipeWire camera sources enabled. Avoid dependence on unstable `/dev/videoN` numbering.
- Install the rule through the shared KWin/Mutter/Gamescope backends and producer package scripts, including Debian/Ubuntu and Fedora file manifests. Use a distinct package-owned filename per producer so desktop packages can coexist.
- Guard against unpatched WirePlumber 0.5.16/0.5.17, whose disabled-device asynchronous hook has a separate regression. Arch/SteamOS require 0.5.18 or later; Debian/Ubuntu/Fedora allow versions below 0.5.16 or at least 0.5.18. The build helper edits only the runtime common package and rejects unsupported metadata layouts.
- Document existing-installation setup, migration from broad video-disable workarounds, version requirements and verification in both guides.
- Add regression tests for matching, unaffected device identities, the Niri package layout, dependency edits, idempotence and version boundaries.

WirePlumber's disabled-device hook fix is [65519a1](https://github.com/PipeWire/wireplumber/commit/65519a1ff7cecebc0622fc4a2badec830ee67d7d). Distribution backports retaining older version numbers can adjust the conservative metadata constraint after confirming that fix is present.

## Validation

```sh
python3 -m unittest discover -s libdisplay_producer/wireplumber/tests -v
git diff --check
```

- All 11 regression tests pass, including parsing the configuration with PipeWire's `spa-json-dump` and executing Niri's actual `package()` in a temporary staging directory.
- KWin CMake and Mutter/Gamescope Meson configure and DESTDIR install checks pass.
- Four Debian/Ubuntu `build_pkg` paths pass with isolated packaging fixtures; a real Fedora 43 KWin spec passes common-package file-list and dependency insertion checks. Gamescope's actual package copy command passes. Complete compositor, DEB and RPM builds were not run.
- On the affected Niri/Arch Linux ARM session, the filter alone restores default playback routing across three WirePlumber restarts.
- With companion PipeWire/WirePlumber error-handling patches installed, three further restarts without the filter successfully route playback despite the original EALREADY failures. Restoring the filter and restarting three times also succeeds. Each stream has two active stereo links to `anland-speaker`; PulseAudio-compatible playback routes correctly as well.
- `anland-mic` and both Anland camera nodes remain visible. Actual USB/remote camera capture and a complete device reboot were not tested.

## Companion upstream fixes

The generic failure path needs two separate dependency fixes: PipeWire must propagate `spa_device_add_listener()` failure and clean up the proxy; WirePlumber must finish activation when `pw_core_export()` returns NULL. Patching only one side either preserves the wait or reaches a NULL-proxy assertion.

Separate patches and an isolated reproducer have been prepared for PipeWire and WirePlumber. Synthetic listener failures cover EALREADY, EIO and ENOMEM, both before and after partial hook registration. Both WirePlumber client contexts return an activation error promptly with the paired fixes, and a subsequent core round trip completes. Those dependency patches are separate from this Anland integration change.
