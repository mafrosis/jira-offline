#! /usr/bin/env python

from setuptools import setup, find_packages

import jira_offline

with open('README.md') as f:
    long_description = f.read()

with open('requirements.txt') as f:
    install_requires = f.readlines()

setup(
    name='jira-offline',
    version=jira_offline.__version__,
    description='CLI for using Jira offline',
    long_description_content_type='text/markdown',
    long_description=long_description,
    author='Matt Black',
    author_email='dev@mafro.net',
    url='http://github.com/mafrosis/jira-offline',
    packages=find_packages(exclude=['test']),
    package_data={'': ['LICENSE']},
    package_dir={'': '.'},
    include_package_data=True,
    install_requires=install_requires,
    license='MIT License',
    entry_points={
        'console_scripts': [
            'jira=jira_offline.cli:cli'
        ]
    },
    classifiers=[
        'Development Status :: 5 - Production/Stable',
        'Environment :: Console',
        'Intended Audience :: Developers',
        'Intended Audience :: System Administrators',
        'Natural Language :: English',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
    ],
)
