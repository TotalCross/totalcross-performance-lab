package totalcross.bench.imagerendering.profiles;

import totalcross.bench.imagerendering.ImageRenderingBenchmarkApp;
import totalcross.ui.MainWindow;
import totalcross.ui.gfx.Graphics;

/** Uses TotalCross production defaults without a runtime configuration rule. */
public final class Default extends MainWindow {
  @Override public void initUI() { ImageRenderingBenchmarkApp.start(this, "default"); }
  @Override public void onPaint(Graphics graphics) {
    super.onPaint(graphics);
    ImageRenderingBenchmarkApp.capturePaint();
  }
}
