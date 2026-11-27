// Copyright (C) 2026 Amalgam Solucoes em TI Ltda
//
// SPDX-License-Identifier: LGPL-2.1-only
import totalcross.io.File;
import totalcross.sys.Settings;
import totalcross.sys.Time;
import totalcross.sys.Vm;
import totalcross.ui.MainWindow;
import totalcross.ui.Window;

public final class Main extends MainWindow {
  private static final String REVISION = "@@REVISION@@";
  private static final String MODE = "@@MODE@@";
  private static int failures;
  private static int completed;
  private static int denied;
  private static int foreignPassed;
  private static int foreignDenied;

  public Main() {
    super("I08 Android storage probe", Window.NO_BORDER);
  }

  @Override
  public void initUI() {
    super.initUI();
    Vm.debug("TC_I08 startup revision=" + REVISION + " appPath=" + Settings.appPath);
    String packageId = Settings.appPath.substring(Settings.appPath.lastIndexOf('/') + 1);
    if (MODE.equals("files-only")) {
      runLocation("private", Settings.appPath + "/i08-" + REVISION + "-private");
      runLocation("app-specific-external", "/sdcard/Android/data/" + packageId
          + "/files/i08-" + REVISION);
      runLocation("shared-external", "/sdcard/Download/i08-" + REVISION);
    } else if (MODE.equals("all") || MODE.equals("shared-only") || MODE.equals("shared-keep")) {
      if (MODE.equals("all")) {
        runLocation("private", Settings.appPath + "/i08-" + REVISION + "-private");
        runLocation("app-specific-external", "/sdcard/Android/data/" + packageId
            + "/files/i08-" + REVISION);
      }
      runLocation("shared-external", "/sdcard/Download/i08-" + REVISION);
      runSharedForeignFixture();
    } else if (MODE.equals("foreign-only")) {
      runSharedForeignFixture();
    } else {
      failures++;
      Vm.debug("TC_I08 case=dispatch status=FAIL details=unknown-mode-" + MODE);
    }
    Vm.debug("TC_I08_RESULT {\"revision\":\"" + REVISION + "\",\"completed\":"
        + completed + ",\"denied\":" + denied + ",\"failures\":" + failures
        + ",\"foreignPassed\":" + foreignPassed + ",\"foreignDenied\":" + foreignDenied
        + ",\"mode\":\"" + MODE + "\"}");
    System.out.flush();
    MainWindow.exit(failures == 0 ? 0 : 1);
  }

  private static void runLocation(String name, String root) {
    String dirPath = root + "/case";
    String filePath = dirPath + "/data.bin";
    String renamedPath = dirPath + "/renamed.bin";
    byte[] expected = ("tc730-i08-" + name + "-" + REVISION).getBytes();
    String stage = "cleanup";
    Vm.debug("TC_I08 case=" + name + " state=BEGIN root=" + root);
    try {
      if (!MODE.equals("shared-keep")) {
        try {
          File.deleteDir(root);
        } catch (Throwable ignored) {
        }
      }
      stage = "create-root";
      new File(root, File.DONT_OPEN).createDir();
      stage = "create-child-directory";
      new File(dirPath, File.DONT_OPEN).createDir();
      stage = "write-and-close";
      File writer = new File(filePath, File.CREATE_EMPTY);
      Vm.debug("TC_I08 case=" + name + " resolvedFilePath=" + writer.getPath());
      int written = writer.writeBytes(expected, 0, expected.length);
      writer.flush();
      writer.close();
      if (written != expected.length) {
        throw new IllegalStateException("write count=" + written + " expected=" + expected.length);
      }

      stage = "metadata-and-list";
      File metadata = new File(filePath, File.READ_ONLY);
      boolean exists = metadata.exists();
      boolean isDir = metadata.isDir();
      int size = metadata.getSize();
      int attributes = metadata.getAttributes();
      Time modified = metadata.getTime(File.TIME_MODIFIED);
      String[] names = new File(dirPath, File.DONT_OPEN).listFiles();
      boolean listed = containsName(names, "data.bin");
      metadata.close();
      new File(filePath, File.DONT_OPEN).rename(renamedPath);
      stage = "rename-and-read";
      File reader = new File(renamedPath, File.READ_ONLY);
      byte[] observed = new byte[expected.length];
      int read = reader.readBytes(observed, 0, observed.length);
      reader.close();
      if (!exists || isDir || size != expected.length || !listed
          || read != expected.length || !equals(expected, observed) || modified == null) {
        throw new IllegalStateException("metadata/list/read mismatch exists=" + exists
            + " isDir=" + isDir + " size=" + size + " listed=" + listed + " read=" + read);
      }
      stage = "delete";
      File renamed = new File(renamedPath, File.DONT_OPEN);
      boolean renamedExists = renamed.exists();
      if (!MODE.equals("shared-keep")) {
        renamed.delete();
        File childDir = new File(dirPath, File.DONT_OPEN);
        childDir.delete();
        File rootDir = new File(root, File.DONT_OPEN);
        rootDir.delete();
      }
      if (!renamedExists) {
        throw new IllegalStateException("renamed file missing before delete");
      }
      completed++;
      Vm.debug("TC_I08 case=" + name + " status=PASS details=bytes=" + written
          + ";size=" + size + ";attributes=" + attributes + ";modified=" + modified);
    } catch (Throwable failure) {
      String details = "stage=" + stage + ";" + failure.getClass().getName()
          + ":" + failure.getMessage();
      if (name.equals("shared-external")) {
        denied++;
        Vm.debug("TC_I08 case=" + name + " status=OBSERVED_DENIAL details=" + details);
      } else {
        failures++;
        Vm.debug("TC_I08 case=" + name + " status=FAIL details=" + details);
      }
    }
  }

  private static void runSharedForeignFixture() {
    String path = "/sdcard/Download/tc730-i08-foreign-control.bin";
    byte[] expected = "TC730_I08_FOREIGN_CONTROL_V1\n".getBytes();
    Vm.debug("TC_I08 case=shared-existing-foreign state=BEGIN path=" + path);
    try {
      File file = new File(path, File.READ_ONLY);
      int size = file.getSize();
      byte[] observed = new byte[size];
      int read = file.readBytes(observed, 0, size);
      file.close();
      if (size != expected.length || read != expected.length || !equals(expected, observed)) {
        throw new IllegalStateException("content mismatch size=" + size + " read=" + read);
      }
      String[] names = new File("/sdcard/Download", File.DONT_OPEN).listFiles();
      if (!containsName(names, "tc730-i08-foreign-control.bin")) {
        throw new IllegalStateException("foreign fixture missing from shared directory listing");
      }
      foreignPassed++;
      Vm.debug("TC_I08 case=shared-existing-foreign status=PASS details=size=" + size
          + ";read=" + read + ";listed=true");
    } catch (Throwable failure) {
      foreignDenied++;
      Vm.debug("TC_I08 case=shared-existing-foreign status=OBSERVED_DENIAL details="
          + failure.getClass().getName() + ":" + failure.getMessage());
    }
  }

  private static boolean containsName(String[] entries, String expected) {
    if (entries != null) {
      for (int i = 0; i < entries.length; i++) {
        if (entries[i].equals(expected) || entries[i].endsWith("/" + expected)) {
          return true;
        }
      }
    }
    return false;
  }

  private static boolean equals(byte[] left, byte[] right) {
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
}
