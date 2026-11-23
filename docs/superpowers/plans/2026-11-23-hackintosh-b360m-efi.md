# 黑苹果 EFI 构建实施计划（i7-8700 / B360M AORUS ELITE / RX 5500 / BCM943602CS / Ventura 13）

> **For agentic workers:** REQUIRED SUB-SKILL: Use subagent-driven-development (recommended) or executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 产出一个可直接复制到 U 盘/硬盘 EFI 分区的 OpenCore 1.0.8 EFI 目录，以及中文 README / SOURCES / 验证记录。

**Architecture:** 用 `scripts/build.py` 把“下载固定版本 → 校验 SHA256 → 解压组装 EFI 树 → 生成 SMBIOS → 基于 OpenCore 官方 `Docs/Sample.plist` 生成 config.plist → ocvalidate + 路径核对”做成可重复执行的阶段；每个阶段独立可验证。产物在 `EFI/`，中间件在 `build/`（不入库、不拷进 U 盘）。

**Tech Stack:** OpenCore 1.0.8 RELEASE、UEFI ACPI(SSDT)、Python 3.13（仅构建脚本，`plistlib`/`zipfile`/`hashlib`，无第三方依赖）、PowerShell、git。目标系统 macOS Ventura 13。

**Spec:** `docs/superpowers/specs/2026-11-23-hackintosh-b360m-efi-design.md`（下称“设计文档”，已批准）。所有配置取值以设计文档 §5 为准，本计划只锁定文件、脚本接口、校验方式。

## Global Constraints

- 只支持 macOS Ventura 13；所有二进制来自 acidanthera / OpenCorePkg 官方 release，版本固定：OpenCore 1.0.8、Lilu 1.7.2、VirtualSMC 1.3.8、WhateverGreen 1.7.1、AppleALC 1.9.8、IntelMausi 1.0.8、NVMeFix 1.1.3。
- 禁止：AirportBrcmFixup / BrcmPatchRAM / BrcmFirmwareData / USBInjectAll / CPUFriend / OpenCanopy 主题 / 任何来源不明的二进制。
- 所有面向用户的文档用中文；脚本与代码标识符用英文。
- 目标机是**单独一块 NVMe 盘**，Windows 盘不动；SMBIOS 由 macserial 现场生成，ROM 先随机占位。
- 静态验证必须通过：`ocvalidate.exe` 0 错误；config 中每个 ACPI/Kext/Driver 路径真实存在；plist 可被 `plistlib` 解析。
- 不在本机（Ryzen/RTX 4070）做任何“实机可用”断言；README 里区分“已验证”和“待实机确认”。
- 每完成一个 Task 提交一次 git commit。

## Review Focus

1. **config.plist 引用了不存在的文件**——引导器直接停在 `OC: Failed to load configuration` 或 kext 加载失败；每个 ACPI/Kext/Driver/Resources 路径都必须存在（Task 3/5 写测试，Task 6 全量核对）。
2. **kext 顺序或依赖错误**——Lilu 不在最前时，依赖它的 WhateverGreen/AppleALC/NVMeFix 全部不生效；SMCProcessor/SMCSuperIO 必须在 VirtualSMC 之后（Task 5 的测试断言顺序）。
3. **SMBIOS 三码非法或重复**——iServices 封禁、甚至无法进系统；生成后必须校验 serial 12 位、MLB 17 位、UUID 36 位，且不去网上共享（Task 4 测试 + README 警告）。
4. **安装时误抹 Windows 盘**——用户数据不可恢复；README 必须写“物理断开/BIOS 禁用 Windows 盘 + 抹盘前核对容量”（Task 7 用关键字测试钉住）。
5. **蓝牙内部 USB 口没进映射**——映射后蓝牙从系统里消失，而用户以为 EFI 有问题；README 必须写“映射时插着蓝牙线、标记 Internal”（Task 7 用关键字测试钉住）。

---

### Task 1: 构建基座（git + 目录 + 测试入口）

**Files:**
- Create: `.gitignore`
- Create: `scripts/build.py`（本任务只建骨架：`ASSETS` 常量与空阶段函数、`main()`）
- Create: `scripts/test_build.py`（断言入口，后续任务往里加 `check_*`）
- Create: `EFI/.gitkeep`

