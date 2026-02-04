venv:
	python3 -m venv .venv

install: venv
	. .venv/bin/activate && pip install -r requirements.txt

bootstrap:
	python3 chirp_scraper.py --help

run:
	. .venv/bin/activate && .venv/bin/python chirp_scraper.py

run-gui:
	. .venv/bin/activate && .venv/bin/python chirp_scraper.py --gui

sdist:
	python3 -m build --sdist
