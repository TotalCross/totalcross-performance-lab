package totalcross.bench.imagerendering.profiles;

import totalcross.bench.imagerendering.ImageRenderingBenchmarkApp;
import totalcross.sys.Settings;
import totalcross.sys.runtime.RuntimeConfiguration;
import totalcross.sys.runtime.RuntimeFeatureState;
import totalcross.sys.runtime.RuntimeWhen;
import totalcross.ui.image.ImageRuntimeRule;
import totalcross.ui.MainWindow;
import totalcross.ui.Window;
import totalcross.ui.gfx.Graphics;

@RuntimeConfiguration
@ImageRuntimeRule(when = @RuntimeWhen(), targetColorConversion = RuntimeFeatureState.ENABLED,
    physicalVariantCache = RuntimeFeatureState.ENABLED)
public final class RasterVariants extends MainWindow {
  public RasterVariants() {
    super("", Window.NO_BORDER);
    setUIStyle(Settings.ANDROID_UI);
    setDeviceTitle("image-scroll-real-workload");
  }

  @Override public void initUI() { ImageRenderingBenchmarkApp.start(this, "raster-variants"); }
  @Override public void onPaint(Graphics graphics) {
    super.onPaint(graphics);
    ImageRenderingBenchmarkApp.capturePaint();
  }
}
