// SPDX-License-Identifier: MIT
package totalcross.lab.graphics;

import totalcross.io.File;
import totalcross.json.JSONObject;
import totalcross.sys.Convert;
import totalcross.sys.Settings;
import totalcross.sys.Vm;
import totalcross.ui.Button;
import totalcross.ui.Control;
import totalcross.ui.Edit;
import totalcross.ui.Label;
import totalcross.ui.MainWindow;
import totalcross.ui.event.ControlEvent;
import totalcross.ui.event.Event;
import totalcross.ui.gfx.Color;
import totalcross.ui.gfx.Graphics;

/**
 * Minimal iOS rendering regression: bright color panels + primitive shapes,
 * simple native controls, and one interactive state transition.
 *
 * TC_GRAPHICS_JSON events are ALSO persisted in appPath/Documents so tests do
 * not depend on privacy-redacted iOS NSLog or Skia accessibility.
 * No SQLite or network operations are used.
 */
public final class GraphicsSmokeProbe extends MainWindow {
  private static final String REPORT_NAME = "tc-ios-graphics-report.log";
  private final StringBuffer report = new StringBuffer();
  private Label status;
  private Label heading;
  private Edit edit;
  private Button button;
  private PrimitivePanel panel;
  private boolean changed;
  private boolean initialPaintReported;
  private boolean updatedPaintReported;

  public GraphicsSmokeProbe() {
    super();
    setBackColor(Color.WHITE);
  }

  @Override
  public void initUI() {
    try {
      emit("startup", "PASS", "platform=" + Settings.platform
          + "; appPath=" + Settings.appPath);
      if (!Settings.isIOS()) {
        emit("platform", "INFO", "Graphics smoke designed for iOS; running on " + Settings.platform);
      }

      int sw = width > 0 ? width : Settings.screenWidth;
      int sh = height > 0 ? height : Settings.screenHeight;
      int margin = Math.max(12, sw / 20);
      int gap = Math.max(8, sh / 90);
      int row = Math.max(36, sh / 17);
      int usable = sw - 2 * margin;
      if (usable <= 40 || sh <= 150) {
        throw new IllegalStateException("Unexpected screen: " + sw + "x" + sh);
      }

      heading = new Label("TOTALCROSS GRAPHICS 7.3.0");
      heading.setForeColor(Color.BLACK);
      add(heading, margin, Math.max(14, sh / 16), usable, row);

      status = new Label("READY - four colors and shapes");
      status.setForeColor(Color.BLACK);
      add(status, margin, Math.max(14, sh / 16) + row + gap, usable, row);

      panel = new PrimitivePanel(this);
      panel.setBackColor(Color.WHITE);
      int panelY = Math.max(14, sh / 16) + 2 * (row + gap);
      int panelH = Math.max(100, Math.min(sh / 3, sh - panelY - 4 * (row + gap)));
      add(panel, margin, panelY, usable, panelH);

      Label editCaption = new Label("EDIT CONTROL");
      editCaption.setForeColor(Color.BLACK);
      int captionY = panelY + panelH + gap;
      add(editCaption, margin, captionY, usable, row);

      edit = new Edit();
      edit.setText("EDIT READY");
      int editY = captionY + row + gap;
      add(edit, margin, editY, usable, row);

      button = new Button("CHANGE COLORS");
      button.setBackColor(Color.getRGB(0, 90, 180));
      button.setForeColor(Color.WHITE);
      int buttonY = editY + row + gap;
      add(button, margin, buttonY, usable, row + Math.max(8, gap));

      Label footer = new Label("Tap button: colors, label and edit change");
      footer.setForeColor(Color.BLACK);
      int footerY = buttonY + row + 2 * gap;
      if (footerY + row < sh) {
        add(footer, margin, footerY, usable, row);
      }
      emit("controls-created", "PASS", "Label, Edit, Button, PrimitivePanel added");
      emit("layout", "INFO", "screen=" + sw + "x" + sh
          + ";buttonCenterRelX=" + ((margin + usable / 2.0) / sw)
          + ";buttonCenterRelY=" + ((buttonY + (row + Math.max(8, gap)) / 2.0) / sh));
      // The actual rendering is verified separately from screenshots by Appium.
      repaintNow();
    } catch (Throwable failure) {
      emit("init", "FAIL", failure.toString());
      failure.printStackTrace();
      try {
        add(new Label("GRAPHICS INIT FAILED"), CENTER, CENTER);
      } catch (Throwable ignored) {
        // Native startup log remains available.
      }
    }
  }

