"""Build a complete OpenCore EFI tree for the B360M / i7-8700 / RX 5500 build.

Stages, each independently runnable and verifiable:

    fetch     download the seven pinned RELEASE archives and verify SHA256
    assemble  unpack them into the EFI/ tree
    smbios    generate iMac19,1 serial / MLB / SystemUUID (ROM placeholder)
    config    generate EFI/OC/config.plist from the release Sample.plist
    verify    run ocvalidate plus cross-checks on every referenced path
    all       fetch -> assemble -> smbios -> config -> verify

Only static verification is possible on this machine (Windows, Ryzen host);
dynamic validation belongs to the target machine and is documented in README.md.
"""

import argparse
import hashlib
import json
import os
import plistlib
import shutil
import subprocess
import sys
import urllib.request
import uuid
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "build" / "cache"
TOOLS = ROOT / "build" / "tools"
EFI = ROOT / "EFI"

# Pinned upstream components (design doc section 5.2).
#
# `sha256` is the value published in the GitHub release API `digest` field, except
# for IntelMausi 1.0.8 where the release predates digests: there the archive was
# downloaded once and hashed locally (reproducible from the pinned URL).
#
# `api_url` is the official GitHub *API asset* endpoint. It returns the identical
# bytes; it is listed first because plain github.com release redirects are not
# reachable from every network while api.github.com is. `url` stays the canonical
# public download URL and is what SOURCES.md documents.
ASSETS = [
    {
        "name": "opencore",
        "version": "1.0.8",
        "url": "https://github.com/acidanthera/OpenCorePkg/releases/download/1.0.8/OpenCore-1.0.8-RELEASE.zip",
        "api_url": "https://api.github.com/repos/acidanthera/OpenCorePkg/releases/assets/593875506",
        "sha256": "2011e8b7216ecb2645d97ea710df965947edd406846e92050b9bc4190be6d27b",
        "members": ["BOOTx64.efi", "OpenCore.efi", "Drivers", "ACPI", "Sample.plist",
                    "macserial", "ocvalidate"],
    },
    {
        "name": "lilu",
        "version": "1.7.2",
        "url": "https://github.com/acidanthera/Lilu/releases/download/1.7.2/Lilu-1.7.2-RELEASE.zip",
        "api_url": "https://api.github.com/repos/acidanthera/Lilu/releases/assets/377952879",
        "sha256": "53967d7dcfaab01023a33df2e969a89522f13d6654a6a56ac4711b62dabf3ab8",
        "members": ["Lilu.kext"],
    },
    {
        "name": "virtualsmc",
        "version": "1.3.8",
        "url": "https://github.com/acidanthera/VirtualSMC/releases/download/1.3.8/VirtualSMC-1.3.8-RELEASE.zip",
        "api_url": "https://api.github.com/repos/acidanthera/VirtualSMC/releases/assets/593862436",
        "sha256": "2e29a8aaf91b4eb0bcdf5913ed17e70f5cf76531122acd4132eff7813a54de8b",
        "members": ["VirtualSMC.kext", "SMCProcessor.kext", "SMCSuperIO.kext"],
    },
    {
        "name": "whatevergreen",
        "version": "1.7.1",
        "url": "https://github.com/acidanthera/WhateverGreen/releases/download/1.7.1/WhateverGreen-1.7.1-RELEASE.zip",
        "api_url": "https://api.github.com/repos/acidanthera/WhateverGreen/releases/assets/593877363",
        "sha256": "1bfdd2d40290ecce237606db121cbc01d7041179f03394bd59660a2ed52e5c95",
        "members": ["WhateverGreen.kext"],
    },
    {
        "name": "applealc",
        "version": "1.9.8",
        "url": "https://github.com/acidanthera/AppleALC/releases/download/1.9.8/AppleALC-1.9.8-RELEASE.zip",
        "api_url": "https://api.github.com/repos/acidanthera/AppleALC/releases/assets/593882851",
        "sha256": "d4d36cd2da7863cf7cbfcb0892d45c08457f4f4ddd065a073dd010e46bd63bcb",
        "members": ["AppleALC.kext"],
    },
    {
        "name": "intelmausi",
        "version": "1.0.8",
        "url": "https://github.com/acidanthera/IntelMausi/releases/download/1.0.8/IntelMausi-1.0.8-RELEASE.zip",
        "api_url": "https://api.github.com/repos/acidanthera/IntelMausi/releases/assets/210764644",
        "sha256": "cc02ea7e972ead536a51e5f6725e79f121026dbf36a766e97044ef2483fd29bc",
        "members": ["IntelMausi.kext"],
    },
    {
        "name": "nvmefix",
        "version": "1.1.3",
        "url": "https://github.com/acidanthera/NVMeFix/releases/download/1.1.3/NVMeFix-1.1.3-RELEASE.zip",
        "api_url": "https://api.github.com/repos/acidanthera/NVMeFix/releases/assets/270693919",
        "sha256": "e1d5657ab7ac31f69771708f7b80bf218ab9aa0b8e4c4fe6ff943983037e3dfb",
        "members": ["NVMeFix.kext"],
    },
]


