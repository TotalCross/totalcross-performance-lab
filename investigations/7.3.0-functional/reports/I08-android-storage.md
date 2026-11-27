# I08 — Android filesystem permission recovery

## Result

**PASS for the tested CRUD and permission behavior on API 29, 30, 35, and 36.**
The official 7.3.0 package and corrected candidate each completed all nine
filesystem operations on private, app-specific external, and app-created shared
storage, with no failures. A separate host-seeded file distinguished app-owned
`Download` content from content created outside the app.

On API 29, the candidate's first foreign-file attempt correctly returned a
permission error after the user denied access. On a later attempt, allowing the
requested permissions let the operation retry and read/list the foreign file.
On API 30, the system showed a read-media permission prompt, and the denied
foreign-file access failed without a `WRITE_EXTERNAL_STORAGE` request loop. On
APIs 35 and 36, foreign-file access failed with `EACCES` and no legacy
permission dialog. These API 30+ denials match the deployed manifest: it does
not request `MANAGE_EXTERNAL_STORAGE`. The pass result validates these observed
boundaries; it does not claim broad shared-storage access on those APIs.

## Packages and environment

Both packages target API 36 and have minSdk 24. The APK explicitly declares
`WRITE_EXTERNAL_STORAGE` and `requestLegacyExternalStorage=true`; it does not
declare `MANAGE_EXTERNAL_STORAGE`. Android's package manager additionally lists
`READ_EXTERNAL_STORAGE` as restricted, although it is not an explicit
`uses-permission` in the APK. The API 30 prompt and permission-result log show
that only READ was requested there.

The official 7.3.0 SDK jar hash is
`23a0e5f16146414419c43f418d554f494d6acad362aa0e03ca11e11bfd430475` and its
deployed ARM64 VM hash is
`bf630c7bf8a7a33323631c3b59699157d621a4f4587aac77779931a2de2544ad`. The
candidate uses source `94af2b8b653cad509994b5ccf3dbb60ac28ef920`, SDK jar
`a18c80e2784543493370d1120afc3e2d10d7594b51e5032d1f779f1f51c2f12d`, and
ARM64 VM `57ec070728ce6362a4ed32c06e05122a4bbdc29d4468dc4630c94d33db029215`.
The exact deployed APK hashes and per-run identities are in the [machine
record](../evidence/I08/android-storage-matrix.json).

All four ARM64 emulators used the Apple M1 Pro host GPU: API 29 / Android 10
used OpenGL ES 2.0; APIs 30 / 11, 35 / 15, and 36 / 16 used OpenGL ES 3.0.

## CRUD matrix

Each run created a root and child directory, created and wrote a file, checked
existence/type/size/attributes/mtime and directory listing, renamed and read
the file, then deleted the file and both directories. All three roots passed
on both revisions at all four APIs:

| API | Official 7.3.0 | Candidate 94af | Permission state for file-only run |
| --- | --- | --- | --- |
| 29 | PASS, 3/3 roots | PASS, 3/3 roots | READ/WRITE granted |
| 30 | PASS, 3/3 roots | PASS, 3/3 roots | READ/WRITE denied |
| 35 | PASS, 3/3 roots | PASS, 3/3 roots | READ/WRITE denied |
| 36 | PASS, 3/3 roots | PASS, 3/3 roots | READ/WRITE denied |

On API 30+, the app-created file in `/sdcard/Download` passed while READ and
WRITE were denied. That is access to the app's own created content and is not
evidence of permission to read a different owner's file.

## Foreign-file authorization

The fixture contains 29 bytes, was pushed by the host to
`/sdcard/Download/tc730-i08-foreign-control.bin`, and was not created by the
probe. The candidate API 29 run first denied the system prompt; the probe
observed `Error Code: 13 - Permission denied`. On the next attempt, allowing
READ and WRITE returned permission result 4 for both; the same call then
retried and read all 29 bytes and listed the fixture. The official API 29
package also read and listed it with READ/WRITE pregranted.

On API 30, denying the single READ request returned result 6 and left both
permissions denied. The probe received `Error Code: 13`; no WRITE request was
issued. On APIs 35 and 36, both permissions remained denied and the foreign
read failed immediately with `EACCES`; neither run showed a permission
controller request. MANAGE_EXTERNAL_STORAGE and legacy app-ops were set to
`ignore` for these controls.

See the [permission event excerpt](../evidence/I08/foreign-permission-events.log),
the [API 29 prompt](../evidence/I08/api29-storage-permission-dialog.png), and
the [API 30 media prompt](../evidence/I08/api30-media-permission-dialog.png).

## Evidence and limits

The eight compact runtime logs and all artifact hashes are indexed in the
[machine record](../evidence/I08/android-storage-matrix.json). The probe source
and host-seeded fixture are retained under `cases/android-storage/`.

The local Android runner does not expose the app process exit code. Each run
had a startup marker, a complete result marker, no native crash, and no app
PID after completion. APIs 24 and 31 were conditional and were not run. Native
SQLite open and permission recovery are tested separately under I09.