  @Override
  public void onEvent(Event event) {
    if (event.type == ControlEvent.PRESSED && event.target == button) {
      try {
        changed = !changed;
        status.setText(changed ? "BUTTON OK - palette changed" : "READY - four colors and shapes");
        edit.setText(changed ? "EDIT UPDATED" : "EDIT READY");
        button.setText(changed ? "RESET COLORS" : "CHANGE COLORS");
        emit("button-pressed", "PASS", "changed=" + changed + ";edit=" + edit.getText());
        panel.repaintNow();
        status.repaintNow();
        edit.repaintNow();
        button.repaintNow();
      } catch (Throwable failure) {
        emit("button-pressed", "FAIL", failure.toString());
        failure.printStackTrace();
      }
    }
  }

  void panelPainted() {
    if (changed) {
      if (!updatedPaintReported) {
        updatedPaintReported = true;
        emit("canvas-painted-updated", "PASS", "palette=updated");
      }
    } else if (!initialPaintReported) {
      initialPaintReported = true;
      emit("canvas-painted-initial", "PASS", "palette=initial");
    }
  }

  private void emit(String stage, String statusText, String detail) {
    try {
      JSONObject record = new JSONObject();
      record.put("stage", stage);
      record.put("status", statusText);
      record.put("detail", detail);
      String line = "TC_GRAPHICS_JSON " + record.toString();
      Vm.debug(line);
      report.append(line).append('\n');
      // Small, discrete checkpoint write; not in every paint frame.
      String path = Convert.appendPath(Settings.appPath, REPORT_NAME);
      byte[] bytes = report.toString().getBytes();
      try (File file = new File(path, File.CREATE_EMPTY)) {
        int n = file.writeBytes(bytes, 0, bytes.length);
        if (n != bytes.length) {
          Vm.debug("TC_GRAPHICS_PERSIST_FAILED short-write=" + n);
        }
        file.flush();
      }
    } catch (Throwable failure) {
      Vm.debug("TC_GRAPHICS_PERSIST_FAILED " + failure);
    }
  }

  private static final class PrimitivePanel extends Control {
    private final GraphicsSmokeProbe owner;

    PrimitivePanel(GraphicsSmokeProbe owner) {
      this.owner = owner;
    }

    @Override
    public void onPaint(Graphics g) {
      int w = Math.max(1, width);
      int h = Math.max(1, height);
      int[] palette = owner.changed
          ? new int[] {Color.CYAN, Color.MAGENTA, Color.ORANGE, Color.getRGB(132, 60, 220)}
          : new int[] {Color.RED, Color.GREEN, Color.BLUE, Color.YELLOW};
      g.backColor = Color.WHITE;
      g.fillRect(0, 0, w, h);
      // Four broad, saturated panels are easy to identify in an iPhone PNG.
      for (int i = 0; i < 4; i++) {
        int x0 = i * w / 4;
        int x1 = (i + 1) * w / 4;
        g.backColor = palette[i];
        g.fillRect(x0, 0, x1 - x0, h);
      }
      g.foreColor = Color.BLACK;
      g.drawRect(0, 0, w - 1, h - 1);
      g.drawLine(0, 0, w - 1, h - 1);
      g.drawLine(0, h - 1, w - 1, 0);
      g.backColor = Color.WHITE;
      g.fillCircle(w / 2, h / 2, Math.max(6, Math.min(w, h) / 6));
      g.foreColor = Color.BLACK;
      g.drawCircle(w / 2, h / 2, Math.max(6, Math.min(w, h) / 6));
      g.drawText("Skia: line / rect / circle", Math.max(6, w / 30), Math.max(14, h / 9));
      owner.panelPainted();
    }
  }
}
