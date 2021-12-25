"""term-img's CLI Implementation"""

from __future__ import annotations

import argparse
import logging
import os
from typing import Optional
from urllib.parse import urlparse

import PIL
import requests

from .exceptions import URLNotFoundError
from .exit_codes import INVALID_SIZE, NO_VALID_SOURCE, SUCCESS
from .image import TermImage


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
        log_exception(
            f"Could not access '{os.path.abspath(dir)}/'", logger, direct=True
        )
        return

    # Some directories can be changed to but cannot be listed
    try:
        entries = os.listdir()
    except OSError:
        log_exception(
            f"Could not get the contents of '{os.path.abspath('.')}/'",
            logger,
            direct=True,
        )
        return os.chdir(prev_dir)

    empty = True
    content = {}
    for entry in entries:
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
                    # The check is only to filter inaccessible files and disallow them
                    # from being reported as directories within the recursive call
                    result = check_dir(entry) if os.path.isdir(entry) else None
            except RecursionError:
                log(f"Too deep: {os.getcwd()!r}", logger, logging.ERROR)
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
    global args, log, log_exception, recursive, show_hidden

    # Ensure user-config is loaded only when the package is executed as a module,
    # from the CLI
    from .tui.config import max_pixels, user_dir
    from .tui.main import scan_dir
    from .tui.widgets import Image
    from .logging import init_log, log, log_exception
    from . import tui

    parser = argparse.ArgumentParser(
        prog="term-img",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description="Display images in a terminal",
        epilog=""" \

'--' should be used to separate positional arguments that begin with an '-' \
from options/flags, to avoid ambiguity.
For example, `$ term-img [options] -- -image.jpg --image.png`

NOTES:
  1. The displayed image uses HEIGHT/2 lines and WIDTH columns.
  2. The size is multiplied by the scale on each axis respectively before the image
     is rendered.
  3. Any image having more pixels than the specified maximum will be replaced
     with a placeholder when displayed but can still be forced to display
     or viewed externally.
     Note that increasing this will have adverse effects on performance.
  4. Any event with a level lower than the specified one is not reported.
  5. Supports all image formats supported by PIL.Image.open().
""",
        add_help=False,  # '-h' is used for HEIGHT
        allow_abbrev=False,  # Allow clustering of short options in 3.7
    )

    # General
    general = parser.add_argument_group("General Options")

    general.add_argument(
        "--help",
        action="help",
        help="show this help message and exit",
    )

    # CLI-only
    cli_options = parser.add_argument_group(
        "CLI-only Options",
        "These options apply only when there is just one valid image source",
    )
    size_options = cli_options.add_mutually_exclusive_group()

    size_options.add_argument(
        "-w",
        "--width",
        type=int,
        metavar="N",
        help="Width of the image to be rendered [1]",
    )
    size_options.add_argument(
        "-h",
        "--height",
        type=int,
        metavar="N",
        help="Height of the image to be rendered [1]",
    )
    cli_options.add_argument(
        "-x",
        "--scale-x",
        type=float,
        metavar="N",
        default=1.0,
        help="x-axis scale of the image to be rendered [2]",
    )
    cli_options.add_argument(
        "-y",
        "--scale-y",
        type=float,
        metavar="N",
        default=1.0,
        help="y-axis scale of the image to be rendered [2]",
    )

    # TUI-only
    tui_options = parser.add_argument_group(
        "TUI-only Options",
        """These options apply only when there is at least one valid directory source \
or multiple valid sources
""",
    )

    tui_options.add_argument(
        "-a",
        "--all",
        action="store_true",
        help="Inlcude hidden file and directories",
    )
    tui_options.add_argument(
        "-r",
        "--recursive",
        action="store_true",
        help="Scan for local images recursively",
    )
    tui_options.add_argument(
        "--max-pixels",
        type=int,
        metavar="N",
        default=max_pixels,
        help="Maximum amount of pixels in images to be displayed (default=4194304) [3]",
    )

    # Logging
    log_options_ = parser.add_argument_group(
        "Logging Options",
        "NOTE: These are all mutually exclusive",
    )
    log_options = log_options_.add_mutually_exclusive_group()

    log_options_.add_argument(
        "-l",
        "--log",
        default=os.path.join(user_dir, "term_img.log"),
        help="Specify a file to write logs to instead of the default",
    )
    log_options.add_argument(
        "--log-level",
        metavar="LEVEL",
        choices=("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"),
        default="WARNING",
        help="Set logging level to any of DEBUG, INFO, WARNING, ERROR, CRITICAL [4]",
    )
    log_options.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="More detailed event reporting. Also implies --log-level=INFO",
    )
    log_options.add_argument(
        "--verbose-log",
        action="store_true",
        help="Like --verbose but only applies to the log file",
    )
    log_options.add_argument(
        "--debug",
        action="store_true",
        help="Implies --log-level=DEBUG with verbosity",
    )

    # Positional
    parser.add_argument(
        "sources",
        nargs="+",
        metavar="source",
        help="Path(s) to local image(s) and/or directory(s) OR URLs",
    )

    args = parser.parse_args()
    recursive = args.recursive
    show_hidden = args.all

    init_log(
        args.log,
        getattr(logging, args.log_level),
        args.debug,
        args.verbose,
        args.verbose_log,
    )

    images = []
    contents = {}

    for source in args.sources:
        if all(urlparse(source)[:3]):  # Is valid URL
            log(
                f"Getting image from {source!r}...",
                logger,
                verbose=True,
            )
            try:
                images.append(
                    (os.path.basename(source), Image(TermImage.from_url(source))),
                )
            # Also handles `ConnectionTimeout`
            except requests.exceptions.ConnectionError:
                log(f"Unable to get {source!r}", logger, logging.ERROR)
            except URLNotFoundError as e:
                log(str(e), logger, logging.ERROR)
            except PIL.UnidentifiedImageError as e:
                log(str(e), logger, logging.ERROR)
            else:
                log("... Done!", logger, verbose=True)
        elif os.path.isfile(source):
            try:
                images.append(
                    (source, Image(TermImage.from_file(os.path.relpath(source))))
                )
            except PIL.UnidentifiedImageError as e:
                log(str(e), logger, logging.ERROR)
            except OSError as e:
                log(
                    f"({e}) {source!r} could not be read",
                    logger,
                    logging.ERROR,
                )
        elif os.path.isdir(source):
            log(
                f"Checking directory {source!r}...",
                logger,
                verbose=True,
            )
            result = check_dir(source, os.getcwd())
            log("... Done!", logger, verbose=True)
            if result is not None:
                source = os.path.relpath(source)
                contents[source] = result
                images.append((source, scan_dir(source, result, os.getcwd())))
        else:
            log(
                f"{source!r} is invalid or does not exist",
                logger,
                logging.ERROR,
            )

    if not images:
        log("No valid source!", logger)
        return NO_VALID_SOURCE

    if len(images) == 1 and isinstance(images[0][1], Image):
        log(
            "Single image source; Printing directly to console",
            logger,
            direct=False,
        )
        image = images[0][1]._image
        try:
            if args.width is not None:
                image.width = args.width
            elif args.height is not None:
                image.height = args.height
            image.scale_x = args.scale_x
            image.scale_y = args.scale_y
        # Handles `ValueError` and `.exceptions.InvalidSize`
        # raised by `TermImage.__valid_size()` or scale setter methods.
        except ValueError as e:
            log(str(e), logger, logging.CRITICAL)
            return INVALID_SIZE
        image.draw_image()
    else:
        tui.init(args, images, contents)

    return SUCCESS


logger = logging.getLogger(__name__)

# Set from within `main()`
args = None
log = None
log_exception = None
