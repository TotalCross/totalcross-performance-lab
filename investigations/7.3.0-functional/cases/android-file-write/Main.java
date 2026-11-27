// SPDX-License-Identifier: MIT
import java.io.IOException;

import totalcross.io.File;
import totalcross.sys.Convert;
import totalcross.sys.Settings;
import totalcross.sys.Vm;
import totalcross.ui.MainWindow;
import totalcross.ui.Window;

public final class Main extends MainWindow {
  private static final String MODE = "@@MODE@@";
  private static int failures;

  public Main() {
    super("I04 File.writeBytes probe", Window.NO_BORDER);
  }

  @Override
  public void initUI() {
    super.initUI();
    Vm.debug("TC_I04 startup mode=" + MODE + " appPath=" + Settings.appPath);
    try {
      if (MODE.equals("standard")) {
        runStandardCases();
      } else if (MODE.equals("external")) {
        runExternalWrite();
      } else if (MODE.equals("race")) {
        runConcurrentWriteClose();
      } else {
        fail("dispatch", "unknown mode " + MODE);
      }
    } catch (Throwable failure) {
      fail("uncaught", failure.toString());
      failure.printStackTrace();
    }
    Vm.debug("TC_I04 completion mode=" + MODE + " failures=" + failures);
    System.out.flush();
    MainWindow.exit(failures == 0 ? 0 : 1);
  }

  private static void runStandardCases() {
    byte[] payload = "tc730-file-write".getBytes();
    String normalPath = path("i04-normal.bin");
    try {
      File file = new File(normalPath, File.CREATE_EMPTY);
      int count = file.writeBytes(payload, 0, payload.length);
      file.flush();
      int size = file.getSize();
      file.close();
      File read = new File(normalPath, File.READ_ONLY);
      byte[] observed = new byte[payload.length];
      int readCount = read.readBytes(observed, 0, observed.length);
      read.close();
      if (count != payload.length || size != payload.length
          || readCount != payload.length || !equal(payload, observed)) {
        fail("normal-write", "count=" + count + "; size=" + size + "; read=" + readCount);
      } else {
        pass("normal-write", "write/flush/readback/close verified " + count + " bytes");
      }
    } catch (Throwable failure) {
      fail("normal-write", failure.toString());
    }

    try {
      File closed = new File(path("i04-closed.bin"), File.CREATE_EMPTY);
      closed.close();
      try {
        closed.writeBytes(payload, 0, payload.length);
        fail("write-after-close", "write unexpectedly returned normally");
      } catch (IOException expected) {
        pass("write-after-close", expected.toString());
      }
    } catch (Throwable failure) {
      fail("write-after-close-setup", failure.toString());
    }

    try {
      File unopened = new File(path("i04-dont-open.bin"), File.DONT_OPEN);
      try {
        unopened.writeBytes(payload, 0, payload.length);
        fail("write-dont-open", "write unexpectedly returned normally");
      } catch (IOException expected) {
        pass("write-dont-open", expected.toString());
      }
      unopened.close();
    } catch (Throwable failure) {
      fail("write-dont-open-setup", failure.toString());
    }

    try {
      File invalid = new File("/proc/tc730-i04-missing/file.bin", File.CREATE);
      invalid.close();
      fail("failed-open", "read-only /proc path unexpectedly opened");
    } catch (IOException expected) {
      pass("failed-open", "constructor rejected path before a File handle existed: "
          + expected.toString());
    } catch (Throwable failure) {
      fail("failed-open", failure.toString());
    }
  }

  private static void runExternalWrite() {
    String target = "/sdcard/tc730-i04-permission.bin";
    byte[] payload = "tc730-permission-write".getBytes();
    Vm.debug("TC_I04 case=external-write state=BEGIN path=" + target);
    try {
      File file = new File(target, File.CREATE_EMPTY);
      int count = file.writeBytes(payload, 0, payload.length);
      file.flush();
      file.close();
      if (count != payload.length) {
        fail("external-write", "wrote " + count + " of " + payload.length);
      } else {
        pass("external-write", "wrote and flushed " + count + " bytes");
      }
    } catch (Throwable failure) {
      fail("external-write", failure.toString());
    }
  }

