package totalcross.bench.imagerendering;

import java.util.Arrays;

import totalcross.json.JSONArray;
import totalcross.json.JSONObject;
import totalcross.sys.RuntimeDiagnosticSnapshot;
import totalcross.sys.RuntimeDiagnostics;
import totalcross.sys.Settings;
import totalcross.ui.ImageControl;
import totalcross.ui.ScrollContainer;
import totalcross.ui.event.DragEvent;
import totalcross.ui.event.TimerEvent;
import totalcross.ui.event.TimerListener;
import totalcross.ui.gfx.Graphics;
import totalcross.ui.image.Image;

/** Real-corpus scroll and explicit visible-image preparation workloads. */
final class ScrollWorkload implements TimerListener {
  private static final int COLUMNS = 3;
  private static final int CELL_HEIGHT = 128;
  private static final int ROW_GAP = 12;
  private static final int STEP_PIXELS = 72;
  private static final int TIMER_MILLIS = 16;

  private final ImageRenderingBenchmarkApp app;
  private final JSONObject config;
  private final boolean preparation;
  private final ScrollContainer scroll;
  private final BenchSupport.DatasetEntry[] entries;
  private final ImageControl[] controls;
  private final boolean[] requested;
  private final SampleSeries paintIntervals = new SampleSeries();
  private final SampleSeries passPaintIntervals = new SampleSeries();
  private final SampleSeries stepIntervals = new SampleSeries();
  private final SampleSeries allStepIntervals = new SampleSeries();
  private final JSONArray passes = new JSONArray();
  private final RuntimeDiagnosticSnapshot diagnosticsBefore;
  private TimerEvent timer;
  private int passNumber;
  private int direction = 1;
  private int currentPassFrames;
  private long passStartedNs;
  private long lastStepNs;
  private long lastPaintNs;
  private long preparationCallStartedNs;
  private long preparationWaitNs;
  private int requestedCount;
  private int callbackCompletions;
  private int loadFailures;
  private boolean preparationPending;
  private boolean collectPaints;
  private int lastPreparedY = -1;
  private int viewportWidth;
  private int viewportHeight;

  ScrollWorkload(ImageRenderingBenchmarkApp app, JSONObject config) throws Exception {
    this.app = app;
    this.config = config;
    String profile = config.getString("profile");
    preparation = profile.startsWith("prepared-") || profile.startsWith("combined-");
    entries = BenchSupport.readDataset(config);
    controls = new ImageControl[entries.length];
    requested = new boolean[entries.length];
    scroll = new ScrollContainer(false, true);
    int requestedWidth = Math.max(1, config.getInt("width"));
    int requestedHeight = Math.max(1, config.getInt("height"));
    viewportWidth = requestedWidth;
    viewportHeight = requestedHeight;
    if (viewportWidth > Settings.screenWidth || viewportHeight > Settings.screenHeight) {
      viewportWidth = Math.min(viewportWidth, Math.max(1, Settings.screenWidth));
      viewportHeight = Math.min(viewportHeight, Math.max(1, Settings.screenHeight));
    }
    BenchSupport.put(config, "requestedLogicalWidth", requestedWidth);
    BenchSupport.put(config, "requestedLogicalHeight", requestedHeight);
    BenchSupport.put(config, "width", viewportWidth);
    BenchSupport.put(config, "height", viewportHeight);
    app.add(scroll);
    scroll.setRect(0, 0, viewportWidth, viewportHeight);
    int cellWidth = Math.max(1, (viewportWidth - 24) / COLUMNS);
    int strideY = CELL_HEIGHT + ROW_GAP;
    String root = config.getString("datasetRoot");
    for (int i = 0; i < entries.length; i++) {
      try {
        Image image = BenchSupport.loadFilesystemImage(root + "/" + entries[i].path);
        Image thumbnail = image.getScaledInstance(cellWidth, CELL_HEIGHT);
        image = null;
        ImageControl control = new ImageControl(thumbnail);
        int column = i % COLUMNS;
        int row = i / COLUMNS;
        control.setRect(8 + column * (cellWidth + 4), 8 + row * strideY, cellWidth, CELL_HEIGHT);
        controls[i] = control;
        scroll.add(control);
      } catch (Throwable failure) {
        loadFailures++;
        throw new IllegalStateException("cannot create image control for " + entries[i].path, failure);
      }
    }
    scroll.resize();
    diagnosticsBefore = configureDiagnostics(true);
  }

