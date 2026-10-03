package totalcross.bench.imagerendering;

import java.util.Arrays;

import totalcross.json.JSONArray;
import totalcross.json.JSONObject;
import totalcross.sys.RuntimeDiagnosticSnapshot;
import totalcross.sys.RuntimeDiagnostics;
import totalcross.sys.Settings;
import totalcross.sys.Vm;
import totalcross.ui.Container;
import totalcross.ui.Control;
import totalcross.ui.ImageControl;
import totalcross.ui.ScrollContainer;
import totalcross.ui.event.DragEvent;
import totalcross.ui.event.TimerEvent;
import totalcross.ui.event.TimerListener;
import totalcross.ui.gfx.Color;
import totalcross.ui.gfx.Graphics;
import totalcross.ui.image.Image;

/** Real-corpus scroll and explicit visible-image preparation workloads. */
final class ScrollWorkload implements TimerListener {
  private static final int COLUMNS = 3;
  private static final int EXPECTED_WIDTH = 540;
  private static final int EXPECTED_HEIGHT = 960;
  private static final int START_STABILIZE_MILLIS = 50;
  private static final int SCROLL_STEP = 120;
  private static final int PASS_COUNT = 3;
  private static final int TIMER_MILLIS = 16;
  private static final String DRIVER_FIXED_STEP = "fixed-step";
  private static final String DRIVER_HISTORICAL = "historical-driver";

  private final ImageRenderingBenchmarkApp app;
  private final JSONObject config;
  private final boolean preparation;
  private final String scrollDriver;
  private final ScrollContainer mainContainer;
  private final ScrollContainer scroll;
  private final BenchSupport.DatasetEntry[] entries;
  private final ImageControl[] controls;
  private final Container[] rows;
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
  private int tileWidth;
  private int scrollMinimum;
  private int scrollMaximum;
  private boolean passPreparationReady;

