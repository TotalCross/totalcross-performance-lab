package totalcross.bench.imagerendering.profiles;

import totalcross.bench.imagerendering.ImageRenderingBenchmarkApp;
import totalcross.sys.Settings;
import totalcross.sys.runtime.RuntimeConfiguration;
import totalcross.sys.runtime.RuntimeWhen;
import totalcross.ui.image.ImagePrefetchWorkerMode;
import totalcross.ui.image.ImageRuntimeRule;
import totalcross.ui.MainWindow;
import totalcross.ui.Window;
import totalcross.ui.gfx.Graphics;

@RuntimeConfiguration
@ImageRuntimeRule(when = @RuntimeWhen(), prefetchWorker = ImagePrefetchWorkerMode.LEGACY_PER_ENTRY_THREAD)
public final class PreparedLegacy extends MainWindow {
  public PreparedLegacy() {
    super("", Window.NO_BORDER);
    setUIStyle(Settings.ANDROID_UI);
    setDeviceTitle("image-scroll-real-workload");
  }

  @Override public void initUI() { ImageRenderingBenchmarkApp.start(this, "prepared-legacy"); }
  @Override public void onPaint(Graphics graphics) {
    super.onPaint(graphics);
    ImageRenderingBenchmarkApp.capturePaint();
  }
}
