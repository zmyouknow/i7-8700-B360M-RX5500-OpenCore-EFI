# EFI 静态验证记录

- 日期：2026-11-23
- 目标平台：i7-8700 / Gigabyte B360M AORUS ELITE / RX 5500 / BCM943602CS / macOS Ventura 13
- OpenCore：1.0.8（ocvalidate 同版本）
- 环境：Windows，Python 3.13.9

> 本记录只覆盖**静态**验证：配置语法、引用路径、文件完整性。真机引导（NVRAM、USB 映射、
> 睡眠唤醒、Wi-Fi/蓝牙）必须在目标机器上验证，见 README 的安装步骤。

## 1. 完整流水线

命令：

```
python scripts/build.py all
```

结果：退出码 0，依次完成 fetch（7 个资产复用缓存并重新校验 SHA256）、assemble、
smbios（复用 `build/smbios.json`）、config、verify。

## 2. ocvalidate 原始输出

命令（`stage_verify` 在 `EFI/OC` 下执行）：

```
build\tools\ocvalidate.exe config.plist
```

输出：

```text
NOTE: This version of ocvalidate is only compatible with OpenCore version 1.0.8!


Completed validating config.plist in 1 ms. No issues found.
```

退出码：0

## 3. 引用路径交叉检查

`stage_verify` 逐项确认以下引用均存在，缺一即失败：

- `ACPI.Add[].Path` → `EFI/OC/ACPI/`（本配置 4 个 SSDT）
- `Kernel.Add[].BundlePath` 与拼接后的 `ExecutablePath` → `EFI/OC/Kexts/`（8 个 kext）
- `UEFI.Drivers[].Path` → `EFI/OC/Drivers/`（3 个驱动）
- `Misc.Tools[].Path` → `EFI/OC/Tools/`（本配置为空列表）
- `EFI/BOOT/BOOTx64.efi` 与 `EFI/OC/OpenCore.efi`

## 4. 自动化测试

命令：

```
python scripts/test_build.py
```

结果：退出码 0，194 项检查全部 `OK`（无 `FAIL`）。原始日志：
`build/logs/task6-green.txt`（`build/` 不提交）。

## 5. 七个资产的 SHA256

全部与 `scripts/build.py` 中的固定值一致，并在每次 fetch 时重新校验。

| 资产 | 版本 | SHA256 |
| --- | --- | --- |
| opencore | 1.0.8 | `2011e8b7216ecb2645d97ea710df965947edd406846e92050b9bc4190be6d27b` |
| lilu | 1.7.2 | `53967d7dcfaab01023a33df2e969a89522f13d6654a6a56ac4711b62dabf3ab8` |
| virtualsmc | 1.3.8 | `2e29a8aaf91b4eb0bcdf5913ed17e70f5cf76531122acd4132eff7813a54de8b` |
| whatevergreen | 1.7.1 | `1bfdd2d40290ecce237606db121cbc01d7041179f03394bd59660a2ed52e5c95` |
| applealc | 1.9.8 | `d4d36cd2da7863cf7cbfcb0892d45c08457f4f4ddd065a073dd010e46bd63bcb` |
| intelmausi | 1.0.8 | `cc02ea7e972ead536a51e5f6725e79f121026dbf36a766e97044ef2483fd29bc` |
| nvmefix | 1.1.3 | `e1d5657ab7ac31f69771708f7b80bf218ab9aa0b8e4c4fe6ff943983037e3dfb` |

## 6. EFI 文件清单

命令：`Get-ChildItem -Recurse -File EFI | Select-Object FullName,Length`