# Payloads taken from the OpenCore archive and the kext release archives
# (design doc sections 5.3 and 5.4).
ACPI_REQUIRED = ["SSDT-PLUG.aml", "SSDT-EC-USBX.aml", "SSDT-AWAC-DISABLE.aml", "SSDT-PMC.aml"]
ACPI_OPTIONAL = ["SSDT-RTC0.aml"]
DRIVERS = ["OpenRuntime.efi", "OpenHfsPlus.efi", "ResetNvramEntry.efi"]
KEXTS = ["Lilu", "VirtualSMC", "SMCProcessor", "SMCSuperIO",
         "WhateverGreen", "AppleALC", "IntelMausi", "NVMeFix"]
KEXT_ARCHIVE = {
    "Lilu": "lilu",
    "VirtualSMC": "virtualsmc",
    "SMCProcessor": "virtualsmc",
    "SMCSuperIO": "virtualsmc",
    "WhateverGreen": "whatevergreen",
    "AppleALC": "applealc",
    "IntelMausi": "intelmausi",
    "NVMeFix": "nvmefix",
}


# --------------------------------------------------------------------------- utils

def sha256_file(path: Path) -> str:
    """Return the lowercase hex SHA256 of *path*, streaming so big zips are fine."""
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_asset(asset: dict, path: Path) -> None:
    """Assert that *path* exists and hashes to the pinned digest for *asset*."""
    if not path.is_file():
        raise SystemExit(f"missing asset {asset['name']}: {path}")
    actual = sha256_file(path)
    expected = asset["sha256"]
    if actual != expected:
        raise SystemExit(
            f"sha256 mismatch for {asset['name']}: expected {expected}, "
            f"got {actual} ({path})"
        )


def _download(asset: dict, dest: Path) -> None:
    """Download *asset* to *dest*, preferring the GitHub API asset endpoint."""
    last_error = None
    for url in (asset.get("api_url"), asset["url"]):
        if not url:
            continue
        headers = {"User-Agent": "efi-build"}
        if "api.github.com" in url:
            headers["Accept"] = "application/octet-stream"
        try:
            request = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(request, timeout=120) as response, \
                    open(dest, "wb") as handle:
                shutil.copyfileobj(response, handle, 1 << 20)
            return
        except Exception as exc:  # network errors: try the next mirror
            last_error = exc
            print(f"{asset['name']}: download failed from {url}: {exc}")
            dest.unlink(missing_ok=True)
    raise SystemExit(f"download failed for {asset['name']}: {last_error}")


# -------------------------------------------------------------------------- stages

