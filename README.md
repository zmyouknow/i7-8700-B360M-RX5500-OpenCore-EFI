# 黑苹果 EFI 使用说明（i7-8700 / B360M AORUS ELITE / RX 5500 / Ventura 13）

本仓库提供一个为下面这套硬件准备的 OpenCore EFI：**i7-8700 + 技嘉 B360M AORUS ELITE + AMD RX 5500 + Broadcom BCM943602CS（PCIe 转接卡）+ macOS Ventura 13**。

> **当前状态：只做了静态构建与校验，没有在目标实机上安装过。**
> 文件完整性、`config.plist` 解析、`ocvalidate`、kext 顺序、SHA256 等属于「已验证（静态）」；能否真正启动、显卡/声卡/网卡/蓝牙是否工作，全部属于「待实机确认」。文末有完整清单。请不要把本文当作「已测试可用」的证明。
>
> **仓库安全提醒：本仓库的 git 历史里也包含构建时生成的三码（不只当前工作区）。不要把本仓库推送到公开远端/公开仓库，也不要把 `.git` 目录发给别人。**

---

## 0. 最短路径

1. **先备份 Windows**：重要数据备份；如果开了 BitLocker，先暂停或保存恢复密钥。
2. **改 BIOS**：按第 2 节关 CSM / Secure Boot / Fast Boot / VT-d / 串口，开 Above 4G、XHCI Hand-off，SATA 设 AHCI，核显 Enabled、DVMT 64M。
3. **做 U 盘**：16GB 以上，按第 3 节（有 Mac 或只有 Windows 两条路），把本仓库的 `EFI` 文件夹放到 U 盘 EFI 分区根目录。
4. **断开 Windows 盘**：关机后拔掉 Windows 盘的 SATA 电源/数据线，或在 BIOS 禁用对应接口；只留目标 NVMe 盘和安装 U 盘（第 4.1 节）。
5. **装系统**：F12 选 UEFI U 盘 → OpenCore 菜单选 Install macOS Ventura → 磁盘工具**核对容量/型号**后抹成 APFS/GUID → 安装 → 多次重启继续（第 4 节）。
6. **EFI 落到 macOS 盘自己的 ESP**：装好后把 `EFI` 复制到 macOS 盘（不是 Windows 盘）的 EFI 分区（第 4.5 节）。
7. **装后必做**：USB 映射（蓝牙线插着、内部口标 `Internal`）、音频 layout 试错、换真实 MAC 作 ROM、iServices 修复（第 5 节）。
8. **备份 EFI**：能正常用之后，把整个 `EFI` 文件夹压缩备份；以后升级前也先备份（第 7 节）。

---

## 1. 硬件清单与本方案的假设

| 部件 | 本方案的假设 | 说明 |
|---|---|---|
| CPU | Intel i7-8700（Coffee Lake，UHD 630） | 核显只做无头计算，不接显示器 |
| 主板 | 技嘉 B360M AORUS ELITE | BIOS 选项名称可能随版本不同 |
| 独显 | AMD RX 5500（Navi 14） | 显示器接这张卡；`agdpmod=pikera` 防黑屏 |
| 无线/蓝牙 | Broadcom BCM943602CS（PCIe 转接卡） | Ventura 原生支持，**不需要** Broadcom 相关 kext；蓝牙走转接卡的 USB 线，插在主板内部 USB 2.0 针脚 |
| 有线网卡 | Intel I219-V | 由 IntelMausi 驱动，应识别为 `en0` |
| 声卡 | Realtek ALC892（假设） | 先用 `alcid=1`，不对再逐个试 layout |
| 系统盘 | 一块**单独的空白 NVMe** | 现有 Windows 盘和数据完全不动；EFI 放 macOS 盘自己的 ESP |
| 引导 | OpenCore 1.0.8 RELEASE | 默认文本选择器，无 OpenCanopy 主题 |
| 机型 | iMac19,1 | 公开仓库里三码是占位值，装前必须按 1.2 生成自己的三码 |
| 系统 | macOS Ventura 13 | 本 EFI 只面向 Ventura，不面向 Sonoma/Sequoia |

### 1.1 动手前需要确认的四件事

1. **声卡到底是不是 ALC892**
   在 Windows 打开「设备管理器 → 声音、视频和游戏控制器 → Realtek High Definition Audio → 属性 → 详细信息 → 硬件 ID」，应看到类似 `HDAUDIO\FUNC_01&VEN_10EC&DEV_0892`。`DEV_0892` 就是 ALC892。
   如果换成了别的 codec，`alcid=1` 不一定有声音，需要按 AppleALC 的支持列表换 layout（见 5.2）。
