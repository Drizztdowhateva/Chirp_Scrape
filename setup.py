from setuptools import setup
from pathlib import Path

here = Path(__file__).parent
reqs = here / 'requirements.txt'
install_requires = []
if reqs.exists():
    install_requires = [r.strip() for r in reqs.read_text().splitlines() if r.strip() and not r.strip().startswith('#')]

setup(
    name='FreqFinder',
    version='0.1.0',
    description='RadioReference FreqFinder scraper',
    author='Tim Rohe',
    py_modules=['freqfinder', 'make_radioref_list'],
    include_package_data=True,
    package_data={'': ['media/*']},
    install_requires=install_requires,
    entry_points={
        'console_scripts': [
            'freqfinder=freqfinder:main',
        ],
    },
)
