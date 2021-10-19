"""term-img's CLI Implementation"""

from __future__ import annotations

import argparse
import os
import sys
from operator import itemgetter
from typing import Generator, Iterator, Optional, Tuple, Union
from urllib.parse import urlparse

import requests
from PIL import Image, UnidentifiedImageError

from .errors import URLNotFoundError
from .image import DrawImage


# Exit Codes
SUCCESS = 0
NO_VALID_SOURCE = 1


def check_dir(dir: str, prev_dir: str = "..") -> Optional[dict]:
    """Scan _dir_ (and sub-directories, if '--recursive' is set)
    and build the tree of directories [recursively] containing readable images.

    Args:
        - dir: Path to directory to be scanned.
        - prev_dir: Path to set as working directory after scannning _dir_
            (default:  parent directory of _dir_).

    Returns:
        - `None` if _dir_ contains no readable images [recursively].
        - A dict representing the resulting directory tree, if _dir_ is "non-empty".

    - If '--hidden' is set, hidden (.*) images and subdirectories are considered.
    """
    os.chdir(dir)
    empty = True
    content = {}
    for entry in os.listdir():
        if entry.startswith(".") and not show_hidden:
            continue
        if os.path.isfile(entry):
            try:
                Image.open(entry)
                if empty:
                    empty = False
            except OSError:
                pass
        elif recursive:
            if os.path.islink(entry):
                # Return to the link's parent rather than the linked directory's parent
                result = check_dir(entry, os.getcwd())
            else:
                result = check_dir(entry)
            if result is not None:
                content[entry + os.sep] = result

    os.chdir(prev_dir)
    return None if empty and not content else content


def scan_dir(
    dir: str, contents: dict, prev_dir: str = ".."
) -> Generator[Tuple[str, Union[DrawImage, Generator]]]:
    """Scan _dir_ (and sub-directories, if '--recursive' is set) for readable images
    using a directory tree of the form produced by `check_dir(dir)`.

    Args:
        - dir: Path to directory to be scanned.
        - contents: Tree of directories containing readable images
            (as produced by `check_dir(dir)`).
        - prev_dir: Path to set as working directory after scannning _dir_
            (default:  parent directory of _dir_).

    Yields:
        - A `DrawImage` instance for each image in _dir_.
        - A similar generator for sub-directories (if '--recursive' is set).

    - If '--hidden' is set, hidden (.*) images and subdirectories are considered.
    """
    os.chdir(dir)
    for entry in os.listdir():
        if entry.startswith(".") and not show_hidden:
            continue
        if os.path.isfile(entry):
            try:
                Image.open(entry)
            except UnidentifiedImageError:
                # Reporting will apply to every non-image file :(
                pass
            except OSError as e:
                print(f"{os.path.realpath(entry)!r} could not be read: {e}")
            else:
                yield entry, DrawImage.from_file(entry)
        elif recursive and entry + os.sep in contents:
            if os.path.islink(entry):
                # Return to the link's parent rather than the linked directory's parent
                yield (
                    entry + os.sep,
                    scan_dir(entry, contents[entry + os.sep], os.getcwd()),
                )
            else:
                yield entry + os.sep, scan_dir(entry, contents[entry + os.sep])

    os.chdir(prev_dir)


depth = -1