def stage_fetch(cache: Path = CACHE) -> dict[str, Path]:
    """Download all pinned archives into *cache* and verify every SHA256.

    Idempotent: an already-cached archive is re-verified and reused, never
    re-downloaded. A cache entry whose hash is wrong is deleted and reported so
    the next run repairs it instead of failing forever.
    """
    cache.mkdir(parents=True, exist_ok=True)
    paths: dict[str, Path] = {}
    for asset in ASSETS:
        dest = cache / f"{asset['name']}.zip"
        if dest.is_file():
            print(f"{asset['name']}: reusing {dest.stat().st_size} bytes")
        else:
            print(f"{asset['name']}: downloading {asset['url']}")
            _download(asset, dest)
        try:
            verify_asset(asset, dest)
        except SystemExit:
            dest.unlink(missing_ok=True)
            raise
        print(f"{asset['name']}: {dest.stat().st_size} bytes sha256 ok")
        paths[asset["name"]] = dest
    return paths


def _write_member(archive: zipfile.ZipFile, member: str, dest: Path) -> None:
    """Write one archive member to *dest* and prove the copy is byte-identical."""
    data = archive.read(member)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(data)
    if dest.read_bytes() != data:
        raise SystemExit(f"copy mismatch: {member} -> {dest}")


def _extract_kext(cache: Path, efi: Path, name: str) -> None:
    """Extract exactly one ``<name>.kext`` bundle, wherever the release keeps it.

    Release archives place kexts either at the root (Lilu.kext/...) or under
    Kexts/ (VirtualSMC). Locate ``Contents/Info.plist`` recursively, then copy
    everything below that bundle only: dSYMs, READMEs and sibling variants
    (AppleALCU, IntelSnowMausi, SMCBatteryManager, ...) are never copied.
    """
    archive_path = cache / f"{KEXT_ARCHIVE[name]}.zip"
    if not archive_path.is_file():
        raise SystemExit(f"missing archive {archive_path}; run the fetch stage first")
    wanted = f"{name}.kext/Contents/Info.plist"
    with zipfile.ZipFile(archive_path) as archive:
        matches = [m for m in archive.namelist()
                   if m == wanted or m.endswith("/" + wanted)]
        if not matches:
            raise SystemExit(f"{wanted} not found in {archive_path.name}")
        prefix = matches[0][: -len("Contents/Info.plist")]
        dest_root = efi / "OC" / "Kexts" / f"{name}.kext"
        for member in archive.namelist():
            if not member.startswith(prefix) or member.endswith("/"):
                continue
            _write_member(archive, member, dest_root / member[len(prefix):])


def stage_assemble(cache: Path = CACHE, efi: Path = EFI) -> None:
    """Build the EFI/ tree from the pinned archives (idempotent)."""
    cache, efi = Path(cache), Path(efi)
    required = [cache / f"{a['name']}.zip" for a in ASSETS]
    missing = [str(p) for p in required if not p.is_file()]
    if missing:
        raise SystemExit(f"missing archives (run fetch first): {', '.join(missing)}")

    with zipfile.ZipFile(cache / "opencore.zip") as archive:
        _write_member(archive, "X64/EFI/BOOT/BOOTx64.efi", efi / "BOOT" / "BOOTx64.efi")
        _write_member(archive, "X64/EFI/OC/OpenCore.efi", efi / "OC" / "OpenCore.efi")
        for name in DRIVERS:
            _write_member(archive, f"X64/EFI/OC/Drivers/{name}",
                          efi / "OC" / "Drivers" / name)
        for name in ACPI_REQUIRED:
            _write_member(archive, f"Docs/AcpiSamples/Binaries/{name}",
                          efi / "OC" / "ACPI" / name)
        for name in ACPI_OPTIONAL:
            _write_member(archive, f"Docs/AcpiSamples/Binaries/{name}",
                          efi / "OC" / "ACPI" / "optional" / name)

    for name in KEXTS:
        _extract_kext(cache, efi, name)

    # Kept empty (no OpenCanopy theme, no OpenShell); placeholders keep the
    # directories alive in git.
    for empty in (efi / "OC" / "Resources", efi / "OC" / "Tools"):
        empty.mkdir(parents=True, exist_ok=True)
        placeholder = empty / ".gitkeep"
        if not placeholder.exists():
            placeholder.write_text("", encoding="utf-8")
    print(f"assemble: {efi} ready")


# ------------------------------------------------------------------------ smbios

