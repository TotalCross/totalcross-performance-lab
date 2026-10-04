package totalcross.bench.imagerendering;

import java.util.Arrays;

import totalcross.json.JSONArray;
import totalcross.json.JSONObject;
import totalcross.sys.RuntimeDiagnosticSnapshot;
import totalcross.sys.RuntimeDiagnostics;
import totalcross.ui.Container;
import totalcross.ui.Flick;
import totalcross.ui.Scrollable;
import totalcross.ui.event.DragEvent;
import totalcross.ui.event.TimerEvent;
import totalcross.ui.event.TimerListener;

/** Observes current TimerEvent Flick callbacks and synthetic UI timer cadence. */
final class PacingWorkload implements TimerListener {
  private static final int SYNTHETIC_SAMPLES = 120;
  private static final int FLICK_REPETITIONS = 5;

  private final ImageRenderingBenchmarkApp app;
  private final JSONObject config;
  private final String workload;
  private final Samples intervals = new Samples();
  private final Samples lateness = new Samples();
  private final long startedNs = System.nanoTime();
  private final RuntimeDiagnosticSnapshot diagnosticsBefore;
  private TimerEvent timer;
  private PacingTarget target;
  private Flick flick;
  private int requestedFps;
  private double targetCadenceHz;
  private boolean diagnosticsActive;
  private int syntheticCount;
  private int syntheticFraction;
  private long lastCallbackNs;
  private long syntheticWallStartedNs;
  private int flickCount;

  PacingWorkload(ImageRenderingBenchmarkApp app, JSONObject config) throws Exception {
    this.app = app;
    this.config = config;
    workload = config.getString("workload");
    diagnosticsBefore = prepareSchedulingDiagnostics();
  }

  void start() throws Exception {
    if (workload.startsWith("flick-")) {
      requestedFps = Integer.parseInt(workload.substring("flick-".length()));
      targetCadenceHz = requestedFps;
      if (requestedFps != 40 && requestedFps != 60) {
        throw new IllegalArgumentException("Flick pacing supports only 40 or 60 fps");
      }
      target = new PacingTarget(this);
      target.setRect(0, 0, 32, 32);
      app.add(target);
      flick = new Flick(target);
      flick.frameRate = requestedFps;
      flick.longestFlick = 400;
      flick.shortestFlick = 1;
      target.setFlick(flick);
      triggerFlick();
    } else if ("synthetic-16ms".equals(workload)) {
      targetCadenceHz = 62.5;
      startSynthetic();
    } else if ("synthetic-16.667ms".equals(workload)) {
      targetCadenceHz = 60.0;
      startSynthetic();
    } else {
      throw new IllegalArgumentException("unsupported pacing workload: " + workload);
    }
  }

  private RuntimeDiagnosticSnapshot prepareSchedulingDiagnostics() {
    if (!RuntimeDiagnostics.isSupported()) {
      return null;
    }
    boolean enabled = false;
    try {
      enabled = config.getBoolean("diagnosticsEnabled");
    } catch (Exception ignored) { }
    RuntimeDiagnostics.setDomainEnabled(RuntimeDiagnosticSnapshot.Domain.SCHEDULING, enabled);
    diagnosticsActive = enabled;
    return RuntimeDiagnostics.snapshot();
  }

  private void triggerFlick() {
    if (flickCount >= FLICK_REPETITIONS) {
      finish();
      return;
    }
    int dragId = flickCount + 1;
    DragEvent start = new DragEvent();
    start.dragId = dragId;
    start.direction = DragEvent.DOWN;
    start.absoluteY = 0;
    start.target = target;
    flick.penDragStart(start);
    DragEvent end = new DragEvent();
    end.dragId = dragId;
    end.direction = DragEvent.DOWN;
    end.absoluteY = 100;
    end.yTotal = 100;
    end.target = target;
    flick.penDragEnd(end);
    if (Flick.currentFlick != flick) {
      throw new IllegalStateException("production Flick timer did not start for " + workload);
    }
  }

  private void startSynthetic() {
    app.addTimerListener(this);
    syntheticWallStartedNs = System.nanoTime();
    schedule(nextSyntheticDelay());
  }

  private int nextSyntheticDelay() {
    if ("synthetic-16ms".equals(workload)) {
      return 16;
    }
    syntheticFraction += 2;
    if (syntheticFraction >= 3) {
      syntheticFraction -= 3;
      return 17;
    }
    return 16;
  }

  @Override
  public void timerTriggered(TimerEvent event) {
    if (event != timer) {
      return;
    }
    app.removeTimer(timer);
    timer = null;
    if (workload.startsWith("flick-")) {
      triggerFlick();
      return;
    }
    long now = System.nanoTime();
    if (lastCallbackNs != 0L) {
      long interval = now - lastCallbackNs;
      intervals.add(interval);
      long targetIntervalNs = "synthetic-16ms".equals(workload) ? 16000000L : 16666667L;
      lateness.add(Math.max(0L, interval - targetIntervalNs));
    }
    lastCallbackNs = now;
    syntheticCount++;
    if (syntheticCount >= SYNTHETIC_SAMPLES) {
      finish();
    } else {
      schedule(nextSyntheticDelay());
    }
  }

  void flickCompleted() {
    flickCount++;
    if (flickCount >= FLICK_REPETITIONS) {
      finish();
      return;
    }
    // Let the UI loop return before starting the next independent Flick cycle.
    app.addTimerListener(this);
    schedule(25);
  }

  private void schedule(int millis) {
    timer = app.addTimer(millis);
  }

