// SPDX-License-Identifier: MIT
package totalcross.lab.sqlite;

import java.sql.SQLException;
import totalcross.io.File;
import totalcross.json.JSONObject;
import totalcross.sql.Connection;
import totalcross.sql.DriverManager;
import totalcross.sql.ResultSet;
import totalcross.sql.Statement;
import totalcross.sys.Convert;
import totalcross.sys.Settings;
import totalcross.ui.MainWindow;

/**
 * Plain SQLite smoke test for the official TotalCross 7.3.0 TCVM.
 * No PRAGMA key, SEE activation, SQLCipher, or cryptographic API is used.
 *
 * The output protocol is one JSON object per line prefixed TC_SQLITE_JSON.
 * Each case terminates the process with a nonzero exit or a FAIL event.
 */
public final class SQLitePlaintextProbe extends MainWindow {
  private String stage = "startup";
  private String databasePath = "";

  @Override
  public void initUI() {
    try {
      emit("startup", "PASS", "platform=" + Settings.platform + "; appPath=" + Settings.appPath
          + "; dataPath=" + Settings.dataPath);
      runMemory();
      runNewFile();
      runReopen();
      verifyPlaintextHeader();
      emit("result", "PASS", "All plaintext SQLite checks passed");
      System.out.flush();
      MainWindow.exit(0);
    } catch (Throwable failure) {
      emit(stage, "FAIL", failure.toString());
      emit("result", "FAIL", "stage=" + stage + "; " + failure);
      failure.printStackTrace();
      System.err.flush();
      System.out.flush();
      MainWindow.exit(1);
    }
  }

  private void runMemory() throws Exception {
    stage = "memory";
    Connection conn = DriverManager.getConnection("jdbc:sqlite::memory:");
    try {
      Statement stmt = conn.createStatement();
      try {
        ResultSet version = stmt.executeQuery("SELECT sqlite_version()");
        try {
          if (!version.next()) {
            throw new IllegalStateException("sqlite_version() returned no row");
          }
          emit("sqlite-version", "INFO", version.getString(1));
        } finally {
          version.close();
        }
        stmt.executeUpdate("CREATE TABLE smoke (id INTEGER PRIMARY KEY, value TEXT NOT NULL)");
        stmt.executeUpdate("INSERT INTO smoke (id, value) VALUES (1, 'memory-ok')");
        assertSingleValue(stmt, "SELECT value FROM smoke WHERE id=1", "memory-ok");
      } finally {
        stmt.close();
      }
    } finally {
      conn.close();
    }
    emit(stage, "PASS", "CREATE, INSERT, SELECT on :memory:");
  }

  private void runNewFile() throws Exception {
    stage = "file-create";
    if (Settings.appPath == null || Settings.appPath.length() == 0) {
      throw new IllegalStateException("Settings.appPath is not available");
    }
    databasePath = Convert.appendPath(Settings.appPath, "sqlite-plaintext-smoke.db");
    emit("database-path", "INFO", databasePath);
    if (new File(databasePath).exists()) {
      throw new IllegalStateException("Test database already exists: " + databasePath);
    }

    Connection conn = DriverManager.getConnection("jdbc:sqlite:" + databasePath);
    try {
      Statement stmt = conn.createStatement();
      try {
        stmt.executeUpdate("CREATE TABLE smoke (id INTEGER PRIMARY KEY, value TEXT NOT NULL)");
        stmt.executeUpdate("INSERT INTO smoke (id, value) VALUES (1, 'plaintext-ok')");
        stmt.executeUpdate("INSERT INTO smoke (id, value) VALUES (2, 'persistent-ok')");
        assertSingleValue(stmt, "SELECT value FROM smoke WHERE id=1", "plaintext-ok");
      } finally {
        stmt.close();
      }
    } finally {
      conn.close();
    }
    emit(stage, "PASS", "CREATE TABLE + INSERT + SELECT on a new on-disk database");
  }

  private void runReopen() throws Exception {
    stage = "file-reopen";
    Connection conn = DriverManager.getConnection("jdbc:sqlite:" + databasePath);
    try {
      Statement stmt = conn.createStatement();
      try {
        assertSingleValue(stmt, "SELECT value FROM smoke WHERE id=2", "persistent-ok");
        stmt.executeUpdate("UPDATE smoke SET value='updated-ok' WHERE id=1");
        assertSingleValue(stmt, "SELECT value FROM smoke WHERE id=1", "updated-ok");
        assertSingleValue(stmt, "PRAGMA integrity_check", "ok");
      } finally {
        stmt.close();
      }
    } finally {
      conn.close();
    }
    emit(stage, "PASS", "Reopen, SELECT, UPDATE and PRAGMA integrity_check");
  }

  private void verifyPlaintextHeader() throws Exception {
    stage = "plaintext-header";
    File file = new File(databasePath, File.READ_ONLY);
    try {
      byte[] buffer = new byte[16];
      int length = file.readBytes(buffer, 0, buffer.length);
      byte[] expected = {
          83, 81, 76, 105, 116, 101, 32, 102, 111, 114, 109, 97, 116, 32, 51, 0
      };
      if (length != expected.length) {
        throw new IllegalStateException("Expected 16 header bytes, got " + length);
      }
      for (int i = 0; i < expected.length; i++) {
        if (buffer[i] != expected[i]) {
          throw new IllegalStateException("Not a plaintext SQLite database: bad header at byte " + i);
        }
      }
      emit(stage, "PASS", "SQLite format 3 header; bytes=" + file.getSize());
    } finally {
      file.close();
    }
  }

  private static void assertSingleValue(Statement statement, String sql, String expected)
      throws SQLException {
    ResultSet rs = statement.executeQuery(sql);
    try {
      if (!rs.next()) {
        throw new IllegalStateException("Query returned no rows: " + sql);
      }
      String value = rs.getString(1);
      if (!expected.equals(value) || rs.next()) {
        throw new IllegalStateException("Unexpected query result for " + sql + ": " + value);
      }
    } finally {
      rs.close();
    }
  }

  private void emit(String name, String status, String detail) {
    try {
      JSONObject record = new JSONObject();
      record.put("schemaVersion", 1);
      record.put("stage", name);
      record.put("status", status);
      record.put("detail", detail);
      record.put("platform", Settings.platform == null ? "unknown" : Settings.platform);
      record.put("databasePath", databasePath);
      System.out.println("TC_SQLITE_JSON " + record.toString());
    } catch (Throwable ignored) {
      System.out.println("TC_SQLITE_EVENT " + name + " " + status + " " + detail);
    }
    System.out.flush();
  }
}