def _extract_tool(archive_path: Path, member: str, dest: Path) -> None:
    """Extract one executable (macserial / ocvalidate) into build/tools."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive_path) as archive:
        data = archive.read(member)
    dest.write_bytes(data)
    print(f"extracted {dest.name} ({len(data)} bytes)")


def valid_smbios(data: object) -> bool:
    """True when *data* has usable iMac19,1 serial / MLB / UUID / ROM values."""
    if not isinstance(data, dict):
        return False
    serial, mlb, system_uuid, rom = (data.get(k) for k in ("serial", "mlb", "uuid", "rom"))
    return (
        isinstance(serial, str) and len(serial) == 12
        and isinstance(mlb, str) and len(mlb) == 17
        and isinstance(system_uuid, str)
        and len(system_uuid) == 36 and system_uuid.count("-") == 4
        and isinstance(rom, str) and len(rom) == 12
        and all(c in "0123456789ABCDEF" for c in rom)
    )


def stage_smbios(cache: Path = CACHE, out: Path | None = None) -> dict:
    """Generate (or reuse) iMac19,1 serial, MLB, SystemUUID and ROM placeholder.

    ``macserial`` 1.0.8 prints ``Serial | MLB`` only -- there is no UUID column --
    so SystemUUID is a fresh RFC 4122 v4 value. ROM is 6 random bytes shown as
    12 uppercase hex digits; README tells the user to replace it with the real
    wired-NIC MAC later.

    Idempotent by design (R4): a schema-valid build/smbios.json is reused, so
    rerunning the pipeline never invalidates a config.plist already generated
    from those codes.
    """
    out = Path(out) if out is not None else ROOT / "build" / "smbios.json"
    if out.is_file():
        try:
            cached = json.loads(out.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            cached = None
        else:
            if valid_smbios(cached):
                print(f"smbios: reusing {out} (serial {cached['serial']})")
                return cached

    macserial = TOOLS / "macserial.exe"
    if not macserial.is_file():
        _extract_tool(Path(cache) / "opencore.zip", "Utilities/macserial/macserial.exe", macserial)

    result = subprocess.run(
        [str(macserial), "-m", "iMac19,1", "-n", "1"],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        raise SystemExit(f"macserial failed ({result.returncode}): {result.stderr.strip()}")

    lines = [line for line in result.stdout.splitlines() if line.strip()]
    if not lines:
        raise SystemExit(f"macserial produced no output: {result.stderr.strip()}")
    columns = [part.strip() for part in lines[0].split("|")]
    if len(columns) < 2:
        raise SystemExit(f"unexpected macserial output: {lines[0]!r}")

    data = {
        "serial": columns[0],
        "mlb": columns[1],
        "uuid": str(uuid.uuid4()).upper(),
        "rom": os.urandom(6).hex().upper(),
    }
    if not valid_smbios(data):
        raise SystemExit(f"macserial produced invalid values: {data}")

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"smbios: iMac19,1 serial={data['serial']} mlb={data['mlb']}")
    print(f"smbios: uuid={data['uuid']} rom={data['rom']} (ROM is a placeholder)")
    return data


# ---------------------------------------------------------------- config stage

#: ACPI tables loaded in a fixed, reviewable order (design §5.3).
ACPI_ADD = [
    ("SSDT-PLUG.aml", "CPU power management"),
    ("SSDT-EC-USBX.aml", "Embedded controller and USB power"),
    ("SSDT-AWAC-DISABLE.aml", "Disable AWAC so the legacy RTC is used"),
    ("SSDT-PMC.aml", "Native NVRAM on 300-series boards"),
]

#: Per-kext comments, in load order (design §5.4). KEXTS holds the names.
KEXT_COMMENTS = {
    "Lilu": "Patch engine",
    "VirtualSMC": "SMC emulator",
    "SMCProcessor": "CPU sensor plugin",
    "SMCSuperIO": "Super I/O sensor plugin",
    "WhateverGreen": "Video patches",
    "AppleALC": "Audio patches",
    "IntelMausi": "Intel Ethernet LAN",
    "NVMeFix": "NVMe power management fixes",
}


#: Minimum macOS kernel version each kext supports (blank = all).
KEXT_MIN_KERNELS = {
    "Lilu": "8.0.0",
    "VirtualSMC": "8.0.0",
    "SMCProcessor": "8.0.0",
    "SMCSuperIO": "8.0.0",
    "WhateverGreen": "10.0.0",
    "AppleALC": "8.0.0",
    "IntelMausi": "13.0.0",
    "NVMeFix": "17.0.0",
}

DRIVER_COMMENTS = {
    "OpenRuntime.efi": "Runtime services and NVRAM support",
    "OpenHfsPlus.efi": "HFS+ driver",
    "ResetNvramEntry.efi": "Reset NVRAM boot entry",
}

#: Exact boot arguments required by design §5.5.
BOOT_ARGS = "-v keepsyms=1 debug=0x100 agdpmod=pikera alcid=1"


def _strip_comments(obj):
    """Drop OpenCore's ``#WARNING``/``#INFO`` documentation keys."""
    if isinstance(obj, dict):
        return {k: _strip_comments(v) for k, v in obj.items() if not k.startswith("#")}
    if isinstance(obj, list):
        return [_strip_comments(v) for v in obj]
    return obj


