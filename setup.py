# -*- coding: utf-8 -*-

# Learn more: https://github.com/kennethreitz/setup.py

from setuptools import setup, find_packages


with open('README.rst') as f:
    readme = f.read()

with open('LICENSE') as f:
    license = f.read()

setup(
    name='ewfwizard',
    version='0.1.0',
    description='Simple wizard for ewfadquire',
    long_description=readme,
    author='Jorge Martin',
    url='https://github.com/jmartinc89/ewfwizard',
    license=license,
    packages=find_packages(exclude=('tests', 'docs'))
)
