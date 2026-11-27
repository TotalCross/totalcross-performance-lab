<!--
Copyright (C) 2026 Amalgam Solucoes em TI Ltda

SPDX-License-Identifier: LGPL-2.1-only
-->
# I07 — `Image(String)` TCZ-first filesystem fallback

This case checks the corrected SDK at source commit
`94af2b8b653cad509994b5ccf3dbb60ac28ef920` with the matching platform runtime.
It uses JPEG fixtures so Linux coverage does not depend on the separate PNG
decoder result.

The probe covers relative and absolute filesystem paths, a device path when the
runtime exposes one, TCZ-only loading, filesystem fallback, TCZ precedence when
both copies exist, malformed and empty TCZ entries without fallback, missing,
invalid, and empty filesystem files, 255/256-character TCZ path boundaries,
`Image(File)` pixel parity, snapshots after the backing file changes, and the
native persistent-owner count while an `ImageControl` attaches and detaches.

`tools/image_string_fallback_730.py` generates the byte-array helper and embeds
TCZ-only fixtures into the application JAR. The two checked-in JPEGs are
2-by-2 (TCZ) and 36-by-36 (filesystem) controls. Their SHA-256 values are
recorded in the platform evidence.

The branch-push workflow is `.github/workflows/image-string-fallback-730.yml`.
Windows reuses the corrected Win32/I386 runtime from Actions run `45907759163`
with the matching corrected SDK from run `45884551862`; the workflow checks PE
machine values and does not build or execute an AMD64 runtime. Linux uses the
campaign's verified frozen-master VM bundle paired with the corrected SDK,
after checking the shared VM subtree and generated native bridge inputs. It
records the unmodified launch first, then uses the existing test-only
`__realpath_chk` shim to exercise I06 ownership and I07 behavior. Shimmed Linux
results are conditional evidence, not an unmodified startup pass. macOS builds
and runs on the canonical ARM64 hosted runner using the prepared dependencies
and generated bridges from product run `45884551862`. Android runs only on the
local hardware-accelerated ARM64 emulator, using the candidate SDK and the AAB
template produced by the documented Android Gradle release tasks.

`device-path-where-supported` is reported as `SKIP` when the runtime cannot
create a file through TotalCross' `device/` path. The summary still includes
the skip count and every executed case marker.

The probe prints one `TC_I07 case=...` line per assertion and a compact
`TC_I07_RESULT` summary so the Android logcat marker stays below line-size
limits. The runner records the native desktop exit code, Android completion
marker, source/artifact hashes, and every case result.
