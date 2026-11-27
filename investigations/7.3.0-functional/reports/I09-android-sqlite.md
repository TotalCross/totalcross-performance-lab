# I09 — Android SQLite permission recovery

## Result

**PASS for the tested SQLite persistence, authorization, and denial behavior on
Android ARM64 APIs 29, 30, 35, and 36.** Candidate 94af recovered a direct
SQLite open on API 29 after the user granted READ and WRITE, and the same open
was denied after those permissions were revoked. Official 7.3.0 passed the
API 29 shared-file read/write control with permissions pregranted. On API 30,
the candidate requested READ only and stopped after denial. On APIs 35 and 36,
foreign-file opens were denied without a legacy permission prompt. App-created
shared Download databases passed on APIs 30, 35, and 36 while READ and WRITE
were denied.

This result covers the observed permission boundary. It does not establish
broad access to foreign files on Android 11 or later.

## Environment and identities

Both probes target SDK 36 and have minSdk 24. The APK explicitly declares
`WRITE_EXTERNAL_STORAGE` and sets `requestLegacyExternalStorage=true`; Android
package management also lists READ_EXTERNAL_STORAGE as a restricted/implicit
permission. The APK does not declare MANAGE_EXTERNAL_STORAGE. Package IDs were
`totalcross.appi09c` for candidate 94af and `totalcross.appi09o` for official
7.3.0.

| API | Android | AVD | Graphics |
| --- | --- | --- | --- |
| 29 | 10 | `emulator-5580` | ARM64, host GPU, GLES 2.0 |
| 30 | 11 | `emulator-5554` | ARM64, host GPU, GLES 3.0 |
| 35 | 15 | `emulator-5582` | ARM64, host GPU, GLES 3.0 |
| 36 | 16 | `emulator-5556` | ARM64, host GPU, GLES 3.0 |

All emulators ran with hardware acceleration on an Apple M1 Pro host. The
candidate source revision was
`94af2b8b653cad509994b5ccf3dbb60ac28ef920`; official 7.3.0 source identity was
`5464c21e3107e3f1ce9c287b724829e2bb870c1d`. The candidate SDK jar and ARM64
VM hashes are `a18c80e2784543493370d1120afc3e2d10d7594b51e5032d1f779f1f51c2f12d`
and `57ec070728ce6362a4ed32c06e05122a4bbdc29d4468dc4630c94d33db029215`.
The official SDK jar and ARM64 VM hashes are
`23a0e5f16146414419c43f418d554f494d6acad362aa0e03ca11e11bfd430475` and
`bf630c7bf8a7a33323631c3b59699157d621a4f4587aac77779931a2de2544ad`. All
mode-specific APK hashes are in the [machine record](../evidence/I09/android-sqlite-matrix.json).

The probe source is retained in `cases/android-sqlite/Main.java`. Python's host
SQLite 3.54.1 created the foreign fixture; the separately checked command-line
SQLite was 3.54.0. The fixture passed `integrity_check` and
contained the row `host-seeded-i09`; its SHA-256 is
`5dbfebcca5f40951c322f014d336ac02866a93eaad237b8adf63a4396bd8bbf6`. Both
TotalCross packages reported embedded SQLite 3.32.3.

## Test results

Private persistence, read-only, invalid SQL, and corrupt-database controls ran
on API 36 for both revisions. Each created and read a private database, closed
and reopened it, ran `integrity_check`, rejected a write through a read-only
connection, rejected invalid SQL, and rejected a corrupt file. A second
process reopened the persisted database and passed its checks. Each phase
reported zero failures.

| Scenario | Candidate 94af | Official 7.3.0 |
| --- | --- | --- |
| API 36 private create, reopen, error controls | PASS, 6 completed, 0 failures | PASS, 6 completed, 0 failures |
| API 36 private second-process persistence | PASS, 3 completed, 0 failures | PASS, 3 completed, 0 failures |
| API 29 foreign DB after denial | Expected denial; READ/WRITE prompt denied | Expected denial; no prompt |
| API 29 foreign DB after authorization | PASS after READ/WRITE grant | PASS with READ/WRITE pregranted |
| API 29 foreign DB after re-denial | Expected denial after revocation | Not part of official recovery flow |
| API 30 foreign DB | Expected denial; READ prompt only | Expected denial; no prompt |
| API 35/36 foreign DB | Expected denial; no prompt | Expected denial; no prompt |
| API 30/35/36 app-created shared DB | PASS with READ/WRITE denied | PASS with READ/WRITE denied |

The API 29 candidate sequence returned PermissionController result 6 for both
permissions on initial denial, result 4 for both on authorization, and result 6
again after revocation. The granted attempt read the host-seeded row, wrote a
recovery row, closed and reopened the database, and passed `integrity_check`.
The official package did not prompt on its denied API 29 attempt; after READ
and WRITE were pregranted, the same fixture read, write, reopen, and integrity
checks passed.

On API 30 the candidate asked only for READ_EXTERNAL_STORAGE. Denial returned
result 6 and no WRITE request followed. Both revisions' foreign-file opens
were denied on API 30, 35, and 36. No legacy permission prompt was observed on
APIs 35 or 36. In separate controls, each revision created a SQLite file in
`/sdcard/Download`, wrote to it, reopened it, and passed `integrity_check` with
READ and WRITE denied. This verifies access to the app-created file used by the
probe; it is not evidence of access to a foreign file.

The candidate Android `NativeDB` implementation filters shared-storage paths
and retries `sqlite3_open_v2` once when an access-related VFS error occurs and
permission authorization changes. The official 7.3.0 implementation calls
`sqlite3_open_v2` without that permission-recovery callback. The runtime
observations match that distinction on API 29.

## SQLite error reporting limits

The probe recorded the public Java exception error code and message. The
wrapper returned `0` for the read-only write error and `-1` for invalid SQL,
corrupt input, and denied opens. The reported primary SQLite codes below are
inferences from the messages, not native return values:

| Case | Reported wrapper code and message | Inferred SQLite code |
| --- | --- | --- |
| Read-only write | `0`, `attempt to write a readonly database` | `SQLITE_READONLY (8)` |
| Invalid SQL | `-1`, `no such table` | `SQLITE_ERROR (1)` |
| Corrupt database | `-1`, `file is not a database` | `SQLITE_NOTADB (26)` |
| Candidate denied open | `-1`, `unable to open database file` | `SQLITE_CANTOPEN (14)` |
| Official denied open | `-1`, `unknown error (out of memory)` | Not inferred; message is ambiguous |

SQLState was null where recorded. The public SQLite bridge does not expose
`sqlite3_extended_errcode`, so extended result codes could not be collected.
The official denied-open message is retained as observed; it is not treated as
a diagnosis of SQLite's native result.

## Evidence and limits

The [machine record](../evidence/I09/android-sqlite-matrix.json) records all
runs, APK/SDK/VM/fixture digests, permission state, result counts, and limits.
Compact runtime and PermissionController excerpts are in
[`android-sqlite-events.log`](../evidence/I09/android-sqlite-events.log), the
final package permission and process snapshot is in
[`permission-states.log`](../evidence/I09/permission-states.log), and the API
30 READ-only dialog is retained as
[`api30-sqlite-permission-prompt.png`](../evidence/I09/api30-sqlite-permission-prompt.png).
Every run emitted a completion marker with zero failures and no app PID was
present afterward. The local runner does not expose an application process
exit code.

I09 covers permission recovery and persistence on Android only. Cross-version
and cross-platform database compatibility, WAL snapshots, and the invalid
format compatibility control remain in I10.
