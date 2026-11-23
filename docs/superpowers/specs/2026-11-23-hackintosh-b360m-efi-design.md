# 黑苹果 EFI 设计方案：i7-8700 / B360M AORUS ELITE / RX 5500 / BCM943602CS / Ventura 13

日期：2026-11-23
状态：已批准（2026-11-23），进入 writing-plans

## 1. 意图与为什么

给一台独立的台式机做一份**开箱即用**的 OpenCore EFI：i7-8700 + 技嘉 B360M AORUS ELITE（小雕）+ AMD RX 5500 + 博通 BCM943602CS（PCIe 转接卡），安装并日常使用 macOS Ventura 13。

为什么是 Ventura：Ventura 13 是最后一个**原生支持博通 BCM94360 系列**的 macOS。Sonoma 及以后需要 OCLP 打根补丁才能用这块网卡，会引入更新风险和维护负担，不适合“稳定日常使用”。

为什么自己做而不是抄一份同主板 EFI：现成 EFI 来源不可信、版本陈旧，可能包含**借用的 SMBIOS 三码**（有被封 iServices 的风险）和来路不明的 ACPI/驱动。自己组装可以做到每个二进制都来自官方 release、有 SHA256、有中文文档解释每个设置的原因。

## 2. 目标 / 非目标 / 反目标

### 目标（装好之后应成立）

1. 从 U 盘启动 OpenCore，进入 Ventura 安装器并完成安装。
2. RX 5500 正常驱动（无黑屏、有硬件加速）。
3. UHD 630 作为**无头计算卡**工作（不接显示器，供 VideoToolbox/核显加速）。
4. Realtek ALC892 音频可用（先 `alcid=1`，附排查方法）。
5. Intel I219-V 有线网卡可用，且被识别为 `en0`（iServices 前提）。
6. BCM943602CS 的 Wi-Fi 与蓝牙可用（Ventura 原生，无需额外 kext）。转接卡的蓝牙已确认通过 USB 线接到主板 USB 2.0 针脚。
7. USB 端口在装好后通过映射全部可用（安装阶段用后置 USB 2.0 口即可）。
8. 睡眠/唤醒正常；NVRAM 持久化（SSDT-PMC）。
9. App Store / iMessage / FaceTime 可用（需要正确的 SMBIOS + en0 + ROM）。
10. 交付中文文档：BIOS 设置、安装步骤、USB 映射、iServices 修复、后续升级方法。

### 非目标

- 不负责“替用户装系统”：安装由用户按 README 操作。
- 不做 Windows 双启动引导配置，不动现有硬盘分区表。
- 不支持 Sonoma/Sequoia/OCLP，不做 OpenCore Legacy Patcher。
- 不做 CPU/内存超频、雷电、独显与核显切换输出。
- 不做 OpenCanopy 图形主题（默认文本选择器；后续可自行加）。

### 反目标（即使“能开机”也算失败）

- 打包来源不明的二进制或从网上抄来的 EFI 片段。
- 使用他人已注册的 SMBIOS 序列号。
- 无理由关闭 SIP / 关闭安全启动相关项。
- 塞入不需要的 kext（每个多余 kext 都是故障面）。
- 声称“已验证可用”但没有实机证据。

## 3. 约束

- **开发机不是目标机**：本机是 Ryzen 7 9700X + ASUS B850M + RTX 4070（Windows），无法在本机启动验证，也无法读取目标机硬件。目标机细节全部来自用户描述。
- 只能做**静态验证**（文件、配置、校验和、ocvalidate），动态验证必须由用户在目标机完成。
- **安装目标是单独一块 NVMe 盘**：现有 Windows 盘和数据完全不动，EFI 放在 macOS 盘自己的 ESP。安装时最好物理断开或 BIOS 禁用 Windows 盘，避免抹错盘、也避免两个 ESP 混淆。
- Ventura 的 15 端口限制：`XhciPortLimit` 在 macOS 11.3+ 已失效，USB 映射只能在装好系统后做；安装阶段必须用后置 USB 2.0 口。
- SMBIOS 序列号必须唯一且未注册；由 macserial 现场生成，用户需自行确认。
- 所有二进制固定版本、记录 SHA256；升级流程写进 README。
- 音频 codec、网卡具体型号以目标机实际为准（B360M AORUS ELITE 常见为 ALC892 + I219-V），文档给出确认与排查路径。