2. **有线网卡是不是 I219-V**
   「设备管理器 → 网络适配器」应看到 `Intel(R) Ethernet Connection I219-V`。如果型号不同，IntelMausi 可能不适用，本文不覆盖那种情况。
3. **目标 NVMe 盘是什么型号**
   在 Windows「磁盘管理」或 CrystalDiskInfo 里看型号。**如果是三星 PM981 / PM991 / PM9A1，先看第 6 节，不要直接装。** 同时确认这块盘是空的、容量足够。
4. **显示器接在 RX 5500 上**
   不要接主板视频口。本方案让 UHD 630 保持无头（不输出画面），只参与硬件加速。

另外建议先确认两件事，避免改完 BIOS 进不去 Windows：

- Windows 是 **UEFI** 启动（`msinfo32` 里「BIOS 模式」显示 UEFI）。如果是 Legacy/MBR，关 CSM 后 Windows 可能无法启动。
- Windows 是否开了 **BitLocker**。关闭 Secure Boot / CSM 可能触发恢复界面，先保存恢复密钥或暂停 BitLocker。

### 1.2 本仓库的 config.plist 是模板（三码为占位值）

公开仓库里的 `EFI/OC/config.plist` **不含真实三码**：`SystemSerialNumber=C02XXXXXXXXX`、`MLB=XXXXXXXXXXXXXXXXX`、`SystemUUID=00000000-0000-0000-0000-000000000000`、`ROM` 为 6 个 0。这样 `ocvalidate` 依然能通过、也能进系统，但**不能登录 iServices / App Store**，更不能两台机器共用。

装之前生成这套机器自己的三码（二选一）：

- **方式 A（推荐，Windows 上在本仓库根目录）**：

  ```powershell
  python scripts/build.py smbios config
  ```

  自动生成 iMac19,1 的 Serial / MLB / SystemUUID 并写回 `EFI/OC/config.plist`。生成的 `build/smbios.json` 要保存好，删掉再跑会换一套号。
- **方式 B（手工）**：用 GenSMBIOS（corpnewt/GenSMBIOS）选 `iMac19,1` 生成，或用本仓库的 `macserial` 生成后，用 ProperTree 填入 `PlatformInfo → Generic`；Serial / MLB / SystemUUID 必须配套，不要混用不同批次。

最后都要把 `ROM` 换成这台机器 **I219-V 的真实 MAC**（见 5.3），再用**同版本** `ocvalidate` 确认 0 错误。

> 三码是你这台机器的身份：不要两台机器共用，也不要提交/推送到公开仓库。生成自己的三码之后，不要再 `git push` 含三码的提交。

---

## 2. BIOS 设置清单

开机按 `Del` 进 BIOS，按 `F10` 保存。不同 BIOS 版本的菜单位置/名称可能略有差异，找同名或意思相近的项。

| 位置（以当前 BIOS 为准） | 选项 | 设为 |
|---|---|---|
| Boot | CSM Support | **Disabled** |
| Boot | Secure Boot | **Disabled**（如果灰色，先关 CSM 再回来） |
| Boot | Fast Boot | **Disabled** |
| Boot | Windows 8/10 Features | **Other OS** |
| Chipset | VT-d | **Disabled** |
| Peripherals | Above 4G Decoding | **Enabled** |
| Peripherals → USB Configuration | XHCI Hand-off | **Enabled** |
| Peripherals → SATA And RST Configuration | SATA Mode Selection | **AHCI** |
| Peripherals | Internal Graphics | **Enabled**（不要选 Auto） |
| Peripherals | DVMT Pre-Allocated | **64M** |
| Peripherals → Super IO Configuration | Serial Port | **Disabled** |

补充说明：

- **Above 4G 必须开**，否则 RX 5500 可能黑屏或引导失败。
- **Internal Graphics 选 Enabled**，保证 UHD 630 设备存在，供 VideoToolbox 使用；DVMT 64M 是推荐值。
- **CFG Lock 不用改**：config 里已经用 `AppleXcpmCfgLock=true` 处理。
- **SATA AHCI**：如果 Windows 目前是 Intel RST / RAID 模式，直接改成 AHCI 可能进不去 Windows。先确认或在 Windows 里切好，并知道怎么改回去。
- 关 Secure Boot / CSM 可能触发 BitLocker 恢复，先保存恢复密钥。
- **升级 BIOS 会重置这些设置**，升级后要重新检查一遍。

---

## 3. 制作安装 U 盘

### 3.0 准备

- 一个 **16GB 以上**的 U 盘（建议 32GB；写入会**清空** U 盘）。
- macOS Ventura 13 安装器。
- 本仓库的 `EFI` 文件夹。
- 最终 U 盘结构必须是：U 盘根目录下有 `EFI` 文件夹，里面有 `EFI/BOOT/BOOTx64.efi` 和 `EFI/OC/OpenCore.efi`。