  void start() {
    app.addTimerListener(this);
    scroll.scrollToOrigin();
    schedule(TIMER_MILLIS);
    if (preparation) {
      requestVisiblePreparation();
    }
  }

  void capturePaint() {
    if (!collectPaints) {
      return;
    }
    long now = System.nanoTime();
    if (lastPaintNs != 0L) {
      long interval = now - lastPaintNs;
      paintIntervals.add(interval);
      passPaintIntervals.add(interval);
    }
    lastPaintNs = now;
  }

  @Override
  public void timerTriggered(TimerEvent event) {
    if (event != timer) {
      return;
    }
    app.removeTimer(timer);
    timer = null;
    try {
      if (passStartedNs == 0L) {
        beginPass();
      }
      if (!preparationPending) {
        moveOneStep();
      }
      if (passStartedNs != 0L && !preparationPending && timer == null) {
        schedule(TIMER_MILLIS);
      }
    } catch (Throwable failure) {
      app.fail(failure);
    }
  }

  private void beginPass() {
    if (passNumber >= 2) {
      finish();
      return;
    }
    scroll.scrollToOrigin();
    direction = 1;
    currentPassFrames = 0;
    lastStepNs = 0L;
    lastPaintNs = 0L;
    stepIntervals.clear();
    passPaintIntervals.clear();
    collectPaints = true;
    passStartedNs = System.nanoTime();
    if (preparation) {
      lastPreparedY = -1;
      requestVisiblePreparation();
    }
  }

  private void moveOneStep() {
    long now = System.nanoTime();
    if (lastStepNs != 0L) {
      long interval = now - lastStepNs;
      stepIntervals.add(interval);
      allStepIntervals.add(interval);
    }
    lastStepNs = now;
    currentPassFrames++;
    int position = scroll.getScrollPosition(DragEvent.DOWN);
    int maxPosition = Math.max(0, scroll.getPreferredHeight() - viewportHeight);
    if (direction > 0) {
      int distance = Math.min(STEP_PIXELS, Math.max(0, maxPosition - position));
      if (distance > 0) {
        scroll.scrollContent(0, distance, true);
      }
      if (position + distance >= maxPosition) {
        direction = -1;
      }
    } else {
      int distance = Math.min(STEP_PIXELS, Math.max(0, position));
      if (distance > 0) {
        scroll.scrollContent(0, -distance, true);
      }
      if (position - distance <= 0) {
        endPass();
        return;
      }
    }
    if (preparation && shouldPrepare()) {
      requestVisiblePreparation();
    }
  }

  private boolean shouldPrepare() {
    int position = scroll.getScrollPosition(DragEvent.DOWN);
    int interval = Math.max(1, viewportHeight - CELL_HEIGHT);
    if (lastPreparedY < 0 || Math.abs(position - lastPreparedY) >= interval) {
      lastPreparedY = position;
      return true;
    }
    return false;
  }

  private void requestVisiblePreparation() {
    if (preparationPending) {
      return;
    }
    preparationPending = true;
    preparationCallStartedNs = System.nanoTime();
    scroll.prepareForDisplay(new Runnable() {
      @Override
      public void run() {
        preparationWaitNs += System.nanoTime() - preparationCallStartedNs;
        callbackCompletions++;
        countVisibleEntries();
        preparationPending = false;
        if (timer == null) {
          schedule(1);
        }
      }
    });
  }

