package totalcross.bench.imagerendering.profiles;

import totalcross.bench.imagerendering.ImageRenderingBenchmarkApp;
import totalcross.sys.runtime.RuntimeConfiguration;
import totalcross.sys.runtime.RuntimeFeatureState;
import totalcross.sys.runtime.RuntimeWhen;
import totalcross.ui.image.ImagePrefetchWorkerMode;
import totalcross.ui.image.ImageRuntimeRule;
import totalcross.ui.image.ImageStorageProfile;
import totalcross.ui.MainWindow;
import totalcross.ui.gfx.Graphics;

@RuntimeConfiguration
@ImageRuntimeRule(when = @RuntimeWhen(), storage = ImageStorageProfile.STANDARD,
    targetColorConversion = RuntimeFeatureState.ENABLED, physicalVariantCache = RuntimeFeatureState.ENABLED,
    scrollRasterReuse = RuntimeFeatureState.ENABLED,
    prefetchWorker = ImagePrefetchWorkerMode.SEMAPHORE_PROCESS_WORKER)
public final class CombinedStandard extends MainWindow {
  @Override public void initUI() { ImageRenderingBenchmarkApp.start(this, "combined-standard"); }
  @Override public void onPaint(Graphics graphics) {
    super.onPaint(graphics);
    ImageRenderingBenchmarkApp.capturePaint();
  }
}
