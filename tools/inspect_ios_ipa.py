#!/usr/bin/env python3
"""Inspect the TotalCross iOS IPA for real-device device farm test uploads.

Optionally enables Documents file sharing in the IPA Info.plist so Appium on a
physical device can download the test log and SQLite file. This changes only
packaging metadata; the original 7.3.0 TotalCross VM binary remains untouched.
The SDK ships a placeholder provision; Device Farm re-signs on upload.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import plistlib
import sys
import zipfile


def enable_documents_file_sharing(ipa):
    # A Device Farm test can inspect the app's private Documents via
    # mobile: pullFile only when UIFileSharingEnabled is true. Keep the
    # SDK's native executable and packaged TCZ byte-for-byte unchanged.
    temporary = ipa.with_name(ipa.name + ".tmp")
    try:
        with zipfile.ZipFile(ipa) as source, zipfile.ZipFile(temporary, "w") as target:
            names = source.namelist()
            configs = [name for name in names if name.startswith("Payload/")
                       and name.endswith(".app/Info.plist")]
            if len(configs) != 1:
                raise RuntimeError("Missing or ambiguous Payload/*.app/Info.plist")
            changed = False
            for member in source.infolist():
                data = source.read(member.filename)
                if member.filename == configs[0]:
                    payload = plistlib.loads(data)
                    payload["UIFileSharingEnabled"] = True
                    payload["LSSupportsOpeningDocumentsInPlace"] = True
                    data = plistlib.dumps(payload, fmt=plistlib.FMT_XML)
                    changed = True
                target.writestr(member, data)
            if not changed:
                raise RuntimeError("Info.plist not rewritten")
        temporary.replace(ipa)
    finally:
        if temporary.exists():
            temporary.unlink()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--enable-file-sharing", action="store_true",
                        help="Enable iOS Documents sharing for Appium file collection; Device Farm must re-sign IPA")
    args = parser.parse_args()
    out = args.out.resolve()
    artifacts = sorted((out / "deployed" / "install" / "ios").glob("*.ipa"))
    if len(artifacts) != 1:
        raise RuntimeError("Expected exactly one iOS .ipa; found: " + str(artifacts))
    ipa = artifacts[0]
    if args.enable_file_sharing:
        enable_documents_file_sharing(ipa)
    info = {
        "ipa": str(ipa.relative_to(out)),
        "ipaSha256": hashlib.sha256(ipa.read_bytes()).hexdigest(),
        "ipaBytes": ipa.stat().st_size,
        "sdkVersion": "7.3.0",
        "sdkSourceSha": "5464c21e3107e3f1ce9c287b724829e2bb870c1d",
        "testedOnDevice": False,
    }
    with zipfile.ZipFile(ipa) as z:
        names = z.namelist()
        apps = sorted(set(s.split(".app/")[0] + ".app" for s in names
                          if s.startswith("Payload/") and ".app/" in s))
        if len(apps) != 1:
            raise RuntimeError("IPA must contain exactly one Payload/*.app: " + str(apps))
        app = apps[0]
        settings = plistlib.loads(z.read(app + "/Info.plist"))
        exe = app + "/" + settings["CFBundleExecutable"]
        if exe not in names:
            raise RuntimeError("No iOS executable: " + exe)
        magic = z.read(exe)[:4].hex()
        if magic not in ("feedfacf", "cffaedfe", "cafebabe", "bebafeca", "cafebabf", "bfbafeca"):
            raise RuntimeError("Unexpected Mach-O executable magic: " + magic)
        if not any(p.endswith("/sqlite-plaintext-smoke.tcz") for p in names):
            raise RuntimeError("TotalCross test application TCZ is absent from iOS IPA")
        info.update({
            "appBundle": app,
            "bundleIdentifier": settings.get("CFBundleIdentifier"),
            "bundleName": settings.get("CFBundleName"),
            "minIOS": settings.get("MinimumOSVersion"),
            "machoMagic": magic,
            "applicationTczIncluded": True,
            "documentsFileSharingEnabled": settings.get("UIFileSharingEnabled") is True,
            "iosDocsExportEnabledByScript": args.enable_file_sharing,
        })
        provision = app + "/embedded.mobileprovision"
        if provision in names:
            # The TotalCross template profile is a nonstandard *dummy* with
            # a 2-byte prefix before the XML property list.
            raw = z.read(provision)
            start = raw.find(b"<?xml")
            if start >= 0:
                profile = plistlib.loads(raw[start:])
                expiry = profile.get("ExpirationDate")
                if expiry is not None:
                    expiry = expiry.replace(tzinfo=timezone.utc)
                info["embeddedProvisioning"] = {
                    "name": profile.get("Name"),
                    "teamId": profile.get("TeamIdentifier"),
                    "expires": expiry.isoformat() if expiry else None,
                    "expired": expiry < datetime.now(timezone.utc) if expiry else None,
                }
        profile = info.get("embeddedProvisioning") or {}
        # A default, unsigned template cannot be installed as-is on iOS devices.
        info["providerResignRequired"] = (
            profile.get("name") == "Dummy Provision"
            or profile.get("expired") is True
            or info.get("bundleIdentifier") == "com.application.name"
        )
    (out / "ios-devicefarm-metadata.json").write_text(json.dumps(info, indent=2) + "\n")
    guide = (
        "TOTALCROSS 7.3.0 - IOS FILE / SQLITE DEVICE FARM TEST\n\n"
        "IPA: deployed/install/ios/sqlite-plaintext-smoke.ipa\n"
        "SHA256: " + info["ipaSha256"] + "\n"
        "Bundle ID (template): " + str(info.get("bundleIdentifier")) + "\n\n"
        "Run on a PHYSICAL iOS device (not the simulator).\n"
        "The TotalCross SDK IPA includes a dummy/expired embedded provisioning\n"
        "profile. Enable the device farm's automatic IPA re-signing or supply\n"
        "valid signing credentials/profile. This artifact itself is not\n"
        "guaranteed to be directly installable without re-signing.\n\n"
        "Capture the native app console / syslog and search TC_SQLITE_JSON.\n"
        "At startup, iOS File.create/write/flush/size/close/read/delete and\n"
        "directory create/delete run BEFORE the SQLite tests.\n"
        "Each operation emits a BEGIN followed by a PASS: the last BEGIN\n"
        "without PASS indicates the operation where the app froze/crashed.\n"
        "Expected after File tests: SQLite in-memory and private appPath\n"
        "create/reopen/integrity/header and result PASS.\n"
        "The app creates only tc-ios-file-smoke.tmp, tc-ios-dir-smoke,\n"
        "and sqlite-plaintext-smoke.db in its own appPath.\n"
        "Automated Device Farm builds additionally enable Documents sharing\n"
        "and create tc-ios-devicefarm-result.log for Appium pullFile.\n"
    )
    (out / "IOS-DEVICEFARM-README.txt").write_text(guide)
    print("iOS IPA verified:", ipa)
    print("iOS bundle:", info.get("bundleIdentifier"), "min iOS:", info.get("minIOS"))
    print("IPA SHA256:", info["ipaSha256"])
    if info["providerResignRequired"]:
        print("NOTICE: IPA has a placeholder/expired provisioning profile. "
              "Use device-farm re-signing or a valid signing identity.", file=sys.stderr)


if __name__ == "__main__":
    main()
