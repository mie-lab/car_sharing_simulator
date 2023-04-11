"""Package installer."""
import os
from setuptools import setup
from setuptools import find_packages

LONG_DESCRIPTION = ""
if os.path.exists("README.md"):
    with open("README.md") as fp:
        LONG_DESCRIPTION = fp.read()

scripts = []

setup(
    name="carsharing",
    version="0.0.1",
    description="agent-based car sharing simulator",
    long_description=LONG_DESCRIPTION,
    long_description_content_type="text/markdown",
    author="MIE Lab",
    author_email=("nwiedemann@ethz.ch"),
    license="GPLv3",
    url="https://github.com/mie-lab/car_sharing_simulator/",
    install_requires=["numpy", "scipy", "pandas", "geopandas"],
    classifiers=[
        "License :: OSI Approved :: MIT License",
        "Intended Audience :: Science/Research",
        "Programming Language :: Python :: 3.8",
        "Topic :: Software Development :: Libraries :: Python Modules",
    ],
    packages=find_packages("."),
    python_requires=">=3.8",
)