**Interfaces:**
- Consumes: 无
- Produces: `scripts/build.py` 的 `ASSETS: list[dict]`（字段 `name, version, url, sha256, members`）；`main()` 支持子命令 `fetch|assemble|smbios|config|verify`；`scripts/test_build.py` 的 `check(name, cond)` 与退出码约定（失败非 0）。

- [ ] **Step 1: 初始化仓库与忽略规则**

`.gitignore` 内容：

```
build/
*.zip
__pycache__/
```

Run: `git init; git add .gitignore; git commit -m "chore: init workspace"`

- [ ] **Step 2: 写失败测试（骨架必需可导入且子命令存在）**

`scripts/test_build.py`：

```python
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
sys.exit(1 if fails else 0)
```

- [ ] **Step 3: 运行测试确认失败**

Run: `python scripts/test_build.py`
Expected: FAIL（`build.py` 不存在），退出码 1。

- [ ] **Step 4: 实现 `scripts/build.py` 骨架**

```python
import argparse, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "build" / "cache"
EFI = ROOT / "EFI"

ASSETS = []  # Task 2 填充

def main(argv=None):
    p = argparse.ArgumentParser(prog="build.py")
    p.add_argument("cmd", choices=["fetch", "assemble", "smbios", "config", "verify", "all"])
    args, _ = p.parse_known_args(argv)
    print(f"stage {args.cmd}: not implemented yet")
    return 0 if args.cmd == "all" else 1

if __name__ == "__main__":
    sys.exit(main())
```

（后续任务在每个 stage 里替换实现；`main` 对未实现阶段返回 1。）

- [ ] **Step 5: 运行测试确认通过**

Run: `python scripts/test_build.py`
Expected: 两行 `OK`，退出码 0。

- [ ] **Step 6: 提交**

```bash
git add scripts .gitignore EFI/.gitkeep
git commit -m "chore: build script skeleton and test runner"
```

---

### Task 2: 下载与 SHA256 校验阶段

**Files:**
- Modify: `scripts/build.py`（`ASSETS` 填充、`stage_fetch()`）
- Modify: `scripts/test_build.py`

**Interfaces:**
- Consumes: Task 1 的 `ASSETS`/`main()`。
- Produces: `stage_fetch(cache: Path) -> dict[str, Path]`，键为资产名；下载到 `build/cache/<name>.zip` 并在 `fetch` 时断言 SHA256 与 `ASSETS[i]["sha256"]` 一致。

- [ ] **Step 1: 取 7 个 RELEASE zip 的官方 digest**

对每个仓库执行（`<ver>` 为固定版本）：

```powershell
Invoke-RestMethod "https://api.github.com/repos/acidanthera/<repo>/releases/tags/<ver>" |
  Select-Object -ExpandProperty assets |
  Where-Object name -like "*-RELEASE.zip" |
  Select-Object name, digest, browser_download_url
```

把 `digest` 去掉前缀 `sha256:` 后填进 `ASSETS`。OpenCorePkg 的 release 资产名是 `OpenCore-1.0.8-RELEASE.zip`，同样处理。

- [ ] **Step 2: 写失败测试（八项资产都被下载且哈希匹配）**

在 `scripts/test_build.py` 末尾追加：

```python
import hashlib, importlib.util
spec = importlib.util.spec_from_file_location("b", ROOT/"scripts"/"build.py")
b = importlib.util.module_from_spec(spec); spec.loader.exec_module(b)
for a in b.ASSETS:
    z = ROOT/"build"/"cache"/(a["name"]+".zip")
    check(f"资产存在 {a['name']}", z.exists())
    if z.exists():
        h = hashlib.sha256(z.read_bytes()).hexdigest()
        check(f"哈希匹配 {a['name']}", h == a["sha256"])
```

Run: `python scripts/test_build.py`
Expected: FAIL（`ASSETS` 为空，`fetch` 未实现）。

- [ ] **Step 3: 实现 `ASSETS` 与 `stage_fetch`**

`ASSETS` 形如：

```python
ASSETS = [
    {"name": "opencore", "version": "1.0.8",
     "url": "https://github.com/acidanthera/OpenCorePkg/releases/download/1.0.8/OpenCore-1.0.8-RELEASE.zip",
     "sha256": "..."},
    # lilu / virtualsmc / whatevergreen / applealc / intelmausi / nvmefix 同构
]
```

`stage_fetch` 用 `urllib.request.urlretrieve` 下载到 `CACHE`，已存在则跳过下载但仍校验；哈希不符时抛出 `SystemExit("sha256 mismatch ...")`。

