from setuptools import setup

classifiers = [
    "Environment :: Console",
    "License :: OSI Approved :: MIT License",
    "Intended Audience :: Developers",
    "Operating System :: POSIX :: Linux",
    "Operating System :: MacOS",
    "Operating System :: Android",
    "Operating System :: Microsoft :: Windows",
    "Programming Language :: Python :: 3",
    "Programming Language :: Python :: 3.7",
    "Programming Language :: Python :: 3.8",
    "Programming Language :: Python :: 3.9",
    "Programming Language :: Python :: 3.10",
    "Programming Language :: Python :: 3.11",
    "Programming Language :: Python :: 3 :: Only",
    "Topic :: Software Development :: Libraries",
    "Topic :: Terminals :: Terminal Emulators/X Terminals",
    "Topic :: Multimedia :: Graphics :: Viewers",
]

with open("README.md", "r") as fp:
    long_description = fp.read()

setup(
    name="term-image",
    version="0.6.2",
    author="Toluwaleke Ogundipe",
    author_email="anonymoux47@gmail.com",
    url="https://github.com/AnonymouX47/term-image",
    description="Display images in the terminal",
    long_description=long_description,
    long_description_content_type="text/markdown",
    license="MIT",
    classifiers=classifiers,
    python_requires=">=3.7",
    install_requires=["pillow>=9.1,<11.0", "requests>=2.23,<3.0"],
    project_urls={
        "Changelog": "https://github.com/AnonymouX47/term-image/blob/main/CHANGELOG.md",
        "Documentation": "https://term-image.readthedocs.io/",
        "Funding": "https://github.com/AnonymouX47/term-image#donate",
        "Source": "https://github.com/AnonymouX47/term-image",
        "Tracker": "https://github.com/AnonymouX47/term-image/issues",
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
        "kitty",
        "iterm2",
        "sixel",
        "graphics",
    ],
)