### 3.1 有 Mac 的电脑（推荐）

1. 在 Mac App Store 下载「macOS Ventura」，得到 `/Applications/Install macOS Ventura.app`。
2. 用「磁盘工具」把 U 盘抹成 **Mac OS Extended (Journaled)**、**GUID 分区图**，名字例如 `MyVolume`。
3. 打开「终端」，执行（把 `MyVolume` 换成你的 U 盘卷名）：

   ```bash
   sudo /Applications/Install\ macOS\ Ventura.app/Contents/Resources/createinstallmedia \
     --volume /Volumes/MyVolume --nointeraction
   ```

4. 完成后卷名会变成 `Install macOS Ventura`。挂载 U 盘的 EFI 分区并复制 EFI：

   ```bash
   diskutil list                    # 找到 U 盘上约 200MB 的 EFI 分区，例如 disk4s1
   sudo diskutil mount disk4s1
   cp -R /path/to/EFI /Volumes/EFI/
   ls /Volumes/EFI/EFI/BOOT/BOOTx64.efi   # 必须存在
   diskutil unmount /Volumes/EFI
   ```

   如果 U 盘 EFI 分区里本来就有 `EFI` 文件夹，直接合并/覆盖成这份 EFI，不要留两套引导文件。

### 3.2 只有 Windows 的电脑

1. 下载 **gibMacOS**（corpnewt/gibMacOS，GitHub），运行 `gibMacOS.bat`，选择 macOS 13 Ventura，下载完整安装器。
2. 按 gibMacOS 自带的 Windows 写入脚本，或按 Dortania 的 Windows 制作流程把安装器写入 U 盘（可使用 BalenaEtcher / Rufus；Rufus 选 **GPT + UEFI（非 CSM）**，不要选 MBR/Legacy）。**写入会清空 U 盘。**
3. 写完后用 **DiskGenius** 查看 U 盘：应有一个 FAT32 的 EFI 分区。给该分区分配盘符，把本仓库的 `EFI` 文件夹整个复制到分区根目录，最终是：

   ```text
   U盘:\EFI\BOOT\BOOTx64.efi
   U盘:\EFI\OC\OpenCore.efi
   U盘:\EFI\OC\config.plist
   ```

4. 如果 Windows 工具反复失败，最稳妥的办法是借一台 Mac 用 3.1 的 `createinstallmedia`。不要使用来源不明的「黑苹果镜像」或别人打包好的 EFI。

> 「只有 Windows」这条路能否一次成功，取决于 gibMacOS/写入工具的版本和 U 盘。写入后如果 U 盘没有 EFI 分区，或 BIOS 根本不识别，按第 8 节先排查，不要反复盲目重写。

---

## 4. 安装 macOS Ventura

### 4.1 装之前：物理断开 Windows 盘（强烈建议）

关机、拔掉电源，然后二选一：

- **物理断开**：拔掉 Windows 盘的 SATA 电源线和数据线（M.2 盘则拆下，或至少断开其供电）。
- **BIOS 禁用**：在 BIOS 里禁用 Windows 盘所在的 SATA / M.2 接口。

只保留：**目标 NVMe 盘 + 安装 U 盘**。这样做的原因：

- 不会在磁盘工具里抹错盘；
- 不会出现两个 EFI 分区（Windows 盘一个、macOS 盘一个）互相混淆；
- 安装器不会去动 Windows 的引导。

如果实在无法断开，抹盘时必须反复核对容量和型号（见 4.3），风险自负。

### 4.2 启动安装器

1. 插上 U 盘，建议插**后置 USB 2.0 口**（安装阶段最稳）。
2. 开机按 `F12`，选 `UEFI: <你的U盘>`。
3. 进入 OpenCore 文本菜单，选 **Install macOS Ventura**。
4. 如果选择后黑屏，先确认显示器接在 RX 5500 上，并看第 8 节。

> config 里 `HideAuxiliary=true`，OpenCore 默认会隐藏 Reset NVRAM 等辅助项；需要时在菜单界面按**空格**显示。

### 4.3 抹盘：先核对容量和型号

1. 进入安装器后，先打开「磁盘工具」。
2. 菜单栏「显示」→「显示所有设备」。
3. 在左侧选中**整块目标 NVMe 盘**（不是它下面的卷，也不是 U 盘）。
4. **执行「抹掉」前，再核对一次：盘符、容量、型号。**
   - 目标盘应该是那块空 NVMe 的容量（例如 500GB / 1TB）。
   - 不要选成 16GB/32GB 的 U 盘。
   - Windows 盘此时应该已经拔掉/禁用；如果还能看到它，立刻停手，回去断开。
