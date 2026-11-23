import subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PY = sys.executable
fails = 0

def check(name, cond):
    global fails
    print(("OK   " if cond else "FAIL ") + name)
    if not cond:
        fails += 1

def run(*args):
    return subprocess.run([PY, str(ROOT / "scripts" / "build.py"), *args],
                          capture_output=True, text=True)

check("build.py 可执行 --help", run("--help").returncode == 0)
check("未知子命令返回非 0", run("nope").returncode != 0)

# ---------------- Task 2: fetch + SHA256 ----------------
import hashlib, importlib.util, tempfile

spec = importlib.util.spec_from_file_location("build", ROOT / "scripts" / "build.py")
b = importlib.util.module_from_spec(spec)
spec.loader.exec_module(b)

check("资产数为 7", len(b.ASSETS) == 7)
for a in b.ASSETS:
    check(f"资产字段完整 {a.get('name')}",
          all(k in a for k in ("name", "version", "url", "sha256", "members")))
    check(f"sha256 形如 64 位小写 hex {a.get('name')}",
          len(a.get("sha256", "")) == 64
          and all(ch in "0123456789abcdef" for ch in a.get("sha256", "")))

check("sha256_file 存在", hasattr(b, "sha256_file"))
if hasattr(b, "sha256_file"):
    with tempfile.NamedTemporaryFile(delete=False) as fh:
        fh.write(b"abc")
        tmp = Path(fh.name)
    try:
        check("sha256_file 与 hashlib 一致",
              b.sha256_file(tmp) == hashlib.sha256(b"abc").hexdigest())
    finally:
        tmp.unlink()

check("verify_asset 存在", hasattr(b, "verify_asset"))
if hasattr(b, "verify_asset"):
    with tempfile.NamedTemporaryFile(delete=False) as fh:
        fh.write(b"not the pinned bytes")
        tmp = Path(fh.name)
    try:
        try:
            b.verify_asset({"name": "probe", "sha256": "0" * 64}, tmp)
            ok = False
        except SystemExit as exc:
            ok = "sha256 mismatch" in str(exc)
        check("verify_asset 哈希不符时 SystemExit('sha256 mismatch')", ok)
    finally:
        tmp.unlink()

for a in b.ASSETS:
    z = ROOT / "build" / "cache" / (a["name"] + ".zip")
    check(f"资产存在 {a['name']}", z.exists())
    if z.exists():
        h = hashlib.sha256(z.read_bytes()).hexdigest()
        check(f"哈希匹配 {a['name']}", h == a["sha256"])

# ---------------- Task 3: assemble EFI tree ----------------
import plistlib, zipfile

r = run("assemble")
check("assemble 成功", r.returncode == 0)

KEXTS = ["Lilu", "VirtualSMC", "SMCProcessor", "SMCSuperIO",
         "WhateverGreen", "AppleALC", "IntelMausi", "NVMeFix"]
want = [
    "BOOT/BOOTx64.efi", "OC/OpenCore.efi",
    "OC/Drivers/OpenRuntime.efi", "OC/Drivers/OpenHfsPlus.efi",
    "OC/Drivers/ResetNvramEntry.efi",
    *[f"OC/Kexts/{k}.kext/Contents/Info.plist" for k in KEXTS],
    "OC/ACPI/SSDT-PLUG.aml", "OC/ACPI/SSDT-EC-USBX.aml",
    "OC/ACPI/SSDT-AWAC-DISABLE.aml", "OC/ACPI/SSDT-PMC.aml",
    "OC/ACPI/optional/SSDT-RTC0.aml",
]
for rel in want:
    check(f"存在 {rel}", (ROOT / "EFI" / rel).exists())

check("Resources 目录存在", (ROOT / "EFI" / "OC" / "Resources").is_dir())
check("Tools 目录存在", (ROOT / "EFI" / "OC" / "Tools").is_dir())

