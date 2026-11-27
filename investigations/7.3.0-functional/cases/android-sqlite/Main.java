// Copyright (C) 2026 Amalgam Solucoes em TI Ltda
//
// SPDX-License-Identifier: LGPL-2.1-only

import totalcross.db.sqlite.SQLiteConfig;
import totalcross.io.File;
import totalcross.sql.Connection;
import totalcross.sql.ResultSet;
import totalcross.sql.Statement;
import totalcross.sys.Settings;
import totalcross.sys.Vm;
import totalcross.ui.MainWindow;
import totalcross.ui.Window;
import java.sql.SQLException;

public final class Main extends MainWindow {
  private static final String REVISION = "@@REVISION@@";
  private static final String MODE = "@@MODE@@";
  private static final String APPLICATION_ID = "@@APPLICATION_ID@@";
  private static int failures;
  private static int completed;

  static {
    Settings.applicationId = APPLICATION_ID;
  }

  public Main() {
    super("I09 Android SQLite probe", Window.NO_BORDER);
  }

  @Override
  public void initUI() {
    super.initUI();
    Vm.debug("TC_I09 startup revision=" + REVISION + " mode=" + MODE
        + " appPath=" + Settings.appPath + " appId=" + APPLICATION_ID);
    if (MODE.equals("private")) {
      runPrivate();
    } else if (MODE.equals("shared-allow") || MODE.equals("shared-deny")) {
      runShared();
    } else if (MODE.equals("shared-owned")) {
      runOwnedShared();
    } else {
      failures++;
      Vm.debug("TC_I09 case=dispatch status=FAIL details=unknown-mode");
    }
    Vm.debug("TC_I09_RESULT {\"revision\":\"" + REVISION + "\",\"mode\":\""
        + MODE + "\",\"completed\":" + completed + ",\"failures\":" + failures + "}");
    System.out.flush();
    MainWindow.exit(failures == 0 ? 0 : 1);
  }

  private static void runPrivate() {
    String path = Settings.appPath + "/i09-private.sqlite";
    try {
      boolean existed = new File(path, File.DONT_OPEN).exists();
      Vm.debug("TC_I09 case=private-create-open state=BEGIN existed=" + existed);
      Connection connection = open(path, false);
      if (!existed) {
        Statement statement = connection.createStatement();
        statement.executeUpdate("CREATE TABLE i09_data (id INTEGER PRIMARY KEY, value TEXT)");
        statement.executeUpdate("INSERT INTO i09_data(value) VALUES ('persisted-marker')");
        statement.close();
      }
      verifyPrivateRow(connection, "private-create-open");
      logIntegrity(connection, "private-before-close");
      connection.close();

      Connection reopened = open(path, false);
      verifyPrivateRow(reopened, existed ? "restart-persistence" : "close-reopen");
      logIntegrity(reopened, "private-after-reopen");
      logSqliteVersion(reopened);
      reopened.close();
      if (!existed) {
        runReadOnly(path);
        runInvalidSql(path);
        runCorruptDatabase();
      }
      completed++;
      Vm.debug("TC_I09 case=" + (existed ? "restart-persistence" : "private-create-open")
          + " status=PASS details=closed,reopened,row-and-integrity-verified");
    } catch (Throwable error) {
      failures++;
      logFailure("private-create-open", error);
    }
  }

  private static void runReadOnly(String path) {
    Vm.debug("TC_I09 case=readonly state=BEGIN");
    try {
      Connection connection = open(path, true);
      verifyPrivateRow(connection, "readonly-read");
      Statement statement = connection.createStatement();
      try {
        statement.executeUpdate("INSERT INTO i09_data(value) VALUES ('readonly-must-fail')");
        failures++;
        Vm.debug("TC_I09 case=readonly-write status=FAIL details=write-succeeded");
      } catch (SQLException expected) {
        int reportedCode = expected.getErrorCode();
        String message = clean(expected.getMessage());
        if (reportedCode == 8 || message.toLowerCase().indexOf("readonly") >= 0) {
          completed++;
          Vm.debug("TC_I09 case=readonly-write status=PASS details=reportedErrorCode=" + reportedCode
              + ";message=" + message + ";resultCodeInference=SQLITE_READONLY(8)");
        } else {
          failures++;
          logSqlException("readonly-write", expected);
        }
      }
      statement.close();
      connection.close();
    } catch (Throwable error) {
      failures++;
      logFailure("readonly", error);
    }
  }

