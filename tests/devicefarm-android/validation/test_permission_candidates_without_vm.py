"""Host-side tests of the exact 7.3.0 storage permission-selection method.

No Android runtime, VM build, emulator, or AWS device scheduling is required.
CI checks out immutable SDK sources and consumes the original APK's prior
non-billable inspection artifact.
"""
import os
from pathlib import Path
import re
import subprocess
import tempfile
import unittest
import zipfile


SOURCE = Path(os.environ.get("TC730_SOURCE_ROOT", "totalcross-730"))
ARTIFACT = Path(os.environ.get(
    "TC730_ARTIFACT_ZIP", "physical-android-ready/source-artifact.zip"))
PERMISSION_JAVA = SOURCE / ("TotalCrossVM/android/app/src/main/java/totalcross"
                            "/android/AndroidPermissionManager.java")
MANIFEST = SOURCE / "TotalCrossVM/android/app/src/main/AndroidManifest.xml"
FILE_NATIVE = SOURCE / "TotalCrossVM/src/nm/io/posix/File_c.h"
SQLITE_NATIVE = SOURCE / "TotalCrossVM/src/nm/db/NativeDB.c"


def extract_method(java_source, declaration):
    """Extract the actual Java method, respecting nested braces."""
    pos = java_source.find(declaration)
    if pos == -1:
        raise AssertionError("Pinned source missing " + declaration)
    brace = java_source.index("{", pos)
    depth = 0
    for offset in range(brace, len(java_source)):
        if java_source[offset] == "{":
            depth += 1
        elif java_source[offset] == "}":
            depth -= 1
            if depth == 0:
                return java_source[pos:offset + 1]
    raise AssertionError("Unbalanced method " + declaration)


def generate_harness(methods, patched):
    # A small host-side surrogate for the Android classes used by this
    # method. The permission-selection METHOD itself is exact pinned source.
    java = r"""
import java.util.*;
public class PermissionCandidates {
  static class Activity {}
  static class Build {
    static class VERSION { static int SDK_INT; }
    static class VERSION_CODES { static final int Q=29, TIRAMISU=33; }
  }
  static class Manifest {
    static class permission {
      static final String READ_EXTERNAL_STORAGE="READ";
      static final String WRITE_EXTERNAL_STORAGE="WRITE";
      static final String READ_MEDIA_IMAGES="IMAGES";
      static final String READ_MEDIA_VIDEO="VIDEO";
    }
  }
  static Set<String> declarations = new LinkedHashSet<>();
  private static Set<String> declaredPermissions(Activity activity) {
    return declarations;
  }

REPLACE_METHODS

  static void run(int api, String declared, String expected) {
    Build.VERSION.SDK_INT = api;
    declarations.clear();
    if (!declared.isEmpty()) declarations.addAll(Arrays.asList(declared.split(",")));
    List<String> actual = mediaPermissionCandidates(new Activity());
    String joined = String.join(",", actual);
    if (!joined.equals(expected)) {
      throw new AssertionError("API " + api + " declared=" + declared
        + " expected=" + expected + " actual=" + joined);
    }
    System.out.println("PASS API " + api + " declared=" + declared
      + " selected=" + joined);
  }
  public static void main(String[] args) {
    run(27, "WRITE", "WRITE");
    run(27, "READ,WRITE", "READ,WRITE");
    run(29, "WRITE", "EXPECTED_API29_WRITE_ONLY");
    run(29, "READ,WRITE", "EXPECTED_API29_READ_WRITE");
    run(29, "READ", "READ");
    run(30, "READ,WRITE", "READ");
    run(32, "READ,WRITE", "READ");
    run(35, "IMAGES,VIDEO", "IMAGES,VIDEO");
  }
}
"""
    # Assert both old and new behaviors, not just that the Java code compiles.
    # Baseline API29 WRITE-only has no candidates. Baseline READ+WRITE
    # only requests READ, so successful READ authorization can leave
    # WRITE denied and the original filesystem operation unrecoverable.
    java = java.replace(
        "EXPECTED_API29_WRITE_ONLY", "WRITE" if patched else "")
    java = java.replace(
        "EXPECTED_API29_READ_WRITE", "READ,WRITE" if patched else "READ")
    return java.replace("REPLACE_METHODS", methods)


class TotalCross730PermissionContract(unittest.TestCase):
    def test_exact_java_method_baseline_and_candidate_patch(self):
        text = PERMISSION_JAVA.read_text()
        method = extract_method(
            text,
            "private static List<String> mediaPermissionCandidates(Activity activity)")
        helper = extract_method(
            text,
            "private static void addIfDeclared(List<String> permissions, "
            "Set<String> declared, String permission)")
        clause = "Build.VERSION.SDK_INT < Build.VERSION_CODES.Q"
        self.assertEqual(method.count(clause), 1,
                         "Pinned 7.3.0 policy unexpectedly changed")
        for patched in (False, True):
            selected = method
            if patched:
                selected = selected.replace(
                    clause, "Build.VERSION.SDK_INT <= Build.VERSION_CODES.Q")
            code = generate_harness(selected + "\n" + helper, patched)
            with tempfile.TemporaryDirectory(prefix="tc730-perms-") as td:
                f = Path(td) / "PermissionCandidates.java"
                f.write_text(code)
                javac = subprocess.run(
                    ["javac", str(f)], capture_output=True, text=True)
                self.assertEqual(javac.returncode, 0, javac.stderr)
                result = subprocess.run(
                    ["java", "-cp", td, "PermissionCandidates"],
                    capture_output=True, text=True)
                self.assertEqual(result.returncode, 0,
                                 result.stdout + "\n" + result.stderr)
                self.assertEqual(result.stdout.count("PASS API"), 8)
                print(("PROPOSED" if patched else "BASELINE") +
                      " raw Java method matrix:\n" + result.stdout)

    def test_original_apk_manifest_explicit_and_implicit_permissions(self):
        with zipfile.ZipFile(ARTIFACT) as z:
            permissions = z.read("apk-permissions.txt").decode()
            badging = z.read("apk-badging.txt").decode()
        self.assertIn("targetSdkVersion:'36'", badging)
        self.assertIn("sdkVersion:'24'", badging)
        self.assertIn(
            "uses-permission: name='android.permission.WRITE_EXTERNAL_STORAGE'",
            permissions)
        # READ was not inserted explicitly in the APK's XML. Android's
        # effective/implicit permission set can nonetheless include it.
        self.assertNotIn("READ_EXTERNAL_STORAGE", permissions)
        self.assertIn(
            "uses-implied-permission: name='android.permission.READ_EXTERNAL_STORAGE'",
            badging)
        manifest = MANIFEST.read_text()
        self.assertIn('android:name="android.permission.WRITE_EXTERNAL_STORAGE"',
                      manifest)
        self.assertNotIn('android:name="android.permission.READ_EXTERNAL_STORAGE"',
                         manifest)

    def test_sqlite_direct_open_bypasses_file_permission_retry(self):
        native_file = FILE_NATIVE.read_text()
        native_sqlite = SQLITE_NATIVE.read_text()
        self.assertIn("#define FILE_RETRY_ACCESS(", native_file)
        self.assertIn('"requestStoragePermission"', native_file)
        self.assertIn("sqlite3_open_v2(str, &db, flags, NULL)", native_sqlite)
        self.assertNotIn("FILE_RETRY_ACCESS", native_sqlite)
        self.assertNotIn("requestStoragePermission", native_sqlite)


if __name__ == "__main__":
    unittest.main()
