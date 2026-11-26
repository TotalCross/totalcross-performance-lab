// SPDX-License-Identifier: MIT

package totalcross.ui.image;

import totalcross.io.File;
import totalcross.ui.Container;
import totalcross.ui.ImageControl;
import totalcross.ui.MainWindow;
import totalcross.ui.gfx.Color;
import totalcross.ui.gfx.Graphics;

/** Native acceptance probe for persistent image ownership and drawing. */
public final class ImageOwnershipLifecycleProbe extends MainWindow {
  private static final int SCREEN_CYCLES = 2;
  private static final int CONTROLS_PER_CYCLE = 1510;
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
      runLargeScreenCycles();
      runDetachedSubtreeScenario();
      runActiveReparentScenario();
      runSharedRasterScenario();
      runPipelineReplacementScenario();
      int pixel = runDrawingScenario();
      System.out.println("TC_IMAGE_OWNERSHIP_JSON {\"status\":\"PASS\","
          + "\"screenCycles\":" + SCREEN_CYCLES + ",\"controlsPerCycle\":"
          + CONTROLS_PER_CYCLE + ",\"distinctImagesPerCycle\":" + CONTROLS_PER_CYCLE
          + ",\"ownersAfterDetach\":0,\"directParentsPreserved\":true,"
          + "\"mutationsWhileDetached\":true,\"ownersRestoredAfterReattach\":true,"
          + "\"activeReparentOwnerCount\":1,\"activeReparentCachePreserved\":true,"
          + "\"maxSharedOwners\":3,\"rasterRetainedUntilFinalOwner\":true,"
          + "\"pipelineReplacementOwners\":3,\"cacheReusedWhileOwned\":true,"
          + "\"cacheEvictedAfterDetach\":true,\"drawPixelRgb\":" + pixel
          + ",\"png\":\"image-ownership-render.png\"}");
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

  private void runLargeScreenCycles() throws Exception {
    for (int cycle = 0; cycle < SCREEN_CYCLES; cycle++) {
      Container screen = new Container();
      Image[] images = new Image[CONTROLS_PER_CYCLE];
      ImagePipeline[] pipelines = new ImagePipeline[CONTROLS_PER_CYCLE];
      ImageControl[] controls = new ImageControl[CONTROLS_PER_CYCLE];
      for (int i = 0; i < CONTROLS_PER_CYCLE; i++) {
        Image image = new Image(RED_PNG);
        images[i] = image;
        pipelines[i] = image.pipelineForSmoke();
        controls[i] = new ImageControl(image);
        controls[i].setRect((i % 37) * 2, ((i / 37) % 37) * 2, 2, 2);
        screen.add(controls[i]);
        if (i > 0) {
          require(images[i] != images[i - 1],
              "each consecutive screen control must own a distinct Image instance");
        }
      }
      add(screen);
      for (int i = 0; i < CONTROLS_PER_CYCLE; i++) {
        require(ImageDrawingBridge.persistentOwnerCount(images[i]) == 1,
            "each attached control must register its distinct image exactly once");
        require(pipelines[i].persistentDrawingOwnerCountForSmoke() == 1,
            "each attached image pipeline must have exactly one persistent owner");
      }

      remove(screen);
      require(controls[0].getParent() == screen,
          "detaching the screen must preserve the control's direct parent");
      for (int i = 0; i < CONTROLS_PER_CYCLE; i++) {
        require(ImageDrawingBridge.persistentOwnerCount(images[i]) == 0,
            "screen detachment must release every owner immediately without GC");
        require(pipelines[i].persistentDrawingOwnerCountForSmoke() == 0,
            "detached image pipelines must have no persistent owners");
      }
      screen.removeAll();
    }
  }

  private void runDetachedSubtreeScenario() throws Exception {
    Image original = new Image(RED_PNG);
    Image replacement = new Image(RED_PNG);
    Image addedImage = new Image(RED_PNG);
    ImagePipeline originalPipeline = original.pipelineForSmoke();
    ImagePipeline replacementPipeline = replacement.pipelineForSmoke();
    ImagePipeline addedPipeline = addedImage.pipelineForSmoke();
    Container root = new Container();
    Container nested = new Container();
    ImageControl existing = new ImageControl(original);
    nested.add(existing);
    root.add(nested);
    add(root);
    require(originalPipeline.persistentDrawingOwnerCountForSmoke() == 1,
        "attached nested control must own its original image");

    remove(root);
    require(existing.getParent() == nested && nested.getParent() == root,
        "removing an ancestor must preserve descendants' direct parent relationships");
    require(originalPipeline.persistentDrawingOwnerCountForSmoke() == 0,
        "removing an ancestor must release descendant image ownership immediately");
    existing.setImage(replacement);
    ImageControl addedWhileDetached = new ImageControl(addedImage);
    nested.add(addedWhileDetached);
    require(originalPipeline.persistentDrawingOwnerCountForSmoke() == 0
        && replacementPipeline.persistentDrawingOwnerCountForSmoke() == 0
        && addedPipeline.persistentDrawingOwnerCountForSmoke() == 0,
        "setImage and child addition while detached must not register owners");

    add(root);
    require(originalPipeline.persistentDrawingOwnerCountForSmoke() == 0
        && replacementPipeline.persistentDrawingOwnerCountForSmoke() == 1
        && addedPipeline.persistentDrawingOwnerCountForSmoke() == 1,
        "reattaching the subtree must restore its current distinct image owners");
    remove(root);
    require(replacementPipeline.persistentDrawingOwnerCountForSmoke() == 0
        && addedPipeline.persistentDrawingOwnerCountForSmoke() == 0,
        "detaching the reattached subtree must release all restored owners");
    root.removeAll();
    nested.removeAll();
  }

