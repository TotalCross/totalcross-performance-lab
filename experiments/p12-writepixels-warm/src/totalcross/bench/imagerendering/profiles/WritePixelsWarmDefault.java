// Copyright (C) 2026 Amalgam Solucoes em TI Ltda
//
// SPDX-License-Identifier: LGPL-2.1-only

package totalcross.bench.imagerendering.profiles;

import totalcross.bench.imagerendering.ImageRenderingBenchmarkApp;
import totalcross.sys.Settings;
import totalcross.ui.MainWindow;
import totalcross.ui.Window;
import totalcross.ui.gfx.Graphics;
import totalcross.ui.image.ImageWritePixelsWarmHooks;
import totalcross.ui.image.ImageDrawPathProbeAccess;

/** Default UI plus isolated historical writePixels hooks; leaves runtime defaults and startup routing intact. */
public final class WritePixelsWarmDefault extends MainWindow {
  public WritePixelsWarmDefault() {
    super("", Window.NO_BORDER);
    setUIStyle(Settings.ANDROID_UI);
    setDeviceTitle("image-scroll-real-workload");
  }

  @Override public void initUI() {
    ImageDrawPathProbeAccess.installCausalHooks(new ImageWritePixelsWarmHooks());
    ImageRenderingBenchmarkApp.start(this, "default");
  }

  @Override public void onPaint(Graphics graphics) {
    super.onPaint(graphics);
    ImageRenderingBenchmarkApp.capturePaint();
  }
}
