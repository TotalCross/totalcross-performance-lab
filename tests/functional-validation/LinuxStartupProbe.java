package totalcross.lab.functional;

import totalcross.ui.MainWindow;

/** Minimal deployed app marker for Linux native VM startup scenarios. */
public final class LinuxStartupProbe extends MainWindow {
  @Override
  public void initUI() {
    System.out.println("TC_STARTUP_MARKER");
    System.out.flush();
    MainWindow.exit(0);
  }
}
