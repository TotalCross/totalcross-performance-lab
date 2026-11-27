// Copyright (C) 2026 Amalgam Solucoes em TI Ltda
//
// SPDX-License-Identifier: LGPL-2.1-only

import java.sql.SQLException;
import totalcross.db.sqlite.SQLiteConfig;
import totalcross.io.File;
import totalcross.sql.Connection;
import totalcross.sql.ResultSet;
import totalcross.sql.Statement;
import totalcross.sys.Convert;
import totalcross.sys.Settings;
import totalcross.sys.Vm;
import totalcross.ui.MainWindow;
import totalcross.ui.Window;

public final class Main extends MainWindow {
  private static final String REVISION = "@@REVISION@@";
  private static final String APP_ID = "i10x";
  private static final String ANDROID_FILES_PATH = "@@ANDROID_FILES_PATH@@";
  private static int completed;
  private static int failures;

  static {
    Settings.applicationId = APP_ID;
  }

  public Main() {
    super("I10 SQLite compatibility", Window.NO_BORDER);
  }

  @Override
  public void initUI() {
    try {
      Config config = readConfig();
      event("startup", "PASS", "revision=" + REVISION + ";mode=" + config.mode
          + ";appPath=" + clean(Settings.appPath));
      if ("create".equals(config.mode)) {
        createDatabase(config);
      } else if ("read".equals(config.mode) || "wal-read".equals(config.mode)) {
        verifyDatabase(config, "wal-read".equals(config.mode));
      } else if ("update".equals(config.mode)) {
        updateDatabase(config);
      } else if ("invalid".equals(config.mode)) {
        verifyInvalidDatabase(config);
      } else {
        throw new IllegalArgumentException("unknown mode=" + config.mode);
      }
    } catch (Throwable error) {
      failures++;
      event("uncaught", "FAIL", error.getClass().getName() + ":" + clean(error.getMessage()));
    }
    event("result", failures == 0 ? "PASS" : "FAIL",
        "completed=" + completed + ";failures=" + failures);
    System.out.flush();
    MainWindow.exit(failures == 0 ? 0 : 1);
  }

  private static void createDatabase(Config config) throws Exception {
    Connection connection = open(config.databasePath, false);
    Statement statement = connection.createStatement();
    statement.executeUpdate("PRAGMA user_version=10");
    statement.executeUpdate("CREATE TABLE i10_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)");
    statement.executeUpdate("CREATE TABLE i10_records (id INTEGER PRIMARY KEY, value TEXT NOT NULL, amount INTEGER NOT NULL)");
    statement.executeUpdate("INSERT INTO i10_meta(key,value) VALUES ('origin','" + sql(config.origin) + "')");
    statement.executeUpdate("INSERT INTO i10_records(id,value,amount) VALUES (1,'" + sql(config.origin)
        + "-origin',10)");
    statement.executeUpdate("INSERT INTO i10_records(id,value,amount) VALUES (2,'transfer-marker',20)");
    statement.close();
    verifyContents(connection, config.origin, false);
    integrity(connection, "create-integrity");
    sqliteDetails(connection);
    connection.close();
    completed++;
    event("create", "PASS", "origin=" + config.origin + ";userVersion=10");
  }

  private static void verifyDatabase(Config config, boolean wal) throws Exception {
    Connection connection = open(config.databasePath, true);
    verifyContents(connection, config.expectedOrigin, wal);
    integrity(connection, "read-integrity");
    sqliteDetails(connection);
    connection.close();
    completed++;
    event(wal ? "wal-snapshot" : "cross-version-read", "PASS",
        "origin=" + config.expectedOrigin + ";databasePath=" + clean(config.databasePath));
  }

  private static void updateDatabase(Config config) throws Exception {
    Connection connection = open(config.databasePath, false);
    verifyContents(connection, config.expectedOrigin, false);
    Statement statement = connection.createStatement();
    statement.executeUpdate("CREATE TABLE IF NOT EXISTS i10_upgrades (revision TEXT PRIMARY KEY)");
    statement.executeUpdate("UPDATE i10_records SET amount=amount+1 WHERE id=1");
    statement.executeUpdate("INSERT OR REPLACE INTO i10_upgrades(revision) VALUES ('"
        + sql(REVISION) + "')");
    statement.close();
    integrity(connection, "update-integrity");
    sqliteDetails(connection);
    connection.close();
    completed++;
    event("update", "PASS", "revision=" + REVISION + ";origin=" + config.expectedOrigin);
  }

  private static void verifyInvalidDatabase(Config config) throws Exception {
    boolean rejected = false;
    Connection connection = null;
    Statement statement = null;
    ResultSet integrity = null;
    try {
      connection = open(config.databasePath, true);
      statement = connection.createStatement();
      integrity = statement.executeQuery("PRAGMA integrity_check");
      String answer = integrity.next() ? integrity.getString(1) : "<no-row>";
      if ("ok".equalsIgnoreCase(answer)) {
        throw new IllegalStateException("invalid non-SQLite file passed integrity_check");
      }
      rejected = true;
      event("invalid-negative", "EXPECTED_ERROR", "integrityCheck=" + clean(answer));
    } catch (SQLException expected) {
      rejected = true;
      event("invalid-negative", "EXPECTED_ERROR", "reportedErrorCode=" + expected.getErrorCode()
          + ";sqlState=" + clean(expected.getSQLState()) + ";message=" + clean(expected.getMessage()));
    } finally {
      if (integrity != null) integrity.close();
      if (statement != null) statement.close();
      if (connection != null) connection.close();
    }
    if (!rejected) {
      throw new IllegalStateException("invalid non-SQLite file opened successfully");
    }
    completed++;
  }