- [ ] **Step 4: 运行 fetch 并确认**

Run: `python scripts/build.py fetch`
Expected: 7 个文件落到 `build/cache/`，打印每个文件的大小与 `sha256 ok`。

- [ ] **Step 5: 运行测试通过**

Run: `python scripts/test_build.py`
Expected: 所有 `OK`，退出码 0。

- [ ] **Step 6: 提交**

```bash
git add scripts
git commit -m "feat: pinned asset download with sha256 verification"
```

---

### Task 3: 组装 EFI 树

**Files:**
- Modify: `scripts/build.py`（`stage_assemble()`）
- Modify: `scripts/test_build.py`

**Interfaces:**
- Consumes: Task 2 的 `ASSETS` 与 cache 内 zip。
- Produces: `stage_assemble(cache: Path, efi: Path) -> None`，生成：

```
EFI/BOOT/BOOTx64.efi
EFI/OC/OpenCore.efi
EFI/OC/Drivers/{OpenRuntime.efi, OpenHfsPlus.efi, ResetNvramEntry.efi}
EFI/OC/Kexts/{Lilu.kext, VirtualSMC.kext, SMCProcessor.kext, SMCSuperIO.kext,
               WhateverGreen.kext, AppleALC.kext, IntelMausi.kext, NVMeFix.kext}
EFI/OC/ACPI/{SSDT-PLUG.aml, SSDT-EC-USBX.aml, SSDT-AWAC-DISABLE.aml, SSDT-PMC.aml}
EFI/OC/ACPI/optional/SSDT-RTC0.aml
```

- [ ] **Step 1: 写失败测试（精确文件清单）**

```python
r = run("assemble")
check("assemble 成功", r.returncode == 0)
want = [
 "BOOT/BOOTx64.efi", "OC/OpenCore.efi",
 "OC/Drivers/OpenRuntime.efi", "OC/Drivers/OpenHfsPlus.efi", "OC/Drivers/ResetNvramEntry.efi",
 *[f"OC/Kexts/{k}.kext/Contents/Info.plist" for k in
   ["Lilu","VirtualSMC","SMCProcessor","SMCSuperIO","WhateverGreen","AppleALC","IntelMausi","NVMeFix"]],
 "OC/ACPI/SSDT-PLUG.aml", "OC/ACPI/SSDT-EC-USBX.aml",
 "OC/ACPI/SSDT-AWAC-DISABLE.aml", "OC/ACPI/SSDT-PMC.aml",
 "OC/ACPI/optional/SSDT-RTC0.aml",
]
for rel in want:
    check(f"存在 {rel}", (ROOT/"EFI"/rel).exists())
check("Resources 目录存在", (ROOT/"EFI"/"OC"/"Resources").is_dir())
check("Tools 目录存在", (ROOT/"EFI"/"OC"/"Tools").is_dir())
```

Run: `python scripts/test_build.py`
Expected: FAIL（`EFI/` 下无文件）。

- [ ] **Step 2: 实现 `stage_assemble`**

要点：从 OC zip 的 `X64/EFI/...` 与 `Docs/AcpiSamples/Binaries/...` 取文件；kext 用 `zipfile` 在压缩包内按 `*.kext/` 目录匹配后整体解出（不同 release 里 kext 可能在根目录或 `Kexts/` 子目录，实现要递归找 `<Name>.kext/Contents/Info.plist` 的父目录）；解出后只保留 `.kext` 目录，丢弃 `dSYM` 与 `README`。

- [ ] **Step 3: 校验 kext 包完整性**

追加测试：每个 `.kext` 必须有 `Contents/Info.plist` 且 `CFBundleIdentifier` 非空；记录到 `SOURCES.md` 时用实际值。对 `IntelMausi.kext` 同时断言 `Contents/MacOS/<exec>` 存在（AppleALC/WhateverGreen/NVMeFix/VirtualSMC/SMCProcessor/SMCSuperIO 同理，可统一按 `Info.plist` 的 `CFBundleExecutable` 取值检查）。

Run: `python scripts/build.py assemble; python scripts/test_build.py`
Expected: 全部 `OK`。

- [ ] **Step 4: 提交**

```bash
git add scripts
git commit -m "feat: assemble EFI tree from pinned releases"
```
（`EFI/` 产物在 Task 6 通过校验后再入库。）

---

### Task 4: 生成 SMBIOS 三码

