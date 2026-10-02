package totalcross.bench.imagerendering;

import totalcross.json.JSONObject;
import totalcross.sys.RuntimeDiagnostics;
import totalcross.sys.runtime.RuntimeConfigurationReport;
import totalcross.sys.runtime.RuntimeEnvironment;
import totalcross.ui.Control;
import totalcross.ui.MainWindow;
import totalcross.ui.event.TimerEvent;
import totalcross.ui.event.TimerListener;
import totalcross.ui.gfx.Graphics;

/** Shared controller used by the direct MainWindow entry classes for each profile. */
public final class ImageRenderingBenchmarkApp {
  private static ImageRenderingBenchmarkApp active;
  private final MainWindow window;
  private final String profile;
  private JSONObject config;
  private ScrollWorkload scrollWorkload;

  private ImageRenderingBenchmarkApp(MainWindow window, String profile) {
    this.window = window;
    this.profile = profile;
  }

  public static ImageRenderingBenchmarkApp start(MainWindow window, String profile) {
    ImageRenderingBenchmarkApp app = new ImageRenderingBenchmarkApp(window, profile);
    active = app;
    try {
      app.initialize();
    } catch (Throwable failure) {
      app.fail(failure);
    }
    return app;
  }

  public static void capturePaint() {
    if (active != null && active.scrollWorkload != null) {
      active.scrollWorkload.capturePaint();
    }
  }

  private void initialize() throws Exception {
    config = BenchSupport.readConfig();
    if (!profile.equals(config.getString("profile"))) {
      throw new IllegalStateException("entry profile " + profile
          + " does not match requested profile " + config.getString("profile"));
    }
    if (config.getBoolean("preflight")) {
      exit(0);
      return;
    }
    String family = config.getString("family");
    if ("decode".equals(family)) {
      DecodeWorkload.run(this, config);
    } else if ("scroll".equals(family) || "preparation".equals(family)) {
      scrollWorkload = new ScrollWorkload(this, config);
      scrollWorkload.start();
    } else {
      throw new IllegalArgumentException("workload family is not in this app slice: " + family);
    }
  }

  JSONObject runRecord(JSONObject measurements, JSONObject durations, int round, String phase,
      String workload) throws Exception {
    RuntimeEnvironment runtime = RuntimeEnvironment.current();
    Graphics graphics = window.getGraphics();
    Object diagnosticValues = measurements.opt("diagnostics");
    Object logical = JSONObject.NULL;
    Object drawable = JSONObject.NULL;
    if ("scroll".equals(config.getString("family"))
        || "preparation".equals(config.getString("family"))) {
      logical = BenchSupport.object("width", config.getInt("width"), "height", config.getInt("height"));
      if (graphics != null) {
        drawable = BenchSupport.object("width", graphics.getSurfacePixelWidth(),
            "height", graphics.getSurfacePixelHeight());
      }
    }
    return BenchSupport.object(
        "schemaVersion", 1,
        "recordType", "run",
        "family", config.getString("family"),
        "workload", workload,
        "profile", config.getString("profile"),
        "runtimeSourceCommit", config.getString("runtimeSourceCommit"),
        "benchmarkSourceCommit", config.getString("benchmarkSourceCommit"),
        "dataset", config.opt("dataset") == null ? JSONObject.NULL : config.opt("dataset"),
        "environment", config.getJSONObject("environment"),
        "runtimeIdentity", config.getString("runtimeIdentity"),
        "logicalDimensions", logical,
        "drawableDimensions", drawable,
        "renderer", runtime.graphicsBackend() == null ? "unavailable" : runtime.graphicsBackend().name(),
        "displayRefreshHz", JSONObject.NULL,
        "diagnosticsSupported", RuntimeDiagnostics.isSupported(),
        "diagnosticsEnabled", config.getBoolean("diagnosticsEnabled") && RuntimeDiagnostics.isSupported(),
        "runtimeConfigurationReport", RuntimeConfigurationReport.describe(),
        "round", config.getInt("round"),
        "phase", config.getString("phase"),
        "durationsNs", durations,
        "measurements", measurements,
        "diagnostics", diagnosticValues == null ? JSONObject.NULL : diagnosticValues);
  }

  void emit(JSONObject record) throws Exception {
    JSONObject summary = BenchSupport.object(
        "schemaVersion", 1,
        "recordType", "summary",
        "family", record.getString("family"),
        "workload", record.getString("workload"),
        "profile", record.getString("profile"),
        "dataset", record.opt("dataset") == null ? JSONObject.NULL : record.opt("dataset"),
        "runtimeSourceCommit", record.getString("runtimeSourceCommit"),
        "benchmarkSourceCommit", record.opt("benchmarkSourceCommit"),
        "rounds", BenchSupport.array(record),
        "failures", record.getJSONObject("measurements").opt("imagesFailed") instanceof Integer
            ? ((Integer) record.getJSONObject("measurements").opt("imagesFailed")).intValue() : 0,
        "statistics", BenchSupport.object("wallTimeNs", BenchSupport.object(
            "median", record.getJSONObject("durationsNs").getLong("wallTime"))),
        "environment", record.getJSONObject("environment"));
    System.out.println(BenchSupport.RESULT_PREFIX + record.toString());
    System.out.println(BenchSupport.RESULT_PREFIX + summary.toString());
    System.out.flush();
  }

  JSONObject getConfig() { return config; }
  Graphics getGraphics() { return window.getGraphics(); }
  void add(Control control) { window.add(control); }
  TimerEvent addTimer(int millis) { return window.addTimer(millis); }
  boolean removeTimer(TimerEvent timer) { return window.removeTimer(timer); }
  void addTimerListener(TimerListener listener) { window.addTimerListener(listener); }
  void removeTimerListener(TimerListener listener) { window.removeTimerListener(listener); }
  void exit(int code) { MainWindow.exit(code); }

  void fail(Throwable failure) {
    System.err.println("image-rendering benchmark failed: " + failure);
    failure.printStackTrace();
    exit(1);
  }
}