  private void runActiveReparentScenario() throws Exception {
    Image image = new Image(RED_PNG);
    ImagePipeline pipeline = image.pipelineForSmoke();
    ImageControl control = new ImageControl(image);
    Container first = new Container();
    Container second = new Container();
    add(first);
    add(second);
    first.add(control);
    Image cached = ImageDrawingBridge.resolveForDrawing(image, 1,
        ImageDrawingBridge.AdmissionMode.IMMEDIATE);
    second.add(control);
    require(control.getParent() == second,
        "active-to-active reparenting must move the control to its new container");
    require(pipeline.persistentDrawingOwnerCountForSmoke() == 1,
        "active-to-active reparenting must preserve one owner");
    require(image.cachedFinalRasterForDrawing(1) == cached,
        "active-to-active reparenting must keep the admitted raster");
    remove(second);
    remove(first);
    require(pipeline.persistentDrawingOwnerCountForSmoke() == 0,
        "removing both active containers must release the reparented owner");
    first.removeAll();
    second.removeAll();
  }

  private void runSharedRasterScenario() throws Exception {
    Image image = new Image(RED_PNG);
    ImagePipeline pipeline = image.pipelineForSmoke();
    Container screen = new Container();
    ImageControl first = new ImageControl(image);
    ImageControl second = new ImageControl(image);
    ImageControl third = new ImageControl(image);
    screen.add(first);
    screen.add(second);
    screen.add(third);
    add(screen);
    require(pipeline.persistentDrawingOwnerCountForSmoke() == 3,
        "three controls sharing an image must register three owners");
    Image cached = ImageDrawingBridge.resolveForDrawing(image, 1,
        ImageDrawingBridge.AdmissionMode.IMMEDIATE);

    screen.remove(first);
    require(pipeline.persistentDrawingOwnerCountForSmoke() == 2
        && image.cachedFinalRasterForDrawing(1) == cached,
        "the raster must remain while two shared owners survive");
    screen.remove(second);
    require(pipeline.persistentDrawingOwnerCountForSmoke() == 1
        && image.cachedFinalRasterForDrawing(1) == cached,
        "the raster must remain while the final shared owner survives");
    screen.remove(third);
    require(pipeline.persistentDrawingOwnerCountForSmoke() == 0
        && pipeline.cachedVariantCountForSmoke() == 0
        && image.cachedFinalRasterForDrawing(1) == null,
        "the final owner release must evict the admitted raster");
    remove(screen);
    screen.removeAll();
  }

  private void runPipelineReplacementScenario() throws Exception {
    Image image = new Image(RED_PNG);
    ImagePipeline previous = image.pipelineForSmoke();
    Container screen = new Container();
    screen.add(new ImageControl(image));
    screen.add(new ImageControl(image));
    screen.add(new ImageControl(image));
    add(screen);
    require(previous.persistentDrawingOwnerCountForSmoke() == 3,
        "the original pipeline must begin with three attached owners");
    image.applyFade(120);
    ImagePipeline replacement = image.pipelineForSmoke();
    require(replacement != previous
        && previous.persistentDrawingOwnerCountForSmoke() == 0
        && replacement.persistentDrawingOwnerCountForSmoke() == 3,
        "replacing an image pipeline must transfer all three owners exactly once");
    remove(screen);
    require(replacement.persistentDrawingOwnerCountForSmoke() == 0,
        "detaching after pipeline replacement must release all transferred owners");
    screen.removeAll();
  }

  private int runDrawingScenario() throws Exception {
    Image image = new Image(RED_PNG);
    Container screen = new Container();
    screen.add(new ImageControl(image));
    add(screen);
    Image firstRaster = ImageDrawingBridge.resolveForDrawing(image, 1,
        ImageDrawingBridge.AdmissionMode.IMMEDIATE);
    Image secondRaster = ImageDrawingBridge.resolveForDrawing(image, 1,
        ImageDrawingBridge.AdmissionMode.IMMEDIATE);
    Image cachedRaster = image.cachedFinalRasterForDrawing(1);
    require(firstRaster == secondRaster && cachedRaster == firstRaster,
        "repeated draw resolution must reuse the same admitted raster");

    Image destination = new Image(4, 4);
    Graphics graphics = destination.getGraphics();
    ImageDrawingBridge.drawPersistentImage(graphics, image, 0, 0, true);
    ImageDrawingBridge.drawPersistentImage(graphics, image, 0, 0, true);
    int pixel = graphics.getPixel(0, 0);
    require(pixel == Color.RED, "native repeated drawing must preserve the red pixel");
    File output = new File("image-ownership-render.png", File.CREATE_EMPTY);
    destination.createPng(output);
    output.close();
    remove(screen);
    require(ImageDrawingBridge.persistentOwnerCount(image) == 0,
        "drawing fixture cleanup must release its image owner");
    screen.removeAll();
    return pixel & 0xFFFFFF;
  }

  private static void require(boolean condition, String message) {
    if (!condition) {
      throw new IllegalStateException(message);
    }
  }
}