  private static void verifyContents(Connection connection, String expectedOrigin, boolean wal)
      throws Exception {
    Statement statement = connection.createStatement();
    ResultSet version = statement.executeQuery("PRAGMA user_version");
    if (!version.next() || version.getInt(1) != 10) {
      throw new IllegalStateException("unexpected user_version");
    }
    version.close();

    ResultSet meta = statement.executeQuery("SELECT value FROM i10_meta WHERE key='origin'");
    if (!meta.next() || !expectedOrigin.equals(meta.getString(1))) {
      throw new IllegalStateException("origin mismatch; expected=" + expectedOrigin);
    }
    meta.close();

    ResultSet rows = statement.executeQuery("SELECT id,value,amount FROM i10_records ORDER BY id");
    if (!rows.next() || rows.getInt(1) != 1
        || !(expectedOrigin + "-origin").equals(rows.getString(2)) || rows.getInt(3) < 10) {
      throw new IllegalStateException("first row mismatch");
    }
    if (!rows.next() || rows.getInt(1) != 2
        || !(wal ? "wal-committed-marker" : "transfer-marker").equals(rows.getString(2))) {
      throw new IllegalStateException("second row mismatch; wal=" + wal);
    }
    if (rows.next()) {
      throw new IllegalStateException("unexpected extra records");
    }
    rows.close();
    statement.close();
  }

  private static void integrity(Connection connection, String name) throws Exception {
    Statement statement = connection.createStatement();
    ResultSet result = statement.executeQuery("PRAGMA integrity_check");
    String answer = result.next() ? result.getString(1) : "<no-row>";
    result.close();
    statement.close();
    if (!"ok".equalsIgnoreCase(answer)) {
      throw new IllegalStateException(name + " returned " + answer);
    }
    event(name, "PASS", "integrity_check=ok");
  }

  private static void sqliteDetails(Connection connection) throws Exception {
    Statement statement = connection.createStatement();
    ResultSet version = statement.executeQuery("SELECT sqlite_version()");
    String sqliteVersion = version.next() ? version.getString(1) : "<no-row>";
    version.close();

    ResultSet options = statement.executeQuery("PRAGMA compile_options");
    StringBuilder compileOptions = new StringBuilder();
    int optionCount = 0;
    while (options.next()) {
      if (optionCount > 0) {
        compileOptions.append(',');
      }
      compileOptions.append(clean(options.getString(1)));
      optionCount++;
    }
    options.close();
    statement.close();
    event("sqlite-build", "INFO", "sqliteVersion=" + sqliteVersion + ";compileOptionCount="
        + optionCount + ";compileOptions=" + compileOptions.toString());
  }

  private static Connection open(String path, boolean readOnly) throws SQLException {
    SQLiteConfig config = new SQLiteConfig();
    config.setReadOnly(readOnly);
    return config.createConnection("jdbc:sqlite:" + path);
  }

  private static Config readConfig() throws Exception {
    String path = Settings.ANDROID.equals(Settings.platform)
        ? ANDROID_FILES_PATH + "/tc-i10-case.txt"
        : Convert.appendPath(Settings.appPath, "tc-i10-case.txt");
    File file = new File(path, File.READ_ONLY);
    int size = file.getSize();
    byte[] bytes = new byte[size];
    int read = file.readBytes(bytes, 0, size);
    file.close();
    if (read != size) {
      throw new IllegalStateException("short config read=" + read + ";expected=" + size);
    }
    Config config = new Config();
    String text = new String(bytes);
    int start = 0;
    while (start < text.length()) {
      int end = text.indexOf('\n', start);
      if (end < 0) {
        end = text.length();
      }
      String line = text.substring(start, end).trim();
      int equals = line.indexOf('=');
      if (equals > 0) {
        String key = line.substring(0, equals).trim();
        String value = line.substring(equals + 1).trim();
        if ("mode".equals(key)) config.mode = value;
        if ("origin".equals(key)) config.origin = value;
        if ("expectedOrigin".equals(key)) config.expectedOrigin = value;
        if ("databasePath".equals(key)) config.databasePath = value;
      }
      start = end + 1;
    }
    if (config.mode.length() == 0 || config.databasePath.length() == 0) {
      throw new IllegalArgumentException("mode and databasePath are required in " + path);
    }
    if (("create".equals(config.mode) && config.origin.length() == 0)
        || (("read".equals(config.mode) || "wal-read".equals(config.mode)
        || "update".equals(config.mode)) && config.expectedOrigin.length() == 0)) {
      throw new IllegalArgumentException("origin field is required for mode=" + config.mode);
    }
    return config;
  }

  private static void event(String stage, String status, String details) {
    String line = "TC_I10_EVENT stage=" + stage + " status=" + status
        + " revision=" + REVISION + " details=" + clean(details);
    Vm.debug(line);
    System.out.println(line);
  }

  private static String sql(String value) {
    return value.replace("'", "''");
  }

  private static String clean(String value) {
    if (value == null) {
      return "null";
    }
    return value.replace('\n', ' ').replace('\r', ' ').replace(';', ',');
  }

  private static final class Config {
    String mode = "";
    String origin = "";
    String expectedOrigin = "";
    String databasePath = "";
  }
}