  ScrollWorkload(ImageRenderingBenchmarkApp app, JSONObject config) throws Exception {
    this.app = app;
    this.config = config;
    String profile = config.getString("profile");
    preparation = profile.startsWith("prepared-") || profile.startsWith("combined-");
    scrollDriver = config.getString("scrollDriver");
    if (!DRIVER_FIXED_STEP.equals(scrollDriver) && !DRIVER_HISTORICAL.equals(scrollDriver)) {
      throw new IllegalArgumentException("unsupported scroll driver: " + scrollDriver);
    }
    if (DRIVER_HISTORICAL.equals(scrollDriver) && (!"default".equals(profile) || preparation)) {
      throw new IllegalArgumentException("historical-driver requires the default profile");
    }
    entries = BenchSupport.readDataset(config);
    if (entries.length != BenchSupport.EXPECTED_FILE_COUNT || entries.length % COLUMNS != 0) {
      throw new IllegalStateException("scroll workload requires 663 images arranged in complete rows");
    }
    controls = new ImageControl[entries.length];
    rows = new Container[entries.length / COLUMNS];
    requested = new boolean[entries.length];
    int requestedWidth = Math.max(1, config.getInt("width"));
    int requestedHeight = Math.max(1, config.getInt("height"));
    if (requestedWidth != EXPECTED_WIDTH || requestedHeight != EXPECTED_HEIGHT
        || Settings.screenWidth != EXPECTED_WIDTH || Settings.screenHeight != EXPECTED_HEIGHT) {
      throw new IllegalStateException("scroll workload requires logical resolution 540x960; config="
          + requestedWidth + "x" + requestedHeight + ", runtime=" + Settings.screenWidth + "x"
          + Settings.screenHeight);
    }
    viewportWidth = requestedWidth;
    viewportHeight = requestedHeight;
    BenchSupport.put(config, "requestedLogicalWidth", requestedWidth);
    BenchSupport.put(config, "requestedLogicalHeight", requestedHeight);
    BenchSupport.put(config, "width", viewportWidth);
    BenchSupport.put(config, "height", viewportHeight);
    mainContainer = new ScrollContainer();
    scroll = new ScrollContainer();
    app.add(mainContainer);
    mainContainer.setBackColor(Color.brighter(Color.BLUE));
    mainContainer.setRect(Control.LEFT, Control.TOP, Control.FILL, Control.FILL);
    scroll.setBackColor(Color.brighter(Color.BLUE));
    mainContainer.add(scroll, Control.LEFT, Control.TOP + 40, Control.FILL, Control.FILL - 60);
    tileWidth = (viewportWidth - 3) / COLUMNS;
    if (tileWidth < 1) {
      throw new IllegalStateException("screen is too narrow for three square image tiles");
    }
    String root = config.getString("datasetRoot");
    Container row = null;
    int controlsInRow = 0;
    for (int i = 0; i < entries.length; i++) {
      try {
        if (i % COLUMNS == 0) {
          int rowIndex = i / COLUMNS;
          if (rowIndex > 0 && controlsInRow != COLUMNS) {
            throw new IllegalStateException("each scroll row must contain exactly three ImageControls");
          }
          row = new Container();
          row.setBackColor(Color.darker(Color.GREEN));
          scroll.add(row, Control.LEFT, Control.AFTER + 2, viewportWidth, tileWidth);
          rows[rowIndex] = row;
          controlsInRow = 0;
        }
        Image image = BenchSupport.loadFilesystemImage(root + "/" + entries[i].path);
        Image thumbnail = image.getSmoothScaledInstance(tileWidth, tileWidth);
        image = null;
        ImageControl control = new ImageControl(thumbnail);
        row.add(control, Control.AFTER + 1, Control.TOP, tileWidth, tileWidth);
        controls[i] = control;
        controlsInRow++;
      } catch (Throwable failure) {
        loadFailures++;
        throw new IllegalStateException("cannot create image control for " + entries[i].path, failure);
      }
    }
    if (controlsInRow != COLUMNS || rows.length != 221 || controls.length != 663) {
      throw new IllegalStateException("scroll hierarchy must contain 221 rows and 663 image controls");
    }
    mainContainer.resize();
    scroll.resize();
    if (scroll.sbV == null) {
      throw new IllegalStateException("real workload vertical scrollbar is missing");
    }
    scrollMinimum = scroll.sbV.getMinimum();
    scrollMaximum = Math.max(scrollMinimum,
        scroll.sbV.getMaximum() - scroll.sbV.getVisibleItems());
    if (scrollMaximum <= scrollMinimum) {
      throw new IllegalStateException("real workload content does not extend beyond its viewport");
    }
    scroll.sbV.setValue(scrollMinimum);
    diagnosticsBefore = configureDiagnostics(true);
    JSONObject dataset = config.getJSONObject("dataset");
    System.out.println("P12_SCROLL_START fixture=ImageScrollRealWorkloadBenchmarkApp"
        + " imageControls=" + controls.length + " rows=" + rows.length + " columns=" + COLUMNS
        + " logicalSize=" + viewportWidth + "x" + viewportHeight + " tileWidth=" + tileWidth
        + " scrollMin=" + scrollMinimum + " scrollMax=" + scrollMaximum
        + " dataset=" + dataset.getString("id") + "/" + dataset.getString("version")
        + " runtimeSha=" + config.getString("runtimeSourceCommit") + " runtimeProfile=" + profile);
  }

