package totalcross.bench.imagerendering.profiles;

import totalcross.bench.imagerendering.ImageRenderingBenchmarkApp;
import totalcross.sys.runtime.RuntimeConfiguration;
import totalcross.sys.runtime.RuntimeWhen;
import totalcross.ui.image.ImageRuntimeRule;
import totalcross.ui.image.ImageStorageProfile;
import totalcross.ui.MainWindow;
import totalcross.ui.gfx.Graphics;

@RuntimeConfiguration
@ImageRuntimeRule(when = @RuntimeWhen(), storage = ImageStorageProfile.COMPACT)
public final class Compact extends MainWindow {
  @Override public void initUI() { ImageRenderingBenchmarkApp.start(this, "compact"); }
  @Override public void onPaint(Graphics graphics) {
    super.onPaint(graphics);
    ImageRenderingBenchmarkApp.capturePaint();
  }
}
