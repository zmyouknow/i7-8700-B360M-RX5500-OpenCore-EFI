"""校验 SOURCES.md：组件、版本、SHA256、许可证、ACPI 来源与三码声明。"""
import re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "SOURCES.md"
fails = 0

def check(name, cond):
    global fails
    print(("OK   " if cond else "FAIL ") + name)
    if not cond:
        fails += 1

# 组件名 -> 固定版本
COMPONENTS = {
    "OpenCorePkg": "1.0.8",
    "Lilu": "1.7.2",
    "VirtualSMC": "1.3.8",
    "WhateverGreen": "1.7.1",
    "AppleALC": "1.9.8",
    "IntelMausi": "1.0.8",
    "NVMeFix": "1.1.3",
}
SHA256 = re.compile(r"^[0-9a-f]{64}$")
HEADER = ["组件", "版本", "下载 URL", "SHA256", "许可证", "备注"]

exists = SRC.is_file()
check("SOURCES.md 存在", exists)
text = SRC.read_text(encoding="utf-8") if exists else ""

# 解析 markdown 表格行：首格 -> 单元格列表
rows = {}
header = None
for line in text.splitlines():
    line = line.strip()
    if not line.startswith("|"):
        continue
    cells = [c.strip() for c in line.strip("|").split("|")]
    if not cells:
        continue
    if header is None and cells[:2] == HEADER[:2]:
        header = cells
        continue
    key = cells[0]
    if set(key) <= set("-: "):      # 分隔行
        continue
    rows.setdefault(key, cells)

check("表格表头为 组件|版本|下载 URL|SHA256|许可证|备注",
      header is not None and header[:6] == HEADER)

for name, version in COMPONENTS.items():
    row = rows.get(name, [])
    check(f"SOURCES 含组件 {name}", name in text)
    check(f"{name} 行版本为 {version}", len(row) > 1 and version in row[1])
    check(f"{name} 行含 64 位 SHA256",
          any(SHA256.match(c) for c in row))
    check(f"{name} 行含 acidanthera 仓库 URL",
          any("github.com/acidanthera/" in c for c in row))
    check(f"{name} 行许可证非空且非占位",
          len(row) > 4 and row[4] not in ("", "?", "-", "TODO"))

acpi = rows.get("ACPI（SSDT）", [])
check("含 ACPI 行并注明 OpenCore release 的 Docs/AcpiSamples/Binaries/",
      len(acpi) > 0 and "Docs/AcpiSamples/Binaries/" in " | ".join(acpi))

check("声明 config.plist 三码文件不列入清单、不要外传",
      "config.plist" in text and "三码" in text and
      ("不要" in text or "不得" in text))
check("含复现/升级说明（重新校验 SHA256、升级 kext）",
      "SHA256" in text and "升级" in text and
      ("releases/tags" in text or "api.github.com" in text))

sys.exit(1 if fails else 0)