// Copyright (C) 2026 Amalgam Solucoes em TI Ltda
//
// SPDX-License-Identifier: LGPL-2.1-only

package totalcross.bench.imagerendering.profiles;

import totalcross.bench.imagerendering.ImageRenderingBenchmarkApp;
import totalcross.sys.Settings;
import totalcross.ui.MainWindow;
import totalcross.ui.Window;
import totalcross.ui.gfx.Graphics;
import totalcross.ui.image.ImageCausalProbeHooks;
import totalcross.ui.image.ImageDrawPathProbeAccess;

/** Default UI plus experiment hooks; leaves runtime defaults and startup routing intact. */
public final class CausalDefault extends MainWindow {
  public CausalDefault() {
    super("", Window.NO_BORDER);
    setUIStyle(Settings.ANDROID_UI);
    setDeviceTitle("image-scroll-real-workload");
  }

  @Override public void initUI() {
    ImageDrawPathProbeAccess.installCausalHooks(new ImageCausalProbeHooks());
    ImageRenderingBenchmarkApp.start(this, "default");
  }

  @Override public void onPaint(Graphics graphics) {
    super.onPaint(graphics);
    ImageRenderingBenchmarkApp.capturePaint();
  }
}
