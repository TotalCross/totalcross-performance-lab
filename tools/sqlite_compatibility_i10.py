# Copyright (C) 2026 Amalgam Solucoes em TI Ltda
#
# SPDX-License-Identifier: LGPL-2.1-only
"""Build and run the I10 SQLite compatibility matrix without publishing it."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shutil
import sqlite3
import struct
import subprocess
import sys
import tarfile
import time
import zipfile

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "investigations/7.3.0-functional/cases/sqlite-compatibility/Main.java"
APP_NAME = "Main"
APP_ID = "totalcross.appi10"
REVISIONS = ("official-7.2.2", "official-7.3.0", "candidate-94af")
TARGETS = {
    "windows-i386": ("win32", "win32", "Main.exe"),
    "macos-arm64": ("macos", "macos", "Main"),
    "linux-x86_64": ("linux", "linux", "Main"),
    "android-arm64": ("android", "android", None),
}


def sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def pe_machine(path):
    with open(path, "rb") as stream:
        if stream.read(2) != b"MZ":
            raise RuntimeError("not a PE executable: " + str(path))
        stream.seek(0x3c)
        offset_data = stream.read(4)
        if len(offset_data) != 4:
            raise RuntimeError("truncated PE header: " + str(path))
        offset = struct.unpack("<I", offset_data)[0]
        stream.seek(offset)
        if stream.read(4) != b"PE\0\0":
            raise RuntimeError("invalid PE signature: " + str(path))
        machine_data = stream.read(2)
        if len(machine_data) != 2:
            raise RuntimeError("truncated PE machine field: " + str(path))
        return struct.unpack("<H", machine_data)[0]


def run_command(args, cwd, log, env=None, timeout=180):
    log.parent.mkdir(parents=True, exist_ok=True)
    with log.open("w", encoding="utf-8") as stream:
        stream.write("$ " + " ".join(map(str, args)) + "\n")
        stream.flush()
        try:
            result = subprocess.run(
                list(map(str, args)), cwd=str(cwd), env=env, text=True,
                stdout=stream, stderr=subprocess.STDOUT, timeout=timeout,
                check=False,
            )
        except subprocess.TimeoutExpired:
            stream.write("\nTIMEOUT after %d seconds\n" % timeout)
            return None
        stream.write("\nEXIT_CODE=%s\n" % result.returncode)
        return result.returncode


def ensure_new(path):
    path = Path(path)
    if path.exists():
        raise RuntimeError("output path already exists; choose a new path: " + str(path))
    path.mkdir(parents=True)
    return path


def safe_extract_zip(archive, destination):
    destination = Path(destination).resolve()
    with zipfile.ZipFile(archive) as package:
        for member in package.infolist():
            output = (destination / member.filename).resolve()
            if not output.is_relative_to(destination):
                raise RuntimeError("unsafe ZIP entry: " + member.filename)
        package.extractall(destination)


def safe_extract_tar(archive, destination):
    destination = Path(destination).resolve()
    with tarfile.open(archive, "r:gz") as package:
        for member in package.getmembers():
            output = (destination / member.name).resolve()
            if not output.is_relative_to(destination):
                raise RuntimeError("unsafe tar entry: " + member.name)
            if member.issym() or member.islnk():
                link = (output.parent / member.linkname).resolve()
                if not link.is_relative_to(destination):
                    raise RuntimeError("unsafe tar link: " + member.name)
        package.extractall(destination)


def find_sdk_root(root):
    root = Path(root)
    candidates = [root, root / "TotalCross", root / "build/TotalCross"]
    candidates.extend(root.glob("**/TotalCross"))
    for candidate in candidates:
        if (candidate / "dist").is_dir() and (candidate / "etc").is_dir():
            return candidate
    raise RuntimeError("SDK root not found under " + str(root))


def stage_official(package, destination):
    destination = ensure_new(destination)
    unpack = destination / "unpacked"
    unpack.mkdir()
    safe_extract_zip(package, unpack)
    try:
        return find_sdk_root(unpack)
    except RuntimeError:
        nested = sorted(unpack.rglob("TotalCross-7.3.0.zip"))
        if len(nested) != 1:
            raise RuntimeError("package has no unique SDK root or nested 7.3.0 package")
        nested_root = destination / "nested"
        nested_root.mkdir()
        safe_extract_zip(nested[0], nested_root)
        return find_sdk_root(nested_root)


def stage_candidate(sdk_archive, target, runtime_root, destination,
                    official_730_root=None, candidate_apk=None):
    destination = ensure_new(destination)
    unpack = destination / "sdk-archive"
    unpack.mkdir()
    safe_extract_tar(sdk_archive, unpack)
    source_root = find_sdk_root(unpack)
    sdk_root = destination / "TotalCross"
    shutil.copytree(source_root, sdk_root)
    runtime_root = Path(runtime_root).resolve() if runtime_root else None

    if target == "windows-i386":
        if runtime_root is None:
            raise RuntimeError("Windows candidate runtime archive is required")
        launcher = runtime_root / "Launcher.exe"
        vm = runtime_root / "tcvm.dll"
        copy_runtime_files(sdk_root, "win32", launcher, vm)
    elif target == "macos-arm64":
        if runtime_root is None:
            raise RuntimeError("macOS candidate runtime archive is required")
        app = runtime_root / "deployed/install/macos/ImageStringFallbackProbe"
        vm = runtime_root / "deployed/install/macos/libtcvm.dylib"
        copy_runtime_files(sdk_root, "macos", app, vm)
    elif target == "linux-x86_64":
        if runtime_root is None:
            raise RuntimeError("Linux candidate runtime bundle is required")
        launcher = runtime_root / "native/Launcher"
        vm = runtime_root / "native/libtcvm.so"
        copy_runtime_files(sdk_root, "linux", launcher, vm)
    elif target == "android-arm64":
        if official_730_root is None or candidate_apk is None:
            raise RuntimeError("Android candidate staging requires official 7.3.0 and candidate APK")
        aab_source = Path(official_730_root) / "dist/vm/android/TotalCross.aab"
        if not aab_source.is_file():
            raise RuntimeError("official Android AAB template is missing")
        sdk_root.joinpath("dist/vm/android").mkdir(parents=True, exist_ok=True)
        patch_android_aab(aab_source, candidate_apk, sdk_root / "dist/vm/android/TotalCross.aab")
        for name in ("TCBase.tcz", "TCFont.tcz", "TCUI.tcz", "Material Icons.tcz"):
            src = Path(official_730_root) / "dist/vm" / name
            if src.is_file() and not (sdk_root / "dist/vm" / name).exists():
                shutil.copy2(src, sdk_root / "dist/vm" / name)
        tools_source = Path(official_730_root) / "etc/tools/android"
        tools_target = sdk_root / "etc/tools/android"
        if tools_source.is_dir():
            shutil.copytree(tools_source, tools_target, dirs_exist_ok=True)
    else:
        raise RuntimeError("unsupported target: " + target)
    return sdk_root


def copy_runtime_files(sdk_root, platform_name, launcher_source, vm_source):
    launcher_source = Path(launcher_source)
    vm_source = Path(vm_source)
    if not launcher_source.is_file() or not vm_source.is_file():
        raise RuntimeError("candidate runtime inputs are missing: "
                           + str(launcher_source) + ", " + str(vm_source))
    launcher_dir = sdk_root / "etc/launchers" / platform_name
    vm_dir = sdk_root / "dist/vm" / platform_name
    launcher_dir.mkdir(parents=True, exist_ok=True)
    vm_dir.mkdir(parents=True, exist_ok=True)
    launcher_name = {"win32": "Launcher.exe", "linux": "Launcher", "macos": "Launcher"}[platform_name]
    shutil.copy2(launcher_source, launcher_dir / launcher_name)
    shutil.copy2(vm_source, vm_dir / vm_source.name)


def patch_android_aab(aab_source, candidate_apk, destination):
    candidate_apk = Path(candidate_apk)
    with zipfile.ZipFile(candidate_apk) as apk:
        matches = [name for name in apk.namelist()
                   if name == "lib/arm64-v8a/libtcvm.so"]
        if len(matches) != 1:
            raise RuntimeError("candidate APK has no unique ARM64 libtcvm.so")
        native_library = apk.read(matches[0])
    tmp = destination.with_suffix(".tmp.aab")
    replaced = False
    with zipfile.ZipFile(aab_source) as src, zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as dst:
        for item in src.infolist():
            data = src.read(item.filename)
            if item.filename == "base/lib/arm64-v8a/libtcvm.so":
                data = native_library
                replaced = True
            dst.writestr(item, data)
    if not replaced:
        tmp.unlink(missing_ok=True)
        raise RuntimeError("Android AAB template has no base ARM64 libtcvm.so")
    tmp.replace(destination)


def get_sdk_jar(sdk_root):
    dist = Path(sdk_root) / "dist"
    preferred = dist / "totalcross-sdk.jar"
    if preferred.is_file():
        return preferred
    matches = [p for p in dist.glob("totalcross-sdk-*.jar")
               if "sources" not in p.name and "javadoc" not in p.name]
    if len(matches) != 1:
        raise RuntimeError("expected one SDK jar under " + str(dist))
    return matches[0]


def build_app(sdk_root, revision, target, output):
    output = ensure_new(output)
    sdk_root = Path(sdk_root)
    platform_dir, platform_subdir, executable_name = TARGETS[target]
    required = []
    if target == "android-arm64":
        required = [sdk_root / "dist/vm/android/TotalCross.aab"]
    elif target == "windows-i386":
        required = [sdk_root / "etc/launchers/win32/Launcher.exe",
                    sdk_root / "dist/vm/win32/tcvm.dll"]
    elif target == "macos-arm64":
        required = [sdk_root / "etc/launchers/macos/Launcher",
                    sdk_root / "dist/vm/macos/libtcvm.dylib"]
    else:
        required = [sdk_root / "etc/launchers/linux/Launcher",
                    sdk_root / "dist/vm/linux/libtcvm.so"]
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        return {"status": "NOT_RUN", "reason": "runtime files absent", "missing": missing}
    source_architecture = {}
    if target == "windows-i386":
        try:
            source_architecture = {str(path.relative_to(sdk_root)): pe_machine(path)
                                   for path in required}
        except RuntimeError as error:
            return {"status": "FAIL", "reason": str(error)}
        if any(machine != 0x014C for machine in source_architecture.values()):
            return {"status": "FAIL", "reason": "Win32 target has non-I386 runtime inputs",
                    "peMachine": source_architecture}

    jar = get_sdk_jar(sdk_root)
    libs = sdk_root / "dist/libs"
    classes = output / "classes"
    classes.mkdir()
    source_dir = output / "source"
    source_dir.mkdir()
    source = source_dir / "Main.java"
    source_text = SOURCE.read_text(encoding="utf-8").replace("@@REVISION@@", revision)
    source.write_text(source_text, encoding="utf-8")
    classpath = os.pathsep.join((str(jar), str(libs / "*")))
    env = os.environ.copy()
    env["TOTALCROSS3_HOME"] = str(sdk_root)
    compile_log = output / "compile.log"
    code = run_command(["javac", "--release", "8", "-cp", classpath,
                        "-d", classes, source], output, compile_log, env)
    if code != 0:
        return {"status": "FAIL", "reason": "javac failed", "exitCode": code,
                "compileLog": str(compile_log)}
    app_jar = output / "Main.jar"
    jar_log = output / "jar.log"
    code = run_command(["jar", "cf", app_jar, "-C", classes, "."], output, jar_log, env)
    if code != 0:
        return {"status": "FAIL", "reason": "jar failed", "exitCode": code,
                "jarLog": str(jar_log)}
    deploy_dir = output / "deployed"
    deploy_dir.mkdir()
    target_switch = {"windows-i386": "-win32", "macos-arm64": "-macos",
                     "linux-x86_64": "-linux", "android-arm64": "-android"}[target]
    deploy_log = output / "deploy.log"
    code = run_command(["java", "-cp", classpath, "tc.Deploy", app_jar,
                        target_switch, "/p", "/n", APP_NAME, "/o", str(deploy_dir) + os.sep],
                       output, deploy_log, env, timeout=1800)
    if code != 0:
        return {"status": "FAIL", "reason": "deployer failed", "exitCode": code,
                "deployLog": str(deploy_log)}
    app_dir = deploy_dir / "install" / platform_dir
    if not app_dir.is_dir():
        return {"status": "FAIL", "reason": "deployer output directory missing",
                "deployLog": str(deploy_log)}
    executable = app_dir / executable_name if executable_name else None
    apk = app_dir / "Main.apk" if target == "android-arm64" else None
    if target in ("windows-i386", "macos-arm64", "linux-x86_64") and not executable.is_file():
        return {"status": "FAIL", "reason": "deployed executable missing",
                "deployLog": str(deploy_log)}
    if apk is not None and not apk.is_file():
        apk_matches = list(app_dir.glob("*.apk"))
        if len(apk_matches) != 1:
            return {"status": "FAIL", "reason": "deployed APK missing",
                    "deployLog": str(deploy_log)}
        apk = apk_matches[0]
    deployed_architecture = {}
    if target == "windows-i386":
        deployed_files = (executable, app_dir / "tcvm.dll")
        try:
            deployed_architecture = {path.name: pe_machine(path) for path in deployed_files}
        except RuntimeError as error:
            return {"status": "FAIL", "reason": str(error), "deployLog": str(deploy_log)}
        if any(machine != 0x014C for machine in deployed_architecture.values()):
            return {"status": "FAIL", "reason": "deployed Win32 app has non-I386 binaries",
                    "peMachine": deployed_architecture, "deployLog": str(deploy_log)}
    return {"status": "PASS", "sdkJar": str(jar), "sdkJarSha256": sha256(jar),
            "appDir": str(app_dir), "executable": str(executable) if executable else None,
            "apk": str(apk) if apk else None, "apkSha256": sha256(apk) if apk else None,
            "deployLog": str(deploy_log), "compileLog": str(compile_log),
            "revision": revision, "target": target, "platformDirectory": platform_subdir,
            "sourcePeMachine": source_architecture,
            "deployedPeMachine": deployed_architecture}


def create_schema(connection, origin, wal=False, include_transfer_row=True):
    connection.execute("PRAGMA user_version=10")
    connection.execute("CREATE TABLE i10_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
    connection.execute("CREATE TABLE i10_records (id INTEGER PRIMARY KEY, value TEXT NOT NULL, amount INTEGER NOT NULL)")
    connection.execute("INSERT INTO i10_meta(key,value) VALUES ('origin',?)", (origin,))
    connection.execute("INSERT INTO i10_records(id,value,amount) VALUES (1,?,10)",
                       (origin + "-origin",))
    if include_transfer_row:
        marker = "wal-committed-marker" if wal else "transfer-marker"
        connection.execute("INSERT INTO i10_records(id,value,amount) VALUES (2,?,20)", (marker,))
    connection.commit()


def inspect_database(path, wal=False):
    uri = Path(path).resolve().as_uri() + "?mode=ro"
    connection = sqlite3.connect(uri, uri=True)
    try:
        integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
        user_version = connection.execute("PRAGMA user_version").fetchone()[0]
        origin = connection.execute("SELECT value FROM i10_meta WHERE key='origin'").fetchone()[0]
        rows = connection.execute(
            "SELECT id,value,amount FROM i10_records ORDER BY id").fetchall()
        compile_options = [row[0] for row in connection.execute("PRAGMA compile_options")]
        return {"sqliteVersion": sqlite3.sqlite_version, "integrityCheck": integrity,
                "userVersion": user_version, "origin": origin, "rows": rows,
                "compileOptions": compile_options}
    finally:
        connection.close()


def create_host_fixtures(directory):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    external = directory / "external-sqlite.sqlite"
    connection = sqlite3.connect(external)
    create_schema(connection, "external-sqlite")
    connection.execute("PRAGMA journal_mode=DELETE")
    connection.close()

    live = directory / "wal-source.sqlite"
    connection = sqlite3.connect(live)
    connection.execute("PRAGMA journal_mode=WAL")
    create_schema(connection, "external-sqlite", wal=True, include_transfer_row=False)
    connection.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    connection.execute("INSERT INTO i10_records(id,value,amount) VALUES (2,'wal-committed-marker',20)")
    connection.commit()
    wal_source = Path(str(live) + "-wal")
    if not wal_source.is_file() or wal_source.stat().st_size == 0:
        connection.close()
        raise RuntimeError("host SQLite did not leave committed pages in the WAL")
    wal_db = directory / "wal-snapshot.sqlite"
    wal_sidecar = Path(str(wal_db) + "-wal")
    shutil.copy2(live, wal_db)
    shutil.copy2(wal_source, wal_sidecar)
    connection.close()
    (directory / "wal-source.sqlite-shm").unlink(missing_ok=True)
    (directory / "wal-source.sqlite-wal").unlink(missing_ok=True)
    (directory / "wal-source.sqlite").unlink(missing_ok=True)

    external_info = inspect_database(external)
    wal_info = inspect_database(wal_db, wal=True)
    if external_info["integrityCheck"] != "ok" or wal_info["integrityCheck"] != "ok":
        raise RuntimeError("host-created fixture failed integrity_check")
    records = {
        "external-sqlite": fixture_record(external, "external-sqlite", "host-python-sqlite"),
        "wal-snapshot": fixture_record(wal_db, "external-sqlite", "host-python-sqlite",
                                        wal_sidecar=wal_sidecar, wal_marker=True),
    }
    manifest = {"schemaVersion": 1, "host": platform.platform(),
                "sqliteVersion": sqlite3.sqlite_version,
                "compileOptions": external_info["compileOptions"], "fixtures": records}
    (directory / "fixture-index.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return records


def fixture_record(path, origin, writer, wal_sidecar=None, wal_marker=False):
    path = Path(path)
    info = inspect_database(path, wal=wal_marker)
    return {"file": path.name, "sha256": sha256(path), "sizeBytes": path.stat().st_size,
            "headerHex": path.read_bytes()[:16].hex(), "origin": origin,
            "writer": writer, "sqliteVersion": info["sqliteVersion"],
            "compileOptions": info["compileOptions"], "integrityCheck": info["integrityCheck"],
            "userVersion": info["userVersion"], "rows": info["rows"],
            "walFile": wal_sidecar.name if wal_sidecar else None,
            "walSha256": sha256(wal_sidecar) if wal_sidecar else None,
            "walSizeBytes": wal_sidecar.stat().st_size if wal_sidecar else None,
            "walOnlyRowExpected": wal_marker}


def write_config(app_dir, mode, database_path, origin="", expected_origin=""):
    lines = ["mode=" + mode, "databasePath=" + str(database_path)]
    if origin:
        lines.append("origin=" + origin)
    if expected_origin:
        lines.append("expectedOrigin=" + expected_origin)
    (Path(app_dir) / "tc-i10-case.txt").write_text("\n".join(lines) + "\n", encoding="ascii")


def parse_result(log_text):
    events = [line for line in log_text.splitlines() if "TC_I10_EVENT " in line]
    results = [line for line in log_text.splitlines() if "TC_I10_EVENT stage=result " in line]
    return events, results[-1] if results else None


def event_ok(events, stage):
    return any("stage=" + stage + " status=PASS " in line for line in events)


def run_desktop_case(target, build, mode, database_path, out, expected_origin="",
                     origin="", source_file=None, wal_file=None, shim=None):
    app_dir = Path(build["appDir"])
    database_path = Path(database_path)
    if mode in ("create", "invalid"):
        for suffix in ("", "-wal", "-shm", "-journal"):
            Path(str(database_path) + suffix).unlink(missing_ok=True)
        if mode == "invalid":
            database_path.mkdir(parents=True)
    if source_file and Path(source_file).resolve() != database_path.resolve():
        shutil.copy2(source_file, database_path)
    if wal_file:
        shutil.copy2(wal_file, str(database_path) + "-wal")
    write_config(app_dir, mode, database_path, origin, expected_origin)
    env = os.environ.copy()
    executable = Path(build["executable"])
    if target == "linux-x86_64":
        env["LD_LIBRARY_PATH"] = str(app_dir) + os.pathsep + env.get("LD_LIBRARY_PATH", "")
        if shim:
            env["LD_PRELOAD"] = str(shim)
        command = ["xvfb-run", "-a", str(executable)] if shutil.which("xvfb-run") else [str(executable)]
    elif target == "macos-arm64":
        env["DYLD_LIBRARY_PATH"] = str(app_dir) + os.pathsep + env.get("DYLD_LIBRARY_PATH", "")
        command = [str(executable)]
    else:
        command = [str(executable)]
    log = Path(out) / "runtime.log"
    code = run_command(command, app_dir, log, env, timeout=120)
    text = log.read_text(encoding="utf-8", errors="replace") if log.exists() else ""
    debug_console = app_dir / "DebugConsole.txt" if target == "windows-i386" else None
    if debug_console and debug_console.is_file():
        debug_text = debug_console.read_text(encoding="utf-8", errors="replace")
        if debug_text:
            with log.open("a", encoding="utf-8") as stream:
                stream.write("\n--- DebugConsole.txt ---\n")
                stream.write(debug_text)
            text += "\n--- DebugConsole.txt ---\n" + debug_text
    events, result = parse_result(text)
    record = {"target": target, "revision": build["revision"], "mode": mode,
              "processExitCode": code, "completionMarkerObserved": result is not None,
              "events": events, "runtimeLog": str(log),
              "databasePath": str(database_path),
              "debugConsoleLog": str(debug_console) if debug_console else None}
    if result is None:
        record["status"] = "BLOCKED_BEFORE_SQLITE"
        record["failureExcerpt"] = relevant_error(text)
    elif code != 0 or "status=PASS" not in result or "failures=0" not in result:
        record["status"] = "FAIL"
        record["failureExcerpt"] = relevant_error(text)
    elif mode == "create" and not event_ok(events, "create"):
        record["status"] = "FAIL"
    elif mode in ("read", "wal-read") and not event_ok(events, "cross-version-read" if mode == "read" else "wal-snapshot"):
        record["status"] = "FAIL"
    elif mode == "update" and not event_ok(events, "update"):
        record["status"] = "FAIL"
    elif mode == "invalid" and not any("stage=invalid-negative status=EXPECTED_ERROR" in x for x in events):
        record["status"] = "FAIL"
    else:
        record["status"] = "PASS"
    return record


def relevant_error(text):
    patterns = ("undefined symbol", "error while loading shared libraries", "buffer overflow",
                "SIGABRT", "SIGSEGV", "Exception", "ERROR", "fatal")
    lines = [line.strip() for line in text.splitlines()
             if any(pattern.lower() in line.lower() for pattern in patterns)]
    return lines[-8:]


def adb_command(serial, *args, input_data=None, timeout=15):
    return subprocess.run(["adb", "-s", serial, *map(str, args)], input=input_data,
                          stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                          timeout=timeout, check=False)


def android_write(serial, relative_path, data):
    command = ["shell", "run-as", APP_ID, "sh", "-c", "cat > " + relative_path]
    result = adb_command(serial, *command, input_data=data)
    if result.returncode:
        raise RuntimeError("run-as write failed for " + relative_path + ": "
                           + result.stdout.decode(errors="replace")[-500:])


def android_read(serial, relative_path):
    result = adb_command(serial, "exec-out", "run-as", APP_ID, "cat", relative_path,
                         timeout=30)
    if result.returncode:
        raise RuntimeError("run-as read failed for " + relative_path + ": "
                           + result.stdout.decode(errors="replace")[-500:])
    return result.stdout


def android_remote_database(serial, remote_db, output):
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(android_read(serial, remote_db))
    wal_data = adb_command(serial, "exec-out", "run-as", APP_ID, "cat", remote_db + "-wal",
                           timeout=30)
    if wal_data.returncode == 0 and wal_data.stdout:
        Path(str(output) + "-wal").write_bytes(wal_data.stdout)
    return {"path": str(output), "sha256": sha256(output),
            "sizeBytes": output.stat().st_size,
            "walPath": str(output) + "-wal" if Path(str(output) + "-wal").is_file() else None,
            "walSha256": sha256(str(output) + "-wal") if Path(str(output) + "-wal").is_file() else None}


def run_android_case(serial, build, mode, remote_db, out, expected_origin="", origin="",
                     source_file=None, wal_file=None):
    apk = build["apk"]
    install = adb_command(serial, "install", "-r", "-d", apk, timeout=180)
    install_text = install.stdout.decode(errors="replace")
    if install.returncode:
        return {"target": "android-arm64", "revision": build["revision"], "mode": mode,
                "status": "FAIL", "installOutput": install_text[-1000:],
                "completionMarkerObserved": False, "processExitCode": None}
    config = ["mode=" + mode, "databasePath=/data/user/0/" + APP_ID + "/" + remote_db]
    if origin:
        config.append("origin=" + origin)
    if expected_origin:
        config.append("expectedOrigin=" + expected_origin)
    remove_db = mode in ("create", "invalid") or source_file is not None
    files_to_remove = [remote_db + "-wal", remote_db + "-shm", "tc-i10-case.txt"]
    if remove_db:
        files_to_remove.append(remote_db)
    cleanup = adb_command(serial, "shell", "run-as", APP_ID, "sh", "-c",
                          "rm -rf " + " ".join(files_to_remove))
    if cleanup.returncode:
        raise RuntimeError("could not clear Android test database: "
                           + cleanup.stdout.decode(errors="replace")[-500:])
    if mode == "invalid":
        make_directory = adb_command(serial, "shell", "run-as", APP_ID, "mkdir", "-p", remote_db)
        if make_directory.returncode:
            raise RuntimeError("could not create Android invalid database path: "
                               + make_directory.stdout.decode(errors="replace")[-500:])
    if source_file:
        android_write(serial, remote_db, Path(source_file).read_bytes())
    if wal_file:
        android_write(serial, remote_db + "-wal", Path(wal_file).read_bytes())
    android_write(serial, "tc-i10-case.txt", ("\n".join(config) + "\n").encode("ascii"))
    adb_command(serial, "logcat", "-c")
    adb_command(serial, "shell", "am", "force-stop", APP_ID)
    launch = adb_command(serial, "shell", "monkey", "-p", APP_ID,
                         "-c", "android.intent.category.LAUNCHER", "1", timeout=30)
    launch_text = launch.stdout.decode(errors="replace")
    started = time.time()
    pid = ""
    log_text = ""
    while time.time() - started < 120:
        logs = adb_command(serial, "logcat", "-d", "-s", "TotalCross:V", timeout=30)
        log_text = logs.stdout.decode(errors="replace")
        state = adb_command(serial, "shell", "pidof", APP_ID)
        pid = state.stdout.decode(errors="replace").strip()
        if "TC_I10_EVENT stage=result " in log_text and not pid:
            break
        if time.time() - started > 5 and not pid and "TC_I10_EVENT stage=result " not in log_text:
            break
        time.sleep(1)
    state = adb_command(serial, "shell", "pidof", APP_ID)
    pid = state.stdout.decode(errors="replace").strip()
    logs = adb_command(serial, "logcat", "-d", "-s", "TotalCross:V", timeout=30)
    log_text = logs.stdout.decode(errors="replace")
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    runtime_log = out / "runtime.log"
    runtime_log.write_text(launch_text + "\n" + log_text, encoding="utf-8")
    events, result = parse_result(log_text)
    record = {"target": "android-arm64", "revision": build["revision"], "mode": mode,
              "status": "BLOCKED_BEFORE_SQLITE", "completionMarkerObserved": result is not None,
              "processExitCode": None, "processAbsentAfterCompletion": not bool(pid),
              "events": events, "runtimeLog": str(runtime_log), "installOutput": install_text}
    if result and not pid and mode in ("create", "update"):
        try:
            record["databasePull"] = android_remote_database(
                serial, remote_db, out / "database-after-run.sqlite")
        except Exception as error:
            record["databasePullError"] = str(error)
    if result is None:
        record["failureExcerpt"] = relevant_error(launch_text + "\n" + log_text)
    elif not pid and "status=PASS" in result and "failures=0" in result:
        expected = (mode == "invalid" and any("stage=invalid-negative status=EXPECTED_ERROR" in x for x in events))
        expected = expected or (mode == "create" and event_ok(events, "create"))
        expected = expected or (mode == "read" and event_ok(events, "cross-version-read"))
        expected = expected or (mode == "wal-read" and event_ok(events, "wal-snapshot"))
        expected = expected or (mode == "update" and event_ok(events, "update"))
        record["status"] = "PASS" if expected else "FAIL"
        record["processAbsentAfterCompletion"] = True
    else:
        record["status"] = "FAIL"
        record["failureExcerpt"] = relevant_error(launch_text + "\n" + log_text)
    return record


def run_case(target, builds, revision, mode, database_path, out, expected_origin="",
             origin="", source_file=None, wal_file=None, shim=None, adb_serial=None):
    build = builds.get(revision)
    if not build or build.get("status") != "PASS":
        return {"target": target, "revision": revision, "mode": mode,
                "status": "NOT_RUN", "reason": "revision runtime was not buildable"}
    if target == "android-arm64":
        return run_android_case(adb_serial, build, mode, Path(database_path).name, out,
                                expected_origin, origin, source_file, wal_file)
    return run_desktop_case(target, build, mode, database_path, out, expected_origin,
                            origin, source_file, wal_file, shim)


def copy_fixture_files(fixture_dir, output):
    fixture_dir = Path(fixture_dir)
    manifest_path = fixture_dir / "fixture-index.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    destination = Path(output) / "fixtures"
    destination.mkdir(parents=True, exist_ok=True)
    records = {}
    for name, record in manifest["fixtures"].items():
        source = fixture_dir / record["file"]
        if sha256(source) != record["sha256"]:
            raise RuntimeError("fixture SHA-256 mismatch: " + str(source))
        target = destination / record["file"]
        shutil.copy2(source, target)
        if sha256(target) != record["sha256"]:
            raise RuntimeError("copied fixture SHA-256 mismatch: " + str(target))
        copied = dict(record)
        copied["path"] = str(target)
        if record.get("walFile"):
            wal_source = fixture_dir / record["walFile"]
            if sha256(wal_source) != record["walSha256"]:
                raise RuntimeError("WAL fixture SHA-256 mismatch: " + str(wal_source))
            wal_target = destination / record["walFile"]
            shutil.copy2(wal_source, wal_target)
            if sha256(wal_target) != record["walSha256"]:
                raise RuntimeError("copied WAL fixture SHA-256 mismatch: " + str(wal_target))
            copied["walPath"] = str(wal_target)
        records[name] = copied
    for origin, filename in (("7.2.2", "7.2.2.sqlite"),
                             ("7.3.0", "7.3.0.sqlite"),
                             ("candidate-94af", "candidate-94af.sqlite")):
        source = fixture_dir / filename
        if source.is_file():
            target = destination / source.name
            shutil.copy2(source, target)
            info = inspect_database(target)
            if info["integrityCheck"] != "ok":
                raise RuntimeError("runtime fixture integrity_check failed: " + str(target))
            records[origin] = {"file": target.name, "path": str(target),
                            "sha256": sha256(target), "sizeBytes": target.stat().st_size,
                            "headerHex": target.read_bytes()[:16].hex(),
                            "origin": info["origin"], "writer": "TotalCross " + origin,
                            "sqliteVersion": info["sqliteVersion"],
                            "compileOptions": info["compileOptions"],
                            "integrityCheck": info["integrityCheck"],
                            "userVersion": info["userVersion"], "rows": info["rows"]}
    return records


def host_verify_update(path):
    connection = sqlite3.connect(path)
    try:
        integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
        origin = connection.execute("SELECT value FROM i10_meta WHERE key='origin'").fetchone()[0]
        amount = connection.execute("SELECT amount FROM i10_records WHERE id=1").fetchone()[0]
        upgrades = [row[0] for row in connection.execute(
            "SELECT revision FROM i10_upgrades ORDER BY revision")]
        return {"sqliteVersion": sqlite3.sqlite_version, "integrityCheck": integrity,
                "origin": origin, "amount": amount, "upgrades": upgrades,
                "sha256": sha256(path), "headerHex": Path(path).read_bytes()[:16].hex()}
    finally:
        connection.close()


def suite(args):
    out = ensure_new(args.out)
    platform_name = args.target
    builds = {}
    stage_results = {}
    for revision, root in zip(REVISIONS, (args.sdk_722, args.sdk_730, args.sdk_candidate)):
        if root is None or not Path(root).is_dir():
            stage_results[revision] = {"status": "NOT_RUN", "reason": "SDK root unavailable"}
            continue
        build_dir = out / "builds" / revision
        build_dir.parent.mkdir(parents=True, exist_ok=True)
        build = build_app(root, revision, platform_name, build_dir)
        builds[revision] = build
        stage_results[revision] = build

    runs = []
    fixture_dir = out / "fixtures"
    if args.create_fixtures:
        host_fixtures = fixture_dir / "host"
        host_fixtures.mkdir(parents=True)
        create_host_fixtures(host_fixtures)
        # Keep the host-produced databases alongside runtime-produced sources.
        for path in host_fixtures.iterdir():
            if path.is_file():
                shutil.copy2(path, fixture_dir / path.name)
        for revision, origin in (("official-7.2.2", "7.2.2"),
                                 ("official-7.3.0", "7.3.0"),
                                 ("candidate-94af", "candidate-94af")):
            if revision not in builds or builds[revision].get("status") != "PASS":
                continue
            db = fixture_dir / (origin + ".sqlite")
            run = run_case(platform_name, builds, revision, "create", db,
                           out / "fixture-writers" / revision, origin=origin,
                           shim=args.linux_shim, adb_serial=args.adb_serial)
            runs.append({"suite":"fixture-writer", "origin":origin, **run})
            pulled = run.get("databasePull", {}).get("path")
            if run["status"] == "PASS" and pulled and Path(pulled).is_file():
                shutil.copy2(pulled, db)
            if run["status"] == "PASS" and db.is_file():
                record = fixture_record(db, origin, revision)
                host_check = inspect_database(db)
                if host_check["integrityCheck"] != "ok":
                    run["status"] = "FAIL"
                    run["failureExcerpt"] = ["host SQLite integrity_check failed"]
                (fixture_dir / (origin + ".json")).write_text(
                    json.dumps({**record, "hostObservation": host_check}, indent=2) + "\n")
        external_records = json.loads((fixture_dir / "host/fixture-index.json").read_text())
        fixtures = dict(external_records["fixtures"])
        for origin in ("7.2.2", "7.3.0", "candidate-94af"):
            db = fixture_dir / (origin + ".sqlite")
            if db.is_file():
                info = inspect_database(db)
                fixtures[origin] = fixture_record(db, info["origin"], "TotalCross " + origin)
        host_version = sqlite3.sqlite_version
        fixture_manifest = {"schemaVersion":1,"target":platform_name,
                            "hostSqliteVersion":host_version,"fixtures":fixtures}
        (fixture_dir / "fixture-index.json").write_text(
            json.dumps(fixture_manifest, indent=2) + "\n")
    else:
        fixtures = copy_fixture_files(args.fixture_dir, out)

    fixture_by_name = {}
    for name, entry in fixtures.items():
        if "path" not in entry:
            entry["path"] = str(fixture_dir / entry["file"])
        fixture_by_name[name] = entry

    for revision in REVISIONS:
        build = builds.get(revision)
        if not build or build.get("status") != "PASS":
            continue
        for fixture_name, entry in fixture_by_name.items():
            if fixture_name in ("wal-source", "host"):
                continue
            if fixture_name == "wal-snapshot":
                mode = "wal-read"
                db_name = "wal-snapshot.sqlite"
                wal_path = entry.get("walPath") or str(fixture_dir / entry["walFile"])
            else:
                mode = "read"
                db_name = fixture_name + ".sqlite"
                wal_path = None
            db = out / "reader-db" / revision / db_name
            db.parent.mkdir(parents=True, exist_ok=True)
            run = run_case(platform_name, builds, revision, mode, db,
                           out / "reader-runs" / revision / fixture_name,
                           expected_origin=entry["origin"], source_file=entry["path"],
                           wal_file=wal_path, shim=args.linux_shim,
                           adb_serial=args.adb_serial)
            runs.append({"suite":"cross-platform-transfer", "fixture":fixture_name, **run})

        invalid_db = out / "invalid" / (revision + ".sqlite")
        invalid_db.parent.mkdir(parents=True, exist_ok=True)
        run = run_case(platform_name, builds, revision, "invalid", invalid_db,
                       out / "invalid-runs" / revision,
                       shim=args.linux_shim,
                       adb_serial=args.adb_serial)
        runs.append({"suite":"invalid-database-negative-control", **run})

    update_db = out / "update-flow" / "shared-update.sqlite"
    update_db.parent.mkdir(parents=True, exist_ok=True)
    if ("candidate-94af" in builds and builds["candidate-94af"].get("status") == "PASS"
            and "official-7.3.0" in builds
            and builds["official-7.3.0"].get("status") == "PASS"):
        base_revision = ("official-7.2.2" if "official-7.2.2" in builds
                         and builds["official-7.2.2"].get("status") == "PASS"
                         else "official-7.3.0")
        base_origin = "7.2.2" if base_revision == "official-7.2.2" else "7.3.0"
        base_run = run_case(platform_name, builds, base_revision, "create", update_db,
                            out / "update-runs" / base_revision,
                            origin=base_origin, shim=args.linux_shim,
                            adb_serial=args.adb_serial)
        runs.append({"suite":"application-update-persistence", **base_run})
        update_sequence = (("candidate-94af", "update"), ("official-7.3.0", "update"))
        if base_run["status"] != "PASS" and base_revision == "official-7.2.2":
            base_revision = "official-7.3.0"
            base_origin = "7.3.0"
            base_run = run_case(platform_name, builds, base_revision, "create", update_db,
                                out / "update-runs" / (base_revision + "-fallback"),
                                origin=base_origin, shim=args.linux_shim,
                                adb_serial=args.adb_serial)
            runs.append({"suite":"application-update-persistence-fallback", **base_run})
        if base_run["status"] == "PASS":
            for revision, mode in update_sequence:
                run = run_case(platform_name, builds, revision, mode, update_db,
                               out / "update-runs" / revision,
                               expected_origin=base_origin,
                               shim=args.linux_shim, adb_serial=args.adb_serial)
                runs.append({"suite":"application-update-persistence", **run})
                if run["status"] != "PASS":
                    break
        update_runs = [item for item in runs if item.get("suite", "").startswith(
            "application-update-persistence")]
        expected_upgrades = {"candidate-94af", "official-7.3.0"}
        if len(update_runs) >= 2 and all(item["status"] == "PASS" for item in update_runs[-2:]):
            if platform_name == "android-arm64":
                pulled = update_runs[-1].get("databasePull", {}).get("path")
                if pulled and Path(pulled).is_file():
                    shutil.copy2(pulled, update_db)
            update_result = host_verify_update(update_db) if update_db.is_file() else {
                "status":"NOT_RUN","reason":"updated database was not pulled from the app sandbox"}
            update_result["status"] = "PASS" if (
                update_result["integrityCheck"] == "ok" and update_result["origin"] == base_origin
                and update_result["amount"] == 12
                and set(update_result["upgrades"]) == expected_upgrades) else "FAIL"
            update_result["baseRevision"] = base_revision
        else:
            update_result = {"status":"NOT_RUN","reason":"one of the update phases did not pass",
                             "baseRevision":base_revision}
    else:
        update_result = {"status":"NOT_RUN","reason":"candidate or official 7.3.0 runtime unavailable"}

    blockers = [item for item in runs if item["status"] in ("BLOCKED_BEFORE_SQLITE", "NOT_RUN")]
    blockers.extend({"revision": revision, "status": build.get("status"),
                     "reason": build.get("reason", "SDK runtime unavailable")}
                    for revision, build in stage_results.items()
                    if build.get("status") == "NOT_RUN")
    failures = [item for item in runs if item["status"] == "FAIL"]
    failures.extend({"revision": revision, "status": build.get("status"),
                     "reason": build.get("reason", "build/deploy failed")}
                    for revision, build in stage_results.items()
                    if build.get("status") == "FAIL")
    if update_result["status"] == "FAIL":
        failures.append({"suite":"application-update-persistence","failure":update_result})
    result = {"schemaVersion":1,"investigationId":"I10","target":platform_name,
              "host":platform.platform(),"pythonSqliteVersion":sqlite3.sqlite_version,
              "status":"FAIL" if failures else ("INCOMPLETE" if blockers or update_result["status"] != "PASS" else "PASS"),
              "builds":stage_results,"runs":runs,"updatePersistence":update_result,
              "blockedCount":len(blockers),"failureCount":len(failures),
              "fixtureManifest":"fixtures/fixture-index.json",
              "startedAt":args.started_at,"finishedAt":time.time()}
    result_path = out / "i10-result.json"
    result_path.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    print("I10 %s: target=%s pass=%d blocked=%d fail=%d result=%s" % (
        result["status"], platform_name,
        sum(1 for item in runs if item["status"] == "PASS"), len(blockers), len(failures), result_path))
    return 1 if failures else 0


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--target", choices=sorted(TARGETS), required=True)
    parser.add_argument("--sdk-722", type=Path)
    parser.add_argument("--sdk-730", type=Path)
    parser.add_argument("--sdk-candidate", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--create-fixtures", action="store_true")
    parser.add_argument("--fixture-dir", type=Path)
    parser.add_argument("--linux-shim", type=Path)
    parser.add_argument("--adb-serial")
    parser.add_argument("--started-at", type=float, default=time.time())
    args = parser.parse_args()
    if args.create_fixtures and args.fixture_dir:
        parser.error("use either --create-fixtures or --fixture-dir")
    if not args.create_fixtures and args.fixture_dir is None:
        parser.error("--fixture-dir is required unless --create-fixtures is set")
    if args.target == "android-arm64" and not args.adb_serial:
        parser.error("--adb-serial is required for Android")
    if args.target == "linux-x86_64" and not args.linux_shim:
        parser.error("Linux I10 runtime requires the recorded test-only realpath shim")
    return suite(args)


if __name__ == "__main__":
    sys.exit(main())