5. 确认无误后点「抹掉」，设置：
   - 名称：`Macintosh HD`
   - 格式：**APFS**
   - 方案：**GUID 分区图**
6. 抹掉完成后关闭磁盘工具。

> 只要容量或型号对不上，就不要点「抹掉」。这一步没有撤销。

### 4.4 安装

1. 选择「安装 macOS Ventura」，同意协议，目标选刚抹好的 `Macintosh HD`。
2. 安装过程中会自动重启多次。**每次重启后在 OpenCore 菜单里继续选 `macOS Installer`**（安装完成后这个入口会消失），最后选 `Macintosh HD` 进入设置向导。
3. 安装期间不要拔 U 盘，不要选 Windows 启动项（此时 Windows 盘也不应该接着）。
4. 进入设置向导后创建本地账户。Apple ID 可以先跳过，等 5.3 把 `en0` 和 ROM 处理好再登录，成功率更高。

### 4.5 把 EFI 放到 macOS 盘自己的 ESP

ESP 就是 EFI System Partition（约 200–300MB 的 FAT32 分区）。**必须放 macOS 盘自己的 ESP，不是 Windows 盘的 ESP。**

1. 进入 macOS 桌面后打开「终端」，先找到 macOS 盘和它的 EFI 分区：

   ```bash
   diskutil list
   ```

   不要假设一定是 `disk0`。按容量、卷名（`Macintosh HD`）确认 macOS 盘，再找同一块盘上类型为 `EFI` 的分区（通常是 `diskXs1`）。

2. 挂载 macOS 盘的 ESP：

   ```bash
   sudo diskutil mount diskXs1
   open /Volumes/EFI
   ```

3. 把本仓库的 `EFI` 文件夹整个复制进去（可以用 Finder，也可以 `cp -R`）。复制后必须是：

   ```text
   /Volumes/EFI/EFI/BOOT/BOOTx64.efi
   /Volumes/EFI/EFI/OC/OpenCore.efi
   /Volumes/EFI/EFI/OC/config.plist
   ```

   可以在终端验证：

   ```bash
   ls /Volumes/EFI/EFI/BOOT/BOOTx64.efi
   ls /Volumes/EFI/EFI/OC/OpenCore.efi
   diskutil unmount /Volumes/EFI
   ```

4. 关机，接回 Windows 盘。开机按 `F12`，现在应该能从 macOS 盘的 UEFI 项进入 OpenCore；Windows 则选 `Windows Boot Manager`。**不要动 Windows 盘自己的 ESP**，两套引导各在各的盘上，用 BIOS 启动菜单切换即可。

> 本 EFI 的 `LauncherOption=Disabled`，不会主动往 BIOS 写启动项。如果 BIOS 启动菜单里看不到 OpenCore，就每次开机按 `F12` 选 macOS 盘的 UEFI 项；也可以在 BIOS 里把该 UEFI 项调到启动顺序第一位。不要为了「自动进 OpenCore」去改 Windows 的引导文件。

---

## 5. 装好之后必须做的事

### 5.1 USB 映射（含蓝牙，最重要）

Ventura 有 15 端口限制，`XhciPortLimit` 在新系统上无效且有害，所以**必须在装好系统后做 USB 映射**。本方案推荐在 Windows 里用 **USBToolBox** 做（同一台机器，映射结果通用）。

**关键提醒：映射时一定要插着 BCM943602CS 的蓝牙 USB 线，并把蓝牙所在的内部口标记为 `Internal`。否则映射完成后蓝牙会消失。**

步骤：

1. 关机接回 Windows 盘，从 Windows 启动。下载 USBToolBox 的 Windows 版。
2. 保持蓝牙 USB 线插在主板的内部 USB 2.0 针脚上。把鼠标、键盘、U 盘等分别插到**每一个物理 USB 口**（USB 2.0 和 USB 3.0 都要插一遍）。
3. 运行 USBToolBox → `Discover Ports`，按提示在每个口插拔设备，直到所有端口都被发现；然后进入 `Select Ports`。
4. 把蓝牙所在的那个内部口类型设为 **`Internal`**（不是 USB 2.0 / USB 3.0），其他口按实际类型设置。不要删除正在使用的端口。
5. 生成 kext：得到 `UTBMap.kext` 和 `USBToolBox.kext`。
6. 把两个 kext 放进 `EFI/OC/Kexts/`。用 ProperTree 打开 `EFI/OC/config.plist`，在 `Kernel → Add` 中添加：
   - `USBToolBox.kext` 在前；
   - `UTBMap.kext` 在后；
   - 两者 `Enabled=true`，`BundlePath` 指向 `Kexts/...`，`PlistPath` 指向 `Contents/Info.plist`。
   - `USBToolBox.kext` 的 `ExecutablePath` 指向 `Contents/MacOS/USBToolBox`；`UTBMap.kext` 是无代码 kext，`ExecutablePath` 留空。
   - 如果之前有别的 `USBMap.kext`，不要同时启用。
   - `Kernel → Quirks → XhciPortLimit` 必须保持 **`false`**。
