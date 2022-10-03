#!/usr/bin/env python

from setuptools import setup

with open('README.md') as f:
      long_description = f.read()

setup(name='pipelinewise-tap-oracle',
      version='1.2.2',
      description='Singer.io tap for extracting data from Oracle - PipelineWise compatible',
      long_description=long_description,
      long_description_content_type='text/markdown',
      author='Stitch',
      url='https://github.com/transferwise/pipelinewise-tap-oracle',
      classifiers=[
          'License :: OSI Approved :: GNU Affero General Public License v3',
          'Programming Language :: Python :: 3 :: Only'
      ],
      install_requires=[
          'pipelinewise-singer-python @ git+https://github.com/mjsqu/pipelinewise-singer-python',
          'cx_Oracle==8.3',
          'strict-rfc3339==0.7'
      ],
      entry_points='''
          [console_scripts]
          tap-oracle=tap_oracle:main
      ''',
      packages=['tap_oracle', 'tap_oracle.sync_strategies']

)
