import os
import sys

from setuptools import find_packages, setup

sys.path.append(os.getcwd())

from term_img import __version__  # noqa: E402

classifiers = [
    "Development Status :: 5 - Production/Stable",
    "Programming Language :: Python :: 3",
    "Programming Language :: Python :: 3.6",
    "Programming Language :: Python :: 3.7",
    "Programming Language :: Python :: 3.8",
    "Programming Language :: Python :: 3.9",
    "Programming Language :: Python :: 3.10",
    "Intended Audience :: Developers",
    "License :: OSI Approved :: MIT License",
    "Topic :: Software Development :: Libraries",
    "Topic :: Utilities",
    "Topic :: Scientific/Engineering :: Image Processing",
]

with open("README.md", "r") as fp:
    long_description = fp.read()

setup(
    name="term-img",
    version=__version__,
    author="Anonymoux47",
    author_email="anonymoux47@gmail.com",
    url="https://github.com/AnonymouX47/term-img",
    description="Display images in the terminal",
    long_description=long_description,
    long_description_content_type="text/markdown",
    packages=find_packages(where=".", include=["term_img*"]),
    license="MIT",
    classifiers=classifiers,
    python_requires=">=3.6",
    install_requires=["pillow>=8.3", "requests>=2.23", "urwid>=2.1"],
    entry_points={
        "console_scripts": ["term-img=term_img.__main__:main"],
    },
    keywords=[
        "image",
        "terminal",
        "viewer",
        "PIL",
        "Pillow",
        "console",
        "xterm",
        "library",
        "cli",
        "tui",
    ],
)