  private static void runInvalidSql(String path) {
    Vm.debug("TC_I09 case=invalid-sql state=BEGIN");
    try {
      Connection connection = open(path, false);
      Statement statement = connection.createStatement();
      try {
        statement.executeQuery("SELECT value FROM table_that_does_not_exist");
        failures++;
        Vm.debug("TC_I09 case=invalid-sql status=FAIL details=query-succeeded");
      } catch (SQLException expected) {
        int reportedCode = expected.getErrorCode();
        String message = clean(expected.getMessage());
        if (reportedCode == 1 || message.toLowerCase().indexOf("no such table") >= 0) {
          completed++;
          Vm.debug("TC_I09 case=invalid-sql status=PASS details=reportedErrorCode=" + reportedCode
              + ";message=" + message + ";resultCodeInference=SQLITE_ERROR(1)");
        } else {
          failures++;
          logSqlException("invalid-sql", expected);
        }
      }
      statement.close();
      connection.close();
    } catch (Throwable error) {
      failures++;
      logFailure("invalid-sql", error);
    }
  }

  private static void runCorruptDatabase() {
    String path = Settings.appPath + "/i09-corrupt.sqlite";
    Vm.debug("TC_I09 case=corrupt-database state=BEGIN");
    try {
      File file = new File(path, File.CREATE_EMPTY);
      byte[] invalidHeader = "not-a-sqlite-database".getBytes();
      file.writeBytes(invalidHeader, 0, invalidHeader.length);
      file.flush();
      file.close();

      Connection connection = open(path, true);
      Statement statement = connection.createStatement();
      try {
        ResultSet result = statement.executeQuery("PRAGMA integrity_check");
        if (result.next() && "ok".equalsIgnoreCase(result.getString(1))) {
          failures++;
          Vm.debug("TC_I09 case=corrupt-database status=FAIL details=invalid-file-accepted");
        } else {
          failures++;
          Vm.debug("TC_I09 case=corrupt-database status=FAIL details=unexpected-integrity-result");
        }
        result.close();
      } catch (SQLException expected) {
        int reportedCode = expected.getErrorCode();
        String message = clean(expected.getMessage());
        if (reportedCode == 11 || reportedCode == 26
            || message.toLowerCase().indexOf("not a database") >= 0
            || message.toLowerCase().indexOf("malformed") >= 0) {
          completed++;
          Vm.debug("TC_I09 case=corrupt-database status=PASS details=reportedErrorCode=" + reportedCode
              + ";message=" + message + ";resultCodeInference=SQLITE_NOTADB(26)");
        } else {
          failures++;
          logSqlException("corrupt-database", expected);
        }
      }
      statement.close();
      connection.close();
    } catch (SQLException expectedAtOpen) {
      int reportedCode = expectedAtOpen.getErrorCode();
      String message = clean(expectedAtOpen.getMessage());
      if (reportedCode == 11 || reportedCode == 26
          || message.toLowerCase().indexOf("not a database") >= 0
          || message.toLowerCase().indexOf("malformed") >= 0) {
        completed++;
        Vm.debug("TC_I09 case=corrupt-database status=PASS details=reportedErrorCode=" + reportedCode
            + ";message=" + message + ";resultCodeInference=SQLITE_NOTADB(26)");
      } else {
        failures++;
        logSqlException("corrupt-database-open", expectedAtOpen);
      }
    } catch (Throwable error) {
      failures++;
      logFailure("corrupt-database", error);
    }
  }

  private static void runShared() {
    String path = "/sdcard/Download/tc730-i09-foreign.sqlite";
    boolean expectedAccess = MODE.equals("shared-allow");
    Vm.debug("TC_I09 case=shared-open state=BEGIN expected="
        + (expectedAccess ? "allow" : "deny") + " path=" + path);
    try {
      Connection connection = open(path, false);
      if (!expectedAccess) {
        failures++;
        Vm.debug("TC_I09 case=shared-open status=FAIL details=open-succeeded-without-authorization");
        connection.close();
        return;
      }
      verifyHostFixture(connection);
      Statement statement = connection.createStatement();
      statement.executeUpdate("CREATE TABLE IF NOT EXISTS i09_recovery (value TEXT)");
      statement.executeUpdate("INSERT INTO i09_recovery(value) VALUES ('permission-recovered')");
      statement.close();
      logIntegrity(connection, "shared-before-close");
      connection.close();

      Connection reopened = open(path, false);
      verifyRecoveryRow(reopened);
      logIntegrity(reopened, "shared-after-reopen");
      reopened.close();
      completed++;
      Vm.debug("TC_I09 case=shared-open status=PASS details=host-row,recovery-write,reopen,integrity-ok");
    } catch (SQLException error) {
      int reportedCode = error.getErrorCode();
      String message = clean(error.getMessage());
      if (!expectedAccess) {
        completed++;
        String resultCodeInference = message.toLowerCase().indexOf("unable to open") >= 0
            ? "SQLITE_CANTOPEN(14)" : "unavailable-from-public-exception";
        Vm.debug("TC_I09 case=shared-open status=EXPECTED_DENIAL details=reportedErrorCode=" + reportedCode
            + ";sqlState=" + clean(error.getSQLState()) + ";message=" + message
            + ";resultCodeInference=" + resultCodeInference);
      } else {
        failures++;
        logSqlException("shared-open", error);
      }
    } catch (Throwable error) {
      failures++;
      logFailure("shared-open", error);
    }
  }

