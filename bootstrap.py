#!/usr/bin/env python3
"""Bootstrap helper: create virtualenv, install requirements, and run chirp_scraper.py.

Usage:
  python3 bootstrap.py [--gui] [--install-only]

This script attempts to be cross-platform (Windows and POSIX).
"""
import os
import sys
import subprocess
import shutil

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
    return py


def install_requirements(python_exe):
    print('Upgrading pip and installing requirements...')
    run([python_exe, '-m', 'pip', 'install', '--upgrade', 'pip'])
    if os.path.exists(REQS):
        run([python_exe, '-m', 'pip', 'install', '-r', REQS])
    else:
        run([python_exe, '-m', 'pip', 'install', 'requests', 'pandas', 'beautifulsoup4'])


def main():
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument('--gui', action='store_true', help='Launch GUI after bootstrap')
    p.add_argument('--install-only', action='store_true', help='Install only, do not run the app')
    args, extra = p.parse_known_args()

    py = ensure_venv()
    install_requirements(py)

    if args.install_only:
        print('Installation complete.')
        return

    cmd = [py, os.path.join(HERE, 'chirp_scraper.py')]
    if args.gui:
        cmd.append('--gui')
    if extra:
        cmd.extend(extra)
    print('Launching app...')
    os.execv(cmd[0], cmd)


if __name__ == '__main__':
    main()
