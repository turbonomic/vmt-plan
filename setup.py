#!/usr/bin/python3

import os
from setuptools import setup, find_packages



here = os.path.abspath(os.path.dirname(__file__))

about = {}
with open(os.path.join(here, 'vmtplanner', '__about__.py'), 'r') as fp:
    exec(fp.read(), about)

with open(os.path.join(here, 'README.md'), 'r') as fp:
    readme = fp.read()

requires = [
    'vmtconnect>=3.2.3',
    'umsg>=1.0.2'
]

setup(
    name=about['__title__'],
    version=about['__version__'],
    description=about['__description__'],
    long_description=readme,
    long_description_content_type='text/markdown',
    author=about['__author__'],
    author_email=about['__author_email__'],
    url='https://github.com/turbonomic/vmt-plan',
    classifiers=[
        'Intended Audience :: Developers',
        'License :: OSI Approved :: Apache Software License',
        'Operating System :: OS Independent',
        'Programming Language :: Python :: 3',
        'Topic :: Software Development',
    ],
    packages=find_packages(),
    package_data={'': ['LICENSE', 'NOTICE']},
    include_package_data=True,
    python_requires=">=3.5",
    install_requires=requires,
    license=about['__license__'],
    zip_safe=False,
)
