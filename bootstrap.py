#!/usr/bin/env python3
"""Unified runtime helper: install, run, test, and security-check FreqFinder.

Usage:
    python3 bootstrap.py [command] [--gui|--cli]

Commands:
    run        Install deps and launch app (default)
    install    Install deps only
    test       Run quick project tests/smoke checks
    security   Run lightweight security scan
    package    Build one-time distributable for current OS
    all        install + security + test + run

This script attempts to be cross-platform (Windows and POSIX).
"""
import os
import sys
import subprocess
import shutil
import pathlib

HERE = os.path.dirname(os.path.abspath(__file__))
VENV_DIR = os.path.join(HERE, '.venv')
REQS = os.path.join(HERE, 'requirements.txt')


def run(cmd, **kw):
    print('> ' + ' '.join(cmd))
    subprocess.check_call(cmd, **kw)


def ensure_venv():
    if os.name == 'nt':
        py = os.path.join(VENV_DIR, 'Scripts', 'python.exe')
    else:
        py = os.path.join(VENV_DIR, 'bin', 'python')
    if not os.path.exists(py):
        print('Creating virtual environment...')
        run([sys.executable, '-m', 'venv', VENV_DIR])
    # Repair an existing broken venv that lacks pip.
    try:
        subprocess.check_call([py, '-m', 'pip', '--version'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        print('Detected broken venv (missing pip). Recreating...')
        if os.path.isdir(VENV_DIR):
            shutil.rmtree(VENV_DIR, ignore_errors=True)
        run([sys.executable, '-m', 'venv', VENV_DIR])
    return py


def install_requirements(python_exe):
    print('Installing requirements...')
    if os.path.exists(REQS):
        run([python_exe, '-m', 'pip', 'install', '-r', REQS])
    else:
        run([python_exe, '-m', 'pip', 'install', 'requests', 'pandas', 'beautifulsoup4'])


def run_tests(python_exe):
    """Run fast, dependency-light checks."""
    print('Running syntax checks...')
    run([
        python_exe,
        '-m',
        'py_compile',
        os.path.join(HERE, 'bootstrap.py'),
        os.path.join(HERE, 'chirp_scraper.py'),
        os.path.join(HERE, 'rr_api.py'),
    ])

    print('Running unittest discovery...')
    proc = subprocess.run([python_exe, '-m', 'unittest', 'discover'], check=False)
    if proc.returncode == 5:
        print('No unit tests found. Treating as pass for smoke test.')
    elif proc.returncode != 0:
        raise subprocess.CalledProcessError(proc.returncode, [python_exe, '-m', 'unittest', 'discover'])


def run_security_scan():
    """Run a lightweight static scan for risky patterns."""
    print('Running lightweight security scan...')
    include_suffixes = {'.py', '.md', '.json', '.html', '.cfg', '.txt', '.yml', '.yaml', '.ini'}
    excluded_dirs = {'.venv', '__pycache__', '.git'}
    patterns = [
        ('eval(', 'dynamic execution via eval'),
        ('exec(', 'dynamic execution via exec'),
        ('shell=True', 'shell execution in subprocess'),
        ('os.system(', 'shell command execution'),
        ('pickle.loads', 'unsafe deserialization risk'),
        ('yaml.load(', 'unsafe YAML loader risk'),
    ]

    findings = []
    root = pathlib.Path(HERE)
    for path in root.rglob('*'):
        if not path.is_file():
            continue
        if any(part in excluded_dirs for part in path.parts):
            continue
        if path.suffix.lower() not in include_suffixes:
            continue
        # Avoid self-matching from this script's token list.
        if path.name == 'bootstrap.py':
            continue
        try:
            text = path.read_text(encoding='utf-8', errors='ignore')
        except Exception:
            continue
        lines = text.splitlines()
        for i, line in enumerate(lines, start=1):
            for token, reason in patterns:
                if token in line:
                    findings.append((path, i, token, reason))

    if not findings:
        print('Security scan: no risky patterns found.')
        return

    print('Security scan findings:')
    for pth, line_no, token, reason in findings:
        rel = os.path.relpath(str(pth), HERE)
        print(f'  - {rel}:{line_no} [{token}] {reason}')


def launch_app(python_exe, gui=True, extra=None):
    extra = extra or []
    cmd = [python_exe, os.path.join(HERE, 'chirp_scraper.py')]
    if gui:
        cmd.append('--gui')
    if extra:
        cmd.extend(extra)
    print('Launching app...')
    os.execv(cmd[0], cmd)


def _python_has_tkinter(python_exe):
    """Return True when tkinter is importable in the target runtime."""
    check = subprocess.run([python_exe, '-c', 'import tkinter'], check=False)
    return check.returncode == 0


def ensure_gui_dependency(python_exe):
    """Best-effort runtime installer/check for GUI dependency (tkinter)."""
    if _python_has_tkinter(python_exe):
        return True

    print('GUI dependency missing: tkinter not found. Attempting runtime install...')

    if os.name == 'nt':
        print('Windows: reinstall Python with Tcl/Tk enabled, then rerun.')
        return False
    if sys.platform == 'darwin':
        print('macOS: use python.org installer (includes Tk) or install python-tk via your package manager.')
        return False

    # Linux: try apt-based install without interactive password prompt.
    apt_bin = shutil.which('apt-get') or shutil.which('apt')
    if not apt_bin:
        print('Linux: no apt/apt-get found; install tkinter package manually (python3-tk).')
        return False

    py_ver_pkg = f'python{sys.version_info.major}.{sys.version_info.minor}-tk'
    candidates = [py_ver_pkg, 'python3-tk']

    if hasattr(os, 'geteuid') and os.geteuid() == 0:
        prefix = []
    elif shutil.which('sudo'):
        prefix = ['sudo', '-n']
    else:
        prefix = []

    for pkg in candidates:
        cmd = prefix + [apt_bin, 'install', '-y', pkg]
        print('> ' + ' '.join(cmd))
        proc = subprocess.run(cmd, check=False)
        if proc.returncode == 0 and _python_has_tkinter(python_exe):
            print(f'Installed GUI dependency: {pkg}')
            return True

    print('Could not auto-install tkinter. Try: sudo apt install python3-tk')
    return False


def package_current_platform():
    """Build distributable artifact for the current platform via scripts/."""
    if os.name == 'nt':
        script = os.path.join(HERE, 'scripts', 'build_windows_exe.ps1')
        if not os.path.exists(script):
            raise FileNotFoundError(script)
        run(['powershell', '-ExecutionPolicy', 'Bypass', '-File', script])
        return

    if sys.platform == 'darwin':
        script = os.path.join(HERE, 'scripts', 'build_macos_app_dmg.sh')
    else:
        script = os.path.join(HERE, 'scripts', 'build_linux_onefile.sh')

    if not os.path.exists(script):
        raise FileNotFoundError(script)
    run(['chmod', '+x', script])
    run([script])


def main():
    import argparse
    p = argparse.ArgumentParser(
        description='Unified FreqFinder runtime/packaging helper',
        epilog=(
            'Examples:\n'
            '  python3 bootstrap.py run\n'
            '  python3 bootstrap.py run -- --help\n'
            '  python3 bootstrap.py run --cli\n'
            '  python3 bootstrap.py package'
        ),
        formatter_class=argparse.RawTextHelpFormatter,
    )
    p.add_argument('command', nargs='?', default='run',
                   choices=['run', 'install', 'test', 'security', 'package', 'all'],
                   help='Runtime command to execute (default: run)')
    p.add_argument('--gui', action='store_true', help='Force GUI mode for run/all (default behavior)')
    p.add_argument('--cli', action='store_true', help='Force CLI mode for run/all')
    p.add_argument('--install-only', action='store_true', help='Install only, do not run the app (legacy)')
    p.add_argument('--test', action='store_true', help='Run tests only (legacy)')
    p.add_argument('--security-check', action='store_true', help='Run security check only (legacy)')
    args, extra = p.parse_known_args()

    # Legacy flag compatibility
    command = args.command
    if args.install_only:
        command = 'install'
    elif args.test:
        command = 'test'
    elif args.security_check:
        command = 'security'

    py = ensure_venv()
    install_requirements(py)

    # Ensure a canonical screenshot filename is present for README and media references.
    try:
        src = os.path.join(HERE, 'media', '26Feb_16_ChirpScrape.png')
        dst = os.path.join(HERE, 'media', 'ChirpScrape_screenshot.png')
        if os.path.exists(src) and not os.path.exists(dst):
            try:
                shutil.copy2(src, dst)
                print(f'Created canonical screenshot: {dst}')
            except Exception:
                pass
    except Exception:
        pass

    if command == 'install':
        print('Installation complete.')
        return

    if command == 'security':
        run_security_scan()
        return

    if command == 'package':
        package_current_platform()
        print('Packaging complete.')
        return

    if command == 'test':
        run_tests(py)
        print('Tests complete.')
        return

    if command == 'all':
        run_security_scan()
        run_tests(py)
        run_with_gui = False if args.cli else True
        if run_with_gui:
            ensure_gui_dependency(py)
        launch_app(py, gui=run_with_gui, extra=extra)
        return

    run_with_gui = False if args.cli else True
    if run_with_gui:
        ensure_gui_dependency(py)
    launch_app(py, gui=run_with_gui, extra=extra)


if __name__ == '__main__':
    main()