  private void finish() {
    try {
      if (timer != null) {
        app.removeTimer(timer);
        timer = null;
      }
      app.removeTimerListener(this);
      if (workload.startsWith("flick-") && intervals.size() == 0) {
        throw new IllegalStateException("production Flick completed without callback interval samples");
      }
      long wall = System.nanoTime() - startedNs;
      Object diagnostics = diagnosticsAfter();
      JSONObject measurements = BenchSupport.object(
          "axes", BenchSupport.object("targetCadenceHz", targetCadenceHz,
              "targetIntervalNs", "flick-40".equals(workload) ? 25000000L
                  : "flick-60".equals(workload) ? 16000000L
                  : "synthetic-16ms".equals(workload) ? 16000000L : 16666667L,
              "driver", workload.startsWith("flick-") ? "production Flick TimerEvent" : "MainWindow TimerEvent"),
          "sampleCount", intervals.size(),
          "callbackIntervalsNs", intervals.toJsonArray(),
          "callbackIntervalStatistics", intervals.statistics(),
          "callbackLatenessNs", lateness.toJsonArray(),
          "callbackLatenessStatistics", lateness.statistics(),
          "diagnostics", diagnostics,
          "flickRepetitions", workload.startsWith("flick-") ? flickCount : JSONObject.NULL,
          "syntheticCallbacks", workload.startsWith("synthetic-") ? syntheticCount : JSONObject.NULL);
      JSONObject durations = BenchSupport.object("wallTime", wall,
          "measurementWindow", workload.startsWith("synthetic-")
              ? System.nanoTime() - syntheticWallStartedNs : wall);
      app.emit(app.runRecord(measurements, durations, config.getInt("round"),
          config.getString("phase"), workload));
      app.exit(0);
    } catch (Throwable failure) {
      app.fail(failure);
    }
  }

  private Object diagnosticsAfter() {
    if (diagnosticsBefore == null || !diagnosticsActive) {
      return JSONObject.NULL;
    }
    RuntimeDiagnosticSnapshot after = RuntimeDiagnostics.snapshot();
    RuntimeDiagnosticSnapshot delta = after.deltaSince(diagnosticsBefore);
    return BenchSupport.object("scope", "aggregate public SCHEDULING domain",
        "before", diagnosticTotals(diagnosticsBefore),
        "after", diagnosticTotals(after),
        "delta", diagnosticTotals(delta));
  }

  private static JSONObject diagnosticTotals(RuntimeDiagnosticSnapshot snapshot) {
    return BenchSupport.object(
        "counter", snapshot.getValue(RuntimeDiagnosticSnapshot.Domain.SCHEDULING,
            RuntimeDiagnosticSnapshot.Kind.COUNTER),
        "timerNs", snapshot.getValue(RuntimeDiagnosticSnapshot.Domain.SCHEDULING,
            RuntimeDiagnosticSnapshot.Kind.TIMER),
        "gauge", snapshot.getValue(RuntimeDiagnosticSnapshot.Domain.SCHEDULING,
            RuntimeDiagnosticSnapshot.Kind.GAUGE));
  }

  private static final class PacingTarget extends Container implements Scrollable {
    private final PacingWorkload owner;
    private Flick flick;
    private int scrollPosition = 500;
    private long lastCallbackNs;

    PacingTarget(PacingWorkload owner) { this.owner = owner; }

    void setFlick(Flick flick) { this.flick = flick; }

    @Override public boolean flickStarted() { lastCallbackNs = 0L; return true; }
    @Override public void flickEnded(boolean atPenDown) { owner.flickCompleted(); }
    @Override public boolean canScrollContent(int direction, Object eventTarget) { return true; }
    @Override public int getScrollPosition(int direction) { return scrollPosition; }
    @Override public Flick getFlick() { return flick; }
    @Override public boolean wasScrolled() { return false; }

    @Override
    public boolean scrollContent(int dx, int dy, boolean fromFlick) {
      long now = System.nanoTime();
      if (lastCallbackNs != 0L) {
        long interval = now - lastCallbackNs;
        owner.intervals.add(interval);
        long expected = 1000000000L / owner.requestedFps;
        owner.lateness.add(Math.max(0L, interval - expected));
      }
      lastCallbackNs = now;
      scrollPosition += dy;
      repaint();
      return true;
    }
  }

  private static final class Samples {
    private long[] values = new long[128];
    private int size;

    void add(long value) {
      if (size == values.length) values = Arrays.copyOf(values, values.length * 2);
      values[size++] = value;
    }

    int size() { return size; }

    JSONArray toJsonArray() {
      JSONArray result = new JSONArray();
      for (int i = 0; i < size; i++) result.put(values[i]);
      return result;
    }

    JSONObject statistics() {
      if (size == 0) {
        return BenchSupport.object("sampleCount", 0, "p50Ns", JSONObject.NULL,
            "p95Ns", JSONObject.NULL, "p99Ns", JSONObject.NULL, "maxNs", JSONObject.NULL);
      }
      long[] sorted = Arrays.copyOf(values, size);
      Arrays.sort(sorted);
      return BenchSupport.object("sampleCount", size,
          "p50Ns", percentile(sorted, 0.50), "p95Ns", percentile(sorted, 0.95),
          "p99Ns", percentile(sorted, 0.99), "maxNs", sorted[size - 1]);
    }

    private static double percentile(long[] sorted, double fraction) {
      double position = (sorted.length - 1) * fraction;
      int low = (int) Math.floor(position);
      int high = (int) Math.ceil(position);
      return sorted[low] + (sorted[high] - sorted[low]) * (position - low);
    }
  }
}
