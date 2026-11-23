"""README.md 静态检查：关键字、章节与关键操作是否齐全。

用法：python scripts/test_readme.py
任何一项失败都会打印 FAIL 并以退出码 1 结束。
"""
import sys
from pathlib import Path

# 保证在重定向/CI 下中文输出不因代码页变成乱码
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parents[1]
README = ROOT / "README.md"

fails = 0


def check(name, cond):
    global fails
    print(("OK   " if cond else "FAIL ") + name)
    if not cond:
        fails += 1


text = README.read_text(encoding="utf-8") if README.is_file() else ""
check("README.md 存在", README.is_file())

headings = [line.strip() for line in text.splitlines() if line.startswith("#")]


def has_heading(fragment):
    return any(fragment in h for h in headings)


# 任务书要求的最小关键字集合
KEYWORDS = [
    "Ventura",
    "断开",
    "容量",
    "Internal",
    "agdpmod=pikera",
    "alcid=1",
    "iMac19,1",
    "USBToolBox",
    "getmac",
    "BIOS",
    "ocvalidate",
    "AWAC",
    "SSDT-RTC0",
    "git 历史",
]
for kw in KEYWORDS:
    check(f"README 含 {kw}", kw in text)

# §5.7 的 8 个内容块（加验证清单）
SECTIONS = [
    "硬件清单",
    "BIOS 设置",
    "制作安装 U 盘",
    "安装 macOS",
    "装好之后",
    "NVMe",
    "升级",
    "排错",
    "待实机确认",
]
for sec in SECTIONS:
    check(f"README 有章节：{sec}", has_heading(sec))

# 关键操作/事实逐条覆盖
CONTENT = [
    ("物理断开或 BIOS 禁用 Windows 盘", "物理断开"),
    ("抹盘前核对容量", "容量"),
    ("抹盘前核对型号", "型号"),
    ("EFI 放 macOS 盘自己的 ESP", "ESP"),
    ("USB 映射时插着蓝牙线", "蓝牙"),
    ("内部口标记 Internal", "Internal"),
    ("三星 PM981 提醒", "PM981"),
    ("三星 PM991 提醒", "PM991"),
    ("三星 PM9A1 提醒", "PM9A1"),
    ("有 Mac 路径 createinstallmedia", "createinstallmedia"),
    ("只有 Windows 路径 gibMacOS", "gibMacOS"),
    ("BIOS 关 CSM", "CSM"),
    ("BIOS 关 Secure Boot", "Secure Boot"),
    ("BIOS 关 Fast Boot", "Fast Boot"),
    ("BIOS 关 VT-d", "VT-d"),
    ("BIOS 开 Above 4G", "Above 4G"),
    ("BIOS 开 XHCI Hand-off", "XHCI Hand-off"),
    ("SATA 设 AHCI", "AHCI"),
    ("核显 DVMT 64MB", "DVMT"),
    ("Windows 8/10 Features 设 Other OS", "Other OS"),
    ("iServices 依赖 en0", "en0"),
    ("真实 MAC 作 ROM", "ROM"),
    ("完整 boot-args", "-v keepsyms=1 debug=0x100 agdpmod=pikera alcid=1"),
    ("UHD 630 无头 ig-platform-id", "0300913E"),
    ("OpenCore 版本", "1.0.8"),
    ("有静态验证清单", "静态"),
    ("明确未在目标实机测试", "未在目标实机"),
]
for name, kw in CONTENT:
    check(f"README 内容：{name}", kw in text)

print(f"\n{len(KEYWORDS) + len(SECTIONS) + len(CONTENT) + 1} 项检查，{fails} 项失败")
sys.exit(1 if fails else 0)