7. 保存后用**同版本**的 `ocvalidate` 检查，0 错误再重启。
8. 重启进 macOS，验证：所有 USB 口、蓝牙（系统设置 → 蓝牙）、睡眠是否正常。**如果蓝牙消失，说明内部口漏了或类型不对，插着蓝牙线重新映射。**

> 也可以在 macOS 里用 USBMap 等工具做映射，但本说明以 USBToolBox 为准；不要两套映射同时启用。

### 5.2 音频（`alcid=1` 只是起点）

本 EFI 的 boot-args 里带 `alcid=1`，这是按 **ALC892** 假设的初始值。没有声音时按顺序排查：

1. 确认 codec 实际型号（第 1.1 节）。不是 ALC892 就查 AppleALC 对该 codec 的支持。
2. 在终端确认 AppleALC 已加载、系统能看到音频设备：

   ```bash
   kextstat | grep -i applealc
   system_profiler SPAudioDataType
   ```

3. 换 layout：编辑 `config.plist` 的 `NVRAM → Add → 7C436110-AB2A-4BBB-A880-FE41995C9F82 → boot-args`，把 `alcid=1` 改成 `alcid=2`、`3`、`7`、`15`、`16`、`20` 等（以 AppleALC Wiki 的 ALC892 列表为准），保存后 **在 OpenCore 菜单执行 Reset NVRAM**（菜单里没有就按空格显示辅助项）再启动（否则 NVRAM 里的旧 boot-args 可能仍生效）。
4. BIOS 里确认板载音频是 Enabled；机箱前置和后置绿色接口都试一遍。
5. 不要装 VoodooHDA 之类替代驱动；先把 AppleALC layout 试对。

### 5.3 iServices（App Store / iMessage / FaceTime）

iServices 能用的前提是：**有线网卡是 `en0` + ROM 是真实 MAC + SMBIOS 三码完整且唯一**。

1. 确认 `en0` 是有线网卡：

   ```bash
   networksetup -listallhardwareports
   ```

   输出里 `en0` 应该对应 Intel I219-V 的 Ethernet。如果 `en0` 是 Wi-Fi 或 USB 网卡，先移除多余网卡/重建网络接口，让有线网卡回到 `en0`。

2. 取真实 MAC：在 Windows 里执行 `getmac /v`（或 `ipconfig /all`），找到 `Intel(R) Ethernet Connection I219-V` 的物理地址，例如 `AA-BB-CC-DD-EE-FF`，去掉分隔符得到 12 位十六进制 `AABBCCDDEEFF`。
3. 用 ProperTree 打开 `config.plist`，把 `PlatformInfo → Generic → ROM` 改成 **Data 类型、6 字节**，填入上面这个 MAC。**config 里原来的 ROM 只是占位，必须换。**
4. 确认 `PlatformInfo → Generic` 里的 Serial / MLB / SystemUUID 都已填写，并且是 iMac19,1 的、未注册的序列号（可在 checkcoverage.apple.com 查，显示「无法验证」是正常的）。
5. 保存 → `ocvalidate` 0 错误 → 重启，在 OpenCore 菜单执行 **Reset NVRAM**。
6. 登录顺序：先 App Store，再 iMessage / FaceTime。失败时检查：系统时间是否自动、`en0` 是否仍然是有线、ROM 是否真的是 `en0` 的 MAC、三码是否完整。
7. 仍然失败：用 GenSMBIOS + macserial 重新生成一套 iMac19,1 的 Serial/MLB/SystemUUID（三码要一起换），再 Reset NVRAM。不要短时间内反复登录尝试。

> 含三码的 `config.plist` 不要发到公开群/论坛；备份时也注意别泄露。**整个 git 历史也含三码（不只工作区）**，不要把本仓库推送到公开远端/公开仓库。

### 5.4 收尾

- 系统稳定几天后，可以把 `-v keepsyms=1 debug=0x100` 从 boot-args 去掉，保留 `agdpmod=pikera` 和 `alcid=<你的layout>`；改动前先备份。
- 把整个 `EFI` 文件夹压缩备份（例如 `EFI-backup-2026xxxx.zip`），并保留一个能启动的 U 盘。以后升级/折腾失败时可以快速回滚。
- 不要关闭 SIP（本 EFI 的 `csr-active-config=00000000` 是开启状态）；没有明确需求不要改 `SecureBootModel`。

