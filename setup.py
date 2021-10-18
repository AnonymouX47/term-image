from setuptools import setup

classifiers = [
    "Development Status :: 5 - Production/Stable",
    "Programming Language :: Python :: 3",
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
    version="0.0.3",
    author="Anonymoux47",
    author_email="lekzy771@gmail.com",
    url="https://github.com/AnonymouX47/img",
    description="Display images in the terminal",
    long_description=long_description,
    long_description_content_type="text/markdown",
    packages=["term_img"],
    license="MIT",
    classifiers=classifiers,
    python_requires=">=3.6",
    install_requires=["pillow", "requests"],
    entry_points={
        "console_scripts": ["term-img=term_img.cli:main"],
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
