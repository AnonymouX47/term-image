"""term-img's CLI Implementation"""

from __future__ import annotations

import argparse
import os
import warnings
from typing import Optional
from urllib.parse import urlparse

import PIL
import requests

from .exceptions import URLNotFoundError
from .exit_codes import INVALID_SIZE, NO_VALID_SOURCE, SUCCESS
from .image import TermImage
from .tui.config import max_pixels
from .tui.main import scan_dir
from .tui.widgets import Image
from . import tui

# Printing to STDERR messes up output, especially with the TUI
warnings.simplefilter("ignore", PIL.Image.DecompressionBombWarning)


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
        print(f"Could not access {os.abspath(dir)}/")
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
                PIL.Image.open(entry)
                if empty:
                    empty = False
            except Exception:
                pass
        elif recursive:
            try:
                if os.path.islink(entry):
                    # Eliminate broken and cyclic symlinks
                    # Return to the link's parent rather than the linked directory's
                    # parent
                    result = (
                        check_dir(entry, os.getcwd())
                        if (
                            os.path.exists(entry)
                            and not os.getcwd().startswith(os.path.realpath(entry))
                        )
                        else None
                    )
                else:
                    result = check_dir(entry)
            except RecursionError:
                print(f"Too deep: {os.getcwd()!r}")
                # Don't bother checking anything else in the current directory
                # Could possibly mark the directory as empty even though it contains
                # image files but at the same time, could be very costly when
                # there are many subdirectories
                break
            if result is not None:
                content[entry] = result

    os.chdir(prev_dir)
    return None if empty and not content else content


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
  3. Any image having more pixels than the specified maximum will be replaced
     with a placeholder when displayed but can still be forced to display
     or viewed externally.
     Note that increasing this will have adverse effects on performance.
  4. Supports all image formats supported by PIL.Image.open().
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
        "--max-pixels",
        type=int,
        default=max_pixels,
        help="Maximum amount of pixels in images to be displayed (default=4194304) [3]",
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
            print(f"Getting image from {source!r}...", end=" ", flush=True)
            try:
                images.append(
                    (os.path.basename(source), Image(TermImage.from_url(source))),
                )
            # Also handles `ConnectionTimeout`
            except requests.exceptions.ConnectionError:
                print(f"Unable to get {source!r}")
            except URLNotFoundError as e:
                print(e)
            except PIL.UnidentifiedImageError as e:
                print(e)
            else:
                print("Done!")
        elif os.path.isfile(source):
            try:
                images.append(
                    (
                        os.path.basename(source),
                        Image(TermImage.from_file(os.path.relpath(source))),
                    )
                )
            except PIL.UnidentifiedImageError as e:
                print(e)
            except OSError as e:
                print(f"{source!r} could not be read: {e}")
        elif os.path.isdir(source):
            print(f"Checking directory {source!r}...", end=" ", flush=True)
            result = check_dir(source, os.getcwd())
            print("Done!")
            if result is not None:
                source = os.path.relpath(source)
                contents[source] = result
                images.append((source, scan_dir(source, result, os.getcwd())))
        else:
            print(f"{source!r} is invalid or does not exist")

    if not images:
        print("No valid source!")
        return NO_VALID_SOURCE

    if len(images) == 1 and isinstance(images[0][1], Image):
        # Single image argument
        image = images[0][1]._image
        try:
            if args.width is not None:
                image.width = args.width
            if args.height is not None:
                if image.size:  # width was also set
                    print("Only one of the dimensions can be specified.")
                    return INVALID_SIZE
                image.height = args.height
        # Handles `ValueError` and `.exceptions.InvalidSize`
        # raised by `TermImage.__valid_size()`
        except ValueError as e:
            print(e)
            return INVALID_SIZE
        image.draw_image()
    else:
        tui.init(args, images, contents)

    return SUCCESS
