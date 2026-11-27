// Copyright (C) 2026 Amalgam Solucoes em TI Ltda
//
// SPDX-License-Identifier: LGPL-2.1-only

package totalcross.ui.image;

import totalcross.io.File;
import totalcross.io.IOException;
import totalcross.sys.Convert;
import totalcross.sys.Settings;
import totalcross.sys.Vm;
import totalcross.ui.ImageControl;
import totalcross.ui.MainWindow;

/** Functional checks for TCZ-first Image(String) loading and filesystem fallback. */
public final class ImageStringFallbackProbe extends MainWindow {
  private interface Probe {
    String run() throws Throwable;
  }

  private static int cases;
  private static int failures;
  private static int skips;

  @Override
  public void initUI() {
    runSuccess("prepare-filesystem-fixtures", this::prepareFilesystemFixtures);
    runSuccess("relative-path-filesystem-only",
        () -> checkImage("filesystem-only.jpg", 36, 36));
    runSuccess("tcz-only", () -> checkImage("tcz-only.jpg", 2, 2));
    runSuccess("both-tcz-precedence", () -> checkImage("precedence.jpg", 2, 2));
    runReject("malformed-tcz-does-not-fallback", () -> checkImage("malformed.jpg", 36, 36));
    runReject("empty-tcz-does-not-fallback", () -> checkImage("empty-tcz.jpg", 36, 36));
    runReject("missing-filesystem", () -> checkImage("missing.jpg", 36, 36));
    runReject("invalid-filesystem", () -> checkImage("invalid.jpg", 36, 36));
    runReject("empty-filesystem", () -> checkImage("empty-file.jpg", 36, 36));
    runSuccess("absolute-path", () -> checkImage(appPath("absolute.jpg"), 36, 36));
    runOptional("device-path-where-supported", this::checkDevicePath);
    runSuccess("path-boundary-255", () -> checkImage(repeat('x', 255), 2, 2));
    runReject("path-boundary-256-does-not-use-tcz",
        () -> checkImage(repeat('x', 256), 2, 2));
    runSuccess("image-file-parity", this::checkImageFileParity);
    runSuccess("snapshot-after-modification", this::checkSnapshotAfterModification);
    runSuccess("native-ownership", this::checkNativeOwnership);

    String status = failures == 0 ? "PASS" : "FAIL";
    String result = "TC_I07_RESULT {\"status\":\"" + status + "\",\"cases\":"
        + cases + ",\"failures\":" + failures + ",\"skips\":" + skips + "}";
    System.out.println(result);
    Vm.debug(result);
    System.out.flush();
    MainWindow.exit(failures == 0 ? 0 : 1);
  }

  private String prepareFilesystemFixtures() throws Throwable {
    writeFile("filesystem-only.jpg", ImageStringFallbackFixtures.LARGE_JPEG);
    writeFile("precedence.jpg", ImageStringFallbackFixtures.LARGE_JPEG);
    writeFile("malformed.jpg", ImageStringFallbackFixtures.LARGE_JPEG);
    writeFile("empty-tcz.jpg", ImageStringFallbackFixtures.LARGE_JPEG);
    writeFile("invalid.jpg", ImageStringFallbackFixtures.INVALID_BYTES);
    writeFile("empty-file.jpg", ImageStringFallbackFixtures.EMPTY_BYTES);
    writeFile("absolute.jpg", ImageStringFallbackFixtures.LARGE_JPEG);
    return "wrote valid, malformed, and empty filesystem controls";
  }

  private static void runSuccess(String name, Probe probe) {
    try {
      String details = probe.run();
      record(name, true, details);
    } catch (Throwable failure) {
      record(name, false, describe(failure));
    }
  }

  private static void runReject(String name, Probe probe) {
    try {
      String details = probe.run();
      record(name, false, "unexpectedly loaded: " + details);
    } catch (ImageException | IOException expected) {
      record(name, true, describe(expected));
    } catch (Throwable expected) {
      record(name, false, "unexpected rejection: " + describe(expected));
    }
  }

  private static void runOptional(String name, Probe probe) {
    try {
      String details = probe.run();
      if (details.startsWith("SKIP:")) {
        recordStatus(name, "SKIP", details.substring("SKIP:".length()).trim());
      } else {
        record(name, true, details);
      }
    } catch (Throwable failure) {
      record(name, false, describe(failure));
    }
  }

  private static void record(String name, boolean passed, String details) {
    recordStatus(name, passed ? "PASS" : "FAIL", details);
  }