def display_images(
    dir: str,
    images: Iterator[Tuple[str, Union[DrawImage, Iterator]]],
    contents: dict,
    prev_dir: str = "..",
    *,
    top_level: bool = False,
) -> None:
    """Display images in _dir_ (and sub-directories, if '--recursive' is set)
    as yielded by `scan_dir(dir)`.

    Args:
        - dir: Path to directory containing images.
        - images: An iterator yielding the images in _dir_ and/or similar iterators
            for sub-directories of _dir_.
        - contents: Tree of directories containing readable images
            (as produced by `check_dir(dir)`).
        - prev_dir: Path to set as working directory after displaying images in _dir_
            (default:  parent directory of _dir_).
        - top_level: Specifies if _dir_ is the top level (For internal use only).
    """
    global depth
    images = sorted(images, key=itemgetter(0))
    os.chdir(dir)
    depth += 1

    # print(f"{entries= }\n")
    if not top_level:
        print("|  " * depth + "..")
    for entry, value in images:
        if isinstance(value, DrawImage):  # Image file
            print("|  " * depth + entry)
        else:  # Directory
            print("|  " * (depth - 1) + "|--" + f"{entry}:")
            if not value.gi_frame:
                print(f"Back into {entry!r}")
                if top_level or os.path.islink(entry):
                    # Return to Top-Level Directory, OR
                    # Return to the link's parent rather than the linked directory's
                    # parent
                    value = scan_dir(entry, contents[entry], os.getcwd())
                else:
                    value = scan_dir(entry, contents[entry])
            if top_level or os.path.islink(entry):
                # Return to Top-Level Directory, OR
                # Return to the link's parent rather than the linked directory's parent
                display_images(entry, value, contents[entry], os.getcwd())
            else:
                display_images(entry, value, contents[entry])
    depth -= 1
    if not top_level:
        os.chdir(prev_dir)


def main():
    """CLI execution entry-point"""
    global recursive, show_hidden

    parser = argparse.ArgumentParser(
        prog="img",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description="Display images in a terminal",
        epilog="""\
'--' should be used to separate positional arguments that begin with an '-' \
from options/flags, to avoid ambiguity.
For example, `$ img [options] -- -image.jpg`

NOTES:
  1. The displayed image uses H/2 lines and W columns.
  2. Supports all image formats supported by PIL.Image.open().
""",
        allow_abbrev=False,  # Allow clustering of short options in 3.7
    )

    parser.add_argument(
        "-a",
        "--all",
        action="store_true",
        help="Inlcude hidden file and directories",
    )
    parser.add_argument(
        "-r",
        "--recursive",
        action="store_true",
        help="Scan for local images recursively",
    )
    parser.add_argument(
        "-s",
        "--size",
        nargs=2,
        metavar=("<W>", "<H>"),
        type=int,
        help="Resolution (Width and Height respectively) of the output, in pixels",
    )
    parser.add_argument(
        "sources",
        nargs="+",
        metavar="source",
        help="Path(s) to local image(s) and/or directory(s) OR URLs",
    )

    args = parser.parse_args()
    recursive = args.recursive
    show_hidden = args.all
    if args.size:
        args.size = tuple(args.size)

    images = []
    contents = {}

    for source in args.sources:
        if all(urlparse(source)[:3]):  # Is valid URL
            try:
                images.append(
                    (os.path.basename(source), DrawImage.from_url(source, args.size)),
                )
            # Also handles `ConnectionTimeout`
            except requests.exceptions.ConnectionError:
                print(f"Unable to get {source!r}")
            except URLNotFoundError as e:
                print(e)
            except UnidentifiedImageError as e:
                print(e)
        elif os.path.isfile(source):
            try:
                images.append(
                    (
                        os.path.relpath(source),
                        DrawImage.from_file(os.path.relpath(source)),
                    )
                )
            except UnidentifiedImageError as e:
                print(e)
            except OSError as e:
                print(f"{source!r} could not be read: {e}")
        elif os.path.isdir(source):
            result = check_dir(source, os.getcwd())
            if result is not None:
                source = os.path.relpath(source) + os.sep
                contents[source] = result
                images.append((source, scan_dir(source, result, os.getcwd())))
        else:
            print(f"{source!r} is invalid or does not exist")

    if not images:
        print("No valid source!")
        return NO_VALID_SOURCE

    if len(images) == 1 and isinstance(images[0][1], DrawImage):
        # Single image argument
        image = images[0][1]
        image.size = args.size
        image.draw_image()
    else:
        display_images(".", iter(images), contents, top_level=True)

    return SUCCESS


if __name__ == "__main__":
    sys.exit(main())