def _require(path, what):
    if not path.exists():
        raise SystemExit(f"config: {what} missing at {path}")


def stage_config(efi=EFI, smbios=None, sample=None):
    """Write EFI/OC/config.plist from the release Sample.plist plus §5.5 tweaks.

    ``smbios`` may be a dict or a path to build/smbios.json; when omitted the
    smbios stage runs (and honours its own caching).  ``sample`` defaults to the
    copy extracted from the OpenCore archive.
    """
    efi = Path(efi)
    sample = Path(sample) if sample is not None else TOOLS / "Sample.plist"
    if not sample.is_file():
        _extract_tool(Path(CACHE) / "opencore.zip", "Docs/Sample.plist", sample)

    if smbios is None:
        smbios = stage_smbios()
    elif not isinstance(smbios, dict):
        smbios = json.loads(Path(smbios).read_text(encoding="utf-8"))
    if not valid_smbios(smbios):
        raise SystemExit(f"config: invalid smbios data: {smbios}")

    cfg = _strip_comments(plistlib.loads(sample.read_bytes()))

    cfg["ACPI"]["Add"] = [
        {"Comment": comment, "Enabled": True, "Path": path}
        for path, comment in ACPI_ADD
    ]

    # RX 5500 (Navi 14) uses the native driver; only the connector-less
    # framebuffer id is injected, matching agdpmod=pikera in boot-args.
    cfg["DeviceProperties"]["Add"] = {
        "PciRoot(0x0)/Pci(0x2,0x0)": {"AAPL,ig-platform-id": bytes.fromhex("0300913E")}
    }
    cfg["DeviceProperties"]["Delete"] = {}

    cfg["Kernel"]["Add"] = []
    for name in KEXTS:
        # Every bundle's CFBundleExecutable matches its bundle stem.
        executable = name
        cfg["Kernel"]["Add"].append({
            "Arch": "Any",
            "BundlePath": f"{name}.kext",
            "Comment": KEXT_COMMENTS[name],
            "Enabled": True,
            "ExecutablePath": f"Contents/MacOS/{executable}",
            "MaxKernel": "",
            "MinKernel": KEXT_MIN_KERNELS[name],
            "PlistPath": "Contents/Info.plist",
        })

    kq = cfg["Kernel"]["Quirks"]
    kq.update({
        "AppleXcpmCfgLock": True,       # Coffee Lake needs this without a DSDT patch
        "CustomSMBIOSGuid": False,
        "DisableIoMapper": True,        # VT-d is disabled in BIOS; macOS must not touch the IOMMU
        "DisableLinkeditJettison": True,
        "PanicNoKextDump": True,
        "PowerTimeoutKernelPanic": True,
        "SetApfsTrimTimeout": -1,
        "XhciPortLimit": False,         # inert on Ventura; ports are mapped post-install (USBToolBox)
    })

    bq = cfg["Booter"]["Quirks"]
    bq.update({
        "DevirtualiseMmio": True,
        "EnableWriteUnprotector": False,
        "RebuildAppleMemoryMap": True,
        "ResizeAppleGpuBars": -1,
        "SetupVirtualMap": True,
        "SyncRuntimePermissions": True,
    })

    cfg["Misc"]["Boot"].update({
        "HideAuxiliary": True,
        "LauncherOption": "Disabled",
        "PickerMode": "Builtin",
        "TakeoffDelay": 0,
    })
    cfg["Misc"]["Debug"].update({
        "AppleDebug": True,
        "ApplePanic": True,
        "DisableWatchDog": True,
        "DisplayLevel": 2147483650,
        "Target": 67,
    })
    cfg["Misc"]["Security"].update({
        "AllowSetDefault": True,
        "BlacklistAppleUpdate": True,
        "DmgLoading": "Signed",
        "ExposeSensitiveData": 6,
        "ScanPolicy": 0,
        "SecureBootModel": "Default",
        "Vault": "Optional",
    })
    # EFI/OC/Tools ships empty, so no tools may be referenced.
    cfg["Misc"]["Tools"] = []

    nvram = cfg["NVRAM"]["Add"]["7C436110-AB2A-4BBB-A880-FE41995C9F82"]
    nvram.update({
        "boot-args": BOOT_ARGS,
        "csr-active-config": bytes(4),   # all SIP bits cleared
        "prev-lang:kbd": "en-US:0",
        "run-efi-updater": "No",
    })
    cfg["NVRAM"]["WriteFlash"] = True

    generic = cfg["PlatformInfo"]["Generic"]
    generic.update({
        "MLB": smbios["mlb"],
        "ProcessorType": 0,
        "ROM": bytes.fromhex(smbios["rom"]),
        "SystemProductName": "iMac19,1",
        "SystemSerialNumber": smbios["serial"],
        "SystemUUID": smbios["uuid"],
    })
    cfg["PlatformInfo"].update({
        "Automatic": True,
        "UpdateSMBIOS": True,
        "UpdateSMBIOSMode": "Create",
    })

    cfg["UEFI"]["APFS"].update({
        "EnableJumpstart": True,
        "MinDate": 0,
        "MinVersion": 0,
    })
    cfg["UEFI"]["ConnectDrivers"] = True
    cfg["UEFI"]["Drivers"] = [
        {
            "Arguments": "",
            "Comment": DRIVER_COMMENTS[path],
            "Enabled": True,
            "HideVerbose": False,
            "LoadEarly": False,
            "Path": path,
        }
        for path in DRIVERS
    ]
    cfg["UEFI"]["Input"]["KeySupport"] = True
    cfg["UEFI"]["Output"]["ProvideConsoleGop"] = True
    cfg["UEFI"]["Quirks"].update({
        "ReleaseUsbOwnership": True,
        "RequestBootVarRouting": True,
        "ResizeGpuBars": -1,
    })

    # Fail loudly before writing a config that points at missing files.
    for path in (p for p, _ in ACPI_ADD):
        _require_exact(efi / "OC" / "ACPI", path, "ACPI table")
    for name in KEXTS:
        bundle = Path("Kexts") / f"{name}.kext"
        _require_exact(efi / "OC", bundle, "kext bundle")
        _require_exact(efi / "OC", bundle / "Contents" / "MacOS" / name,
                       "kext executable")
    for path in DRIVERS:
        _require_exact(efi / "OC" / "Drivers", path, "UEFI driver")

    out = efi / "OC" / "config.plist"
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("wb") as fh:
        plistlib.dump(cfg, fh, fmt=plistlib.FMT_XML, sort_keys=False)
    plistlib.loads(out.read_bytes())
    print(f"config: wrote {out} ({out.stat().st_size} bytes, "
          f"{len(cfg['Kernel']['Add'])} kexts, {len(cfg['ACPI']['Add'])} ACPI tables)")
    return None