  void start() {
    app.addTimerListener(this);
    scroll.sbV.setValue(scrollMinimum);
    schedule(START_STABILIZE_MILLIS);
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
      if (DRIVER_HISTORICAL.equals(scrollDriver)) {
        runHistoricalPass();
        return;
      }
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
    if (passNumber >= PASS_COUNT) {
      finish();
      return;
    }
    if (preparation && !passPreparationReady) {
      passPreparationReady = true;
      lastPreparedY = scroll.sbV.getValue();
      requestVisiblePreparation();
      return;
    }
    direction = passNumber == 1 ? -1 : 1;
    int startPosition = direction > 0 ? scrollMinimum : scrollMaximum;
    scroll.sbV.setValue(startPosition);
    lastStepNs = 0L;
    lastPaintNs = 0L;
    stepIntervals.clear();
    passPaintIntervals.clear();
    collectPaints = true;
    passStartedNs = System.nanoTime();
    if (preparation) {
      lastPreparedY = startPosition;
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
    int position = scroll.sbV.getValue();
    int endpoint = direction > 0 ? scrollMaximum : scrollMinimum;
    if (position == endpoint) {
      endPass();
      return;
    }
    int distance = Math.min(SCROLL_STEP, Math.abs(endpoint - position));
    if (!scroll.scrollContent(0, direction * distance, true)) {
      throw new IllegalStateException("scroll pass stopped before reaching its scrollbar endpoint");
    }
    if (preparation && shouldPrepare()) {
      requestVisiblePreparation();
    }
    if (scroll.sbV.getValue() == endpoint && !preparationPending) {
      endPass();
    }
  }

  private boolean shouldPrepare() {
    int position = scroll.getScrollPosition(DragEvent.DOWN);
    int interval = Math.max(1, scroll.getRect().height - tileWidth);
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
    int bottom = top + Math.max(1, scroll.getRect().height);
    int strideY = tileWidth + 2;
    for (int i = 0; i < entries.length; i++) {
      int itemTop = 2 + (i / COLUMNS) * strideY;
      if (!requested[i] && itemTop < bottom && itemTop + tileWidth > top) {
        requested[i] = true;
        requestedCount++;
      }
    }
  }

  private void endPass() {
    collectPaints = false;
    long wall = System.nanoTime() - passStartedNs;
    String name = passName(passNumber);
    String passDirection = direction > 0 ? "top-to-bottom" : "bottom-to-top";
    JSONObject pass = BenchSupport.object(
        "name", name,
        "direction", passDirection,
        "wallTimeNs", wall,
        "stepSampleCount", stepIntervals.size(),
        "stepIntervalNs", stepIntervals.toJsonArray(),
        "stepIntervalStatistics", stepIntervals.statistics(),
        "paintIntervalNs", passPaintIntervals.toJsonArray(),
        "paintIntervalStatistics", passPaintIntervals.statistics(),
        "scrollPositionEnd", scroll.getScrollPosition(DragEvent.DOWN));
    passes.put(pass);
    passNumber++;
    passPreparationReady = false;
    passStartedNs = 0L;
    if (passNumber < PASS_COUNT) {
      schedule(1);
    } else {
      finish();
    }
  }

  private void runHistoricalPass() throws Exception {
    int minimum = scroll.sbV.getMinimum();
    int endpoint = scrollMaximum;
    if (scroll.sbV.getValue() != minimum) {
      scroll.sbV.setValue(minimum);
    }
    collectPaints = false;

    SampleSeries frameIntervals = new SampleSeries();
    SampleSeries scrollWork = new SampleSeries();
    SampleSeries paintWork = new SampleSeries();
    SampleSeries workTime = new SampleSeries();
    JSONArray frameSamples = new JSONArray();
    long passStartNs = System.nanoTime();
    long previousFrameStartNs = 0L;
    int frameCount = 0;

    while (true) {
      long frameStartNs = System.nanoTime();
      long elapsedNs = frameStartNs - passStartNs;
      long nominalElapsedNs = (long) frameCount * ScrollTiming.HISTORICAL_CADENCE_NS;
      if (frameCount > 0 && elapsedNs < nominalElapsedNs) {
        long remainingNs = nominalElapsedNs - elapsedNs;
        Vm.sleep(ScrollTiming.boundedSleepMillis(remainingNs));
        continue;
      }

      int target = frameCount == 0 ? minimum
          : ScrollTiming.historicalTarget(minimum, endpoint, elapsedNs);
      int before = scroll.sbV.getValue();
      int requestedDelta = target - before;
      long activeWorkStartNs = System.nanoTime();
      long scrollWorkNs = 0L;
      if (requestedDelta != 0) {
        long scrollStartNs = System.nanoTime();
        if (!scroll.scrollContent(0, requestedDelta, true)) {
          throw new IllegalStateException("historical scroll stopped before its time-based target");
        }
        scrollWorkNs = Math.max(0L, System.nanoTime() - scrollStartNs);
      }
      int actualScroll = scroll.sbV.getValue();
      if (actualScroll != target) {
        throw new IllegalStateException("historical scroll did not reach its time-based target: target="
            + target + ", actual=" + actualScroll);
      }

      long paintStartNs = System.nanoTime();
      scroll.repaintNow();
      long paintWorkNs = Math.max(0L, System.nanoTime() - paintStartNs);
      long activeWorkNs = Math.max(0L, System.nanoTime() - activeWorkStartNs);
      long frameIntervalNs = frameCount == 0 ? 0L : frameStartNs - previousFrameStartNs;

      frameSamples.put(BenchSupport.object(
          "frameIndex", frameCount,
          "elapsedNs", elapsedNs,
          "targetScroll", target,
          "actualScroll", actualScroll,
          "requestedDelta", requestedDelta,
          "frameIntervalNs", frameIntervalNs,
          "scrollWorkNs", scrollWorkNs,
          "paintWorkNs", paintWorkNs,
          "workTimeNs", activeWorkNs));
      if (frameCount > 0) {
        frameIntervals.add(frameIntervalNs);
      }
      scrollWork.add(scrollWorkNs);
      paintWork.add(paintWorkNs);
      workTime.add(activeWorkNs);
      previousFrameStartNs = frameStartNs;
      frameCount++;

      if (actualScroll == endpoint && elapsedNs >= ScrollTiming.HISTORICAL_DURATION_NS) {
        break;
      }
    }

    long totalPassWallTimeNs = Math.max(0L, System.nanoTime() - passStartNs);
    int finalScrollPosition = scroll.sbV.getValue();
    if (finalScrollPosition != endpoint || frameCount == 0) {
      throw new IllegalStateException("historical scroll pass did not finish at the scrollbar endpoint");
    }
    app.removeTimerListener(this);
    JSONObject measurements = BenchSupport.object(
        "scrollDriver", DRIVER_HISTORICAL,
        "passDirection", "top-to-bottom",
        "passCount", 1,
        "targetDurationNs", ScrollTiming.HISTORICAL_DURATION_NS,
        "targetCadenceNs", ScrollTiming.HISTORICAL_CADENCE_NS,
        "frameCount", frameCount,
        "totalPassWallTimeNs", totalPassWallTimeNs,
        "frameSamples", frameSamples,
        "frameIntervalStatistics", frameIntervals.statistics(),
        "scrollWorkStatistics", scrollWork.statistics(),
        "paintWorkStatistics", paintWork.statistics(),
        "workTimeStatistics", workTime.statistics(),
        "finalScrollPosition", finalScrollPosition,
        "scrollEndpoint", endpoint,
        "diagnostics", JSONObject.NULL);
    JSONObject durations = BenchSupport.object("wallTime", totalPassWallTimeNs);
    app.emit(app.runRecord(measurements, durations, config.getInt("round"),
        config.getString("phase"), config.getString("family")));
    app.exit(0);
  }

  private static String passName(int index) {
    if (index == 0) {
      return "cold-forward";
    }
    if (index == 1) {
      return "warm-reverse";
    }
    return "warm-forward";
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
              "logicalViewportWidth", scroll.getRect().width,
              "logicalViewportHeight", scroll.getRect().height,
              "displayScale", getDisplayScale()),
          "logicalWindowWidth", viewportWidth,
          "logicalWindowHeight", viewportHeight,
          "imageControls", controls.length,
          "rows", rows.length,
          "columns", COLUMNS,
          "tileWidth", tileWidth,
          "scrollMinimum", scrollMinimum,
          "scrollMaximum", scrollMaximum,
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
      } else if (Boolean.TRUE.equals(config.opt("holdForVisualValidation"))) {
        scroll.sbV.setValue(scrollMinimum);
        scroll.repaintNow();
        System.out.println("P12_SCROLL_VALIDATION_READY; window is positioned at the first row for visual review");
        System.out.flush();
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
