import os
from setuptools import setup

STATIC_JS_FILES = [
    "dataclean/static/main.js",
    "dataclean/static/jquery.tablesorter.min.js",
    "dataclean/static/iosbadge.js",
    "dataclean/static/main.css",
]


def read_long_description():
    with open(os.path.join(os.path.dirname(__file__), "README.rst")) as fp:
        return fp.read()


setup(
    name="sherlockml-dataclean",
    version="0.2.2",
    url="https://github.com/ASIDataScience/sherlockml-dataclean",
    author="ASI Data Science",
    author_email="opensource@asidatascience.com",
    description="Interactive cleaning for pandas DataFrames",
    license="Apache 2.0",
    long_description=read_long_description(),
    data_files=[("share/jupyter/nbextensions/sherlockml-dataclean", STATIC_JS_FILES)],
    packages=["dataclean"],
    install_requires=[
        "future",
        "ipython",
        "ipywidgets>=7.0.0",
        "matplotlib",
        "numpy",
        "pandas",
        "scikit-learn",
        "scipy",
        "sherlockml-boltzmannclean",
        'funcsigs;python_version<"3.0"',
    ],
)
