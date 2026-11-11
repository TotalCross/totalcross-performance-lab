import totalcross.io.File;
import totalcross.sys.Convert;
import totalcross.sys.Settings;
import totalcross.ui.Container;
import totalcross.ui.Edit;
import totalcross.ui.gfx.Color;

public class TestPermission extends Container {
	
	Container mainContainer;
	Edit edir = new Edit();
	
	@Override
	public void initUI() {
		super.initUI();
		
		mainContainer = new Container();
		mainContainer.setBackColor(Color.WHITE);
		add(mainContainer, LEFT, TOP, FILL, FILL);
		mainContainer.add(edir, LEFT, TOP, FILL, FILL);
		Settings.dataPath = "/sdcard/";
		checkFolderPermission();
	}
	public void checkFolderPermission() {
		String folderName = "asd";
		try (File fileDir = new File(Convert.appendPath(Settings.dataPath, folderName))) {
			fileDir.createDir();
			fileDir.delete();
		} catch (Exception e) {
			e.printStackTrace();
			edir.setText(e.getMessage());
		}
	}
	
}