  private static void runOwnedShared() {
    String path = "/sdcard/Download/tc730-i09-owned-" + APPLICATION_ID.toLowerCase() + ".sqlite";
    Vm.debug("TC_I09 case=shared-app-owned state=BEGIN path=" + path);
    try {
      boolean existed = new File(path, File.DONT_OPEN).exists();
      Connection connection = open(path, false);
      if (!existed) {
        Statement statement = connection.createStatement();
        statement.executeUpdate("CREATE TABLE i09_owned (value TEXT)");
        statement.executeUpdate("INSERT INTO i09_owned(value) VALUES ('app-owned-marker')");
        statement.close();
      }
      verifyOwnedRow(connection);
      logIntegrity(connection, "shared-owned-before-close");
      connection.close();

      Connection reopened = open(path, false);
      verifyOwnedRow(reopened);
      logIntegrity(reopened, "shared-owned-after-reopen");
      reopened.close();
      completed++;
      Vm.debug("TC_I09 case=shared-app-owned status=PASS details=created,reopened,integrity-ok;existed="
          + existed);
    } catch (Throwable error) {
      failures++;
      logFailure("shared-app-owned", error);
    }
  }

  private static void verifyOwnedRow(Connection connection) throws SQLException {
    Statement statement = connection.createStatement();
    ResultSet result = statement.executeQuery("SELECT value FROM i09_owned LIMIT 1");
    boolean valid = result.next() && "app-owned-marker".equals(result.getString(1));
    result.close();
    statement.close();
    if (!valid) {
      throw new IllegalStateException("app-owned shared row mismatch");
    }
  }

  private static Connection open(String path, boolean readOnly) throws SQLException {
    SQLiteConfig config = new SQLiteConfig();
    config.setReadOnly(readOnly);
    return config.createConnection("jdbc:sqlite:" + path);
  }

  private static void verifyPrivateRow(Connection connection, String name) throws SQLException {
    Statement statement = connection.createStatement();
    ResultSet result = statement.executeQuery("SELECT value FROM i09_data WHERE id=1");
    boolean valid = result.next() && "persisted-marker".equals(result.getString(1));
    result.close();
    statement.close();
    if (!valid) {
      throw new IllegalStateException(name + ": persisted row mismatch");
    }
    Vm.debug("TC_I09 case=" + name + " status=PASS details=row=persisted-marker");
  }

  private static void verifyHostFixture(Connection connection) throws SQLException {
    Statement statement = connection.createStatement();
    ResultSet result = statement.executeQuery("SELECT value FROM i09_host_fixture LIMIT 1");
    boolean valid = result.next() && "host-seeded-i09".equals(result.getString(1));
    result.close();
    statement.close();
    if (!valid) {
      throw new IllegalStateException("host fixture row mismatch");
    }
    Vm.debug("TC_I09 case=shared-host-fixture status=PASS details=row=host-seeded-i09");
  }

  private static void verifyRecoveryRow(Connection connection) throws SQLException {
    Statement statement = connection.createStatement();
    ResultSet result = statement.executeQuery("SELECT value FROM i09_recovery ORDER BY rowid DESC LIMIT 1");
    boolean valid = result.next() && "permission-recovered".equals(result.getString(1));
    result.close();
    statement.close();
    if (!valid) {
      throw new IllegalStateException("recovered row mismatch after reopen");
    }
  }

  private static void logIntegrity(Connection connection, String name) throws SQLException {
    Statement statement = connection.createStatement();
    ResultSet result = statement.executeQuery("PRAGMA integrity_check");
    String answer = result.next() ? result.getString(1) : "<no-row>";
    result.close();
    statement.close();
    if (!"ok".equalsIgnoreCase(answer)) {
      throw new IllegalStateException(name + ": integrity_check=" + answer);
    }
    completed++;
    Vm.debug("TC_I09 case=" + name + " status=PASS details=integrity_check=ok");
  }

  private static void logSqliteVersion(Connection connection) throws SQLException {
    Statement statement = connection.createStatement();
    ResultSet result = statement.executeQuery("SELECT sqlite_version()");
    String version = result.next() ? result.getString(1) : "<no-row>";
    result.close();
    statement.close();
    Vm.debug("TC_I09 sqliteVersion=" + version);
  }

  private static void logSqlException(String name, SQLException error) {
    Vm.debug("TC_I09 case=" + name + " status=SQL_ERROR reportedErrorCode=" + error.getErrorCode()
        + " sqlState=" + clean(error.getSQLState()) + " message=" + clean(error.getMessage()));
  }

  private static void logFailure(String name, Throwable error) {
    Vm.debug("TC_I09 case=" + name + " status=FAIL details=" + error.getClass().getName()
        + ":" + clean(error.getMessage()));
  }

  private static String clean(String value) {
    return value == null ? "null" : value.replace('\n', ' ').replace('\r', ' ');
  }
}
