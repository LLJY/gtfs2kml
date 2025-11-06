"""
Setup configuration for gtfs2kml package.
"""

from setuptools import setup, find_packages
from pathlib import Path

# Read README for long description
readme_file = Path(__file__).parent / "README.md"
long_description = ""
if readme_file.exists():
    long_description = readme_file.read_text(encoding='utf-8')

setup(
    name="gtfs2kml",
    version="0.1.0",
    author="GTFS2KML Contributors",
    description="Convert GTFS transit feeds to KML format for visualization",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/yourusername/gtfs2kml",
    package_dir={"": "src"},
    packages=find_packages(where="src"),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Topic :: Scientific/Engineering :: GIS",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
    ],
    python_requires=">=3.8",
    install_requires=[
        "click>=8.0.0",
        "simplekml>=1.3.6",
    ],
    entry_points={
        "console_scripts": [
            "gtfs2kml=gtfs2kml.cli:main",
        ],
    },
    keywords="gtfs kml transit gis visualization mapping",
    project_urls={
        "Bug Reports": "https://github.com/yourusername/gtfs2kml/issues",
        "Source": "https://github.com/yourusername/gtfs2kml",
    },
)
