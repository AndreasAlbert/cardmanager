from setuptools import setup, find_packages

with open('requirements.txt') as f:
    requirements = f.read().splitlines()

setup(
    name = 'cardmanager',
    version = '0.0.1',
    url = 'https://github.com/AndreasAlbert/cardmanager',
    author = 'Andreas Albert',
    author_email = 'andreas.albert@cern.ch',
    description = 'Sane tool for editing combine cards',
    packages = find_packages(),    
    install_requires = requirements,
    scripts=["./scripts/cardmanage"],
)
