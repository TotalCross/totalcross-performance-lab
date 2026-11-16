# Android 10 storage permission regression — without a TotalCross VM build

This is an independent Android APK, not TotalCross. It compiles the **exact**
`AndroidPermissionManager.java` from the TotalCross 7.3.0 source commit
`5464c21e3107e3f1ce9c287b724829e2bb870c1d`, unchanged. It does not
rebuild the TotalCross VM, JNI, native libraries, SDK, or customer application.

The fixture explicitly declares the same baseline `WRITE_EXTERNAL_STORAGE`
permission and `requestLegacyExternalStorage=true`. Android may additionally
grant an *implied* READ permission, which the logs record.

Checks on Android 10/API29:
1. Without runtime authorization, attempt a Java `File` write and an Android
   `SQLiteDatabase` open on `/sdcard` (no permission call).
2. Call the real `AndroidPermissionManager.requestFileAccessBlocking()` from
   a worker thread; capture UI dialog, callback, and the ensuing File/SQLite
   retry. ADB automation identifies Allow through UI XML.
3. After `pm grant READ_EXTERNAL_STORAGE` and `pm grant WRITE_EXTERNAL_STORAGE`,
   retry both operations using the exact same APK.
4. Compare targetSdk 29 vs 36 to isolate storage compatibility behavior.
5. Attempt app-private SQLite as a control.

This measures Android **framework** SQLite, not TotalCross's direct
`sqlite3_open_v2()`. It cannot validate native VM retry behavior.

A failed or inconclusive emulator is not evidence of a regression.
No AWS Device Farm or paid physical devices are invoked. The workflow uploads
logs, actual grants, appops, and machine-readable results even on failure.
