import glob
import os
import shutil
import sys

DLL_PATTERNS = ("tcl*.dll", "tk*.dll", "*tk*.dll", "zlib*.dll", "libtommath*.dll")


def main() -> int:
    dest = os.path.abspath(sys.argv[1])
    try:
        import _tkinter
        import tkinter
    except ImportError:
        print("В установленном Python нет tkinter. Переустановите Python с компонентом tcl/tk.")
        return 1

    dll_dir = os.path.dirname(_tkinter.__file__)
    files = {_tkinter.__file__}
    for pattern in DLL_PATTERNS:
        files.update(glob.glob(os.path.join(dll_dir, pattern)))
    for path in sorted(files):
        shutil.copy2(path, dest)
        print("  +", os.path.basename(path))

    pkg_src = os.path.dirname(tkinter.__file__)
    pkg_dst = os.path.join(dest, "Lib", "tkinter")
    shutil.copytree(pkg_src, pkg_dst, dirs_exist_ok=True,
                    ignore=shutil.ignore_patterns("__pycache__", "test", "tests"))
    print("  + Lib\\tkinter")

    root = tkinter.Tk()
    root.withdraw()
    libs = {
        "tcl" + root.tk.eval("info tclversion"): root.tk.eval("info library"),
        "tk" + root.tk.eval("set tk_version"): root.tk.eval("set tk_library"),
    }
    root.destroy()
    for name, src in libs.items():
        if src.startswith("//zipfs:"):
            print(f"  = {name}: встроена в DLL")
            continue
        shutil.copytree(os.path.normpath(src), os.path.join(dest, "tcl", name), dirs_exist_ok=True)
        print(f"  + tcl\\{name}  (из {src})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