  private void countVisibleEntries() {
    int top = scroll.getScrollPosition(DragEvent.DOWN);
    int bottom = top + Math.max(1, viewportHeight - 16);
    int strideY = CELL_HEIGHT + ROW_GAP;
    for (int i = 0; i < entries.length; i++) {
      int itemTop = 8 + (i / COLUMNS) * strideY;
      if (!requested[i] && itemTop < bottom && itemTop + CELL_HEIGHT > top) {
        requested[i] = true;
        requestedCount++;
      }
    }
  }

  private void endPass() {
    collectPaints = false;
    long wall = System.nanoTime() - passStartedNs;
    String name = passNumber == 0 ? "first-workload" : "warm";
    JSONObject pass = BenchSupport.object(
        "name", name,
        "direction", "top-to-bottom-then-bottom-to-top",
        "wallTimeNs", wall,
        "stepSampleCount", stepIntervals.size(),
        "stepIntervalNs", stepIntervals.toJsonArray(),
        "stepIntervalStatistics", stepIntervals.statistics(),
        "paintIntervalNs", passPaintIntervals.toJsonArray(),
        "paintIntervalStatistics", passPaintIntervals.statistics(),
        "scrollPositionEnd", scroll.getScrollPosition(DragEvent.DOWN));
    passes.put(pass);
    passNumber++;
    passStartedNs = 0L;
    if (passNumber < 2) {
      schedule(1);
    } else {
      finish();
    }
  }

  private void finish() {
    try {
      app.removeTimerListener(this);
      Object diagnostics = diagnosticsAfter();
      long totalWall = 0L;
      for (int i = 0; i < passes.length(); i++) {
        totalWall += passes.getJSONObject(i).getLong("wallTimeNs");
      }
      JSONObject measurements = BenchSupport.object(
          "axes", BenchSupport.object("requestedLogicalViewportWidth", config.getInt("requestedLogicalWidth"),
              "requestedLogicalViewportHeight", config.getInt("requestedLogicalHeight"),
              "logicalViewportWidth", viewportWidth, "logicalViewportHeight", viewportHeight,
              "displayScale", getDisplayScale()),
          "imageControls", controls.length,
          "rows", (controls.length + COLUMNS - 1) / COLUMNS,
          "columns", COLUMNS,
          "passes", passes,
          "frameSampleCount", paintIntervals.size(),
          "paintIntervalNs", paintIntervals.toJsonArray(),
          "paintIntervalStatistics", paintIntervals.statistics(),
          "frameBudgetShares", paintIntervals.budgetShares(),
          "scrollStepSampleCount", allStepIntervals.size(),
          "preparation", preparation,
          "requestedEntries", preparation ? requestedCount : JSONObject.NULL,
          "readyOrAdoptedEntries", JSONObject.NULL,
          "failures", loadFailures,
          "callbackCompletions", preparation ? callbackCompletions : JSONObject.NULL,
          "preparationWaitTimeNs", preparation ? preparationWaitNs : JSONObject.NULL,
          "diagnostics", diagnostics);
      JSONObject durations = BenchSupport.object("wallTime", totalWall,
          "preparationWaitTime", preparation ? preparationWaitNs : 0L);
      app.emit(app.runRecord(measurements, durations, config.getInt("round"),
          config.getString("phase"), config.getString("family")));
      if (controls.length != BenchSupport.EXPECTED_FILE_COUNT || loadFailures != 0) {
        app.fail(new IllegalStateException("scroll workload did not create the complete image corpus"));
      } else {
        app.exit(0);
      }
    } catch (Throwable failure) {
      app.fail(failure);
    }
  }

