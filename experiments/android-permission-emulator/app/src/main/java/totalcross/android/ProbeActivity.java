// Copyright (C) 2026 Amalgam Solucoes em TI Ltda
// SPDX-License-Identifier: LGPL-2.1-only
package totalcross.android;

import android.Manifest;
import android.app.Activity;
import android.content.pm.PackageManager;
import android.database.Cursor;
import android.database.sqlite.SQLiteDatabase;
import android.os.Build;
import android.os.Bundle;
import android.os.Environment;
import android.os.Process;
import android.util.Log;
import android.widget.TextView;

import org.json.JSONObject;

import java.io.File;
import java.io.FileOutputStream;
import java.nio.charset.StandardCharsets;

/**
 * Isolates Android storage permission behavior with the real 7.3.0 coordinator.
 * This is NOT a TotalCross VM application and uses Android's own SQLite engine.
 */
public final class ProbeActivity extends Activity {
    private static final String TAG = "TC_PERMISSION_PROBE";
    private static final String PREFIX = "TC_PROBE_JSON ";
    private String mode;
    private String unique;
    private TextView status;

    @Override
    protected void onCreate(Bundle state) {
        super.onCreate(state);
        status = new TextView(this);
        status.setText("Independent Android permission test");
        setContentView(status);
        AndroidPermissionManager.attach(this);
        mode = getIntent().getStringExtra("mode");
        if (mode == null) mode = "direct";
        unique = "tc-permission-730-" + Process.myPid() + "-" + System.currentTimeMillis();
        final String modeSnapshot = mode;
        new Thread(() -> runProbe(modeSnapshot), "tc-permission-probe").start();
    }

    private static String errorText(Throwable error) {
        return error.getClass().getSimpleName() + ": " + String.valueOf(error.getMessage());
    }

    private void emit(String stage, String state, String detail) {
        try {
            JSONObject data = new JSONObject();
            data.put("stage", stage);
            data.put("status", state);
            data.put("detail", detail);
            data.put("mode", mode);
            data.put("sdk", Build.VERSION.SDK_INT);
            data.put("targetSdk", getApplicationInfo().targetSdkVersion);
            data.put("pid", Process.myPid());
            Log.i(TAG, PREFIX + data.toString());
        } catch (Exception e) {
            Log.e(TAG, "Cannot serialize probe stage " + stage, e);
        }
    }

    private void permissions(String stage) {
        int read = checkSelfPermission(Manifest.permission.READ_EXTERNAL_STORAGE);
        int write = checkSelfPermission(Manifest.permission.WRITE_EXTERNAL_STORAGE);
        boolean legacy = Build.VERSION.SDK_INT >= 29 && Environment.isExternalStorageLegacy();
        emit(stage, "STATE", "READ=" + (read == PackageManager.PERMISSION_GRANTED)
                + " WRITE=" + (write == PackageManager.PERMISSION_GRANTED)
                + " legacy=" + legacy);
    }

    private void fileWrite(String stage, File destination) {
        try (FileOutputStream file = new FileOutputStream(destination)) {
            file.write("tc probe".getBytes(StandardCharsets.UTF_8));
            file.flush();
            emit(stage, "PASS", destination.getAbsolutePath());
        } catch (Exception e) {
            emit(stage, "FAIL", errorText(e));
        } finally {
            // Delete only the unique file created by this smoke test.
            if (destination.exists()) destination.delete();
        }
    }

    private void sqliteOpen(String stage, File destination) {
        SQLiteDatabase database = null;
        try {
            database = SQLiteDatabase.openOrCreateDatabase(destination, null);
            database.execSQL("CREATE TABLE IF NOT EXISTS probe (value TEXT)");
            database.execSQL("INSERT INTO probe VALUES ('works')");
            try (Cursor cursor = database.rawQuery("SELECT COUNT(*) FROM probe", null)) {
                if (!cursor.moveToFirst() || cursor.getInt(0) < 1) {
                    throw new IllegalStateException("SQLite query returned no row");
                }
            }
            emit(stage, "PASS", destination.getAbsolutePath());
        } catch (Exception e) {
            emit(stage, "FAIL", errorText(e));
        } finally {
            if (database != null) database.close();
            for (String suffix : new String[] {"", "-journal", "-wal", "-shm"}) {
                File local = new File(destination.getAbsolutePath() + suffix);
                if (local.exists()) local.delete();
            }
        }
    }

    private void runProbe(String currentMode) {
        emit("start", "RUNNING", "standalone app: TotalCross 7.3.0 permission coordinator <= Q candidate");
        permissions("permissions-before");
        // A private database must work with no external storage permissions.
        sqliteOpen("private-sqlite", new File(getFilesDir(), unique + "-internal.db"));
        fileWrite("external-file-before", new File("/sdcard/" + unique + "-before.txt"));
        sqliteOpen("external-sqlite-before", new File("/sdcard/" + unique + "-before.db"));

        if ("request".equals(currentMode)) {
            emit("permission-request", "START", "requestFileAccessBlocking");
            int response = AndroidPermissionManager.requestFileAccessBlocking();
            emit("permission-return", "RESULT", Integer.toString(response));
            permissions("permissions-after-request");
            fileWrite("external-file-after", new File("/sdcard/" + unique + "-after.txt"));
            sqliteOpen("external-sqlite-after", new File("/sdcard/" + unique + "-after.db"));
        }
        emit("complete", "DONE", currentMode);
    }

    @Override
    public void onRequestPermissionsResult(int requestCode, String[] permissions,
                                           int[] grantResults) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults);
        StringBuilder summary = new StringBuilder();
        for (int i = 0; i < permissions.length; i++) {
            summary.append(permissions[i]).append('=')
                    .append(i < grantResults.length ? grantResults[i] : "missing").append(';');
        }
        emit("permission-callback", "RESULT", summary.toString());
        AndroidPermissionManager.onRequestPermissionsResult(requestCode, permissions, grantResults);
    }

    @Override
    protected void onActivityResult(int requestCode, int resultCode, android.content.Intent data) {
        super.onActivityResult(requestCode, resultCode, data);
        AndroidPermissionManager.onActivityResult(requestCode, resultCode);
    }
}
