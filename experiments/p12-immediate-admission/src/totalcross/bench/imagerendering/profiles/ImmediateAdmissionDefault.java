// Copyright (C) 2026 Amalgam Solucoes em TI Ltda
//
// SPDX-License-Identifier: LGPL-2.1-only

package totalcross.bench.imagerendering.profiles;

import totalcross.bench.imagerendering.ImageRenderingBenchmarkApp;
import totalcross.sys.Settings;
import totalcross.ui.MainWindow;
import totalcross.ui.Window;
import totalcross.ui.gfx.Graphics;
import totalcross.ui.image.ImageImmediateAdmissionHooks;
import totalcross.ui.image.ImageDrawPathProbeAccess;

/** Default UI plus isolated immediate-admission hooks; leaves runtime defaults and startup routing intact. */
public final class ImmediateAdmissionDefault extends MainWindow {
  public ImmediateAdmissionDefault() {
    super("", Window.NO_BORDER);
    setUIStyle(Settings.ANDROID_UI);
    setDeviceTitle("image-scroll-real-workload");
  }

  @Override public void initUI() {
    ImageDrawPathProbeAccess.installCausalHooks(new ImageImmediateAdmissionHooks());
    ImageRenderingBenchmarkApp.start(this, "default");
  }

  @Override public void onPaint(Graphics graphics) {
    super.onPaint(graphics);
    ImageRenderingBenchmarkApp.capturePaint();
  }
}
