// Copyright (C) 2026 Amalgam Solucoes em TI Ltda
//
// SPDX-License-Identifier: LGPL-2.1-only

package totalcross.bench.imagerendering.profiles;

import totalcross.bench.imagerendering.ImageRenderingBenchmarkApp;
import totalcross.sys.Settings;
import totalcross.ui.MainWindow;
import totalcross.ui.Window;
import totalcross.ui.gfx.Graphics;
import totalcross.ui.image.ImageAdmissionMemoryHooks;
import totalcross.ui.image.ImageDrawPathProbeAccess;

/** Default UI with isolated final-raster ownership accounting. */
public final class MaterializedAdmissionMemoryDefault extends MainWindow {
  public MaterializedAdmissionMemoryDefault() {
    super("", Window.NO_BORDER);
    setUIStyle(Settings.ANDROID_UI);
    setDeviceTitle("image-scroll-real-workload");
  }

  @Override public void initUI() {
    ImageDrawPathProbeAccess.installAdmissionMemoryHooks(new ImageAdmissionMemoryHooks());
    ImageRenderingBenchmarkApp.start(this, "default");
  }

  @Override public void onPaint(Graphics graphics) {
    super.onPaint(graphics);
    ImageRenderingBenchmarkApp.capturePaint();
  }
}