```text
EFI/.gitkeep  0
EFI/BOOT/BOOTx64.efi  24576
EFI/OC/ACPI/optional/SSDT-RTC0.aml  142
EFI/OC/ACPI/SSDT-AWAC-DISABLE.aml  78
EFI/OC/ACPI/SSDT-EC-USBX.aml  306
EFI/OC/ACPI/SSDT-PLUG.aml  900
EFI/OC/ACPI/SSDT-PMC.aml  143
EFI/OC/config.plist  36281
EFI/OC/Drivers/OpenHfsPlus.efi  40960
EFI/OC/Drivers/OpenRuntime.efi  24576
EFI/OC/Drivers/ResetNvramEntry.efi  45056
EFI/OC/Kexts/AppleALC.kext/Contents/Info.plist  439447
EFI/OC/Kexts/AppleALC.kext/Contents/MacOS/AppleALC  3810852
EFI/OC/Kexts/IntelMausi.kext/Contents/Info.plist  3587
EFI/OC/Kexts/IntelMausi.kext/Contents/MacOS/IntelMausi  168888
EFI/OC/Kexts/Lilu.kext/Contents/Info.plist  2742
EFI/OC/Kexts/Lilu.kext/Contents/MacOS/Lilu  527456
EFI/OC/Kexts/NVMeFix.kext/Contents/Info.plist  2367
EFI/OC/Kexts/NVMeFix.kext/Contents/MacOS/NVMeFix  51312
EFI/OC/Kexts/SMCProcessor.kext/Contents/Info.plist  2738
EFI/OC/Kexts/SMCProcessor.kext/Contents/MacOS/SMCProcessor  49968
EFI/OC/Kexts/SMCSuperIO.kext/Contents/Info.plist  2620
EFI/OC/Kexts/SMCSuperIO.kext/Contents/MacOS/SMCSuperIO  223800
EFI/OC/Kexts/VirtualSMC.kext/Contents/Info.plist  8652
EFI/OC/Kexts/VirtualSMC.kext/Contents/MacOS/VirtualSMC  245408
EFI/OC/Kexts/WhateverGreen.kext/Contents/Info.plist  3020
EFI/OC/Kexts/WhateverGreen.kext/Contents/MacOS/WhateverGreen  527896
EFI/OC/OpenCore.efi  626688
EFI/OC/Resources/.gitkeep  0
EFI/OC/Tools/.gitkeep  0
```

## 7. 结论

- ocvalidate 1.0.8 对 `EFI/OC/config.plist` 报告 `No issues found`，退出码 0。
- 配置引用的 ACPI 表、kext（含可执行文件）、UEFI 驱动全部存在。
- 测试套件 194 项通过，构建流水线可重复执行（fetch/assemble/smbios 均幂等）。
- 已知限制：`PlatformInfo.Generic.ROM` 是随机占位值，装好系统后应改为网卡 MAC；
  未做真机引导验证。

## 8. 最终交付包

- 文件：`build/EFI-2026-11-23.zip`（4,041,833 字节、27 个文件；`build/` 不提交）。
  重建必须剔除 `.gitkeep` 占位与随之变空的 `Resources/`、`Tools/` 目录，否则
  `Compress-Archive -Path EFI` 会得到 39 个条目/30 个文件、字节数不符。可复现命令：

  ```powershell
  Remove-Item -Recurse -Force build\stage -ErrorAction SilentlyContinue
  Copy-Item -Recurse EFI build\stage\EFI
  Get-ChildItem build\stage\EFI -Recurse -Filter .gitkeep | Remove-Item -Force
  Remove-Item -Recurse build\stage\EFI\OC\Resources, build\stage\EFI\OC\Tools
  Compress-Archive -Path build\stage\EFI -DestinationPath build\EFI-2026-11-23.zip -CompressionLevel Optimal -Force
  ```

  产物为 36 个 zip 条目（27 个文件 + 9 个目录条目：`Kexts/` 与 8 个 `.kext/`），
  大小与随附 `build/EFI-2026-11-23.zip` 一致（4,041,833 字节）。
- 内容：27 个文件（已剔除 `.gitkeep` 占位），路径分隔符为 `/`，macOS 访达/解压工具可直接展开。
- 已核对必须存在的条目：
  - `EFI/BOOT/BOOTx64.efi`
  - `EFI/OC/OpenCore.efi`、`EFI/OC/config.plist`
  - 4 个 ACPI 表 + `ACPI/optional/SSDT-RTC0.aml`
  - 3 个驱动（OpenRuntime、OpenHfsPlus、ResetNvramEntry）
  - 8 个 kext（Lilu、VirtualSMC、SMCProcessor、SMCSuperIO、WhateverGreen、AppleALC、
    IntelMausi、NVMeFix），每个含 `Contents/Info.plist` 与 `Contents/MacOS/<同名>`（UTBMap 除外，未随包提供）
- 不含：`build/`、下载的 zip、`.superpowers/`、`.git/`、SMBIOS 备份文件；`config.plist` 内含三码，**不要公开分享**。
- `python scripts/test_build.py`（194 项）、`python scripts/test_readme.py`（48 项）、
  `python scripts/test_sources.py`（39 项）均为退出码 0。