# ---------------------------------------------------------------- verify stage

def _require_exact(base, relative, what):
    """Require each component of ``relative`` under ``base`` with exact case.

    Windows path lookups are case-insensitive, so ``Path.exists()`` accepts
    ``ACPI/SSDT-plug.aml`` for ``SSDT-PLUG.aml``; macOS would silently fail to
    load that table.  Walk the tree and match names against ``os.listdir``.
    """
    base = Path(base)
    relative = Path(relative)
    current = base
    for part in relative.parts:
        try:
            entries = os.listdir(current)
        except OSError:
            entries = []
        if part not in entries:
            raise SystemExit(f"config: {what} missing at {base / relative}")
        current = current / part
    return current


def _check_config_paths(cfg, efi):
    """Cross-check every path the config tells OpenCore to load."""
    oc = efi / "OC"
    for a in cfg["ACPI"]["Add"]:
        _require_exact(oc / "ACPI", a["Path"], f"ACPI table {a['Path']}")
    for k in cfg["Kernel"]["Add"]:
        bundle = Path("Kexts") / k["BundlePath"]
        _require_exact(oc, bundle, f"kext {k['BundlePath']}")
        if k["ExecutablePath"]:
            _require_exact(oc, bundle / k["ExecutablePath"],
                           f"kext executable {k['BundlePath']}/{k['ExecutablePath']}")
    for d in cfg["UEFI"]["Drivers"]:
        _require_exact(oc / "Drivers", d["Path"], f"driver {d['Path']}")
    for t in cfg["Misc"]["Tools"]:
        _require_exact(oc / "Tools", t["Path"], f"tool {t['Path']}")


