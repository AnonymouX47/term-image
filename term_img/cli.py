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

from .exceptions import URLNotFoundError
from .image import DrawImage


# Exit Codes
SUCCESS = 0
NO_VALID_SOURCE = 1
INVALID_SIZE = 2


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
    try:
        os.chdir(dir)
    except OSError:
        print(f"Could not access {dir}/")
        return None
    empty = True
    content = {}
    for entry in os.listdir():
        if entry.startswith(".") and not show_hidden:
            continue
        if os.path.isfile(entry):
            if not empty:
                continue
            try:
                Image.open(entry)
                if empty:
                    empty = False
            except Exception:
                pass
        elif recursive:
            if os.path.islink(entry):
                # Return to the link's parent rather than the linked directory's parent
                # Eliminate broken symlinks
                result = (
                    check_dir(entry, os.getcwd()) if os.path.exists(entry) else None
                )
            else:
                result = check_dir(entry)
            if result is not None:
                content[entry] = result

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
            except Exception as e:
                print(
                    f"{os.path.realpath(entry)!r} could not be read: "
                    f"{type(e).__name__}: {e}"
                )
            else:
                yield entry, DrawImage.from_file(entry)
        elif recursive and entry in contents:
            if os.path.islink(entry):  # check_dir() already eliminates broken symlinks
                # Return to the link's parent rather than the linked directory's parent
                yield (
                    entry,
                    scan_dir(entry, contents[entry], os.getcwd()),
                )
            else:
                yield entry, scan_dir(entry, contents[entry])

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
            print("|  " * (depth - 1) + "|--" + f"{entry}/:")
            if not value.gi_frame:  # The directory has been visited earlier
                if top_level or os.path.islink(entry):
                    # Return to Top-Level Directory, OR
                    # Return to the link's parent rather than the linked directory's
                    # parent
                    value = scan_dir(entry, contents[entry], os.getcwd())
                else:
                    value = scan_dir(entry, contents[entry])
            if top_level or os.path.islink(entry):  # broken symlinks already eliminated
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
  1. The displayed image uses HEIGHT/2 lines and WIDTH columns.
  2. Only one of the dimensions can be specified.
  3. Supports all image formats supported by PIL.Image.open().
""",
        add_help=False,  # '-h' is used for HEIGHT
        allow_abbrev=False,  # Allow clustering of short options in 3.7
    )

    parser.add_argument(
        "--help",
        action="help",
        help="show this help message and exit",
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
        "-w",
        "--width",
        type=int,
        help=(
            "Width of the image to be rendered "
            "(Ignored for multiple valid sources) [1][2]"
        ),
    )
    parser.add_argument(
        "-h",
        "--height",
        type=int,
        help=(
            "Height of the image to be rendered "
            "(Ignored for multiple valid sources) [1][2]"
        ),
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

    images = []
    contents = {}

    for source in args.sources:
        if all(urlparse(source)[:3]):  # Is valid URL
            try:
                images.append(
                    (os.path.basename(source), DrawImage.from_url(source)),
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
                source = os.path.relpath(source)
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
        try:
            if args.width is not None:
                image.width = args.width
            if args.height is not None:
                if image.size:  # width was also set
                    print("Only one of the dimensions can be specified.")
                    return INVALID_SIZE
                image.height = args.height
        # Handles `ValueError` and `.exceptions.InvalidSize`
        # raised by `DrawImage.__valid_size()`
        except ValueError as e:
            print(e)
            return INVALID_SIZE
        image.draw_image()
    else:
        display_images(".", iter(images), contents, top_level=True)

    return SUCCESS


if __name__ == "__main__":
    sys.exit(main())
