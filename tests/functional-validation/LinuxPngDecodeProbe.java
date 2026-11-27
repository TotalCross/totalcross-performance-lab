package totalcross.lab.functional;

import totalcross.io.File;
import totalcross.sys.Convert;
import totalcross.sys.Settings;
import totalcross.ui.MainWindow;
import totalcross.ui.image.Image;

/** Functional PNG/JPEG probe. Constructor and pixel-decode results are separate. */
public final class LinuxPngDecodeProbe extends MainWindow {
  private interface ImageLoader {
    Image load() throws Throwable;
  }

  @Override
  public void initUI() {
    String root = Settings.appPath;
    probe("png-file", () -> imageFromFile(root, "comparison-png.png"), 36, 36);
    probe("png-bytes", () -> new Image(readFile(root, "comparison-png.png")), 36, 36);
    probe("tcz-png", () -> new Image("fixtures/tcz-png.png"), 2, 2);
    probe("alpha-png", () -> imageFromFile(root, "alpha.png"), 2, 2);
    probe("indexed-png", () -> imageFromFile(root, "indexed.png"), 2, 2);
    probe("jpeg-file", () -> imageFromFile(root, "comparison-control.jpg"), 512, 512);
    probe("jpeg-bytes", () -> new Image(readFile(root, "comparison-control.jpg")), 512, 512);
    probe("invalid-file", () -> imageFromFile(root, "invalid.bin"), -1, -1);
    probe("invalid-bytes", () -> new Image(readFile(root, "invalid.bin")), -1, -1);
    System.out.println("TC_PNG_RESULT complete=true");
    System.out.flush();
    MainWindow.exit(0);
  }

  private static Image imageFromFile(String root, String name) throws Throwable {
    File file = new File(Convert.appendPath(root, name), File.READ_ONLY);
    try {
      return new Image(file);
    } finally {
      file.close();
    }
  }

  private static byte[] readFile(String root, String name) throws Throwable {
    return new File(Convert.appendPath(root, name), File.READ_ONLY).readAndClose();
  }

  private static void probe(String name, ImageLoader loader, int expectedWidth, int expectedHeight) {
    boolean constructed = false;
    boolean decoded = false;
    int width = -1;
    int height = -1;
    int pixelCount = -1;
    String firstPixel = "none";
    String exception = "none";
    try {
      Image image = loader.load();
      constructed = true;
      width = image.getWidth();
      height = image.getHeight();
      int[] pixels = image.getPixels();
      pixelCount = pixels.length;
      if (pixels.length > 0) {
        firstPixel = Integer.toHexString(pixels[0]);
      }
      boolean contentValid = pixels.length > 0;
      if ("alpha-png".equals(name) || "tcz-png".equals(name)) {
        int alpha = pixels[0] >>> 24;
        contentValid = alpha > 0 && alpha < 255;
      } else if ("indexed-png".equals(name)) {
        contentValid = pixels.length == 4 && pixels[0] != pixels[1]
            && pixels[2] != pixels[3];
      }
      decoded = width == expectedWidth && height == expectedHeight
          && pixelCount == expectedWidth * expectedHeight && contentValid;
      if (!decoded) {
        exception = "dimension-or-pixel-count-mismatch";
      }
    } catch (Throwable failure) {
      exception = (failure.getClass().getName() + ":" + String.valueOf(failure.getMessage()))
          .replace('\n', ' ');
    }
    System.out.println("TC_PNG case=" + name + ",construct=" + constructed
        + ",decode=" + decoded + ",width=" + width + ",height=" + height
        + ",pixelCount=" + pixelCount + ",pixel0=" + firstPixel
        + ",expectedBehavior=" + (expectedWidth < 0 ? "reject" : "decode")
        + ",exception=" + exception);
  }
}