  private RuntimeDiagnosticSnapshot configureDiagnostics(boolean enable) {
    if (!RuntimeDiagnostics.isSupported()) {
      return null;
    }
    boolean requestedByRunner = false;
    try {
      requestedByRunner = config.getBoolean("diagnosticsEnabled");
    } catch (Exception ignored) { }
    RuntimeDiagnostics.setDomainEnabled(RuntimeDiagnosticSnapshot.Domain.IMAGE, enable && requestedByRunner);
    RuntimeDiagnostics.setDomainEnabled(RuntimeDiagnosticSnapshot.Domain.PREFETCH, enable && requestedByRunner);
    boolean active = enable && requestedByRunner;
    diagnosticsActive = active;
    return RuntimeDiagnostics.snapshot();
  }

  private boolean diagnosticsActive;

  private Object diagnosticsAfter() {
    if (diagnosticsBefore == null || !diagnosticsActive || !RuntimeDiagnostics.isSupported()) {
      return JSONObject.NULL;
    }
    RuntimeDiagnosticSnapshot after = RuntimeDiagnostics.snapshot();
    RuntimeDiagnosticSnapshot delta = after.deltaSince(diagnosticsBefore);
    return BenchSupport.object(
        "scope", "aggregate public IMAGE and PREFETCH domains",
        "before", diagnosticTotals(diagnosticsBefore),
        "after", diagnosticTotals(after),
        "delta", diagnosticTotals(delta));
  }

  private static JSONObject diagnosticTotals(RuntimeDiagnosticSnapshot snapshot) {
    return BenchSupport.object(
        "image", diagnosticDomain(snapshot, RuntimeDiagnosticSnapshot.Domain.IMAGE),
        "prefetch", diagnosticDomain(snapshot, RuntimeDiagnosticSnapshot.Domain.PREFETCH));
  }

  private static JSONObject diagnosticDomain(RuntimeDiagnosticSnapshot snapshot,
      RuntimeDiagnosticSnapshot.Domain domain) {
    return BenchSupport.object(
        "counter", snapshot.getValue(domain, RuntimeDiagnosticSnapshot.Kind.COUNTER),
        "timerNs", snapshot.getValue(domain, RuntimeDiagnosticSnapshot.Kind.TIMER),
        "gauge", snapshot.getValue(domain, RuntimeDiagnosticSnapshot.Kind.GAUGE));
  }

  private double getDisplayScale() {
    Graphics graphics = app.getGraphics();
    return graphics == null ? 1.0 : graphics.getContentScale();
  }

  private void schedule(int millis) {
    timer = app.addTimer(millis);
  }

  private static final class SampleSeries {
    private long[] values = new long[2048];
    private int size;

    void add(long value) {
      if (size == values.length) {
        values = Arrays.copyOf(values, values.length * 2);
      }
      values[size++] = value;
    }

    int size() { return size; }

    void clear() { size = 0; }

    JSONArray toJsonArray() {
      JSONArray result = new JSONArray();
      for (int i = 0; i < size; i++) {
        result.put(values[i]);
      }
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
          "p50Ns", percentile(sorted, 0.50),
          "p95Ns", percentile(sorted, 0.95),
          "p99Ns", percentile(sorted, 0.99),
          "maxNs", sorted[sorted.length - 1]);
    }

    JSONObject budgetShares() {
      if (size == 0) {
        return BenchSupport.object("atOrUnder22_222msPercent", JSONObject.NULL,
            "atOrUnder16_667msPercent", JSONObject.NULL);
      }
      int under45 = 0;
      int under60 = 0;
      for (int i = 0; i < size; i++) {
        if (values[i] <= 22222000L) under45++;
        if (values[i] <= 16667000L) under60++;
      }
      return BenchSupport.object("atOrUnder22_222msPercent", 100.0 * under45 / size,
          "atOrUnder16_667msPercent", 100.0 * under60 / size);
    }

    private static double percentile(long[] sorted, double fraction) {
      double position = (sorted.length - 1) * fraction;
      int low = (int) Math.floor(position);
      int high = (int) Math.ceil(position);
      return sorted[low] + (sorted[high] - sorted[low]) * (position - low);
    }
  }
}