### 5.5 时间/NVRAM 异常与 AWAC 回退

B360 属于 300 系芯片组。部分固件没有 Legacy RTC 开关，或者没有 `STAS` 变量，macOS 可能无法正确接管 RTC。典型症状是：**时间或 NVRAM 不持久（例如 boot-args、启动磁盘设置每次重启都丢）、休眠唤醒异常、偶发启动卡住**。如果只是时间偶尔不准，先在「系统设置 → 通用 → 日期与时间」确认自动同步，并换主板电池；排除电池/时区问题后，再考虑下面的回退。

回退步骤（先备份 `EFI` 和 `config.plist`）：

1. 用 ProperTree 打开 `EFI/OC/config.plist`，在 `ACPI → Add` 里找到 `SSDT-AWAC-DISABLE.aml`，把 `Enabled` 改为 **false**。
2. 把 `EFI/OC/ACPI/optional/SSDT-RTC0.aml` 复制到 `EFI/OC/ACPI/`（与 `SSDT-AWAC-DISABLE.aml` 同一目录）。
3. 回到 `ACPI → Add` 新增一项：`Path` = `SSDT-RTC0.aml`，`Enabled` = **true**；`Comment` 可写 `RTC0 fallback`，其他字段与现有 ACPI 项保持一致。
4. 用**同版本**的 `ocvalidate` 检查，0 错误后保存；在 OpenCore 菜单执行 Reset NVRAM（菜单里没有就按空格显示辅助项），再启动观察。

> **不要同时启用 `SSDT-AWAC-DISABLE.aml` 和 `SSDT-RTC0.aml`**：两者是互斥的 RTC 补丁。默认只启用 AWAC 补丁；只有出现上面的 RTC 症状时才切到 RTC0，切换后先稳定使用，不要来回反复改。

---

## 6. NVMe 硬盘兼容性提醒

本方案按「一块单独的空白 NVMe」准备。**三星 PM981 / PM991 / PM9A1 这一类型号在 macOS 下有已知兼容问题**，常见表现是安装失败、卡顿、掉盘、随机重启。它们不是靠 kext 就能稳定解决的。

- 装之前先在 Windows「磁盘管理」/ CrystalDiskInfo 里确认目标盘型号。
- 如果目标盘是 PM981 / PM991 / PM9A1：**先换盘**，换一块其他 NVMe，或改用 SATA SSD，再开始安装。
- 本 EFI 已包含 **NVMeFix**，它用于改善 NVMe 电源管理/兼容性，但**不能修复**上述三星型号的问题。
- 如果已经装在这类型号上并出现掉盘/卡顿，先备份数据，换盘重装，不要继续在上面做生产力使用。

---

## 7. 以后怎么升级

### 7.1 升级前

- 备份整个 `EFI` 文件夹（zip，带日期），并保留一个能启动的 U 盘。
- 一次只升一个东西（先 OpenCore，或先某个 kext），出问题才知道是谁导致的。

### 7.2 升级 OpenCore

1. 下载新版 OpenCorePkg RELEASE，阅读其中的 `Docs/Differences.pdf`（版本间的 config 变更）。
2. 用 ProperTree 对比新版 `Docs/Sample.plist` 和你的 `config.plist`，把新增/变更的键合并进去。**不要直接用新 Sample 覆盖**，否则会丢 SMBIOS、boot-args 等。
3. 替换 `EFI/BOOT/BOOTx64.efi`、`EFI/OC/OpenCore.efi`、`EFI/OC/Drivers/OpenRuntime.efi` 等对应文件（以新版 release 的目录为准）。
4. 用**同版本**的 `ocvalidate` 校验 `config.plist`，必须 0 错误。
5. 先在一张 U 盘上试新 EFI，能正常启动后再写回硬盘 ESP；失败就用旧备份。

### 7.3 升级 kext

1. 从各自官方 release 下载新版本，替换 `EFI/OC/Kexts/` 下同名 `.kext`。
2. 保持加载顺序不变：**Lilu → VirtualSMC → SMCProcessor → SMCSuperIO → WhateverGreen → AppleALC → IntelMausi → NVMeFix**（USB 映射的 kext 按 5.1 的顺序另算）。Lilu 必须最先加载。
3. 更新 `SOURCES.md` 里的版本和 SHA256，运行 `ocvalidate`，重启验证。

### 7.4 升级 macOS

