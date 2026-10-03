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
import totalcross.ui.image.ImageDrawPathProbeAccess;

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
  private static final String DRIVER_PAINT_SPLIT = "paint-split-probe";
  private static final String DRIVER_PAINT_PREPARATION = "paint-preparation-probe";
  private static final String DRIVER_PHYSICAL_MAPPING = "physical-mapping-probe";
  private static final String DRIVER_DRAW_PATH = "draw-path-probe";
  private static final int PAINT_SPLIT_SAMPLE_COUNT = 5;
  private static final int PAINT_PREPARATION_NOT_STARTED = 0;
  private static final int PAINT_PREPARATION_WAITING = 1;
  private static final int PAINT_PREPARATION_CALLBACK_COMPLETE = 2;

  private final ImageRenderingBenchmarkApp app;
  private final JSONObject config;
  private final boolean preparation;
  private final String scrollDriver;
  private final PaintProbeCounters paintProbeCounters;
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
  private PaintSplitPhase unpreparedPaints;
  private volatile int paintPreparationProbeState;
  private int paintPreparationRequestCount;
  private volatile int paintPreparationCallbackCount;
  private volatile long paintPreparationCallStartNs;
  private volatile long paintPreparationCallbackNs;
  private volatile long paintPreparationWaitNs;
  private int paintPreparationVisibleControlsAtRequest;
  private int paintPreparationScrollPositionBefore;
  private long paintPreparationPhaseAStartNs;
  private long paintPreparationPhaseAEndNs;
  private long paintPreparationPhaseCStartNs;
  private long paintPreparationPhaseCEndNs;
  private RuntimeDiagnosticSnapshot paintPreparationDiagnosticsBefore;
  private RuntimeDiagnosticSnapshot paintPreparationDiagnosticsAfter;
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
    if (!DRIVER_FIXED_STEP.equals(scrollDriver) && !DRIVER_HISTORICAL.equals(scrollDriver)
        && !DRIVER_PAINT_SPLIT.equals(scrollDriver) && !DRIVER_PAINT_PREPARATION.equals(scrollDriver)
        && !DRIVER_DRAW_PATH.equals(scrollDriver) && !DRIVER_PHYSICAL_MAPPING.equals(scrollDriver)) {
      throw new IllegalArgumentException("unsupported scroll driver: " + scrollDriver);
    }
    if ((DRIVER_HISTORICAL.equals(scrollDriver) || DRIVER_PAINT_SPLIT.equals(scrollDriver)
        || DRIVER_PAINT_PREPARATION.equals(scrollDriver) || DRIVER_DRAW_PATH.equals(scrollDriver) || DRIVER_PHYSICAL_MAPPING.equals(scrollDriver))
        && (!"default".equals(profile) || preparation)) {
      throw new IllegalArgumentException(scrollDriver + " requires the default profile");
    }
    paintProbeCounters = DRIVER_PAINT_SPLIT.equals(scrollDriver) || DRIVER_PAINT_PREPARATION.equals(scrollDriver)
        || DRIVER_DRAW_PATH.equals(scrollDriver)
        ? new PaintProbeCounters() : null;
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
    scroll = paintProbeCounters == null ? new ScrollContainer() : new MeasuredScrollContainer();
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
          row = paintProbeCounters == null ? new Container() : new MeasuredRow(paintProbeCounters);
          row.setBackColor(Color.darker(Color.GREEN));
          scroll.add(row, Control.LEFT, Control.AFTER + 2, viewportWidth, tileWidth);
          rows[rowIndex] = row;
          controlsInRow = 0;
        }
        Image image = BenchSupport.loadFilesystemImage(root + "/" + entries[i].path);
        Image thumbnail = image.getSmoothScaledInstance(tileWidth, tileWidth);
        image = null;
        ImageControl control = paintProbeCounters == null ? new ImageControl(thumbnail)
            : new MeasuredImageControl(thumbnail, paintProbeCounters);
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
      if (DRIVER_PHYSICAL_MAPPING.equals(scrollDriver)) {
        runPhysicalMappingProbe();
        return;
      }
      if (DRIVER_DRAW_PATH.equals(scrollDriver)) {
        runDrawPathProbe();
        return;
      }
      if (DRIVER_HISTORICAL.equals(scrollDriver)) {
        runHistoricalPass();
        return;
      }
      if (DRIVER_PAINT_SPLIT.equals(scrollDriver)) {
        runPaintSplitProbe();
        return;
      }
      if (DRIVER_PAINT_PREPARATION.equals(scrollDriver)) {
        if (paintPreparationProbeState == PAINT_PREPARATION_NOT_STARTED) {
          startPaintPreparationProbe();
        } else if (paintPreparationProbeState == PAINT_PREPARATION_CALLBACK_COMPLETE) {
          finishPaintPreparationProbe();
        } else {
          throw new IllegalStateException("paint-preparation-probe timer fired before preparation callback");
        }
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

  private void runPhysicalMappingProbe() throws Exception {
    moveToPaintProbePosition(0);
    if (countVisibleImageControls(0) != 18) {
      throw new IllegalStateException("physical mapping probe requires eighteen visible controls");
    }
    Image[] retainedImages = new Image[18];
    ImageControl[] retainedControls = new ImageControl[18];
    for (int i = 0; i < 18; i++) {
      retainedImages[i] = controls[i].getImage();
      retainedControls[i] = controls[i];
    }
    scroll.repaintNow();
    requirePaintProbePosition(0);
    JSONArray individual = new JSONArray();
    for (int i = 0; i < 18; i++) {
      requireDrawPathIdentity(i, retainedControls[i], retainedImages[i], rows[i / COLUMNS]);
      Graphics graphics = controls[i].getGraphics();
      JSONObject metadata = ImageDrawPathProbeAccess.mappingMetadata(retainedImages[i], graphics);
      BenchSupport.put(metadata, "drawX", controls[i].lastX);
      BenchSupport.put(metadata, "drawY", controls[i].lastY);
      individual.put(BenchSupport.object("datasetIndex", i, "rowIndex", i / COLUMNS,
          "path", entries[i].path, "format", entries[i].format,
          "intrinsicWidth", entries[i].width, "intrinsicHeight", entries[i].height,
          "plan", metadata));
      requireDrawPathIdentity(i, retainedControls[i], retainedImages[i], rows[i / COLUMNS]);
    }
    app.removeTimerListener(this);
    JSONObject measurements = BenchSupport.object("scrollDriver", DRIVER_PHYSICAL_MAPPING,
        "imageControls", controls.length, "rows", rows.length, "columns", COLUMNS, "tileWidth", tileWidth,
        "scrollPosition", 0, "stabilizationRepaints", 1, "perControlSamples", 18,
        "prepareRequests", 0, "preparation", false, "timedPaintSamples", 0,
        "sameImageInstances", true, "sameControlInstances", true, "sameRowInstances", true,
        "perControl", individual,
        "canvasMatrixEvidence", "native skia_setSurfaceScale resets matrix then scales by Graphics.getContentScale",
        "axes", BenchSupport.object("logicalViewportWidth", scroll.getRect().width,
            "logicalViewportHeight", scroll.getRect().height, "displayScale", getDisplayScale()));
    app.emit(app.runRecord(measurements, BenchSupport.object("wallTime", 0L),
        config.getInt("round"), config.getString("phase"), config.getString("family")));
    app.exit(0);
  }

  private void runDrawPathProbe() throws Exception {
    if (paintProbeCounters == null || !(scroll instanceof MeasuredScrollContainer) || scrollMinimum != 0) {
      throw new IllegalStateException("draw-path-probe requires measured controls at top position zero");
    }
    moveToPaintProbePosition(0);
    // Retain the exact visible row/control/Image references before stabilization.
    int visibleCount = countVisibleImageControls(0);
    if (visibleCount != 18) {
      throw new IllegalStateException("draw-path-probe requires eighteen visible controls");
    }
    ImageControl[] visibleControls = new ImageControl[visibleCount];
    Image[] visibleImages = new Image[visibleCount];
    Container[] visibleRows = new Container[visibleCount];
    int[] visibleIndices = new int[visibleCount];
    int visibleIndex = 0;
    for (int i = 0; i < controls.length; i++) {
      int itemTop = 2 + (i / COLUMNS) * (tileWidth + 2);
      if (itemTop < scroll.getRect().height && itemTop + tileWidth > 0) {
        visibleControls[visibleIndex] = controls[i];
        visibleImages[visibleIndex] = controls[i].getImage();
        visibleRows[visibleIndex] = rows[i / COLUMNS];
        visibleIndices[visibleIndex++] = i;
      }
    }
    scroll.repaintNow(); // exactly one ordinary untimed stabilization repaint
    requirePaintProbePosition(0);
    paintProbeCounters.reset();
    ImageDrawPathProbeAccess.reset();
    long aggregateStartNs = System.nanoTime();
    ((MeasuredScrollContainer) scroll).paintTreeOnly();
    long aggregateElapsedNs = System.nanoTime() - aggregateStartNs;
    JSONObject aggregateAccounting = ImageDrawPathProbeAccess.snapshot();
    JSONObject aggregate = drawPathSample(aggregateAccounting, aggregateElapsedNs, "paintTreeNs");
    if (paintProbeCounters.rowPaintCount != 6 || paintProbeCounters.imagePaintCount != 18) {
      throw new IllegalStateException("draw-path-probe aggregate must paint six rows/eighteen controls");
    }
    JSONArray individual = new JSONArray();
    long[] elapsedTimes = new long[visibleCount];
    long sumNs = 0L;
    boolean unexpected = ImageDrawPathProbeAccess.unexpectedDisabledPathActivity(aggregateAccounting);
    for (int i = 0; i < visibleCount; i++) {
      requireDrawPathIdentity(visibleIndices[i], visibleControls[i], visibleImages[i], visibleRows[i]);
      paintProbeCounters.reset();
      ImageDrawPathProbeAccess.reset();
      long start = System.nanoTime();
      visibleControls[i].onPaint(visibleControls[i].getGraphics());
      long elapsed = System.nanoTime() - start;
      JSONObject accounting = ImageDrawPathProbeAccess.snapshot();
      requireDrawPathIdentity(visibleIndices[i], visibleControls[i], visibleImages[i], visibleRows[i]);
      elapsedTimes[i] = elapsed;
      sumNs += elapsed;
      JSONObject sample = drawPathSample(accounting, elapsed, "imageControlPaintNs");
      BenchSupport.put(sample, "datasetIndex", visibleIndices[i]);
      BenchSupport.put(sample, "path", entries[visibleIndices[i]].path);
      BenchSupport.put(sample, "format", entries[visibleIndices[i]].format);
      BenchSupport.put(sample, "rowIndex", visibleIndices[i] / COLUMNS);
      BenchSupport.put(sample, "copyRectAttemptsExceedOne", accounting.getInt("copyRectPlanAttempts") > 1);
      unexpected |= ImageDrawPathProbeAccess.unexpectedDisabledPathActivity(accounting);
      individual.put(sample);
    }
    for (int i = 0; i < visibleCount; i++) {
      requireDrawPathIdentity(visibleIndices[i], visibleControls[i], visibleImages[i], visibleRows[i]);
    }
    Arrays.sort(elapsedTimes);
    JSONObject measurements = BenchSupport.object(
        "scrollDriver", DRIVER_DRAW_PATH, "imageControls", controls.length, "rows", rows.length,
        "columns", COLUMNS, "tileWidth", tileWidth, "scrollPosition", 0,
        "stabilizationRepaints", 1, "aggregateSamples", 1, "perControlSamples", 18,
        "prepareRequests", 0, "preparation", false, "diagnostics", JSONObject.NULL,
        "sameImageInstances", true, "sameControlInstances", true, "sameRowInstances", true,
        "physicalCopyAccounting", "hit-only; attempt/fallback counters unavailable",
        "lastStatusScope", "last copyRect plan attempt in each accounting sample",
        "aggregate", aggregate, "perControl", individual, "unexpectedDisabledPathActivity", unexpected,
        "individualTimingNs", BenchSupport.object("min", elapsedTimes[0],
            "median", elapsedTimes[8] + (elapsedTimes[9] - elapsedTimes[8]) / 2.0,
            "max", elapsedTimes[17], "sum", sumNs),
        "axes", BenchSupport.object("requestedLogicalViewportWidth", config.getInt("width"),
            "requestedLogicalViewportHeight", config.getInt("height"),
            "logicalViewportWidth", scroll.getRect().width, "logicalViewportHeight", scroll.getRect().height,
            "displayScale", getDisplayScale()));
    app.removeTimerListener(this);
    app.emit(app.runRecord(measurements, BenchSupport.object("wallTime", aggregateElapsedNs + sumNs),
        config.getInt("round"), config.getString("phase"), config.getString("family")));
    app.exit(0);
  }

  private void requireDrawPathIdentity(int index, ImageControl control, Image image, Container row) {
    requirePaintProbePosition(0);
    if (controls[index] != control || control.getImage() != image || rows[index / COLUMNS] != row) {
      throw new IllegalStateException("draw-path-probe changed its row/control/Image instances");
    }
  }

  private JSONObject drawPathSample(JSONObject accounting, long elapsedNs, String timingKey) throws Exception {
    requirePaintProbePosition(0);
    int status = accounting.getInt("copyRectPlanLastStatus");
    return BenchSupport.object(timingKey, elapsedNs, "counters", accounting,
        "rawStatus", status, "statusHex", ImageDrawPathProbeAccess.statusHex(status),
        "statusFlags", ImageDrawPathProbeAccess.decodeStatus(status),
        "classification", ImageDrawPathProbeAccess.classify(accounting),
        "rowPaintCount", paintProbeCounters.rowPaintCount, "rowPaintNs", paintProbeCounters.rowPaintNs,
        "imagePaintCount", paintProbeCounters.imagePaintCount, "imagePaintNs", paintProbeCounters.imagePaintNs,
        "scrollPosition", scroll.sbV.getValue());
  }

  private void runPaintSplitProbe() throws Exception {
    if (paintProbeCounters == null || !(scroll instanceof MeasuredScrollContainer)) {
      throw new IllegalStateException("paint-split-probe requires benchmark paint instrumentation");
    }
    int middle = scrollMinimum + (scrollMaximum - scrollMinimum) / 2;
    int[] positions = {scrollMinimum, middle, scrollMaximum};
    String[] labels = {"top", "middle", "bottom"};
    JSONArray positionResults = new JSONArray();
    long probeStartedNs = System.nanoTime();
    boolean fullCorpusPaintDetected = false;

    for (int positionIndex = 0; positionIndex < positions.length; positionIndex++) {
      int expectedPosition = positions[positionIndex];
      moveToPaintProbePosition(expectedPosition);
      scroll.repaintNow(); // one untimed stabilization repaint at this fixed position
      requirePaintProbePosition(expectedPosition);

      PaintSplitPhase tree = measurePaintSplitPhase(false, expectedPosition);
      requirePaintProbePosition(expectedPosition);
      PaintSplitPhase repaint = measurePaintSplitPhase(true, expectedPosition);
      requirePaintProbePosition(expectedPosition);

      boolean comparable = sameDistribution(tree.rowCounts, repaint.rowCounts)
          && sameDistribution(tree.imageCounts, repaint.imageCounts);
      Object residual = comparable
          ? Double.valueOf(repaint.paintTimes.percentileValue(0.50)
              - tree.paintTimes.percentileValue(0.50))
          : JSONObject.NULL;
      boolean fullCorpusAtPosition = tree.paintsFullCorpus() || repaint.paintsFullCorpus();
      fullCorpusPaintDetected |= fullCorpusAtPosition;
      JSONObject viewport = scrollViewport();
      positionResults.put(BenchSupport.object(
          "label", labels[positionIndex],
          "requestedPosition", expectedPosition,
          "scrollPosition", scroll.sbV.getValue(),
          "scrollContentPosition", scroll.getScrollPosition(DragEvent.DOWN),
          "scrollViewport", viewport,
          "paintTreeOnly", tree.toJson("paintTreeNs"),
          "repaintNow", repaint.toJson("repaintNowNs"),
          "visibleWorkComparable", comparable,
          "estimatedPresentResidualNs", residual,
          "fullCorpusPaintDetected", fullCorpusAtPosition));
    }

    long totalProbeWallTimeNs = Math.max(0L, System.nanoTime() - probeStartedNs);
    app.removeTimerListener(this);
    JSONObject measurements = BenchSupport.object(
        "scrollDriver", DRIVER_PAINT_SPLIT,
        "positionCount", positions.length,
        "samplesPerMeasurement", PAINT_SPLIT_SAMPLE_COUNT,
        "imageControls", controls.length,
        "rows", rows.length,
        "columns", COLUMNS,
        "tileWidth", tileWidth,
        "scrollMinimum", scrollMinimum,
        "scrollMaximum", scrollMaximum,
        "positions", positionResults,
        "fullCorpusPaintDetected", fullCorpusPaintDetected,
        "preparation", false,
        "diagnostics", JSONObject.NULL,
        "axes", BenchSupport.object(
            "requestedLogicalViewportWidth", config.getInt("requestedLogicalWidth"),
            "requestedLogicalViewportHeight", config.getInt("requestedLogicalHeight"),
            "logicalViewportWidth", scroll.getRect().width,
            "logicalViewportHeight", scroll.getRect().height,
            "displayScale", getDisplayScale()));
    JSONObject durations = BenchSupport.object("wallTime", totalProbeWallTimeNs);
    app.emit(app.runRecord(measurements, durations, config.getInt("round"),
        config.getString("phase"), config.getString("family")));
    app.exit(0);
  }

  private void moveToPaintProbePosition(int target) {
    int delta = target - scroll.sbV.getValue();
    if (delta != 0 && !scroll.scrollContent(0, delta, true)) {
      throw new IllegalStateException("paint probe could not move to its fixed viewport position");
    }
    requirePaintProbePosition(target);
  }

  private void requirePaintProbePosition(int expected) {
    int scrollbarPosition = scroll.sbV.getValue();
    int contentPosition = scroll.getScrollPosition(DragEvent.DOWN);
    if (scrollbarPosition != expected || contentPosition != expected) {
      throw new IllegalStateException("paint probe viewport position is not synchronized: expected="
          + expected + ", scrollbar=" + scrollbarPosition + ", content=" + contentPosition);
    }
  }

  private JSONObject scrollViewport() {
    return BenchSupport.object("x", scroll.getRect().x, "y", scroll.getRect().y,
        "width", scroll.getRect().width, "height", scroll.getRect().height);
  }

  private PaintSplitPhase measurePaintSplitPhase(boolean fullRepaint, int expectedPosition) {
    return measurePaintSplitPhase(fullRepaint, expectedPosition, false);
  }

  private PaintSplitPhase measurePaintSplitPhase(boolean fullRepaint, int expectedPosition,
      boolean preparationComparison) {
    PaintSplitPhase result = new PaintSplitPhase(PAINT_SPLIT_SAMPLE_COUNT, preparationComparison);
    for (int sampleIndex = 0; sampleIndex < PAINT_SPLIT_SAMPLE_COUNT; sampleIndex++) {
      requirePaintProbePosition(expectedPosition);
      paintProbeCounters.reset();
      long startedNs = System.nanoTime();
      if (fullRepaint) {
        scroll.repaintNow();
      } else {
        ((MeasuredScrollContainer) scroll).paintTreeOnly();
      }
      long elapsedNs = Math.max(0L, System.nanoTime() - startedNs);
      requirePaintProbePosition(expectedPosition);
      result.add(sampleIndex, fullRepaint ? "repaintNowNs" : "paintTreeNs", elapsedNs,
          paintProbeCounters, scroll.sbV.getValue(), scroll.getScrollPosition(DragEvent.DOWN));
    }
    return result;
  }

  private void startPaintPreparationProbe() {
    if (paintProbeCounters == null || !(scroll instanceof MeasuredScrollContainer)) {
      throw new IllegalStateException("paint-preparation-probe requires benchmark paint instrumentation");
    }
    moveToPaintProbePosition(scrollMinimum);
    scroll.repaintNow(); // one untimed stabilization repaint before the unprepared samples
    requirePaintProbePosition(scrollMinimum);
    paintPreparationPhaseAStartNs = System.nanoTime();
    unpreparedPaints = measurePaintSplitPhase(false, scrollMinimum, true);
    paintPreparationPhaseAEndNs = System.nanoTime();
    requirePaintProbePosition(scrollMinimum);
    paintPreparationScrollPositionBefore = scroll.getScrollPosition(DragEvent.DOWN);
    paintPreparationVisibleControlsAtRequest = countVisibleImageControls(paintPreparationScrollPositionBefore);
    if (paintPreparationRequestCount != 0) {
      throw new IllegalStateException("paint-preparation-probe attempted more than one preparation request");
    }
    paintPreparationDiagnosticsBefore = RuntimeDiagnostics.isSupported() ? RuntimeDiagnostics.snapshot() : null;
    paintPreparationProbeState = PAINT_PREPARATION_WAITING;
    paintPreparationCallStartNs = System.nanoTime();
    paintPreparationRequestCount++;
    scroll.prepareForDisplay(new Runnable() {
      @Override
      public void run() {
        if (!recordPaintPreparationCallback()) {
          app.fail(new IllegalStateException("paint-preparation-probe received more than one callback"));
          return;
        }
        paintPreparationCallbackNs = System.nanoTime();
        paintPreparationWaitNs = paintPreparationCallbackNs - paintPreparationCallStartNs;
        paintPreparationDiagnosticsAfter = RuntimeDiagnostics.isSupported() ? RuntimeDiagnostics.snapshot() : null;
        paintPreparationProbeState = PAINT_PREPARATION_CALLBACK_COMPLETE;
        schedule(1);
      }
    });
  }

  private boolean recordPaintPreparationCallback() {
    synchronized (this) {
      paintPreparationCallbackCount++;
      return paintPreparationCallbackCount == 1;
    }
  }

  private void finishPaintPreparationProbe() throws Exception {
    if (paintPreparationRequestCount != 1 || paintPreparationCallbackCount != 1
        || paintPreparationProbeState != PAINT_PREPARATION_CALLBACK_COMPLETE) {
      throw new IllegalStateException("paint-preparation-probe did not complete exactly one preparation callback");
    }
    requirePaintProbePosition(scrollMinimum);
    paintPreparationPhaseCStartNs = System.nanoTime();
    PaintSplitPhase preparedPaints = measurePaintSplitPhase(false, scrollMinimum, true);
    paintPreparationPhaseCEndNs = System.nanoTime();
    requirePaintProbePosition(scrollMinimum);
    int paintPreparationScrollPositionAfter = scroll.getScrollPosition(DragEvent.DOWN);
    boolean sameViewport = paintPreparationScrollPositionBefore == scrollMinimum
        && paintPreparationScrollPositionAfter == scrollMinimum;
    boolean sameControlCounts = Arrays.equals(unpreparedPaints.rowCounts, preparedPaints.rowCounts)
        && Arrays.equals(unpreparedPaints.imageCounts, preparedPaints.imageCounts);
    boolean requestVisibilityMatchesPaint = paintPreparationVisibleControlsAtRequest > 0;
    for (int i = 0; i < unpreparedPaints.imageCounts.length; i++) {
      requestVisibilityMatchesPaint &= unpreparedPaints.imageCounts[i] == paintPreparationVisibleControlsAtRequest
          && preparedPaints.imageCounts[i] == paintPreparationVisibleControlsAtRequest;
    }
    boolean timingComparisonValid = sameViewport && sameControlCounts && requestVisibilityMatchesPaint;
    Object absoluteDifferenceNs = JSONObject.NULL;
    Object percentageReduction = JSONObject.NULL;
    if (timingComparisonValid) {
      double difference = unpreparedPaints.paintTimes.percentileValue(0.50)
          - preparedPaints.paintTimes.percentileValue(0.50);
      absoluteDifferenceNs = Double.valueOf(difference);
      percentageReduction = unpreparedPaints.paintTimes.percentileValue(0.50) == 0.0
          ? JSONObject.NULL
          : Double.valueOf(100.0 * difference / unpreparedPaints.paintTimes.percentileValue(0.50));
    }
    JSONArray phaseOrder = new JSONArray();
    phaseOrder.put("A-unprepared");
    phaseOrder.put("B-prepareForDisplay-call");
    phaseOrder.put("B-callback-complete");
    phaseOrder.put("C-prepared");
    JSONObject measurements = BenchSupport.object(
        "scrollDriver", DRIVER_PAINT_PREPARATION,
        "imageControls", controls.length,
        "rows", rows.length,
        "columns", COLUMNS,
        "tileWidth", tileWidth,
        "scrollMinimum", scrollMinimum,
        "scrollPositionBeforePreparation", paintPreparationScrollPositionBefore,
        "scrollPositionAfterPreparation", paintPreparationScrollPositionAfter,
        "phaseOrder", phaseOrder,
        "phaseAStartedNs", paintPreparationPhaseAStartNs,
        "phaseACompletedNs", paintPreparationPhaseAEndNs,
        "prepareRequests", paintPreparationRequestCount,
        "prepareCallStartNs", paintPreparationCallStartNs,
        "prepareCallbackNs", paintPreparationCallbackNs,
        "prepareWaitNs", paintPreparationWaitNs,
        "callbackCompletions", paintPreparationCallbackCount,
        "prepareStatus", "callback-completed",
        "visibleImageControlsAtRequest", paintPreparationVisibleControlsAtRequest,
        "phaseCStartedNs", paintPreparationPhaseCStartNs,
        "phaseCCompletedNs", paintPreparationPhaseCEndNs,
        "paintSamplesPerPhase", PAINT_SPLIT_SAMPLE_COUNT,
        "unpreparedPaintTree", unpreparedPaints.toJson("paintTreeNs"),
        "preparedPaintTree", preparedPaints.toJson("paintTreeNs"),
        "unpreparedImageControlPaintP50PerSampleNs", unpreparedPaints.imagePaintP50Ns(),
        "preparedImageControlPaintP50PerSampleNs", preparedPaints.imagePaintP50Ns(),
        "sameViewport", sameViewport,
        "sameControlCounts", sameControlCounts,
        "requestVisibilityMatchesPaint", requestVisibilityMatchesPaint,
        "timingComparisonValid", timingComparisonValid,
        "comparisonStatus", comparisonStatus(sameViewport, sameControlCounts, requestVisibilityMatchesPaint),
        "absolutePaintTreeDifferenceNs", absoluteDifferenceNs,
        "paintTreeReductionPercent", percentageReduction,
        "explicitPreparationPerformed", true,
        "preparation", false,
        "diagnostics", JSONObject.NULL,
        "preparationRuntimeDiagnosticsAvailable",
            paintPreparationDiagnosticsBefore != null && paintPreparationDiagnosticsAfter != null,
        "preparationRuntimeDiagnostics", preparationDiagnosticDelta(),
        "axes", BenchSupport.object(
            "requestedLogicalViewportWidth", config.getInt("requestedLogicalWidth"),
            "requestedLogicalViewportHeight", config.getInt("requestedLogicalHeight"),
            "logicalViewportWidth", scroll.getRect().width,
            "logicalViewportHeight", scroll.getRect().height,
            "displayScale", getDisplayScale()));
    long totalProbeWallTimeNs = Math.max(0L, paintPreparationPhaseCEndNs - paintPreparationPhaseAStartNs);
    app.removeTimerListener(this);
    JSONObject durations = BenchSupport.object("wallTime", totalProbeWallTimeNs);
    app.emit(app.runRecord(measurements, durations, config.getInt("round"),
        config.getString("phase"), config.getString("family")));
    app.exit(0);
  }

  private int countVisibleImageControls(int position) {
    int bottom = position + Math.max(1, scroll.getRect().height);
    int strideY = tileWidth + 2;
    int visible = 0;
    for (int i = 0; i < controls.length; i++) {
      int itemTop = 2 + (i / COLUMNS) * strideY;
      if (controls[i] != null && itemTop < bottom && itemTop + tileWidth > position) {
        visible++;
      }
    }
    return visible;
  }

  private Object preparationDiagnosticDelta() {
    if (paintPreparationDiagnosticsBefore == null || paintPreparationDiagnosticsAfter == null) {
      return JSONObject.NULL;
    }
    RuntimeDiagnosticSnapshot delta = paintPreparationDiagnosticsAfter.deltaSince(paintPreparationDiagnosticsBefore);
    return BenchSupport.object(
        "diagnosticsEnabled", false,
        "image", diagnosticDomain(delta, RuntimeDiagnosticSnapshot.Domain.IMAGE),
        "prefetch", diagnosticDomain(delta, RuntimeDiagnosticSnapshot.Domain.PREFETCH));
  }

  private static String comparisonStatus(boolean sameViewport, boolean sameControlCounts,
      boolean requestVisibilityMatchesPaint) {
    if (!sameViewport) {
      return "invalid-position-mismatch";
    }
    if (!sameControlCounts) {
      return "invalid-visible-count-mismatch";
    }
    if (!requestVisibilityMatchesPaint) {
      return "invalid-request-visible-count-mismatch";
    }
    return "valid";
  }

  private static boolean sameDistribution(int[] left, int[] right) {
    if (left.length != right.length) {
      return false;
    }
    int[] sortedLeft = Arrays.copyOf(left, left.length);
    int[] sortedRight = Arrays.copyOf(right, right.length);
    Arrays.sort(sortedLeft);
    Arrays.sort(sortedRight);
    return Arrays.equals(sortedLeft, sortedRight);
  }

  private static final class PaintProbeCounters {
    int rowPaintCount;
    int imagePaintCount;
    long rowPaintNs;
    long imagePaintNs;

    void reset() {
      rowPaintCount = 0;
      imagePaintCount = 0;
      rowPaintNs = 0L;
      imagePaintNs = 0L;
    }

    void recordRow(long elapsedNs) {
      rowPaintCount++;
      rowPaintNs += Math.max(0L, elapsedNs);
    }

    void recordImage(long elapsedNs) {
      imagePaintCount++;
      imagePaintNs += Math.max(0L, elapsedNs);
    }
  }

  private static final class MeasuredRow extends Container {
    private final PaintProbeCounters counters;

    MeasuredRow(PaintProbeCounters counters) {
      this.counters = counters;
    }

    @Override
    public void onPaint(Graphics graphics) {
      long startedNs = System.nanoTime();
      try {
        super.onPaint(graphics);
      } finally {
        counters.recordRow(System.nanoTime() - startedNs);
      }
    }
  }

  private static final class MeasuredImageControl extends ImageControl {
    private final PaintProbeCounters counters;

    MeasuredImageControl(Image image, PaintProbeCounters counters) {
      super(image);
      this.counters = counters;
    }

    @Override
    public void onPaint(Graphics graphics) {
      long startedNs = System.nanoTime();
      try {
        super.onPaint(graphics);
      } finally {
        counters.recordImage(System.nanoTime() - startedNs);
      }
    }
  }

  private static final class MeasuredScrollContainer extends ScrollContainer {
    void paintTreeOnly() {
      Graphics graphics = getGraphics();
      if (graphics == null) {
        throw new IllegalStateException("paint probe has no graphics surface");
      }
      onPaint(graphics);
      paintChildren();
    }
  }

  private static final class PaintSplitPhase {
    private final JSONArray samples = new JSONArray();
    private final SampleSeries paintTimes = new SampleSeries();
    private final boolean preparationComparison;
    private final SampleSeries imagePaintTimes;
    private final int[] rowCounts;
    private final int[] imageCounts;
    private long cumulativeRowPaintNs;
    private long cumulativeImagePaintNs;

    PaintSplitPhase(int sampleCount) {
      this(sampleCount, false);
    }

    PaintSplitPhase(int sampleCount, boolean preparationComparison) {
      this.preparationComparison = preparationComparison;
      imagePaintTimes = preparationComparison ? new SampleSeries() : null;
      rowCounts = new int[sampleCount];
      imageCounts = new int[sampleCount];
    }

    void add(int sampleIndex, String timingKey, long elapsedNs, PaintProbeCounters counters,
        int scrollbarPosition, int contentPosition) {
      rowCounts[sampleIndex] = counters.rowPaintCount;
      imageCounts[sampleIndex] = counters.imagePaintCount;
      cumulativeRowPaintNs += counters.rowPaintNs;
      cumulativeImagePaintNs += counters.imagePaintNs;
      paintTimes.add(elapsedNs);
      if (imagePaintTimes != null) {
        imagePaintTimes.add(counters.imagePaintNs);
      }
      JSONObject sample = BenchSupport.object(
          "sampleIndex", sampleIndex,
          timingKey, elapsedNs,
          "rowPaintCount", counters.rowPaintCount,
          "rowPaintNs", counters.rowPaintNs,
          "imagePaintCount", counters.imagePaintCount,
          "imagePaintNs", counters.imagePaintNs,
          "scrollbarPosition", scrollbarPosition,
          "scrollContentPosition", contentPosition);
      if (preparationComparison) {
        BenchSupport.put(sample, "scrollPosition", contentPosition);
      }
      samples.put(sample);
    }

    boolean paintsFullCorpus() {
      for (int i = 0; i < rowCounts.length; i++) {
        if (rowCounts[i] >= 221 || imageCounts[i] >= 663) {
          return true;
        }
      }
      return false;
    }

    JSONObject toJson(String timingKey) {
      JSONObject result = BenchSupport.object(
          "sampleCount", paintTimes.size(),
          "samples", samples,
          "statistics", paintTimes.statistics(),
          "rowPaintCounts", intArray(rowCounts),
          "imagePaintCounts", intArray(imageCounts),
          "cumulativeRowPaintNs", cumulativeRowPaintNs,
          "cumulativeImageControlPaintNs", cumulativeImagePaintNs,
          "timingKey", timingKey);
      if (preparationComparison) {
        BenchSupport.put(result, "imageControlPaintP50PerSampleNs", imagePaintTimes.percentileValue(0.50));
      }
      return result;
    }

    double imagePaintP50Ns() {
      return imagePaintTimes == null ? 0.0 : imagePaintTimes.percentileValue(0.50);
    }

    private static JSONArray intArray(int[] values) {
      JSONArray result = new JSONArray();
      for (int value : values) {
        result.put(value);
      }
      return result;
    }
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

    double percentileValue(double fraction) {
      if (size == 0) {
        return 0.0;
      }
      long[] sorted = Arrays.copyOf(values, size);
      Arrays.sort(sorted);
      return percentile(sorted, fraction);
    }
  }
}
