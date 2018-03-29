from setuptools import setup
import os

def read(fname):
    return open(os.path.join(os.path.dirname(__file__), fname)).read()

static_js_files = [
    'dataclean/static/main.js',
    'dataclean/static/jquery.tablesorter.min.js',
    'dataclean/static/iosbadge.js',
    'dataclean/static/main.css',
]

setup(
    name='sherlockml-dataclean',
    version='0.2.2',
    url='https://sherlockml.com',
    author='ASI Data Science',
    author_email='engineering@asidatascience.com',
    description='Interactive cleaning for pandas DataFrames',
    license='Apache 2.0',
    long_description=read('README.rst'),
    data_files=[
        ('share/jupyter/nbextensions/sherlockml-dataclean', static_js_files)
    ],
    packages=['dataclean'],
    install_requires=[
        'pandas',
        'numpy',
        'matplotlib',
        'ipywidgets>=7.0.0',
        'funcsigs;python_version<"3.0"',
        'scipy',
        'scikit-learn',
        'ipython',
        'future',
        'sherlockml-boltzmannclean'
    ]
)