- Ventura 的**小版本**更新一般可以直接在「系统设置 → 通用 → 软件更新」里做；更新前备份 EFI 和重要数据。
- **不要用这份 EFI 直接升 Sonoma / Sequoia**：本方案只针对 Ventura，也没有使用 OpenCore Legacy Patcher。大版本升级需要重新评估 kext、OC 版本和补丁。
- 升级后如果无法启动，用备份 U 盘启动，恢复旧 EFI。

---

## 8. 排错表

排错原则：**一次只改一个变量**；改前备份 `config.plist`/EFI；优先用 U 盘上的 EFI 试验，成功后再写回硬盘 ESP。通用第一步是看 `-v` 最后一行并拍照、用同版本 `ocvalidate` 检查、在 OpenCore 菜单 Reset NVRAM（没有就按空格显示辅助项）、换后置 USB 2.0 口。

| 现象 | 先检查什么（按顺序） |
|---|---|
| 卡在 `[EB\|#LOG:EXITBS_PAD]` | 1. 换后置 USB 2.0 口；BIOS 关 CSM/Fast Boot、开 Above 4G。<br>2. 看 `-v` 最后一行，确认卡在哪个 kext/阶段。<br>3. 用同版本 `ocvalidate` 检查 config；确认 `OpenRuntime.efi` 存在且启用。<br>4. 确认 kext 顺序 Lilu 第一；临时移除可疑 kext 再试。<br>5. OpenCore 菜单 Reset NVRAM 后重试。 |
| 选安装器后黑屏/无信号 | 1. 显示器必须接 RX 5500，不接主板视频口。<br>2. boot-args 是否含 `agdpmod=pikera`；用 `-v` 看停在哪。<br>3. BIOS Internal Graphics=Enabled、DVMT=64M；`AAPL,ig-platform-id=0300913E` 未被改。<br>4. 换 U 盘/后置 USB 2.0；确认安装器完整。<br>5. 进度条后黑屏可先等 1–2 分钟再判断。 |
| 没有声音 | 1. `kextstat \| grep -i applealc` 确认 AppleALC 已加载；`system_profiler SPAudioDataType` 看设备。<br>2. 确认 `alcid=1` 已生效；换 layout 后必须 Reset NVRAM。<br>3. 按 AppleALC 的 ALC892 列表逐个试 layout（1、2、3、7、15、16、20 等）。<br>4. BIOS 板载音频 Enabled；前置/后置接口都试。<br>5. 确认 codec 实际型号，不是 ALC892 就查对应支持。 |
| 没有有线网络 / 不是 en0 | 1. BIOS 板载网卡 Enabled；`kextstat \| grep -i intelmausi`。<br>2. `networksetup -listallhardwareports` 看 `en0` 是否 Ethernet。<br>3. 换网线/路由器口；Windows 下确认是 I219-V。<br>4. 移除 USB 网卡等会抢占 `en0` 的设备，重建网络接口。<br>5. 确认没有把 Wi-Fi 当成 `en0`。 |
| 睡眠/唤醒异常 | 1. 先完成 USB 映射（未映射的内部设备会阻止睡眠）。<br>2. `pmset -g assertions` 看谁阻止睡眠。<br>3. 确认 SSDT-PMC 生效、NVRAM 能持久化。<br>4. BIOS 关掉 Wake on LAN 等唤醒项；拔掉不必要 USB。<br>5. Reset NVRAM 后再观察。 |
| USB 口失效 / 蓝牙消失 | 1. `UTBMap.kext`、`USBToolBox.kext` 已启用，顺序为 USBToolBox 在前。<br>2. `XhciPortLimit=false`。<br>3. 映射时蓝牙线是否插着，内部口是否标 `Internal`。<br>4. 重新映射；不要同时启用旧 USBMap。<br>5. 先试后置 USB 2.0 口。 |
| Wi-Fi / 蓝牙不可用 | 1. 蓝牙 USB 线是否插在主板内部 USB 2.0 针脚。<br>2. `system_profiler SPBluetoothDataType` 和 Wi-Fi 菜单是否有设备。<br>3. 本 EFI **不需要** Broadcom kext，不要额外装 AirportBrcmFixup/BrcmPatchRAM。<br>4. USB 映射是否把内部口删掉；天线是否接好。<br>5. 关机断电，重插转接卡。 |
| OpenCore 菜单看不到 U 盘 | 1. BIOS 仅 UEFI、CSM 关、Fast Boot 关。<br>2. U 盘是 GPT，EFI 分区是 FAT32，根目录有 `EFI/BOOT/BOOTx64.efi`。<br>3. 换后置 USB 2.0 口，重新插拔。<br>4. 用 DiskGenius 确认 EFI 分区没被写坏。<br>5. 重新制作 U 盘。 |
| iServices 登录失败 | 1. `en0` 是有线 I219-V（`networksetup -listallhardwareports`）。<br>2. ROM 是 `en0` 的真实 MAC（6 字节 Data），不是占位值。<br>3. Serial/MLB/SystemUUID 完整且未注册。<br>4. Reset NVRAM；先登录 App Store，再 iMessage。<br>5. 仍失败就换一套三码重生成，不要频繁重试。 |
| `ocvalidate` 报错 | 1. 用与 OpenCore 同版本的 `ocvalidate`。<br>2. 检查 Path 大小写、文件是否真的存在。<br>3. 不要手改出非法类型；用 ProperTree 编辑。<br>4. 对照同版本 `Sample.plist` 补缺失键。<br>5. 改到 0 错误再重启。 |