# 只保留 8 个 kext，不夹带 dSYM / README / AppleALCU 等
kext_dir = ROOT / "EFI" / "OC" / "Kexts"
got = sorted(p.name for p in kext_dir.glob("*.kext")) if kext_dir.is_dir() else []
check("Kexts 恰好 8 个 .kext", got == sorted(k + ".kext" for k in KEXTS))
check("无 dSYM 残留", not list(kext_dir.rglob("*.dSYM")) if kext_dir.is_dir() else False)

for name in KEXTS:
    info = kext_dir / f"{name}.kext" / "Contents" / "Info.plist"
    check(f"kext Info.plist {name}", info.exists())
    if info.exists():
        meta = plistlib.loads(info.read_bytes())
        check(f"kext CFBundleIdentifier {name}", bool(meta.get("CFBundleIdentifier")))
        exe = meta.get("CFBundleExecutable")
        check(f"kext CFBundleExecutable {name}", bool(exe))
        if exe:
            check(f"kext 可执行文件 {name}",
                  (info.parent / "MacOS" / exe).exists())

# 字节一致性：assembled 文件必须与 zip 内成员逐字节相同
with zipfile.ZipFile(ROOT / "build" / "cache" / "opencore.zip") as zf:
    src = zf.read("X64/EFI/BOOT/BOOTx64.efi")
boot = ROOT / "EFI" / "BOOT" / "BOOTx64.efi"
check("BOOTx64.efi 与 zip 字节一致", boot.is_file() and boot.read_bytes() == src)
with zipfile.ZipFile(ROOT / "build" / "cache" / "lilu.zip") as zf:
    src = zf.read("Lilu.kext/Contents/Info.plist")
lilu_info = kext_dir / "Lilu.kext" / "Contents" / "Info.plist"
check("Lilu Info.plist 与 zip 字节一致",
      lilu_info.is_file() and lilu_info.read_bytes() == src)

r = run("assemble")
check("assemble 可重复执行", r.returncode == 0)

# ---------------- Task 4: SMBIOS ----------------
import json

r = run("smbios")
check("smbios 成功", r.returncode == 0)
smbios_path = ROOT / "build" / "smbios.json"
check("smbios.json 存在", smbios_path.exists())
if smbios_path.exists():
    d = json.loads(smbios_path.read_text(encoding="utf-8"))
    check("serial 12 位", isinstance(d.get("serial"), str) and len(d["serial"]) == 12)
    check("mlb 17 位", isinstance(d.get("mlb"), str) and len(d["mlb"]) == 17)
    check("uuid 36 位",
          isinstance(d.get("uuid"), str) and len(d["uuid"]) == 36 and d["uuid"].count("-") == 4)
    check("rom 12 位 hex",
          isinstance(d.get("rom"), str) and len(d["rom"]) == 12
          and all(c in "0123456789ABCDEF" for c in d["rom"]))
    check("iMac19,1 序列号前缀", d["serial"].startswith("C02"))

    # R4: 幂等——再次运行不得生成新三码
    first = dict(d)
    r = run("smbios")
    check("smbios 可重复执行", r.returncode == 0)
    check("smbios 幂等（三码不变）",
          json.loads(smbios_path.read_text(encoding="utf-8")) == first)

