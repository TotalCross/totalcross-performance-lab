// SPDX-License-Identifier: MIT
import totalcross.io.File;
import totalcross.sql.Connection;
import totalcross.sql.DriverManager;
import totalcross.sql.ResultSet;
import totalcross.sql.Statement;
import totalcross.sys.Convert;
import totalcross.sys.Settings;
import totalcross.sys.Vm;
import totalcross.ui.Button;
import totalcross.ui.MainWindow;
import totalcross.ui.Window;

public final class Main extends MainWindow {
  private static final String MODE = "@@MODE@@";
  private final totalcross.util.concurrent.Lock gate = new totalcross.util.concurrent.Lock();
  private boolean workerReady;
  private boolean workerFinished;

  public Main() {
    super("I05 shutdown probe", Window.NO_BORDER);
  }

  @Override
  public void initUI() {
    super.initUI();
    Vm.debug("TC_I05 startup mode=" + MODE + " appPath=" + Settings.appPath);
    try {
      if (MODE.equals("normal")) {
        Vm.debug("TC_I05 case=normal-exit state=EXIT_REQUEST");
        exitNormally();
      } else if (MODE.equals("worker")) {
        showWorkerExitButton();
      } else if (MODE.equals("file-io")) {
        exitDuringFileWrite();
      } else if (MODE.equals("sqlite")) {
        exitDuringSqlite();
      } else if (MODE.equals("external")) {
        exitAfterExternalPermissionOperation();
      } else {
        Vm.debug("TC_I05 case=dispatch state=FAIL detail=unknown-mode");
        MainWindow.exit(2);
      }
    } catch (Throwable failure) {
      Vm.debug("TC_I05 case=" + MODE + " state=FAIL detail=" + failure.toString());
      failure.printStackTrace();
      System.out.flush();
      MainWindow.exit(1);
    }
  }

  private void showWorkerExitButton() {
    final boolean[] run = {true};
    new Thread(new Runnable() {
      @Override
      public void run() {
        synchronized (gate) {
          workerReady = true;
        }
        Vm.debug("TC_I05 case=worker state=READY");
        while (run[0]) {
          Thread.yield();
        }
        synchronized (gate) {
          workerFinished = true;
        }
      }
    }).start();
    Button exit = new Button("Exit with worker active");
    exit.addPressListener(event -> {
      Vm.debug("TC_I05 case=worker state=EXIT_REQUEST");
      exitNormally();
    });
    add(exit, LEFT, TOP, FILL, PREFERRED);
  }

  private void exitDuringFileWrite() {
    final File file;
    try {
      file = new File(path("i05-shutdown-write.bin"), File.CREATE_EMPTY);
    } catch (Throwable failure) {
      Vm.debug("TC_I05 case=file-io state=OPEN_EXCEPTION detail=" + failure.toString());
      MainWindow.exit(1);
      return;
    }
    final byte[] payload = new byte[1024 * 1024];
    new Thread(new Runnable() {
      @Override
      public void run() {
        synchronized (gate) {
          workerReady = true;
        }
        Vm.debug("TC_I05 case=file-io state=WRITE_BEGIN bytes=" + payload.length);
        try {
          for (int i = 0; i < 16; i++) {
            file.writeBytes(payload, 0, payload.length);
          }
          file.flush();
          file.close();
          synchronized (gate) {
            workerFinished = true;
          }
        } catch (Throwable failure) {
          // Do not call back into native logging after the UI thread requests
          // VM shutdown; that could itself touch the mutex under investigation.
          synchronized (gate) {
            workerFinished = false;
          }
        }
      }
    }).start();
    if (awaitWorkerReady()) {
      Vm.debug("TC_I05 case=file-io state=EXIT_REQUEST after=worker-ready");
      exitNormally();
    } else {
      throw new IllegalStateException("file writer did not reach barrier");
    }
  }

  private void exitDuringSqlite() {
    new Thread(new Runnable() {
      @Override
      public void run() {
        Connection connection = null;
        Statement statement = null;
        try {
          connection = DriverManager.getConnection("jdbc:sqlite::memory:");
          statement = connection.createStatement();
          statement.executeUpdate("CREATE TABLE shutdown_probe (value TEXT)");
          synchronized (gate) {
            workerReady = true;
          }
          Vm.debug("TC_I05 case=sqlite state=QUERY_BEGIN");
          ResultSet result = statement.executeQuery("SELECT randomblob(4194304)");
          boolean row = result.next();
          synchronized (gate) {
            workerFinished = row;
          }
          result.close();
        } catch (Throwable failure) {
          synchronized (gate) {
            workerFinished = false;
          }
        } finally {
          try {
            if (statement != null) {
              statement.close();
            }
            if (connection != null) {
              connection.close();
            }
          } catch (Throwable closeFailure) {
            synchronized (gate) {
              workerFinished = false;
            }
          }
        }
      }
    }).start();
    if (awaitWorkerReady()) {
      Vm.debug("TC_I05 case=sqlite state=EXIT_REQUEST after=worker-ready");
      exitNormally();
    } else {
      throw new IllegalStateException("SQLite worker did not reach barrier");
    }
  }

  private void exitAfterExternalPermissionOperation() {
    String target = "/sdcard/tc730-i05-shutdown-permission.bin";
    Vm.debug("TC_I05 case=permission state=BEGIN path=" + target);
    try {
      File file = new File(target, File.CREATE_EMPTY);
      byte[] payload = "shutdown-after-permission".getBytes();
      file.writeBytes(payload, 0, payload.length);
      file.flush();
      file.close();
      Vm.debug("TC_I05 case=permission state=WRITE_COMPLETE");
    } catch (Throwable failure) {
      Vm.debug("TC_I05 case=permission state=WRITE_EXCEPTION detail=" + failure.toString());
    }
    Vm.debug("TC_I05 case=permission state=EXIT_REQUEST after=permission-operation");
    exitNormally();
  }

  private boolean awaitWorkerReady() {
    for (int i = 0; i < 10000; i++) {
      synchronized (gate) {
        if (workerReady) {
          return true;
        }
      }
      Vm.safeSleep(1);
    }
    return false;
  }

  private void exitNormally() {
    System.out.flush();
    MainWindow.exit(0);
  }

  private static String path(String name) {
    return Convert.appendPath(Settings.appPath, name);
  }
}