## 4. 方案对比（对话中已选定 A）

| 方案 | 内容 | 取舍 | 结论 |
|---|---|---|---|
| **A（选中）** | 完整 `EFI/` 目录：OpenCore 1.0.8 RELEASE + 固定版本 kext + OpenCore 自带 ACPI 样例 + 针对本机调好的 config.plist + 生成的 iMac19,1 SMBIOS + 中文 README/SOURCES | 开箱即用、可追溯、可解释；代价是序列号需生成、ROM 先占位、USB 映射装后做 | **采用** |
| B | 半成品：只给 config.plist + 下载脚本 + 清单，用户自己拼装 | 灵活，但步骤多、kext 顺序/路径极易出错 | 否决 |
| C | 改一份同主板现成 EFI | 最省事，但来源不可信、版本旧，可能含借用三码和未知 ACPI/驱动，安全与稳定性风险 | 否决 |

选 A 的理由：这套硬件是标准 Coffee Lake 桌面组合（Dortania 有完整官方指引），组装成本低；A 用“升级文档”补回了 B 的可维护性优势。

## 5. 设计

### 5.1 交付物与目录结构

工作区根目录 `C:\Users\Administrator\Desktop\EFI\`：

```
EFI\                          # 直接复制到 U 盘/硬盘 EFI 分区的内容
├── BOOT\
│   └── BOOTx64.efi           # OpenCore 引导入口
└── OC\
    ├── ACPI\                 # SSDT-PLUG / SSDT-EC-USBX / SSDT-AWAC-DISABLE / SSDT-PMC
    │   └── optional\         # SSDT-RTC0.aml（默认不加载，出问题时替换 AWAC）
    ├── Drivers\              # OpenRuntime.efi / OpenHfsPlus.efi / ResetNvramEntry.efi
    ├── Kexts\                # Lilu, VirtualSMC, SMCProcessor, SMCSuperIO,
    │                         # WhateverGreen, AppleALC, IntelMausi, NVMeFix
    ├── Resources\            # 空（不用 OpenCanopy），保留占位说明
    ├── Tools\                # 空（不放 OpenShell）
    ├── OpenCore.efi
    └── config.plist
