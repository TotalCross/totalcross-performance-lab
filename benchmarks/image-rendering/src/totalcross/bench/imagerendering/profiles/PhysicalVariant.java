package totalcross.bench.imagerendering.profiles;

import totalcross.bench.imagerendering.ImageRenderingBenchmarkApp;
import totalcross.sys.runtime.RuntimeConfiguration;
import totalcross.sys.runtime.RuntimeFeatureState;
import totalcross.sys.runtime.RuntimeWhen;
import totalcross.ui.image.ImageRuntimeRule;
import totalcross.ui.MainWindow;
import totalcross.ui.gfx.Graphics;

@RuntimeConfiguration
@ImageRuntimeRule(when = @RuntimeWhen(), physicalVariantCache = RuntimeFeatureState.ENABLED)
public final class PhysicalVariant extends MainWindow {
  @Override public void initUI() { ImageRenderingBenchmarkApp.start(this, "physical-variant"); }
  @Override public void onPaint(Graphics graphics) {
    super.onPaint(graphics);
    ImageRenderingBenchmarkApp.capturePaint();
  }
}
