# PyInstaller build spec.
#
#   pyinstaller packaging/schedule-picker.spec
#
# ONEFILE is off by default: a single .exe on Windows reliably trips antivirus
# heuristics, and the people running this are classmates who will not know to
# whitelist it. A zipped folder is the safer default there. Set
# SCHEDULE_PICKER_ONEFILE=1 for the single-file build (fine on Linux).
#
# --collect-all textual is not optional: Textual loads its .tcss stylesheets at
# runtime from inside the package, and a plain import scan does not find them.

import os

from PyInstaller.utils.hooks import collect_all

ONEFILE = os.environ.get("SCHEDULE_PICKER_ONEFILE") == "1"

datas, binaries, hiddenimports = collect_all("textual")

# Ship the known exports so the binary is useful on its own.
datas += [("../data", "data")]

a = Analysis(
    ["entry.py"],
    pathex=["../src"],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports + ["schedule_picker"],
    hookspath=[],
    runtime_hooks=[],
    excludes=["tkinter", "unittest", "pydoc_data", "pytest"],
    noarchive=False,
)

pyz = PYZ(a.pure)

if ONEFILE:
    exe = EXE(
        pyz,
        a.scripts,
        a.binaries,
        a.datas,
        [],
        name="schedule-picker",
        console=True,
        upx=False,
        strip=False,
    )
else:
    exe = EXE(
        pyz,
        a.scripts,
        [],
        exclude_binaries=True,
        name="schedule-picker",
        console=True,
        upx=False,
        strip=False,
    )
    coll = COLLECT(
        exe,
        a.binaries,
        a.datas,
        name="schedule-picker",
        upx=False,
        strip=False,
    )