# ---------------- Task 5: config.plist ----------------
r = run("config")
check("config 成功", r.returncode == 0)
p = ROOT / "EFI" / "OC" / "config.plist"
check("config.plist 存在", p.exists())
if p.exists():
    c = plistlib.loads(p.read_bytes())
    nvram = c["NVRAM"]["Add"]["7C436110-AB2A-4BBB-A880-FE41995C9F82"]
    boot_args = nvram["boot-args"]

    check("config 可被 plistlib 解析", isinstance(c, dict))
    smb = json.loads((ROOT / "build" / "smbios.json").read_text(encoding="utf-8"))
    check("boot-args", boot_args == "-v keepsyms=1 debug=0x100 agdpmod=pikera alcid=1")
    check("product", c["PlatformInfo"]["Generic"]["SystemProductName"] == "iMac19,1")
    check("ig-platform",
          c["DeviceProperties"]["Add"]["PciRoot(0x0)/Pci(0x2,0x0)"]["AAPL,ig-platform-id"]
          == bytes.fromhex("0300913E"))

    names = [k["BundlePath"].split("/")[0].replace(".kext", "")
             for k in c["Kernel"]["Add"] if k["Enabled"]]
    check("kext 数 8", len(names) == 8)
    check("Lilu 第一", names and names[0] == "Lilu")
    check("kext 顺序完全正确",
          names == ["Lilu", "VirtualSMC", "SMCProcessor", "SMCSuperIO",
                    "WhateverGreen", "AppleALC", "IntelMausi", "NVMeFix"])
    if "VirtualSMC" in names and "SMCProcessor" in names:
        check("VirtualSMC 早于 SMC*", names.index("VirtualSMC") < names.index("SMCProcessor"))
    check("XhciPortLimit 关", c["Kernel"]["Quirks"]["XhciPortLimit"] is False)
    check("agdpmod 黑屏补丁参数在", "agdpmod=pikera" in boot_args)

    for a in c["ACPI"]["Add"]:
        check(f"ACPI 文件存在 {a['Path']}", (ROOT / "EFI" / "OC" / "ACPI" / a["Path"]).exists())
    check("ACPI 4 项且全启用",
          len(c["ACPI"]["Add"]) == 4 and all(a["Enabled"] for a in c["ACPI"]["Add"]))
    for k in c["Kernel"]["Add"]:
        base = ROOT / "EFI" / "OC" / "Kexts"
        check(f"kext 目录存在 {k['BundlePath']}", (base / k["BundlePath"]).exists())
        check(f"kext 可执行路径存在 {k['BundlePath']}",
              (base / k["BundlePath"] / k["ExecutablePath"]).exists())
    for drv in c["UEFI"]["Drivers"]:
        check(f"driver 存在 {drv['Path']}", (ROOT / "EFI" / "OC" / "Drivers" / drv["Path"]).exists())
    check("drivers 恰好 3 个且全启用",
          [d["Path"] for d in c["UEFI"]["Drivers"] if d["Enabled"]]
          == ["OpenRuntime.efi", "OpenHfsPlus.efi", "ResetNvramEntry.efi"])
    check("drivers 均声明 HideVerbose",
          all(isinstance(drv.get("HideVerbose"), bool) for drv in c["UEFI"]["Drivers"]))
    check("Misc.Tools 为空（Tools/ 未放工具）", c["Misc"]["Tools"] == [])

    bq = c["Booter"]["Quirks"]
    check("Booter DevirtualiseMmio", bq["DevirtualiseMmio"] is True)
    check("Booter EnableWriteUnprotector 关", bq["EnableWriteUnprotector"] is False)
    check("Booter ProtectUefiServices 关", bq["ProtectUefiServices"] is False)
    check("Booter RebuildAppleMemoryMap", bq["RebuildAppleMemoryMap"] is True)
    check("Booter SetupVirtualMap", bq["SetupVirtualMap"] is True)
    check("Booter SyncRuntimePermissions", bq["SyncRuntimePermissions"] is True)
    check("Booter ResizeAppleGpuBars", bq["ResizeAppleGpuBars"] == -1)

    kq = c["Kernel"]["Quirks"]
    for key in ("AppleXcpmCfgLock", "DisableIoMapper", "PanicNoKextDump",
                "PowerTimeoutKernelPanic", "DisableLinkeditJettison"):
        check(f"Kernel Quirks {key}", kq[key] is True)
    check("Kernel SetApfsTrimTimeout", kq["SetApfsTrimTimeout"] == -1)
    check("Kernel CustomSMBIOSGuid 关", kq["CustomSMBIOSGuid"] is False)

    mb = c["Misc"]["Boot"]
    check("Misc.Boot HideAuxiliary", mb["HideAuxiliary"] is True)
    check("Misc.Boot PickerMode", mb["PickerMode"] == "Builtin")
    check("Misc.Boot TakeoffDelay", mb["TakeoffDelay"] == 0)
    check("Misc.Boot LauncherOption", mb["LauncherOption"] == "Disabled")

    md = c["Misc"]["Debug"]
    check("Misc.Debug AppleDebug", md["AppleDebug"] is True)
    check("Misc.Debug ApplePanic", md["ApplePanic"] is True)
    check("Misc.Debug DisableWatchDog", md["DisableWatchDog"] is True)
    check("Misc.Debug Target", md["Target"] == 67)
    check("Misc.Debug DisplayLevel", md["DisplayLevel"] == 2147483650)

    ms = c["Misc"]["Security"]
    check("Misc.Security SecureBootModel", ms["SecureBootModel"] == "Default")
    check("Misc.Security Vault", ms["Vault"] == "Optional")
    check("Misc.Security DmgLoading", ms["DmgLoading"] == "Signed")
    check("Misc.Security ScanPolicy", ms["ScanPolicy"] == 0)
    check("Misc.Security BlacklistAppleUpdate", ms["BlacklistAppleUpdate"] is True)
    check("Misc.Security AllowSetDefault", ms["AllowSetDefault"] is True)
    check("Misc.Security ExposeSensitiveData", ms["ExposeSensitiveData"] == 6)

    gen = c["PlatformInfo"]["Generic"]
    check("PlatformInfo Automatic", c["PlatformInfo"]["Automatic"] is True)
    check("PlatformInfo UpdateSMBIOSMode", c["PlatformInfo"]["UpdateSMBIOSMode"] == "Create")
    check("PlatformInfo ProcessorType", gen["ProcessorType"] == 0)
    check("PlatformInfo 序列号来自 smbios.json",
          gen["SystemSerialNumber"] == smb["serial"])
    check("PlatformInfo MLB 来自 smbios.json", gen["MLB"] == smb["mlb"])
    check("PlatformInfo UUID 来自 smbios.json", gen["SystemUUID"] == smb["uuid"])
    check("PlatformInfo ROM 为 bytes", gen["ROM"] == bytes.fromhex(smb["rom"]))

    check("NVRAM csr-active-config 全关", nvram["csr-active-config"] == bytes(4))
    check("NVRAM run-efi-updater", nvram["run-efi-updater"] == "No")
    check("NVRAM prev-lang:kbd 字符串", nvram["prev-lang:kbd"] == "en-US:0")
    check("NVRAM WriteFlash", c["NVRAM"]["WriteFlash"] is True)

    ue = c["UEFI"]
    check("UEFI ConnectDrivers", ue["ConnectDrivers"] is True)
    check("UEFI APFS EnableJumpstart", ue["APFS"]["EnableJumpstart"] is True)
    check("UEFI APFS MinVersion", ue["APFS"]["MinVersion"] == 0)
    check("UEFI Input KeySupport", ue["Input"]["KeySupport"] is True)
    check("UEFI Output ProvideConsoleGop", ue["Output"]["ProvideConsoleGop"] is True)
    check("UEFI RequestBootVarRouting", ue["Quirks"]["RequestBootVarRouting"] is True)
    check("UEFI ReleaseUsbOwnership", ue["Quirks"]["ReleaseUsbOwnership"] is True)
    check("UEFI ResizeGpuBars", ue["Quirks"]["ResizeGpuBars"] == -1)

# ---------------- Task 6: verify ----------------
r = run("verify")
out = r.stdout + r.stderr
check("verify 成功", r.returncode == 0)
check("ocvalidate 无错误", "No issues found" in out or "0 errors" in out.lower())
check("ocvalidate 版本提示 1.0.8", "1.0.8" in out)
check("BOOTx64.efi 存在", (ROOT / "EFI" / "BOOT" / "BOOTx64.efi").exists())
check("OpenCore.efi 存在", (ROOT / "EFI" / "OC" / "OpenCore.efi").exists())

sys.exit(1 if fails else 0)