**Files:**
- Modify: `scripts/build.py`（`stage_smbios()`）
- Create: `build/smbios.json`（不入库）
- Modify: `scripts/test_build.py`

**Interfaces:**
- Consumes: cache 内 OC zip 的 `Utilities/macserial/macserial.exe`。
- Produces: `stage_smbios(cache: Path, out: Path) -> dict`，返回 `{"serial": str, "mlb": str, "uuid": str, "rom": str}`；`rom` 为随机 6 字节的 12 位大写十六进制。

- [ ] **Step 1: 写失败测试（格式与唯一性）**

```python
import json
r = run("smbios")
check("smbios 成功", r.returncode == 0)
d = json.loads((ROOT/"build"/"smbios.json").read_text())
check("serial 12 位", len(d["serial"]) == 12)
check("mlb 17 位", len(d["mlb"]) == 17)
check("uuid 36 位", len(d["uuid"]) == 36 and d["uuid"].count("-") == 4)
check("rom 12 位 hex", len(d["rom"]) == 12 and all(c in "0123456789ABCDEF" for c in d["rom"]))
```

Run: `python scripts/test_build.py`
Expected: FAIL（无 `build/smbios.json`）。

- [ ] **Step 2: 实现 `stage_smbios`**

解压 `macserial.exe` 到 `build/tools/`，执行 `macserial -a iMac19,1`，按 `|` 分列解析 `Type | Serial | Board Serial | UUID`；生成 `rom = os.urandom(6).hex().upper()`；写 `build/smbios.json`（`ensure_ascii=False`）。

- [ ] **Step 3: 运行并人工核对**

Run: `python scripts/build.py smbios`
Expected: 打印 `iMac19,1` 三码；打开 https://checkcoverage.apple.com 确认序列号“无法验证”（未注册）。把结果抄进 `build/smbios.json` 备份。

- [ ] **Step 4: 运行测试通过**

Run: `python scripts/test_build.py`
Expected: 全部 `OK`。

- [ ] **Step 5: 提交**

```bash
git add scripts
git commit -m "feat: generate iMac19,1 smbios with macserial"
```

---

### Task 5: 生成 config.plist

**Files:**
- Modify: `scripts/build.py`（`stage_config()`）
- Modify: `scripts/test_build.py`
- Create: `EFI/OC/config.plist`（产物）

**Interfaces:**
- Consumes: Task 3 的 `EFI/` 树、Task 4 的 `build/smbios.json`、cache 内 OC zip 的 `Docs/Sample.plist`。
- Produces: `stage_config(efi: Path, smbios: dict, sample: Path) -> None`，用 `plistlib` 读 Sample、按设计文档 §5.5 覆盖后写 XML（`fmt=FMT_XML`），并断言生成文件可被再次 `plistlib.loads` 解析。

- [ ] **Step 1: 写失败测试（关键取值 + kext 顺序 + 路径存在）**

```python
import plistlib
p = ROOT/"EFI"/"OC"/"config.plist"
check("config.plist 存在", p.exists())
if p.exists():
    c = plistlib.loads(p.read_bytes())
    check("boot-args", c["NVRAM"]["Add"]["7C436110-AB2A-4BBB-A880-FE41995C9F82"]["boot-args"]
          == "-v keepsyms=1 debug=0x100 agdpmod=pikera alcid=1")
    check("product", c["PlatformInfo"]["Generic"]["SystemProductName"] == "iMac19,1")
    check("ig-platform", c["DeviceProperties"]["Add"]["PciRoot(0x0)/Pci(0x2,0x0)"]["AAPL,ig-platform-id"]
          == bytes.fromhex("0300913E"))
    names = [k["BundlePath"].split("/")[0].replace(".kext","") for k in c["Kernel"]["Add"] if k["Enabled"]]
    check("kext 数 8", len(names) == 8)
    check("Lilu 第一", names[0] == "Lilu")
    check("VirtualSMC 早于 SMC*", names.index("VirtualSMC") < names.index("SMCProcessor"))
    check("XhciPortLimit 关", c["Kernel"]["Quirks"]["XhciPortLimit"] is False)
    check("agdpmod 黑屏补丁参数在", "agdpmod=pikera" in c["NVRAM"]["Add"]["7C436110-AB2A-4BBB-A880-FE41995C9F82"]["boot-args"])
    for a in c["ACPI"]["Add"]:
        check(f"ACPI 文件存在 {a['Path']}", (ROOT/"EFI"/"OC"/"ACPI"/a["Path"]).exists())
    for k in c["Kernel"]["Add"]:
        check(f"kext 目录存在 {k['BundlePath']}", (ROOT/"EFI"/"OC"/k["BundlePath"]).exists())
    for d in c["UEFI"]["Drivers"]:
        check(f"driver 存在 {d['Path']}", (ROOT/"EFI"/"OC"/"Drivers"/d["Path"]).exists())
```