---

## 9. 已验证（静态）/ 待实机确认

### 9.1 已验证（静态）

这些是**在构建机上**能确认的、不依赖目标机硬件的项目：

- [x] `README.md` 的关键字、章节和关键操作由 `python scripts/test_readme.py` 检查，全部通过。
- [x] `EFI/` 目录结构完整；`config.plist` 引用的 ACPI / kext / driver 路径均存在（构建脚本检查）。
- [x] `config.plist` 可被 plist 解析器解析，`ocvalidate` 校验 0 错误（结果记录在 `docs/verification.md`）。
- [x] 组件版本与 SHA256 记录在 `SOURCES.md`；kext 顺序为 Lilu → VirtualSMC → SMCProcessor → SMCSuperIO → WhateverGreen → AppleALC → IntelMausi → NVMeFix。
- [x] boot-args、SMBIOS（iMac19,1）、无头核显 `AAPL,ig-platform-id=0300913E` 已按设计写入 `config.plist`。
- [x] 未安装 Broadcom 相关 kext；未随包提供 USBMap（装后用 USBToolBox 生成）；未使用 OpenCanopy 主题。

### 9.2 待实机确认

以下全部**没有在目标实机上验证**，需要用户按本文操作后确认：

- [ ] 能从 U 盘启动 OpenCore 并进入 Ventura 安装器。
- [ ] 安装过程能完成，多次重启后进入桌面。
- [ ] RX 5500 正常驱动、无黑屏、有硬件加速。
- [ ] UHD 630 以无头方式参与 VideoToolbox/硬件加速。
- [ ] ALC892 在 `alcid=1` 下有声音（否则按 5.2 试其他 layout）。
- [ ] Intel I219-V 被识别为 `en0`，有线网络正常。
- [ ] BCM943602CS 的 Wi-Fi 与蓝牙正常（尤其是 USB 映射之后）。
- [ ] 睡眠/唤醒正常，NVRAM 能持久化。
- [ ] USB 映射后所有物理端口可用。
- [ ] BIOS 选项名称/位置与实际版本一致；实际安装步骤无遗漏。
- [ ] 序列号唯一且未注册；ROM 已替换为真实 MAC；iServices 可登录。

> 再次说明：本 README **未在目标实机上验证**动态结果，也没有声称「已测试可用」。遇到与本文不一致的地方，以实机现象和 OpenCore 日志为准，并先备份 EFI。

---

## 10. 附录：本 EFI 的关键配置

| 项目 | 值 |
|---|---|
| OpenCore | 1.0.8 RELEASE |
| SMBIOS | iMac19,1 |
| boot-args | `-v keepsyms=1 debug=0x100 agdpmod=pikera alcid=1` |
| 无头核显 | `PciRoot(0x0)/Pci(0x2,0x0)` → `AAPL,ig-platform-id=0300913E` |
| 音频 | AppleALC，先 `alcid=1`（ALC892 假设） |
| 有线网卡 | IntelMausi（I219-V） |
| 无线/蓝牙 | BCM943602CS 原生，无额外 Broadcom kext |
| USB | 不随包提供 USBMap；装后用 USBToolBox 映射 |
| kext 顺序 | Lilu → VirtualSMC → SMCProcessor → SMCSuperIO → WhateverGreen → AppleALC → IntelMausi → NVMeFix |
| SIP | `csr-active-config=00000000`（开启） |
| 主题 | 无 OpenCanopy，默认文本选择器 |

- 组件版本、下载地址、SHA256、许可证见 `SOURCES.md`。
- 构建/校验记录见 `docs/verification.md`。
- 如果 `config.plist` 被改坏，优先用备份恢复；不要从网上抄别人的 config 片段。

---

**最后提醒**：黑苹果没有「保证成功」。本 EFI 的目标是让这套常见硬件有一个干净、可解释、可回滚的起点；请按顺序操作、每一步核对、出问题先备份再改。