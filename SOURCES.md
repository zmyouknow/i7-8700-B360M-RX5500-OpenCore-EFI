# SOURCES.md — EFI 组件来源与校验清单

目标机：i7-8700 / 技嘉 B360M AORUS ELITE / AMD RX 5500 / BCM943602CS，macOS Ventura 13。

原则：`EFI/` 内的每个二进制都来自 **acidanthera 官方 GitHub release**，版本固定、可下载、可校验；
不使用网盘、论坛或他人整包 EFI 里的文件。下表 SHA256 均为发布资产 `*-RELEASE.zip` 的哈希。

- 校验时间：2026-11-23
- 数据来源：GitHub REST API `GET /repos/acidanthera/<repo>/releases/tags/<version>` 中 asset 的 `digest` 字段
  （形如 `sha256:<hex>`，本表只记录 `<hex>`）；许可证取自 `GET /repos/acidanthera/<repo>/license`，
  NVMeFix 因许可证文件名为 `LICENSE.txt` 未被 GitHub 自动识别，按文件正文归类（见备注）。
- 本清单**不含**任何 SMBIOS 三码或 MAC 地址。

## 组件清单

| 组件 | 版本 | 下载 URL | SHA256 | 许可证 | 备注 |
|---|---|---|---|---|---|
| OpenCorePkg | 1.0.8 RELEASE | https://github.com/acidanthera/OpenCorePkg/releases/download/1.0.8/OpenCore-1.0.8-RELEASE.zip | 2011e8b7216ecb2645d97ea710df965947edd406846e92050b9bc4190be6d27b | BSD-3-Clause | 引导器发布包（10,544,084 字节）：`BOOTx64.efi`、`OpenCore.efi`、`Drivers/`（OpenRuntime、OpenHfsPlus、ResetNvramEntry）、`Utilities/macserial`、`Utilities/ocvalidate`、`Docs/AcpiSamples` |
| Lilu | 1.7.2 RELEASE | https://github.com/acidanthera/Lilu/releases/download/1.7.2/Lilu-1.7.2-RELEASE.zip | 53967d7dcfaab01023a33df2e969a89522f13d6654a6a56ac4711b62dabf3ab8 | BSD-3-Clause | kext 注入基础库，加载顺序必须第一（781,360 字节） |
| VirtualSMC | 1.3.8 RELEASE | https://github.com/acidanthera/VirtualSMC/releases/download/1.3.8/VirtualSMC-1.3.8-RELEASE.zip | 2e29a8aaf91b4eb0bcdf5913ed17e70f5cf76531122acd4132eff7813a54de8b | BSD-3-Clause | 含 `VirtualSMC.kext`、`SMCProcessor.kext`、`SMCSuperIO.kext`（1,400,933 字节） |
| WhateverGreen | 1.7.1 RELEASE | https://github.com/acidanthera/WhateverGreen/releases/download/1.7.1/WhateverGreen-1.7.1-RELEASE.zip | 1bfdd2d40290ecce237606db121cbc01d7041179f03394bd59660a2ed52e5c95 | BSD-3-Clause | RX 5500 显卡补丁，需配合 boot-arg `agdpmod=pikera`（567,275 字节） |
| AppleALC | 1.9.8 RELEASE | https://github.com/acidanthera/AppleALC/releases/download/1.9.8/AppleALC-1.9.8-RELEASE.zip | d4d36cd2da7863cf7cbfcb0892d45c08457f4f4ddd065a073dd010e46bd63bcb | BSD-3-Clause | ALC892 音频，layout 先用 `alcid=1` 试（3,780,656 字节） |
| IntelMausi | 1.0.8 RELEASE | https://github.com/acidanthera/IntelMausi/releases/download/1.0.8/IntelMausi-1.0.8-RELEASE.zip | cc02ea7e972ead536a51e5f6725e79f121026dbf36a766e97044ef2483fd29bc | GPL-2.0 | I219-V 有线网卡。该资产在 API 中 `digest` 为 `null`，SHA256 为 2026-11-23 下载后本地计算（869,695 字节） |
| NVMeFix | 1.1.3 RELEASE | https://github.com/acidanthera/NVMeFix/releases/download/1.1.3/NVMeFix-1.1.3-RELEASE.zip | e1d5657ab7ac31f69771708f7b80bf218ab9aa0b8e4c4fe6ff943983037e3dfb | BSD-3-Clause | NVMe 电源管理/兼容性（108,136 字节）。`LICENSE.txt` 正文为 BSD-3-Clause，另附 Linux 内核 GPL-2.0 片段 |
| ACPI（SSDT） | OpenCore 1.0.8 发布包内 | 同 OpenCorePkg 行（整个发布包） | 随 OpenCorePkg 发布包校验（2011e8b7216ecb2645d97ea710df965947edd406846e92050b9bc4190be6d27b） | BSD-3-Clause | 取自 OpenCore 1.0.8 release 的 `Docs/AcpiSamples/Binaries/`：SSDT-PLUG、SSDT-EC-USBX、SSDT-AWAC-DISABLE、SSDT-PMC，备用 SSDT-RTC0 放 `ACPI/optional/`；与引导器同版本，不需单独下载 |