Run: `python scripts/test_build.py`
Expected: FAIL（`config.plist` 不存在）。

- [ ] **Step 2: 实现 `stage_config` 覆盖项**

按设计文档 §5.5 逐项覆盖；`Kernel.Add` 的每个条目填 `BundlePath`（如 `Lilu.kext`）、`ExecutablePath`（`Contents/MacOS/Lilu`）、`PlistPath`（`Contents/Info.plist`）、`Enabled`，以及 OC 版本要求的 `Arch`/`MinKernel`/`MaxKernel`/`Comment` 等字段（从 Sample 对应条目抄结构）。`UEFI.Drivers` 条目为 `{"Path": "...", "Enabled": true}`（再带 `LoadEarly`/`Arguments`/`Comment` 按 Sample）。`PlatformInfo.Generic` 填 `MLB`/`SystemSerialNumber`/`SystemUUID`/`ROM`（ROM 为 bytes，`smbios["rom"]` hex 解码）。

- [ ] **Step 3: 运行并跑测试**

Run: `python scripts/build.py config; python scripts/test_build.py`
Expected: 全部 `OK`。

- [ ] **Step 4: 提交**

```bash
git add scripts EFI/OC/config.plist
git commit -m "feat: generate hardware-tuned config.plist"
```

---

### Task 6: ocvalidate 清零 + 集成 verify 阶段

**Files:**
- Modify: `scripts/build.py`（`stage_verify()`、`all` 串联）
- Modify: `scripts/test_build.py`
- Create: `docs/verification.md`

**Interfaces:**
- Consumes: `EFI/OC/config.plist`、cache 内 `Utilities/ocvalidate/ocvalidate.exe`。
- Produces: `stage_verify(efi: Path, cache: Path) -> str`，返回 ocvalidate 控制台输出；`python scripts/build.py all` 依次执行 fetch→assemble→smbios→config→verify。

- [ ] **Step 1: 写失败测试（ocvalidate 必须 0 错误）**

```python
r = run("verify")
out = r.stdout + r.stderr
check("verify 成功", r.returncode == 0)
check("ocvalidate 无错误", "No issues found" in out or "0 errors" in out.lower())
```

- [ ] **Step 2: 实现 `stage_verify`**

解压 `ocvalidate.exe`，在 `EFI/OC` 下执行 `ocvalidate.exe config.plist`；任何非 0 退出或输出含 `error`（不区分大小写）都 `SystemExit(1)`。同时做交叉检查：每个 `ACPI.Add[].Path`、`Kernel.Add[].BundlePath`、`Kernel.Add[].ExecutablePath`（拼接后）、`UEFI.Drivers[].Path`、`Misc.Tools` 引用路径必须存在；`BOOT/BOOTx64.efi` 与 `OC/OpenCore.efi` 存在。

- [ ] **Step 3: 逐条修正直到 0 错误**

按 ocvalidate 输出修正 `stage_config` 的覆盖（常见：`Misc.Security.SecureBootModel` 取值大小写、`UEFI.APFS.MinVersion`、`Kernel.Add` 缺字段）。**只改脚本再重新生成**，不手改 config.plist。

- [ ] **Step 4: 运行测试通过**

Run: `python scripts/build.py all; python scripts/test_build.py`
Expected: ocvalidate `No issues found`，测试全 `OK`。

- [ ] **Step 5: 记录验证结果**

新建 `docs/verification.md`，写入日期、OC 版本、ocvalidate 原始输出、EFI 文件清单（`Get-ChildItem -Recurse` 结果）、7 个资产的 SHA256。用 `python scripts/test_build.py` 的通过记录作为“静态验证通过”的证据。

- [ ] **Step 6: 提交**

```bash
git add scripts docs/verification.md EFI
git commit -m "feat: ocvalidate-clean config and static verification record"
```

---

### Task 7: README.md（中文）

**Files:**
- Create: `README.md`

