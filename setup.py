#!/usr/bin/env python

from __future__ import unicode_literals
from distutils.core import setup
import setuptools

setup(name='rpi_epd3in7',
      version='0.0.1',
      description='Library for using the Waveshare 3.7inch Waveshare e-Paper HAT with the Raspberry Pi',
      author='Chris Twomey',
      author_email='chrisjg.twomey@gmail.com',
      url='https://github.com/chrisjtwomey/rpi-epd3in7',
      classifiers=[
            "Programming Language :: Python :: 3",
            "License :: OSI Approved :: MIT License",
            "Operating System :: OS Independent",
      ],
      package_dir={"": "src"},
      packages=setuptools.find_packages(where="src"),
      python_requires=">=3.6",
)