### 表格说明

- 各组件资产的体积与版本以 release 页面为准；上表字节数是 GitHub API 返回的 asset 大小。
- IntelMausi 的发布资产上传于 2024-12，GitHub 未提供 `digest`；本表数值来自实际下载
  （`releases/download/1.0.8/IntelMausi-1.0.8-RELEASE.zip`），可用下文“重新校验”中的本地方法复算。
- OpenCorePkg 与 ACPI 样例同包：只需校验一个 zip，即可同时确认引导器与 4 个 SSDT 的来源。
- kext 的 `CFBundleIdentifier` 以 `EFI/OC/Kexts/<名称>.kext/Contents/Info.plist` 为准，本表只记录发布包来源。

### 在 EFI 中的去向

- OpenCorePkg → `EFI/BOOT/BOOTx64.efi`、`EFI/OC/OpenCore.efi`、`EFI/OC/Drivers/*.efi`
- Lilu → `EFI/OC/Kexts/Lilu.kext`
- VirtualSMC → `EFI/OC/Kexts/VirtualSMC.kext`、`SMCProcessor.kext`、`SMCSuperIO.kext`
- WhateverGreen → `EFI/OC/Kexts/WhateverGreen.kext`
- AppleALC → `EFI/OC/Kexts/AppleALC.kext`
- IntelMausi → `EFI/OC/Kexts/IntelMausi.kext`
- NVMeFix → `EFI/OC/Kexts/NVMeFix.kext`
- ACPI（SSDT） → `EFI/OC/ACPI/*.aml`（`SSDT-RTC0.aml` 仅在 `optional/`，默认不加载）

Kext 加载顺序（`Kernel → Add`，Lilu 必须最前）：
Lilu → VirtualSMC → SMCProcessor → SMCSuperIO → WhateverGreen → AppleALC → IntelMausi → NVMeFix。

## 复现与升级

### 重新校验 SHA256

用 GitHub API（无需登录，未认证限 60 次/小时，请逐个请求、间隔几秒）：

```powershell
curl.exe -s https://api.github.com/repos/acidanthera/Lilu/releases/tags/1.7.2 |
  python -c "import json,sys; a=[x for x in json.load(sys.stdin)['assets'] if x['name'].endswith('-RELEASE.zip')][0]; print(a['name'], a['digest'])"
```

把输出的 `sha256:<hex>` 与本表对应行逐字符比对；不一致就**不要**把该文件放进 EFI。

已下载到本地时：

```powershell
Get-FileHash -Algorithm SHA256 .\Lilu-1.7.2-RELEASE.zip
```

（IntelMausi 只能用这种本地方式，因为它的 API `digest` 为空。）

### 升级某个 kext（以 Lilu 为例）

1. 先整份备份现有 `EFI/` 目录（升级失败可原样回滚）。
2. 查新版本 release 的 asset `digest`，更新本文件的“版本 / 下载 URL / SHA256”三列。
3. 只替换 `EFI/OC/Kexts/Lilu.kext` 整个目录，不要新旧文件混放。
4. 保持加载顺序不变（Lilu 仍第一），检查 `config.plist` 的 `Kernel → Add` 中
   `BundlePath` / `ExecutablePath` / `PlistPath` 仍与该 kext 实际结构一致。
5. 用 OpenCore 自带的 `ocvalidate` 校验 `config.plist`，0 错误后再上机。
6. 实机启动、睡眠唤醒、显卡/音频/网络都正常后，才删除旧备份。

### 升级 OpenCore

1. 备份 `EFI/`。
2. 替换 `BOOTx64.efi`、`OpenCore.efi`、`Drivers/`，并按需更新 `Docs/AcpiSamples/Binaries/` 的 SSDT（本表 ACPI 行随发布包一起更新）。
3. **不要**直接用新版 `Sample.plist` 覆盖 `config.plist`：用 ProperTree 等工具对比新旧 sample，逐项合并。
4. `ocvalidate` 通过后再上机；三码沿用原 `config.plist`，不要重新生成（换三码会影响 iServices）。

## 不列入本清单的文件（有意为之）

- **`EFI/OC/config.plist` 中的 SMBIOS 三码**（`SystemSerialNumber`、`MLB`、`SystemUUID`）以及 `ROM`：
  它们是本机专属、由 `macserial` 现场生成，不属于“公开组件来源”。本文件**不得**写入三码，
  含三码的 config.plist 或整份 EFI 也**不要**发到公开群、论坛或网盘（有被封 iServices 的风险）。
- 装系统后自行生成的 USB 映射 kext（`UTBMap.kext` / `USBToolBox.kext`）：由用户本机用 USBToolBox 生成，
  来源是本地硬件，不在本表；生成步骤见 README。
- `Resources/`、`Tools/` 为空的占位目录，不含二进制。
- 本文件不含任何序列号、MLB、UUID 或 MAC 地址。