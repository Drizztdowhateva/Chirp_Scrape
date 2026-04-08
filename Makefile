venv:
	python3 -m venv .venv

install: venv
	. .venv/bin/activate && pip install -r requirements.txt

bootstrap:
	python3 freqfinder.py --help

run:
	. .venv/bin/activate && .venv/bin/python freqfinder.py

run-gui:
	. .venv/bin/activate && .venv/bin/python freqfinder.py --gui

sdist:
	python3 -m build --sdist