  private static void runConcurrentWriteClose() {
    // A multi-megabyte write keeps the native fwrite path active long enough
    // for the competing close thread to reach the same File instance.
    final byte[] payload = new byte[8 * 1024 * 1024];
    final String prefix = path("i04-race-");
    final totalcross.util.concurrent.Lock gate = new totalcross.util.concurrent.Lock();
    int completed = 0;
    for (int run = 0; run < 10; run++) {
      final int index = run;
      final File file;
      try {
        file = new File(prefix + index + ".bin", File.CREATE_EMPTY);
      } catch (Throwable failure) {
        fail("write-close-race-" + index, "open: " + failure.toString());
        break;
      }
      final boolean[] ready = {false, false};
      final boolean[] start = {false};
      final boolean[] finished = {false, false};
      final String[] result = {"pending", "pending"};
      Thread writer = new Thread(new Runnable() {
        @Override
        public void run() {
          synchronized (gate) {
            ready[0] = true;
          }
          awaitStart(gate, start);
          result[0] = "write-entered";
          try {
            result[0] += "; wrote=" + file.writeBytes(payload, 0, payload.length);
          } catch (Throwable failure) {
            result[0] = "write-exception=" + failure.toString();
          }
          synchronized (gate) {
            finished[0] = true;
          }
        }
      });
      Thread closer = new Thread(new Runnable() {
        @Override
        public void run() {
          synchronized (gate) {
            ready[1] = true;
          }
          awaitStart(gate, start);
          result[1] = "close-entered";
          try {
            file.close();
            result[1] += "; closed";
          } catch (Throwable failure) {
            result[1] = "close-exception=" + failure.toString();
          }
          synchronized (gate) {
            finished[1] = true;
          }
        }
      });
      writer.start();
      closer.start();
      if (!awaitReady(gate, ready)) {
        fail("write-close-race-" + index, "barrier-ready timeout");
        break;
      }
      synchronized (gate) {
        start[0] = true;
      }
      if (!awaitFinished(gate, finished)) {
        fail("write-close-race-" + index, "barrier-finish timeout");
        break;
      }
      completed++;
      pass("write-close-race-" + index, result[0] + "; " + result[1]);
    }
    if (completed != 10) {
      fail("write-close-race", "completed " + completed + " of 10 bounded barrier runs");
    } else {
      pass("write-close-race", "completed 10 barrier-released write/close races");
    }
  }

  private static void awaitStart(totalcross.util.concurrent.Lock gate, boolean[] start) {
    for (int i = 0; i < 10000; i++) {
      synchronized (gate) {
        if (start[0]) {
          return;
        }
      }
      Vm.safeSleep(1);
    }
  }

  private static boolean awaitReady(totalcross.util.concurrent.Lock gate, boolean[] ready) {
    for (int i = 0; i < 10000; i++) {
      synchronized (gate) {
        if (ready[0] && ready[1]) {
          return true;
        }
      }
      Vm.safeSleep(1);
    }
    return false;
  }

  private static boolean awaitFinished(totalcross.util.concurrent.Lock gate, boolean[] finished) {
    for (int i = 0; i < 10000; i++) {
      synchronized (gate) {
        if (finished[0] && finished[1]) {
          return true;
        }
      }
      Vm.safeSleep(1);
    }
    return false;
  }

  private static String path(String name) {
    return Convert.appendPath(Settings.appPath, name);
  }

  private static boolean equal(byte[] left, byte[] right) {
    if (left.length != right.length) {
      return false;
    }
    for (int i = 0; i < left.length; i++) {
      if (left[i] != right[i]) {
        return false;
      }
    }
    return true;
  }

  private static void pass(String name, String detail) {
    Vm.debug("TC_I04 case=" + name + " state=PASS detail=" + detail);
  }

  private static void fail(String name, String detail) {
    failures++;
    Vm.debug("TC_I04 case=" + name + " state=FAIL detail=" + detail);
  }
}