**Interfaces:**
- Consumes: 设计文档 §2/§5.7；Task 6 的验证结论。
- Produces: 用户唯一需要照着做的文档。

- [ ] **Step 1: 写失败测试（关键字与章节）**

```python
t = (ROOT/"README.md").read_text(encoding="utf-8")
for kw in ["Ventura", "断开", "容量", "Internal", "agdpmod=pikera", "alcid=1",
           "iMac19,1", "USBToolBox", "getmac", "BIOS", "ocvalidate"]:
    check(f"README 含 {kw}", kw in t)
```

Run: `python scripts/test_build.py`
Expected: FAIL（README 不存在）。

- [ ] **Step 2: 按设计文档 §5.7 的 8 个小节写 README**

必须包含：硬件假设与确认方法；BIOS 设置清单；U 盘制作（有 Mac / 只有 Windows 两条路径）；安装步骤（**先断开 Windows 盘、抹盘前核对容量/型号、EFI 放 macOS 盘 ESP**）；装后必做（USB 映射时插蓝牙线并标 `Internal`、音频 layout 试错、iServices 修复、换真实 MAC 作 ROM）；NVMe 兼容性提醒（PM981/PM991/PM9A1）；升级方法；排错表。文末写“已验证（静态）/ 待实机确认”清单。

- [ ] **Step 3: 运行测试通过**

Run: `python scripts/test_build.py`
Expected: 全部 `OK`。

- [ ] **Step 4: 提交**

```bash
git add README.md
git commit -m "docs: chinese README with bios, install, mapping, troubleshooting"
```

---

### Task 8: SOURCES.md 与最终一致性核对

**Files:**
- Create: `SOURCES.md`
- Modify: `scripts/test_build.py`（可选：断言 SOURCES 含每个组件名与 sha256）

**Interfaces:**
- Consumes: `ASSETS`、`EFI/OC/Kexts/*/Contents/Info.plist`、`build/smbios.json`（不写三码）。
- Produces: 可追溯清单（组件、版本、URL、SHA256、许可证、kext CFBundleIdentifier）。

- [ ] **Step 1: 写失败测试**

```python
s = (ROOT/"SOURCES.md").read_text(encoding="utf-8")
for name in ["OpenCorePkg","Lilu","VirtualSMC","WhateverGreen","AppleALC","IntelMausi","NVMeFix"]:
    check(f"SOURCES 含 {name}", name in s)
```

- [ ] **Step 2: 写 SOURCES.md**

表格：组件 | 版本 | 下载 URL | SHA256 | 许可证 | 备注。ACPI 行注明“来自 OpenCore 1.0.8 release `Docs/AcpiSamples/Binaries/`”。**不要写入 SMBIOS 三码**。

- [ ] **Step 3: 最终核对**

```powershell
Remove-Item -Recurse -Force EFI
python scripts/build.py all
python scripts/test_build.py
git status --short
```

Expected: 全流程成功、测试全 `OK`、`git status` 只显示应提交的文件。

- [ ] **Step 4: 提交**

```bash
git add SOURCES.md scripts
git commit -m "docs: sources and provenance table"
```

---

### Task 9: 交付打包与最终报告

**Files:**
- Create: `build/EFI-2026-11-23.zip`（不入库）
- Modify: `docs/verification.md`（补充最终清单）

- [ ] **Step 1: 打包并核对 zip 内容**

```powershell
Compress-Archive -Path EFI -DestinationPath build/EFI-2026-11-23.zip
Add-Type -AssemblyName System.IO.Compression.FileSystem
[IO.Compression.ZipFile]::OpenRead((Resolve-Path build/EFI-2026-11-23.zip)).Entries.Count
```

Expected: 条目数等于 Task 6 记录的 EFI 文件数 + 目录项一致（人工核对 `BOOTx64.efi`、`OpenCore.efi`、8 个 kext、4+1 个 aml、3 个 driver 全在）。

- [ ] **Step 2: 给用户的交付说明**

在最终回复里列出：`EFI/` 已通过哪些静态检查；三码位置与“别外传”警告；README 的安装顺序；实机验证清单（能否进安装器 → 装完进桌面 → 显卡/音频/网卡/蓝牙/USB/睡眠/iServices）；出问题时最可能先查的三处（boot-args、kext 路径、USB 映射）。

- [ ] **Step 3: 提交收尾**

```bash
git add docs/verification.md
git commit -m "docs: final delivery checklist"
```