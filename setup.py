#! /usr/bin/env python

import os
import sys

from setuptools import setup, find_packages

import jira_cli

if sys.argv[-1] == 'publish':
    os.system('python setup.py sdist upload')
    sys.exit()

REQUIRES = [
    open('requirements.txt').read()
]

setup(
    name='jira_cli',
    version=jira_cli.__version__,
    description='Jira CLI automation tool',
    long_description=open('README.md').read(),
    author='Matt Black',
    author_email='dev@mafro.net',
    url='http://github.com/mafrosis/jira-cli',
    packages=find_packages(exclude=['test']),
    package_data={'': ['LICENSE']},
    package_dir={'': '.'},
    include_package_data=True,
    install_requires=REQUIRES,
    license=open('LICENSE').read(),
    entry_points={
        'console_scripts': [
            'jira=jira_cli.main:cli'
        ]
    },
    classifiers=(
        'Development Status :: 3 - Alpha',
        'Environment :: Console',
        'Intended Audience :: Developers',
        'Intended Audience :: System Administrators',
        'Natural Language :: English',
        'License :: OSI Approved :: BSD License',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3.7',
    ),
)
