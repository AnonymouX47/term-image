import os
import sys

from setuptools import find_packages, setup

# To locate the package since `setuptools.build_meta` modifies `sys.path`
sys.path.append(os.getcwd())

from term_img import __version__  # noqa: E402

classifiers = [
    "Development Status :: 3 - Alpha",
    "Environment :: Console",
    "License :: OSI Approved :: MIT License",
    "Intended Audience :: Developers",
    "Intended Audience :: End Users/Desktop",
    "Operating System :: POSIX :: Linux",
    "Operating System :: MacOS",
    "Operating System :: Android",
    "Operating System :: Microsoft :: Windows :: Windows 10",
    "Programming Language :: Python :: 3",
    "Programming Language :: Python :: 3.6",
    "Programming Language :: Python :: 3.7",
    "Programming Language :: Python :: 3.8",
    "Programming Language :: Python :: 3.9",
    "Programming Language :: Python :: 3.10",
    "Topic :: Software Development :: Libraries",
    "Topic :: Utilities",
    "Topic :: Multimedia :: Graphics :: Viewers",
]

with open("README.md", "r") as fp:
    long_description = fp.read()

setup(
    name="term-image",
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
    install_requires=["pillow>=9.1,<10.0", "requests>=2.23,<3.0", "urwid>=2.1,<3.0"],
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
        "ANSI",
        "ASCII-Art",
    ],
)
