package totalcross.bench.imagerendering;

import totalcross.json.JSONArray;
import totalcross.json.JSONObject;
import totalcross.sys.Vm;
import totalcross.ui.gfx.Graphics;
import totalcross.ui.image.Image;

/** Sequential and seeded-random decode/materialization work over image-scroll/v1. */
final class DecodeWorkload {
  private DecodeWorkload() { }

  static void run(ImageRenderingBenchmarkApp app, JSONObject config) throws Exception {
    BenchSupport.DatasetEntry[] entries = BenchSupport.readDataset(config);
    String source = config.getString("source");
    String scale = config.getString("scale");
    String order = config.getString("order");
    if (!("filesystem".equals(source) || "tcz".equals(source))) {
      throw new IllegalArgumentException("unknown decode source: " + source);
    }
    if (!("full".equals(scale) || "half".equals(scale))) {
      throw new IllegalArgumentException("unknown decode scale: " + scale);
    }
    if (!("sequential".equals(order) || "seeded-random".equals(order))) {
      throw new IllegalArgumentException("unknown decode order: " + order);
    }
    int[] indices = sequence(entries.length, order);
    JSONArray imageResults = new JSONArray();
    int succeeded = 0;
    int failed = 0;
    long decodeNanos = 0L;
    long wallStart = System.nanoTime();
    for (int index = 0; index < indices.length; index++) {
      BenchSupport.DatasetEntry entry = entries[indices[index]];
      int requestedWidth = "half".equals(scale) ? Math.max(1, entry.width / 2) : entry.width;
      int requestedHeight = "half".equals(scale) ? Math.max(1, entry.height / 2) : entry.height;
      long started = System.nanoTime();
      Image sourceImage = null;
      Image resultImage = null;
      Graphics materialized = null;
      try {
        String path = imagePath(config, source, entry.path);
        sourceImage = "filesystem".equals(source) ? BenchSupport.loadFilesystemImage(path) : new Image(path);
        resultImage = "half".equals(scale)
            ? sourceImage.getScaledInstance(requestedWidth, requestedHeight) : sourceImage;
        materialized = resultImage.getGraphics();
        if (materialized == null) {
          throw new IllegalStateException("image materialization returned no graphics surface");
        }
        long elapsed = System.nanoTime() - started;
        decodeNanos += elapsed;
        succeeded++;
        imageResults.put(BenchSupport.object(
            "path", entry.path,
            "format", entry.format,
            "requestedWidth", requestedWidth,
            "requestedHeight", requestedHeight,
            "resultWidth", resultImage.getPixelWidth(),
            "resultHeight", resultImage.getPixelHeight(),
            "durationNs", elapsed));
      } catch (Throwable failure) {
        long elapsed = System.nanoTime() - started;
        decodeNanos += elapsed;
        failed++;
        imageResults.put(BenchSupport.object(
            "path", entry.path,
            "format", entry.format,
            "requestedWidth", requestedWidth,
            "requestedHeight", requestedHeight,
            "resultWidth", 0,
            "resultHeight", 0,
            "durationNs", elapsed,
            "error", failure.toString()));
      } finally {
        materialized = null;
        resultImage = null;
        sourceImage = null;
      }
      if ((index + 1) % 32 == 0) {
        Vm.gc();
      }
    }
    long wallNanos = System.nanoTime() - wallStart;
    JSONObject measurements = BenchSupport.object(
        "axes", BenchSupport.object("source", source, "scale", scale, "order", order,
            "seed", "seeded-random".equals(order) ? BenchSupport.RANDOM_SEED : JSONObject.NULL),
        "imagesAttempted", indices.length,
        "imagesSucceeded", succeeded,
        "imagesFailed", failed,
        "images", imageResults);
    JSONObject durations = BenchSupport.object("wallTime", wallNanos, "decodeMaterialization", decodeNanos);
    JSONObject record = app.runRecord(measurements, durations, config.getInt("round"),
        config.getString("phase"), "decode");
    app.emit(record);
    if (indices.length != BenchSupport.EXPECTED_FILE_COUNT || succeeded != BenchSupport.EXPECTED_FILE_COUNT
        || failed != 0) {
      app.fail(new IllegalStateException("decode workload requires " + BenchSupport.EXPECTED_FILE_COUNT
          + " successful images; attempted=" + indices.length + ", succeeded=" + succeeded + ", failed=" + failed));
    } else {
      app.exit(0);
    }
  }

  private static String imagePath(JSONObject config, String source, String relative) throws Exception {
    if ("tcz".equals(source)) {
      return config.getString("datasetTczPrefix") + relative;
    }
    return config.getString("datasetRoot") + "/" + relative;
  }

  private static int[] sequence(int length, String order) {
    int[] result = new int[length];
    for (int i = 0; i < length; i++) {
      result[i] = i;
    }
    if ("seeded-random".equals(order)) {
      int randomState = (int) BenchSupport.RANDOM_SEED;
      for (int i = result.length - 1; i > 0; i--) {
        randomState ^= randomState << 13;
        randomState ^= randomState >>> 17;
        randomState ^= randomState << 5;
        int selected = (randomState & 0x7fffffff) % (i + 1);
        int swap = result[i];
        result[i] = result[selected];
        result[selected] = swap;
      }
    }
    return result;
  }
}