def stage_verify(efi=EFI, cache=CACHE):
    """Validate the generated config with ocvalidate and static path checks.

    Returns ocvalidate's console output.  Any non-zero exit code, any "error"
    in the output, or any config path missing from the tree is fatal.
    """
    efi = Path(efi)
    cache = Path(cache)
    config = efi / "OC" / "config.plist"
    if not config.is_file():
        raise SystemExit(f"verify: missing {config}")

    ocvalidate = TOOLS / "ocvalidate.exe"
    if not ocvalidate.is_file():
        _extract_tool(cache / "opencore.zip",
                      "Utilities/ocvalidate/ocvalidate.exe", ocvalidate)

    result = subprocess.run(
        [str(ocvalidate), "config.plist"],
        cwd=efi / "OC", capture_output=True, text=True,
    )
    output = result.stdout + result.stderr
    print(output.rstrip())
    if result.returncode != 0:
        raise SystemExit(f"verify: ocvalidate exited {result.returncode}")
    # Some builds print "errors" yet exit 0, so inspect the text as well.
    if "error" in output.lower():
        raise SystemExit(f"verify: ocvalidate reported errors:\n{output}")

    cfg = plistlib.loads(config.read_bytes())
    _require(efi / "BOOT" / "BOOTx64.efi", "OpenCore boot entry")
    _require(efi / "OC" / "OpenCore.efi", "OpenCore core")
    _check_config_paths(cfg, efi)
    print(f"verify: ocvalidate clean, every referenced path exists "
          f"({len(cfg['ACPI']['Add'])} ACPI tables, "
          f"{len(cfg['Kernel']['Add'])} kexts, "
          f"{len(cfg['UEFI']['Drivers'])} drivers, "
          f"{len(cfg['Misc']['Tools'])} tools)")
    return output


# ---------------------------------------------------------------------------- main

def main(argv=None):
    parser = argparse.ArgumentParser(prog="build.py")
    parser.add_argument("cmd", choices=["fetch", "assemble", "smbios", "config", "verify", "all"])
    args, _ = parser.parse_known_args(argv)

    if args.cmd == "fetch":
        stage_fetch()
        return 0
    if args.cmd == "assemble":
        stage_assemble()
        return 0
    if args.cmd == "smbios":
        stage_smbios()
        return 0
    if args.cmd == "config":
        stage_config()
        return 0
    if args.cmd == "verify":
        stage_verify()
        return 0
    if args.cmd == "all":
        stage_fetch()
        stage_assemble()
        stage_smbios()
        stage_config()
        stage_verify()
        return 0

    print(f"stage {args.cmd}: not implemented yet")
    return 1


if __name__ == "__main__":
    sys.exit(main())