  private static void recordStatus(String name, String status, String details) {
    cases++;
    if ("FAIL".equals(status)) {
      failures++;
    } else if ("SKIP".equals(status)) {
      skips++;
    }
    System.out.println("TC_I07 case=" + name + " status=" + status
        + " details=" + details.replace('\n', ' '));
  }

  private static String checkImage(String path, int expectedWidth, int expectedHeight)
      throws Throwable {
    Image image = new Image(path);
    return checkDecodedImage(image, expectedWidth, expectedHeight);
  }

  private static String checkDecodedImage(Image image, int expectedWidth, int expectedHeight)
      throws Throwable {
    int width = image.getPixelWidth();
    int height = image.getPixelHeight();
    int[] pixels = image.getPixels();
    if (width != expectedWidth || height != expectedHeight
        || pixels.length != expectedWidth * expectedHeight) {
      throw new AssertionError("expected=" + expectedWidth + "x" + expectedHeight
          + " observed=" + width + "x" + height + " pixels=" + pixels.length);
    }
    return "dimensions=" + width + "x" + height + ",pixels=" + pixels.length;
  }

  private String checkImageFileParity() throws Throwable {
    Image fromPath = new Image("filesystem-only.jpg");
    File file = new File(appPath("filesystem-only.jpg"), File.READ_ONLY);
    Image fromFile;
    try {
      fromFile = new Image(file);
    } finally {
      file.close();
    }
    int[] pathPixels = fromPath.getPixels();
    int[] filePixels = fromFile.getPixels();
    if (fromPath.getPixelWidth() != fromFile.getPixelWidth()
        || fromPath.getPixelHeight() != fromFile.getPixelHeight()
        || pathPixels.length != filePixels.length) {
      throw new AssertionError("Image(String) and Image(File) dimensions differ");
    }
    for (int i = 0; i < pathPixels.length; i++) {
      if (pathPixels[i] != filePixels[i]) {
        throw new AssertionError("Image(String) and Image(File) pixels differ at " + i);
      }
    }
    return "pixels=" + pathPixels.length;
  }

  private String checkSnapshotAfterModification() throws Throwable {
    writeFile("snapshot.jpg", ImageStringFallbackFixtures.SMALL_JPEG);
    Image snapshot = new Image("snapshot.jpg");
    writeFile("snapshot.jpg", ImageStringFallbackFixtures.LARGE_JPEG);
    return checkDecodedImage(snapshot, 2, 2);
  }

  private String checkDevicePath() throws Throwable {
    String path = "device/runtime-image-string-fallback-device.jpg";
    try {
      writeDeviceFile(path, ImageStringFallbackFixtures.LARGE_JPEG);
    } catch (Throwable unsupported) {
      return "SKIP: device filesystem unavailable: " + describe(unsupported);
    }
    try {
      return checkImage(path, 36, 36);
    } finally {
      try (File file = new File(path)) {
        if (file.exists()) {
          file.delete();
        }
      } catch (Throwable ignored) {
        // Cleanup must not hide the path-loading assertion result.
      }
    }
  }

  private String checkNativeOwnership() throws Throwable {
    Image image = new Image("tcz-only.jpg");
    ImageControl control = new ImageControl(image);
    add(control);
    int attached = ImageDrawingBridge.persistentOwnerCount(image);
    remove(control);
    int detached = ImageDrawingBridge.persistentOwnerCount(image);
    if (attached != 1 || detached != 0) {
      throw new AssertionError("owners attached=" + attached + " detached=" + detached);
    }
    return "owners attached=1 detached=0";
  }

  private static void writeFile(String name, byte[] bytes) throws Throwable {
    File file = new File(appPath(name), File.CREATE_EMPTY);
    try {
      file.writeBytes(bytes, 0, bytes.length);
    } finally {
      file.close();
    }
  }

  private static void writeDeviceFile(String name, byte[] bytes) throws Throwable {
    try (File file = new File(name, File.CREATE_EMPTY)) {
      file.writeBytes(bytes, 0, bytes.length);
    }
  }

  private static String appPath(String relative) {
    return Convert.appendPath(Settings.appPath, relative);
  }

  private static String repeat(char value, int length) {
    StringBuilder result = new StringBuilder(length);
    for (int i = 0; i < length; i++) {
      result.append(value);
    }
    return result.toString();
  }

  private static String describe(Throwable failure) {
    return failure.getClass().getName() + ":" + String.valueOf(failure.getMessage());
  }

}
