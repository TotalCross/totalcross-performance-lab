// SPDX-License-Identifier: MIT

package totalcross.ui.image;

import totalcross.ui.Container;
import totalcross.ui.ImageControl;
import totalcross.ui.MainWindow;
import totalcross.ui.gfx.Color;
import totalcross.ui.gfx.Graphics;

/** Small native-runtime ownership, cache, and draw-pixel acceptance probe. */
public final class ImageOwnershipLifecycleProbe extends MainWindow {
  private static final int SCREEN_CYCLES = 64;
  private static final byte[] RED_PNG = {
      (byte) 0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A,
      0x00, 0x00, 0x00, 0x0D, 0x49, 0x48, 0x44, 0x52,
      0x00, 0x00, 0x00, 0x02, 0x00, 0x00, 0x00, 0x02,
      0x08, 0x06, 0x00, 0x00, 0x00, 0x72, (byte) 0xB6, 0x0D,
      0x24, 0x00, 0x00, 0x00, 0x11, 0x49, 0x44, 0x41,
      0x54, 0x78, (byte) 0x9C, 0x63, (byte) 0xF8, (byte) 0xCF,
      (byte) 0xC0, (byte) 0xF0, 0x1F, (byte) 0x84, 0x19, 0x60,
      0x0C, 0x00, 0x47, (byte) 0xCA, 0x07, (byte) 0xF9,
      0x67, 0x59, 0x6E, (byte) 0xB7, 0x00, 0x00, 0x00,
      0x00, 0x49, 0x45, 0x4E, 0x44, (byte) 0xAE, 0x42,
      0x60, (byte) 0x82
  };

  @Override
  public void initUI() {
    try {
      runOwnershipSmoke();
      System.out.println("TC_IMAGE_OWNERSHIP_JSON {\"status\":\"PASS\",\"screenCycles\":"
          + SCREEN_CYCLES + ",\"maxSharedOwners\":2,\"ownersAfterDetach\":0,"
          + "\"cacheReusedWhileOwned\":true,\"cacheEvictedAfterDetach\":true,"
          + "\"drawPixelRgb\":16711680}");
      System.out.flush();
      MainWindow.exit(0);
    } catch (Throwable failure) {
      System.err.println("TC_IMAGE_OWNERSHIP_FAIL " + failure.getClass().getName() + ": "
          + failure.getMessage());
      failure.printStackTrace();
      System.err.flush();
      System.out.flush();
      MainWindow.exit(1);
    }
  }

  private void runOwnershipSmoke() throws Exception {
    Image image = new Image(RED_PNG);
    ImagePipeline pipeline = image.pipelineForSmoke();
    Image destination = new Image(2, 2);

    for (int cycle = 0; cycle < SCREEN_CYCLES; cycle++) {
      Container screen = new Container();
      ImageControl first = new ImageControl(image);
      ImageControl second = new ImageControl(image);
      first.setRect(0, 0, 2, 2);
      second.setRect(2, 0, 2, 2);
      screen.add(first);
      screen.add(second);
      add(screen);

      require(ImageDrawingBridge.persistentOwnerCount(image) == 2,
          "both shared controls must register after screen attachment");
      require(pipeline.persistentDrawingOwnerCountForSmoke() == 2,
          "pipeline owner count must match attached controls");

      Image firstRaster = ImageDrawingBridge.resolveForDrawing(image, 1,
          ImageDrawingBridge.AdmissionMode.IMMEDIATE);
      Image cachedRaster = image.cachedFinalRasterForDrawing(1);
      require(cachedRaster != null && cachedRaster == firstRaster,
          "persistent draw must admit and expose the materialized raster");
      Image secondRaster = ImageDrawingBridge.resolveForDrawing(image, 1,
          ImageDrawingBridge.AdmissionMode.IMMEDIATE);
      require(secondRaster == cachedRaster,
          "repeated resolution must reuse the admitted raster");
      require(pipeline.cachedVariantCountForSmoke() == 1,
          "one materialized variant must remain while owners are attached");

      Graphics destinationGraphics = destination.getGraphics();
      ImageDrawingBridge.drawPersistentImage(destinationGraphics, image, 0, 0, true);
      require(destinationGraphics.getPixel(0, 0) == Color.RED,
          "native drawing must preserve the source red pixel");

      remove(first);
      require(ImageDrawingBridge.persistentOwnerCount(image) == 1,
          "removing one shared control must retain the remaining owner");
      require(image.cachedFinalRasterForDrawing(1) == cachedRaster,
          "the cached raster must survive while one owner remains");

      remove(screen);
      screen.removeAll();
      require(ImageDrawingBridge.persistentOwnerCount(image) == 0,
          "removing a screen root must release descendants without GC");
      require(pipeline.persistentDrawingOwnerCountForSmoke() == 0,
          "pipeline owner count must reach zero immediately after detach");
      require(pipeline.cachedVariantCountForSmoke() == 0,
          "the final owner detach must evict the cached raster");
      require(image.cachedFinalRasterForDrawing(1) == null,
          "the draw cache must be empty after the last owner detaches");
    }

    require(ImageDrawingBridge.persistentOwnerCount(image) == 0,
        "screen reconstruction must not accumulate stale owners");
  }

  private static void require(boolean condition, String message) {
    if (!condition) {
      throw new IllegalStateException(message);
    }
  }
}
