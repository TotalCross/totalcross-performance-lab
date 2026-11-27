# I06 — Windows Win32/I386 priority validation

## Result

**PASS: persistent image ownership is functionally validated on the production
Windows Win32/I386 target for TotalCross source `94af2b8b653cad509994b5ccf3dbb60ac28ef920`.** The minimal native startup probe passed, then the ownership smoke passed against the same runtime on the same hosted Windows runner. All required markers were present, both native processes exited with code 0, and neither timed out.

This campaign reuses the completed hosted run because it already matches the
requested source, I386 architecture, production rendering configuration, and
same-runner historical comparison. It is verified existing Actions evidence,
not a new run dispatched from the performance-lab branch. The broader I06
investigation is now `PASS`: the Linux x86_64 ownership assertions also
completed, conditionally under its test-only startup shim, as recorded in the
[Linux report](I06-linux-ownership.md).

## Historical I386 comparison

Run [45907759163](https://github.com/TotalCross/totalcross/actions/runs/45907759163)
compared the historical artifacts from runs `44414042826` and `44565183218`
with the corrected source. All three startup probes ran in the same
`windows-2022` job and passed on Win32/I386:

| Revision | Source commit | Startup | Exit | PE target |
| --- | --- | --- | ---: | --- |
| Historical A | `61034a7562e7fa43df076dcc38bcd48128605395` | PASS | 0 | I386 (`0x014c`) |
| Historical B | `c7cf79575602f3cc19e107643f0fa39d3e151004` | PASS | 0 | I386 (`0x014c`) |
| Corrected | `94af2b8b653cad509994b5ccf3dbb60ac28ef920` | PASS | 0 | I386 (`0x014c`) |

The historical and corrected runs all reached the six probe application
markers. Their source and downloaded artifact identities are retained in the
[evidence record](../evidence/I06/windows-win32-45907759163.json). The corrected
result artifact is `windows-historical-i386-validation-results` (ID
`15158866549`); its downloaded ZIP SHA-256 was verified against the Actions
artifact digest.

## Corrected I386 build and startup gate

The product source was clean at the exact correction commit and tree recorded
in the evidence record. CMake used `Visual Studio 17 2022`, `-A Win32`, and
`Release`, matching the normal production target. The build script asserted
Skia enabled, legacy renderer disabled, SDL windowing enabled, native windowing
disabled, software graphics enabled, and GLES disabled. It did not switch to
the legacy renderer.

PE inspection recorded machine `0x014c` for the built `Launcher.exe`, built
`tcvm.dll`, and deployed `WindowsNativeStartupProbe.exe`. The deployed VM hash
matches the built VM. The SDK JAR and seven TCZ files are Java/TotalCross
artifacts rather than PE files; their hashes and corrected SDK build provenance
are recorded in the evidence JSON. The runner host reports X64, but no AMD64
TotalCross executable or DLL was mixed into the tested pair.

The startup probe observed all six markers, including
`tcdiag-window-render-returned.marker` and
`tcdiag-application-complete.marker`. Its recorded native exit code was
`0x00000000`; timeout was false and no crash dump was produced. The probe
completed before the ownership smoke began.

## Ownership smoke

The existing `ImageOwnershipLifecycleProbe` completed all seven stages using
the same `Launcher.exe` and `tcvm.dll` hashes as the startup gate. It ran two
consecutive screens of 1,510 controls and 1,510 distinct images per cycle. The
captured assertions confirm:

- ancestor detach released all owners (`ownersAfterDetach = 0`); reattachment
  restored owners and active reparenting preserved the cache;
- shared ownership reached three owners; ImagePipeline replacement retained
  three owners;
- the raster remained alive through the final owner, the cache was reused while
  owned, and it was evicted after detach;
- native rendering returned RGB `16711680` (`#ff0000`); the rendered PNG is
  retained below and its hash is in the evidence record;
- all seven stages completed, with zero ownership mismatches, no ownership
  underflow messages in the captured runtime log, no crash dump, and process
  exit code 0.

![Native ownership smoke pixel output](../evidence/I06/windows-win32-ownership-render.png)

## AMD64 distinction and remaining limits

For the same correction, the existing AMD64 startup failure remains a separate
preexisting result documented on [PR #567](https://github.com/TotalCross/totalcross/pull/567).
This validation confirms corrected I386 PASS; it does not retest AMD64, compare
fault RVAs across architectures, or establish an AMD64 root cause. The x64
failure is not a gate for the production Win32/I386 correction.

The retained smoke is the existing functional fixture, not a performance
benchmark. It validates the listed lifecycle and rendering assertions on the
hosted runner. I06 Linux x86_64 ownership validation, other platform claims,
and general customer-desktop coverage remain separate work.

## Workflow and remote evidence

- Actions run: [45907759163](https://github.com/TotalCross/totalcross/actions/runs/45907759163)
- Job: [Historical I386 startup and gated ownership smoke](https://github.com/TotalCross/totalcross/actions/runs/45907759163/job/140208504320)
- Diagnostic workflow commit: `cf3487e76147be4ee272cf435f1789c567e10e13` on
  `codex/windows-historical-startup-compatibility`.
- Existing ownership fixture commit: `bf691c14d7c5fe807c62de98c7285f65d38de87e`
  on `codex/windows-i386-ownership-smoke` in performance-lab.
- No production implementation was changed. No additional Windows workflow
  dispatch or AMD64 run was needed; the captured Actions result already met the
  priority correction's execution gates.
- Artifact IDs, digests, PE identities, SDK/TCZ hashes, markers, and assertions
  are indexed in [windows-win32-45907759163.json](../evidence/I06/windows-win32-45907759163.json).
