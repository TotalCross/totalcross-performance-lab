import totalcross.sys.Settings;
import totalcross.sys.Vm;
import totalcross.ui.MainWindow;
import totalcross.ui.Window;
import totalcross.ui.font.Font;

public class Main extends MainWindow {
	
	public Main() {
		super("", Window.NO_BORDER);
		setDeviceTitle("TcTest");
		setUIStyle(Settings.ANDROID_UI);
		Settings.windowSize = Settings.WINDOWSIZE_600X800;
		Vm.disableDebug = false;
		if (Settings.version < 600) {
			setFont(Font.getFont(20));
		}
	}
	
	@Override
	public void initUI() {
		super.initUI();
		showTestPermission();
	}

	
	private void showTestPermission() {
		swap(new TestPermission());
	}

	
}
