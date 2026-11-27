// SPDX-License-Identifier: MIT

package totalcross.ui.image;

import totalcross.io.File;
import totalcross.sys.Settings;
import totalcross.sys.Vm;
import totalcross.ui.Container;
import totalcross.ui.ImageControl;
import totalcross.ui.MainWindow;
import totalcross.ui.gfx.Color;
import totalcross.ui.gfx.Graphics;

/** Native acceptance probe for persistent image ownership and drawing. */
public final class ImageOwnershipLifecycleProbe extends MainWindow {
  private static final int SCREEN_CYCLES = 2;
  private static final int CONTROLS_PER_CYCLE = 1510;
  private static boolean baselineObservation;
  private static int ownershipMismatches;
  private static String currentStage = "startup";
  private static String IMAGE_FIXTURE_FORMAT = "png";
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
    IMAGE_FIXTURE_FORMAT = imageFixtureFormat();
    baselineObservation = isBaselineObservation();
    markStage("stage-1-mainwindow-entered");
    Vm.debug("TC_IMAGE_OWNERSHIP_START cycles=" + SCREEN_CYCLES + " controlsPerCycle="
        + CONTROLS_PER_CYCLE);
    try {
      currentStage = "stage-1-mainwindow";
      markStage("stage-1-mainwindow-complete");
      currentStage = "stage-2-single-control";
      markStage("stage-2-single-control-entered");
      runSingleControlScenario();
      markStage("stage-2-single-control-complete");
      currentStage = "stage-3-native-drawing";
      markStage("stage-3-native-drawing-entered");
      int pixel = runDrawingScenario();
      markStage("stage-3-native-drawing-complete");
      currentStage = "stage-4-container-hierarchy";
      markStage("stage-4-container-hierarchy-entered");
      runDetachedSubtreeScenario();
      markStage("stage-4-container-hierarchy-complete");
      currentStage = "stage-5-ancestor-detach";
      markStage("stage-5-ancestor-detach-complete");
      currentStage = "stage-6-shared-and-replacement";
      markStage("stage-6-shared-and-replacement-entered");
      runActiveReparentScenario();
      runSharedRasterScenario();
      runPipelineReplacementScenario();
      markStage("stage-6-shared-and-replacement-complete");
      currentStage = "stage-7-large-screen";
      markStage("stage-7-large-screen-entered");
      runLargeScreenCycles();
      markStage("stage-7-large-screen-complete");
      String status = baselineObservation ? "BASELINE_OBSERVED" : "PASS";
      String result = "TC_IMAGE_OWNERSHIP_JSON {\"status\":\"" + status + "\","
          + "\"diagnosticMode\":\"" + (baselineObservation ? "baseline" : "fixed")
          + "\",\"imageFixtureFormat\":\"" + IMAGE_FIXTURE_FORMAT + "\""
          + ",\"screenCycles\":" + SCREEN_CYCLES + ",\"controlsPerCycle\":"
          + CONTROLS_PER_CYCLE + ",\"distinctImagesPerCycle\":" + CONTROLS_PER_CYCLE
          + ",\"ownershipMismatches\":" + ownershipMismatches
          + ",\"highestCompletedStage\":7,\"drawPixelRgb\":" + pixel
          + ",\"png\":\"image-ownership-render.png\""
          + (baselineObservation ? "" : fixedOwnershipMetrics()) + "}";
      System.out.println(result);
      Vm.debug(result);
      writeDiagnosticFile("tcdiag-result.txt",
          result.substring("TC_IMAGE_OWNERSHIP_JSON ".length()));
      System.out.flush();
      MainWindow.exit(0);
    } catch (Throwable failure) {
      markStage("failure-" + currentStage);
      String failureRecord = "TC_IMAGE_OWNERSHIP_FAIL " + failure.getClass().getName() + ": "
          + currentStage + ": " + failure.getMessage();
      writeDiagnosticFile("tcdiag-failure.txt", failureRecord);
      System.err.println(failureRecord);
      Vm.debug(failureRecord);
      failure.printStackTrace();
      System.err.flush();
      System.out.flush();
      MainWindow.exit(1);
    }
  }

  private static boolean isBaselineObservation() {
    Object mode = Settings.appProps == null ? null : Settings.appProps.get("diagnostic.mode");
    return "baseline".equals(mode);
  }

  private static String imageFixtureFormat() {
    Object format = Settings.appProps == null ? null : Settings.appProps.get("diagnostic.imageFormat");
    return "jpeg".equals(format) ? "jpeg" : "png";
  }

  private static Image newFixtureImage() throws Exception {
    return "jpeg".equals(IMAGE_FIXTURE_FORMAT)
        ? new Image(ImageOwnershipJpegFixture.RED_JPEG) : new Image(RED_PNG);
  }

  private static String fixedOwnershipMetrics() {
    return ",\"ownersAfterDetach\":0,\"directParentsPreserved\":true,"
        + "\"mutationsWhileDetached\":true,\"ownersRestoredAfterReattach\":true,"
        + "\"activeReparentOwnerCount\":1,\"activeReparentCachePreserved\":true,"
        + "\"maxSharedOwners\":3,\"rasterRetainedUntilFinalOwner\":true,"
        + "\"pipelineReplacementOwners\":3,\"cacheReusedWhileOwned\":true,"
        + "\"cacheEvictedAfterDetach\":true";
  }

  private static void markStage(String stage) {
    String marker = "TC_IMAGE_OWNERSHIP_STAGE " + stage;
    Vm.debug(marker);
    System.out.println(marker);
    try {
      writeDiagnosticFile("tcdiag-" + stage + ".marker", stage);
    } catch (Throwable ignored) {
      // Vm.debug and stdout still identify the stage when the marker path is unavailable.
    }
  }

  private static void writeDiagnosticFile(String filename, String contents) {
    File output = null;
    try {
      output = new File(Settings.appPath + filename, File.CREATE_EMPTY);
      byte[] bytes = contents.getBytes();
      output.writeBytes(bytes, 0, bytes.length);
    } catch (Throwable ignored) {
      // The native diagnostic stream remains available as a second marker path.
    } finally {
      if (output != null) {
        try {
          output.close();
        } catch (Throwable ignored) {
          // The marker file is best-effort; this probe must keep its test path simple.
        }
      }
    }
  }

  private static void recordOwnershipMismatch(String message) {
    ownershipMismatches++;
    String detail = "TC_IMAGE_OWNERSHIP_BASELINE_MISMATCH " + currentStage + ": " + message;
    Vm.debug(detail);
    System.out.println(detail);
    try {
      File output = new File(Settings.appPath + "tcdiag-mismatch-" + ownershipMismatches
          + ".txt", File.CREATE_EMPTY);
      byte[] bytes = detail.getBytes();
      output.writeBytes(bytes, 0, bytes.length);
      output.close();
    } catch (Throwable ignored) {
      // The mismatch remains visible in the native diagnostic stream.
    }
  }

  private static void requireOwnership(boolean condition, String message) {
    if (condition) {
      return;
    }
    if (baselineObservation) {
      recordOwnershipMismatch(message);
    } else {
      require(false, message);
    }
  }

  private void runSingleControlScenario() throws Exception {
    Image image = newFixtureImage();
    ImageControl control = new ImageControl(image);
    add(control);
    requireOwnership(ImageDrawingBridge.persistentOwnerCount(image) == 1,
        "one attached control must own its image");
    remove(control);
    requireOwnership(ImageDrawingBridge.persistentOwnerCount(image) == 0,
        "removing the one-control fixture must release its image");
  }

  private void runLargeScreenCycles() throws Exception {
    for (int cycle = 0; cycle < SCREEN_CYCLES; cycle++) {
      Container screen = new Container();
      Image[] images = new Image[CONTROLS_PER_CYCLE];
      ImagePipeline[] pipelines = new ImagePipeline[CONTROLS_PER_CYCLE];
      ImageControl[] controls = new ImageControl[CONTROLS_PER_CYCLE];
      for (int i = 0; i < CONTROLS_PER_CYCLE; i++) {
        Image image = newFixtureImage();
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
        requireOwnership(ImageDrawingBridge.persistentOwnerCount(images[i]) == 1,
            "each attached control must register its distinct image exactly once");
        requireOwnership(pipelines[i].persistentDrawingOwnerCountForSmoke() == 1,
            "each attached image pipeline must have exactly one persistent owner");
      }

      remove(screen);
      require(controls[0].getParent() == screen,
          "detaching the screen must preserve the control's direct parent");
      for (int i = 0; i < CONTROLS_PER_CYCLE; i++) {
        requireOwnership(ImageDrawingBridge.persistentOwnerCount(images[i]) == 0,
            "screen detachment must release every owner immediately without GC");
        requireOwnership(pipelines[i].persistentDrawingOwnerCountForSmoke() == 0,
            "detached image pipelines must have no persistent owners");
      }
      screen.removeAll();
    }
  }

  private void runDetachedSubtreeScenario() throws Exception {
    Image original = newFixtureImage();
    Image replacement = newFixtureImage();
    Image addedImage = newFixtureImage();
    ImagePipeline originalPipeline = original.pipelineForSmoke();
    ImagePipeline replacementPipeline = replacement.pipelineForSmoke();
    ImagePipeline addedPipeline = addedImage.pipelineForSmoke();
    Container root = new Container();
    Container nested = new Container();
    ImageControl existing = new ImageControl(original);
    nested.add(existing);
    root.add(nested);
    add(root);
    markStage("stage-4-container-hierarchy-complete");
    currentStage = "stage-5-ancestor-detach";
    markStage("stage-5-ancestor-detach-entered");
    requireOwnership(originalPipeline.persistentDrawingOwnerCountForSmoke() == 1,
        "attached nested control must own its original image");

    remove(root);
    require(existing.getParent() == nested && nested.getParent() == root,
        "removing an ancestor must preserve descendants' direct parent relationships");
    requireOwnership(originalPipeline.persistentDrawingOwnerCountForSmoke() == 0,
        "removing an ancestor must release descendant image ownership immediately");
    existing.setImage(replacement);
    ImageControl addedWhileDetached = new ImageControl(addedImage);
    nested.add(addedWhileDetached);
    requireOwnership(originalPipeline.persistentDrawingOwnerCountForSmoke() == 0
        && replacementPipeline.persistentDrawingOwnerCountForSmoke() == 0
        && addedPipeline.persistentDrawingOwnerCountForSmoke() == 0,
        "setImage and child addition while detached must not register owners");

    add(root);
    requireOwnership(originalPipeline.persistentDrawingOwnerCountForSmoke() == 0
        && replacementPipeline.persistentDrawingOwnerCountForSmoke() == 1
        && addedPipeline.persistentDrawingOwnerCountForSmoke() == 1,
        "reattaching the subtree must restore its current distinct image owners");
    remove(root);
    requireOwnership(replacementPipeline.persistentDrawingOwnerCountForSmoke() == 0
        && addedPipeline.persistentDrawingOwnerCountForSmoke() == 0,
        "detaching the reattached subtree must release all restored owners");
    markStage("stage-5-ancestor-detach-complete");
    root.removeAll();
    nested.removeAll();
  }

  private void runActiveReparentScenario() throws Exception {
    Image image = newFixtureImage();
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
    requireOwnership(pipeline.persistentDrawingOwnerCountForSmoke() == 1,
        "active-to-active reparenting must preserve one owner");
    requireOwnership(image.cachedFinalRasterForDrawing(1) == cached,
        "active-to-active reparenting must keep the admitted raster");
    remove(second);
    remove(first);
    requireOwnership(pipeline.persistentDrawingOwnerCountForSmoke() == 0,
        "removing both active containers must release the reparented owner");
    first.removeAll();
    second.removeAll();
  }

  private void runSharedRasterScenario() throws Exception {
    Image image = newFixtureImage();
    ImagePipeline pipeline = image.pipelineForSmoke();
    Container screen = new Container();
    ImageControl first = new ImageControl(image);
    ImageControl second = new ImageControl(image);
    ImageControl third = new ImageControl(image);
    screen.add(first);
    screen.add(second);
    screen.add(third);
    add(screen);
    requireOwnership(pipeline.persistentDrawingOwnerCountForSmoke() == 3,
        "three controls sharing an image must register three owners");
    Image cached = ImageDrawingBridge.resolveForDrawing(image, 1,
        ImageDrawingBridge.AdmissionMode.IMMEDIATE);

    screen.remove(first);
    requireOwnership(pipeline.persistentDrawingOwnerCountForSmoke() == 2
        && image.cachedFinalRasterForDrawing(1) == cached,
        "the raster must remain while two shared owners survive");
    screen.remove(second);
    requireOwnership(pipeline.persistentDrawingOwnerCountForSmoke() == 1
        && image.cachedFinalRasterForDrawing(1) == cached,
        "the raster must remain while the final shared owner survives");
    screen.remove(third);
    requireOwnership(pipeline.persistentDrawingOwnerCountForSmoke() == 0
        && pipeline.cachedVariantCountForSmoke() == 0
        && image.cachedFinalRasterForDrawing(1) == null,
        "the final owner release must evict the admitted raster");
    remove(screen);
    screen.removeAll();
  }

  private void runPipelineReplacementScenario() throws Exception {
    Image image = newFixtureImage();
    ImagePipeline previous = image.pipelineForSmoke();
    Container screen = new Container();
    screen.add(new ImageControl(image));
    screen.add(new ImageControl(image));
    screen.add(new ImageControl(image));
    add(screen);
    requireOwnership(previous.persistentDrawingOwnerCountForSmoke() == 3,
        "the original pipeline must begin with three attached owners");
    image.applyFade(120);
    ImagePipeline replacement = image.pipelineForSmoke();
    requireOwnership(replacement != previous
        && previous.persistentDrawingOwnerCountForSmoke() == 0
        && replacement.persistentDrawingOwnerCountForSmoke() == 3,
        "replacing an image pipeline must transfer all three owners exactly once");
    remove(screen);
    requireOwnership(replacement.persistentDrawingOwnerCountForSmoke() == 0,
        "detaching after pipeline replacement must release all transferred owners");
    screen.removeAll();
  }

  private int runDrawingScenario() throws Exception {
    Image image = newFixtureImage();
    Container screen = new Container();
    screen.add(new ImageControl(image));
    add(screen);
    Image firstRaster = ImageDrawingBridge.resolveForDrawing(image, 1,
        ImageDrawingBridge.AdmissionMode.IMMEDIATE);
    Image secondRaster = ImageDrawingBridge.resolveForDrawing(image, 1,
        ImageDrawingBridge.AdmissionMode.IMMEDIATE);
    Image cachedRaster = image.cachedFinalRasterForDrawing(1);
    requireOwnership(firstRaster == secondRaster && cachedRaster == firstRaster,
        "repeated draw resolution must reuse the same admitted raster");

    Image destination = new Image(4, 4);
    Graphics graphics = destination.getGraphics();
    ImageDrawingBridge.drawPersistentImage(graphics, image, 0, 0, true);
    ImageDrawingBridge.drawPersistentImage(graphics, image, 0, 0, true);
    int pixel = graphics.getPixel(0, 0);
    File output = new File("image-ownership-render.png", File.CREATE_EMPTY);
    destination.createPng(output);
    output.close();
    int rgb = pixel & 0xFFFFFF;
    boolean redPixel = "jpeg".equals(IMAGE_FIXTURE_FORMAT)
        ? ((rgb >> 16) & 0xFF) >= 240 && ((rgb >> 8) & 0xFF) <= 10 && (rgb & 0xFF) <= 10
        : rgb == Color.RED;
    require(redPixel, "native repeated drawing must preserve the red pixel; got 0x"
        + Integer.toHexString(pixel));
    remove(screen);
    requireOwnership(ImageDrawingBridge.persistentOwnerCount(image) == 0,
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