README.md                     # 中文：BIOS 设置、装 U 盘、安装、USB 映射、iServices、升级、排错
SOURCES.md                    # 每个组件的版本、下载 URL、SHA256、许可证
docs\superpowers\specs\       # 本设计文档 + 后续计划/验证记录
```

`EFI/` 之外的文件不放进 EFI 分区。

### 5.2 组件与版本（构建时按此下载并校验）

| 组件 | 版本 | 用途 |
|---|---|---|
| OpenCorePkg | 1.0.8 RELEASE | 引导器（含 OpenRuntime/HfsPlus/ResetNvram、`Utilities/macserial`、`Utilities/ocvalidate`、`Docs/AcpiSamples`） |
| Lilu | 1.7.2 | kext 注入基础 |
| VirtualSMC | 1.3.8 | SMC 模拟（含 SMCProcessor / SMCSuperIO） |
| WhateverGreen | 1.7.1 | 显卡补丁（RX 5500 必需） |
| AppleALC | 1.9.8 | 音频 |
| IntelMausi | 1.0.8 | 有线网卡 |
| NVMeFix | 1.1.3 | NVMe 电源管理/兼容性（目标盘已确认为 NVMe） |
| OpenCore 自带 ACPI 样例 | OpenCore 1.0.8 release 内 `Docs/AcpiSamples/Binaries/` | SSDT-PLUG / EC-USBX / AWAC / PMC / RTC0（官方、与 OC 同版本） |

**不安装**：AirportBrcmFixup、BrcmPatchRAM、BrcmFirmwareData（BCM943602CS 在 Ventura 原生）；USBInjectAll（用 USBToolBox 映射）；CPUFriend（非必需）。

### 5.3 ACPI（SSDT）

- `SSDT-PLUG.aml`（OpenCore 官方样例）：CPU 电源管理（`plugin-type=1`，配合 iMac19,1）。
- `SSDT-EC-USBX.aml`（OpenCore 官方样例）：桌面 EC 仿冒（`ACID0001`，不重命名 EC0）+ USB 供电属性（USBX）。
- `SSDT-AWAC-DISABLE.aml`（OpenCore 官方样例，300 系专用，原理是注入 `STAS=1` 强制走 Legacy RTC）：在 BIOS 无法直接开启 Legacy RTC 时使用。
- 备选 `SSDT-RTC0.aml`（OpenCore 官方样例）：当固件没有 `STAS` 变量、`SSDT-AWAC-DISABLE` 不适用时，用它伪造 PNP0B00 RTC 设备。放在 `EFI/OC/ACPI/optional/`，默认不启用，README 写明判断与替换方法。
- `SSDT-PMC.aml`（OpenCore 官方样例）：B360（非 Z370）无原生 NVRAM，用 PMC 补丁开启。
- 不放 `SSDT-PNLF`（无内屏）、不放 `SSDT-USBX` 单独文件（已含在 EC-USBX）、不放 `SSDT-CPUR`（AMD 用）、不放 `SSDT-RHUB`（非必需）。

用 OpenCore 自带的 ACPI 样例而不是 Dortania 仓库的预编译文件，理由是版本与引导器同源、来源单一、SHA256 可随 OC 发布包一起校验。

### 5.4 Kext 与加载顺序

顺序：`Lilu` → `VirtualSMC` → `SMCProcessor` → `SMCSuperIO` → `WhateverGreen` → `AppleALC` → `IntelMausi` → `NVMeFix`。Lilu 必须最先加载；SMCProcessor/SMCSuperIO 依赖 VirtualSMC；NVMeFix 依赖 Lilu，位置放在最后即可。

不加载：博通相关 kext（原生）、USBMap（装后生成再加）。

### 5.5 config.plist 关键内容（以下为我的判断，builder 可微调并在文档记录）

- **ACPI → Add**：4 项，`Enabled=true`，Path 指向上表文件。
- **Booter → Quirks**：`DevirtualiseMmio=true`、`EnableWriteUnprotector=false`、`ProtectUefiServices=false`（B360 不需要）、`RebuildAppleMemoryMap=true`、`SetupVirtualMap=true`（技嘉需要）、`SyncRuntimePermissions=true`、`ResizeAppleGpuBars=-1`。
- **DeviceProperties**：`PciRoot(0x0)/Pci(0x2,0x0)` → `AAPL,ig-platform-id=0300913E`（UHD 630 无头计算，不接显示器）。音频先不写 layout-id，用 boot-arg 控制，方便试错。
- **Kernel → Add**：8 个 kext，`Enabled=true`，正确 BundlePath/ExecutablePath/PlistPath。
- **Kernel → Quirks**：`AppleXcpmCfgLock=true`、`DisableIoMapper=true`、`PanicNoKextDump=true`、`PowerTimeoutKernelPanic=true`、`DisableLinkeditJettison=true`、`SetApfsTrimTimeout=-1`、`XhciPortLimit=false`（Ventura 上无效且有害）。
- **Misc → Boot**：`HideAuxiliary=true`、`PickerMode=Builtin`、`TakeoffDelay=0`、`LauncherOption=Disabled`（U 盘阶段不需要写 BIOS 启动项）。
- **Misc → Debug**：`AppleDebug=true`、`ApplePanic=true`、`DisableWatchDog=true`、`Target=67`、`DisplayLevel=2147483650`。
- **Misc → Security**：`SecureBootModel=Default`、`Vault=Optional`、`DmgLoading=Signed`、`ScanPolicy=0`、`BlacklistAppleUpdate=true`、`AllowSetDefault=true`、`ExposeSensitiveData=6`。
- **NVRAM**：`boot-args="-v keepsyms=1 debug=0x100 agdpmod=pikera alcid=1"`；`csr-active-config=00000000`；`run-efi-updater=No`；`prev-lang:kbd` 为 String `en-US:0`；`WriteFlash=true`。
- **PlatformInfo**：`Automatic=true`、`UpdateSMBIOSMode=Create`、`CustomSMBIOSGuid=false`、`SystemProductName=iMac19,1`、`ProcessorType=0`，Generic 里填生成的 Serial/MLB/SystemUUID/ROM。
- **UEFI → Drivers**：`OpenRuntime.efi`（必需）、`OpenHfsPlus.efi`、`ResetNvramEntry.efi`；`ConnectDrivers=true`。
- **UEFI → APFS**：`EnableJumpstart=true`、`GlobalConnect=false`、`HideVerbose=true`、`MinVersion=0`。
- **UEFI → Input**：`KeySupport=true`（外接键盘可用）。
- **UEFI → Output**：`ProvideConsoleGop=true`、`TextResolution=0`。
- **UEFI → Quirks**：`RequestBootVarRouting=true`、`ReleaseUsbOwnership=true`、`ResizeGpuBars=-1`。
- **启动参数说明**：`-v` 与 `debug=0x100`/`keepsyms=1` 保留到装机稳定为止（排错必需）；`agdpmod=pikera` 是 RX 5500 防黑屏必需；`alcid=1` 是音频初值。

### 5.6 SMBIOS（iMac19,1）

- 用 `GenSMBIOS.py`（corpnewt/GenSMBIOS，Windows 可运行）+ `macserial.exe`（从 OpenCorePkg release 的 `Utilities/macserial` 取）生成 iMac19,1 的 Serial / MLB / SystemUUID。
- `ROM` 先用随机 6 字节占位；README 教用户在 Windows 里用 `getmac`/网卡属性查出有线网卡 MAC 后替换（ROM 用真实 MAC 是 iServices 稳定的关键）。
- 用户须知：序列号未注册（Apple 保修查询应显示“无法验证”）；不要把含三码的 config.plist 发到公开群/论坛；iServices 登录失败时按 README 排查（换序列号重生成、清 NVRAM、确认 en0、检查 ROM）。
- 风险：极低概率生成的序列号被 Apple 判定为他人已注册；README 给重生成步骤。

### 5.7 README 内容（中文）

1. 硬件清单与本方案的假设（codec/网卡以实际为准，附确认方法）。
2. BIOS 设置（Gigabyte B360M AORUS ELITE）：关 CSM、关 Secure Boot、关 Fast Boot、关 VT-d、关 Serial Port、开 Above 4G、开 XHCI Hand-off、SATA 设 AHCI、Internal Graphics 设 Enabled、DVMT 设 64MB、Windows 8/10 Features 设 Other OS。
3. 制作安装 U 盘（16GB+）：
   - 有 Mac：`createinstallmedia` + 复制 `EFI/`。
   - 只有 Windows：gibMacOS 下载 Ventura 安装器 + 用 BalenaEtcher/Rufus 写入 U 盘（或按 Dortania 的 Windows 制作流程），再把 `EFI/` 复制到 U 盘 EFI 分区（用 DiskGenius/挂载盘符）。
4. 安装：BIOS 选 UEFI 启动 U 盘 → OpenCore 菜单选 “Install macOS Ventura” → 磁盘工具抹盘（APFS / GUID）→ 安装 → 重启继续。
   - **装之前先物理断开或 BIOS 禁用 Windows 盘**（拔 SATA/电源线，或 BIOS 里禁用该 SATA/M.2 口），只留目标 NVMe 盘和安装 U 盘；这样不会抹错盘，也不会出现两个 EFI 分区互相混淆。
   - 抹盘前在磁盘工具里核对**盘的容量/型号**，确认是那块空 NVMe 盘，再执行“抹掉”。
   - macOS 装好后，EFI 放在 **macOS 盘自己** 的 EFI 分区（不是 Windows 盘的 ESP），装完再把 Windows 盘接回来，用 BIOS 启动菜单切换系统。
5. 装后必做：USB 映射（USBToolBox Windows 版生成 `UTBMap.kext` + `USBToolBox.kext`，加入 config 的 Kernel Add）。**映射时必须插着 BCM943602CS 的蓝牙 USB 线**，并把该内部口标记为 `Internal`；否则映射后蓝牙会消失。另：音频 layout 调整；iServices 修复；换真实 ROM。
6. 硬盘注意：本方案按 NVMe 盘准备。三星 PM981/PM991/PM9A1 一类盘在 macOS 下有兼容问题（卡顿/掉盘），README 写明；若目标盘是这类型号，先换盘或改用 SATA SSD。NVMeFix 已包含，用于修电源管理。
7. 升级方法：OC 用 ProperTree 比较新旧 config 的 sample，kext 逐个替换并保持顺序；OpenCore 升版本前备份 EFI。
8. 排错：卡 `[EB|#LOG:EXITBS_PAD]`、黑屏、无声、无网、睡眠唤醒、USB 失效，各给 3–5 条检查项。

### 5.8 验证（构建时执行，动态验证归用户）

静态：
1. 每个下载文件校验 SHA256 并记入 SOURCES.md。
2. `config.plist` 能被 plist 解析器解析；ACPI/Kext/Driver 中每个路径在 `EFI/` 下真实存在。
3. 用 OpenCore release 自带的 `ocvalidate.exe` 校验，要求 0 错误；把输出记入 `docs/verification.md`。
4. 交叉检查：kext 顺序、Lilu 第一、BundlePath 与 ExecutablePath 一致、`OpenRuntime.efi` 存在、`BOOTx64.efi` 来源正确。
5. 检查 config 中不存在未提供的文件引用（Resources 音频/字体、Tools）。

动态（用户实机）：README 附“首次启动检查清单”（能进安装器 / 装完能进桌面 / 显卡加速 / 音频 / 有线 / Wi-Fi / 蓝牙 / USB / 睡眠 / iServices）。

## 6. 留给 builder 的

- 实际下载、解压、组装 `EFI/`；生成 SMBIOS；写 config.plist；跑 ocvalidate 与静态检查。
- README 与 SOURCES.md 的具体措辞、排错条目、AppleALC layout 候选列表。
- 是否加入 OpenCanopy/OpenShell 等可选组件：按“最小化”原则默认不加。
- 用户后续提供真实 MAC 后替换 ROM 的具体操作说明。

## 7. 风险与缓解

| 风险 | 缓解 |
|---|---|
| SSDT-AWAC-DISABLE 与固件不兼容（无 `STAS`） | 备 `SSDT-RTC0.aml`（OpenCore 官方样例，默认放 optional/ 不启用），README 写明判断与替换 |
| 音频 codec 不是 ALC892 | README 给 codec 确认方法与 AppleALC layout 试错清单 |
| Ventura 15 端口限制导致部分 USB 不可用 | 安装用后置 USB 2.0；装后用 USBToolBox 映射 |
| RX 5500 黑屏 | `agdpmod=pikera` + WhateverGreen；README 给“去掉该参数对比”的排错法 |
| iServices 登录失败 | en0 + 真实 ROM + 未注册序列号 + 清 NVRAM，README 给流程 |
| 博通卡在 Ventura 上被识别但速率低 | 确认 3 根天线接好；`airport -I` 查看速率；必要时检查转接卡供电 |
| 用户误用 Sonoma 安装器 | README 明确只支持 Ventura 13 |
| NVMe 盘型号不兼容（PM981/PM991/PM9A1 等） | README 列兼容性说明与自查方法；NVMeFix 已含；必要时换 SATA SSD |
| 蓝牙内部 USB 口没进映射 | README 明确“映射时插蓝牙线、标记 Internal”，并给验证方法（`系统信息→蓝牙`、`ioreg`） |
| 装系统时误抹 Windows 盘 | 约束 + 安装步骤要求物理断开/BIOS 禁用 Windows 盘，抹盘前核对容量型号 |

## 8. 已由用户决定 vs 我的判断

- 用户已决定：目标硬件、Ventura 13、方案 A（完整 EFI）；**装在单独一块空的 NVMe 盘上，Windows 盘完全不动**；**BCM943602CS 的蓝牙通过 USB 线接到主板 USB 2.0 针脚**。
- 我的判断（可在评审时改）：iMac19,1、各 kext 取舍（含加 NVMeFix）、config 各 quirk 取值、ACPI 样例取自 OpenCore release、`SSDT-RTC0` 仅作 optional 备用、不装 OpenCanopy、SMBIOS 生成方式、USB 映射后置。
- 已解决的设计矛盾：原文档“不动 Windows 分区表”与“抹盘安装”冲突，现明确为“独立 NVMe 盘 + 安装时断开 Windows 盘”，两者不再冲突。