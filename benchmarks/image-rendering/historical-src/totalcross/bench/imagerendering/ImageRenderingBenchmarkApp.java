// Copyright (C) 2026 Amalgam Solucoes em TI Ltda
//
// SPDX-License-Identifier: LGPL-2.1-only

package totalcross.bench.imagerendering;

import totalcross.json.JSONObject;
import totalcross.sys.Settings;
import totalcross.ui.Control;
import totalcross.ui.MainWindow;
import totalcross.ui.event.TimerEvent;
import totalcross.ui.event.TimerListener;
import totalcross.ui.gfx.Graphics;
import totalcross.ui.image.ImageOptimizationSettings;

/** Isolated controller for the f5dad132 static preparation probe only. */
public final class ImageRenderingBenchmarkApp {
  private final MainWindow window;
  private JSONObject config;
  private ScrollWorkload scroll;

  private ImageRenderingBenchmarkApp(MainWindow window) { this.window = window; }

  public static ImageRenderingBenchmarkApp start(MainWindow window, String profile) {
    ImageRenderingBenchmarkApp app = new ImageRenderingBenchmarkApp(window);
    try {
      app.initialize(profile);
    } catch (Throwable failure) {
      app.fail(failure);
    }
    return app;
  }

  public static void capturePaint() { /* Static probe measures explicit paint calls. */ }

  private void initialize(String profile) throws Exception {
    config = BenchSupport.readConfig();
    long mask = ImageOptimizationSettings.getMask();
    long effectiveMask = ImageOptimizationSettings.getEffectiveMask();
    System.out.println("HISTORICAL_DEFAULT_MASK configured=" + mask + " effective=" + effectiveMask);
    System.out.flush();
    if (mask != 32799L || effectiveMask != 32799L) {
      throw new IllegalStateException("historical natural default must be 32799 for both masks");
    }
    if (!"default".equals(profile) || !profile.equals(config.getString("profile"))
        || !"scroll".equals(config.getString("family"))
        || !"scroll".equals(config.getString("workload"))
        || !"paint-preparation-probe".equals(config.getString("scrollDriver"))
        || !"f5dad132cafea5c9086f6f946a6f44ca5bcb5f76".equals(config.getString("runtimeSourceCommit"))
        || config.getBoolean("preflight") || config.getBoolean("diagnosticsEnabled")
        || config.getInt("width") != 540 || config.getInt("height") != 960
        || Settings.screenWidth != 540 || Settings.screenHeight != 960) {
      throw new IllegalStateException("historical probe requires one static default 540x960 process");
    }
    BenchSupport.readDataset(config); // Validate the same manifest before UI construction.
    System.out.println(BenchSupport.PREFLIGHT_PREFIX + BenchSupport.object(
        "recordType", "historical-preflight", "configuredMask", mask, "effectiveMask", effectiveMask,
        "runtimeSourceCommit", config.getString("runtimeSourceCommit"),
        "diagnosticsSupported", false, "diagnosticsEnabled", false));
    System.out.flush();
    scroll = new ScrollWorkload(this, config);
    scroll.historicalVisibleIdentity(); // Capture references before the first measurement.
    scroll.start();
  }

  JSONObject runRecord(JSONObject measurements, JSONObject durations, int round, String phase,
      String workload) throws Exception {
    BenchSupport.put(measurements, "historicalVisibleIdentity", scroll.historicalVisibleIdentity());
    if (ImageOptimizationSettings.getMask() != 32799L
        || ImageOptimizationSettings.getEffectiveMask() != 32799L) {
      throw new IllegalStateException("historical masks changed during probe");
    }
    Graphics graphics = getGraphics();
    return BenchSupport.object(
        "schemaVersion", 1, "recordType", "run", "family", "scroll", "workload", workload,
        "profile", "default", "round", round, "phase", phase,
        "runtimeSourceCommit", config.getString("runtimeSourceCommit"),
        "benchmarkSourceCommit", config.getString("benchmarkSourceCommit"),
        "dataset", config.getJSONObject("dataset"),
        "logicalDimensions", BenchSupport.object("width", Settings.screenWidth, "height", Settings.screenHeight),
        "drawableDimensions", BenchSupport.object("width", graphics.getSurfacePixelWidth(),
            "height", graphics.getSurfacePixelHeight()),
        "renderer", "RASTER", // Builder verifies software surface / Skia / SDL in CMakeCache.
        "rendererEvidence", "native-build-cache",
        "configuredMask", ImageOptimizationSettings.getMask(),
        "effectiveMask", ImageOptimizationSettings.getEffectiveMask(),
        "diagnosticsSupported", false, "diagnosticsEnabled", false,
        "durationsNs", durations, "measurements", measurements);
  }

  void emit(JSONObject record) {
    System.out.println(BenchSupport.RESULT_PREFIX + record.toString());
    System.out.flush();
  }

  Graphics getGraphics() { return window.getGraphics(); }
  void add(Control control) { window.add(control); }
  TimerEvent addTimer(int millis) { return window.addTimer(millis); }
  boolean removeTimer(TimerEvent timer) { return window.removeTimer(timer); }
  void addTimerListener(TimerListener listener) { window.addTimerListener(listener); }
  void removeTimerListener(TimerListener listener) { window.removeTimerListener(listener); }
  void exit(int code) { MainWindow.exit(code); }
  void fail(Throwable failure) {
    System.err.println("historical static probe failed: " + failure);
    failure.printStackTrace();
    exit(1);
  }
}
