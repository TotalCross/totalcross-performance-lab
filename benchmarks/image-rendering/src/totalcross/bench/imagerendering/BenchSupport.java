package totalcross.bench.imagerendering;

import totalcross.io.File;
import totalcross.json.JSONArray;
import totalcross.json.JSONObject;
import totalcross.json.JSONException;
import totalcross.ui.image.Image;

/** Shared configuration, dataset and JSON protocol helpers for benchmark apps. */
final class BenchSupport {
  static final int EXPECTED_FILE_COUNT = 663;
  static final long RANDOM_SEED = 12012026L;
  static final String RESULT_PREFIX = "TCBENCH_JSON ";

  private BenchSupport() { }

  static JSONObject readConfig() throws Exception {
    File file = new File("tcbench-run.json", File.READ_ONLY);
    try {
      int length = file.getSize();
      byte[] bytes = new byte[length];
      int read = file.readBytes(bytes, 0, length);
      if (read != length) {
        throw new IllegalStateException("incomplete tcbench-run.json read");
      }
      return new JSONObject(new String(bytes, "UTF-8"));
    } finally {
      file.close();
    }
  }

  static DatasetEntry[] readDataset(JSONObject config) throws Exception {
    if (config.isNull("datasetManifestPath")) {
      throw new IllegalStateException("dataset manifest path is missing");
    }
    File file = new File(config.getString("datasetManifestPath"), File.READ_ONLY);
    JSONObject manifest;
    try {
      int length = file.getSize();
      byte[] bytes = new byte[length];
      int read = file.readBytes(bytes, 0, length);
      if (read != length) {
        throw new IllegalStateException("incomplete dataset manifest read");
      }
      manifest = new JSONObject(new String(bytes, "UTF-8"));
    } finally {
      file.close();
    }
    JSONArray files = manifest.getJSONArray("files");
    if (files.length() != EXPECTED_FILE_COUNT) {
      throw new IllegalStateException("dataset manifest file count is " + files.length()
          + "; expected " + EXPECTED_FILE_COUNT);
    }
    DatasetEntry[] entries = new DatasetEntry[files.length()];
    int jpegCount = 0;
    int pngCount = 0;
    for (int i = 0; i < files.length(); i++) {
      JSONObject item = files.getJSONObject(i);
      String format = item.getString("format");
      jpegCount += "jpeg".equals(format) ? 1 : 0;
      pngCount += "png".equals(format) ? 1 : 0;
      entries[i] = new DatasetEntry(item.getString("path"), format,
          item.getInt("width"), item.getInt("height"));
    }
    if (jpegCount != 660 || pngCount != 3) {
      throw new IllegalStateException("dataset formats differ from the benchmark contract: jpeg="
          + jpegCount + ", png=" + pngCount);
    }
    return entries;
  }

  static Image loadFilesystemImage(String path) throws Exception {
    File file = new File(path, File.READ_ONLY);
    try {
      return new Image(file);
    } finally {
      file.close();
    }
  }

  static JSONObject object(Object... fields) {
    JSONObject result = new JSONObject();
    try {
      for (int i = 0; i < fields.length; i += 2) {
        result.put((String) fields[i], fields[i + 1]);
      }
      return result;
    } catch (JSONException error) {
      throw new IllegalStateException("cannot create benchmark JSON", error);
    }
  }

  static JSONArray array(Object... values) {
    JSONArray result = new JSONArray();
    for (Object value : values) {
      result.put(value);
    }
    return result;
  }

  static void put(JSONObject target, String key, Object value) {
    try {
      target.put(key, value);
    } catch (JSONException error) {
      throw new IllegalStateException("cannot create benchmark JSON field " + key, error);
    }
  }

  static final class DatasetEntry {
    final String path;
    final String format;
    final int width;
    final int height;

    DatasetEntry(String path, String format, int width, int height) {
      this.path = path;
      this.format = format;
      this.width = width;
      this.height = height;
    }
  }
}
