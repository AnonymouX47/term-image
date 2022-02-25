"""term-img's CLI Implementation"""

import argparse
import logging as _logging
import os
import queue
import sys
from multiprocessing import Process, Queue as mp_Queue
from operator import mul, setitem
from threading import Thread, current_thread
from typing import Any, Dict, Generator, List, Optional, Tuple
from urllib.parse import urlparse

import PIL
import requests

from . import __version__, notify, set_font_ratio, tui
from .config import config_options, font_ratio, max_pixels, user_dir
from .exceptions import InvalidSize, URLNotFoundError
from .exit_codes import FAILURE, INVALID_SIZE, NO_VALID_SOURCE, SUCCESS
from .image import _ALPHA_THRESHOLD, TermImage
from .logging import init_log, log, log_exception
from .tui.widgets import Image


def check_dir(dir: str, prev_dir: str = "..") -> Optional[Dict[str, Dict[str, dict]]]:
    """Scan *dir* (and sub-directories, if '--recursive' is set)
    and build the tree of directories [recursively] containing readable images.

    Args:
        - dir: Path to directory to be scanned.
        - prev_dir: Path (absolute or relative to *dir*) to set as working directory
          after scannning *dir* (default:  parent directory of *dir*).

    Returns:
        - `None` if *dir* contains no readable images [recursively].
        - A dict representing the resulting directory tree, if *dir* is "non-empty".

    - If '--hidden' is set, hidden (.[!.]*) images and subdirectories are considered.
    """
    try:
        os.chdir(dir)
    except OSError:
        log_exception(
            f"Could not access '{os.path.abspath(dir)}{os.sep}'",
            logger,
            direct=True,
        )
        return

    # Some directories can be changed to but cannot be listed
    try:
        entries = os.listdir()
    except OSError:
        log_exception(
            f"Could not get the contents of '{os.path.abspath('.')}{os.sep}'",
            logger,
            direct=True,
        )
        return os.chdir(prev_dir)

    empty = True
    content = {}
    for entry in entries:
        if entry.startswith(".") and not SHOW_HIDDEN:
            continue
        if os.path.isfile(entry):
            if not empty:
                continue
            try:
                PIL.Image.open(entry)
                if empty:
                    empty = False
                    if not RECURSIVE:
                        break
            except Exception:
                pass
        elif RECURSIVE:
            try:
                if os.path.islink(entry):
                    # Eliminate broken and cyclic symlinks
                    # Return to the link's parent rather than the linked directory's
                    # parent
                    result = (
                        check_dir(entry, os.getcwd())
                        if (
                            os.path.exists(entry)  # not broken
                            # not cyclic
                            and not os.getcwd().startswith(os.path.realpath(entry))
                        )
                        else None
                    )
                else:
                    # The check is only to filter inaccessible files and disallow them
                    # from being reported as inaccessible directories within the
                    # recursive call
                    result = check_dir(entry) if os.path.isdir(entry) else None
            except RecursionError:
                log(f"Too deep: {os.getcwd()!r}", logger, _logging.ERROR)
                # Don't bother checking anything else in the current directory
                # Could possibly mark the directory as empty even though it contains
                # image files but at the same time, not doing this could be very costly
                # when there are many subdirectories
                break
            if result is not None:
                content[entry] = result

    os.chdir(prev_dir)
    return None if empty and not content else content


def check_dirs(
    checker_no: int,
    content_queue: mp_Queue,
    dir_queue: mp_Queue,
    log_queue: mp_Queue,
    progress_queue: mp_Queue,
    logging_level: int,
    globals_: Dict[str, Any],
    logging_: Dict[str, Any],
):
    """Checks a directory source in a newly **spawned** child process.

    Intended as the *target* of a **spawned** process to parallelize directory checks.
    """
    from traceback import format_exception

    from . import logging

    def redirect_logs(record):
        attrdict = record.__dict__
        exc_info = attrdict["exc_info"]
        if exc_info:
            # traceback objects cannot be pickled
            attrdict["msg"] = "\n".join(
                (attrdict["msg"], "".join(format_exception(*exc_info)))
            ).rstrip()
            attrdict["exc_info"] = None
        log_queue.put(attrdict)

        return False  # Prevent logs from being emitted by spawned processes

    globals().update(globals_)
    logging.__dict__.update(logging_)
    logger.setLevel(logging_level)
    logger.filter = redirect_logs

    logger.debug("Starting")
    source = dir_queue.get()
    while source:
        progress_queue.put((checker_no, source))
        log(f"Checking {source!r}", logger, verbose=True)
        result = False
        try:
            result = check_dir(source)
        except KeyboardInterrupt:
            break
        except Exception:
            log_exception(f"Checking {source!r} failed", logger)
        finally:
            content_queue.put((source, result))
        source = dir_queue.get()
    progress_queue.put((checker_no, None))
    logger.debug("Exiting")


def manage_checkers(
    dir_queue: mp_Queue,
    contents: Dict[str, Dict],
    images: List[Tuple[str, Generator]],
    opener: Thread,
) -> None:
    """Manages the processing of directory sources in parallel using multiple processes.

    If multiprocessing is not supported on the host platform, the sources are processed
    serially in the current thread of execution, after all file sources have been
    processed.
    """
    from . import logging

    def process_log() -> None:
        attrdict = log_queue.get()
        attrdict["process"] = PID
        logger.handle(_logging.makeLogRecord(attrdict))

    def process_result(source: str, result: Optional[bool], n: int = -1) -> None:
        if MULTI:
            if n > -1:
                log(
                    f"Checker-{n} was terminated by signal {-checkers[n].exitcode} "
                    f"while checking {source!r}",
                    logger,
                    _logging.ERROR,
                    direct=False,
                )

        log(
            (
                f"Checking {source!r} failed"
                if result is False
                else f"{source!r} is empty"
                if result is None
                else f"Done checking {source!r}"
            ),
            logger,
            _logging.ERROR if result is False else _logging.INFO,
            verbose=result is not False,
        )

        if False is not result is not None:
            source = os.path.abspath(source)
            contents[source] = result
            images.append((source, ...))

    try:
        content_queue = mp_Queue()
        log_queue = mp_Queue()
        progress_queue = mp_Queue()
    except ImportError:
        MULTI = False
        log(
            "Multiprocessing not supported on this platform, "
            "directory sources will be processed serially",
            logger,
            _logging.ERROR,
        )
    else:
        MULTI = True

    if MULTI:
        # Process.close() and Process.kill() were added in Python 3.7
        CLOSE_KILL = sys.version_info[:2] >= (3, 7)

        MAX_CHECKERS = args.checkers
        PID = os.getpid()
        checker_progress = [True] * MAX_CHECKERS
        logging_level = logger.getEffectiveLevel()
        globals_ = {
            **{"log_queue": log_queue},
            **{name: globals()[name] for name in ("RECURSIVE", "SHOW_HIDDEN")},
        }
        logging_ = {  # "Constants" from `.logging`
            name: value for name, value in logging.__dict__.items() if name.isupper()
        }

        checkers = [
            Process(
                name=f"Checker-{n}",
                target=check_dirs,
                args=(
                    n,
                    content_queue,
                    dir_queue,
                    log_queue,
                    progress_queue,
                    logging_level,
                    globals_,
                    logging_,
                ),
            )
            for n in range(MAX_CHECKERS)
        ]

        for checker in checkers:
            checker.start()

        try:
            # Wait until at least one checker starts processing a directory
            while progress_queue.empty():
                pass

            while not interrupted.is_set() and not (
                not any(checker_progress)
                and log_queue.empty()
                and content_queue.empty()
            ):
                if not log_queue.empty():
                    process_log()
                if not content_queue.empty():
                    process_result(*content_queue.get())
                for n, checker in enumerate(checkers):
                    if not checker.is_alive() and checker_progress[n]:
                        # Ensure it's actually the last source processed by the dead
                        # process that's taken into account.
                        while not progress_queue.empty():
                            setitem(checker_progress, *progress_queue.get())
                        if checker_progress[n]:  # Externally terminated
                            process_result(checker_progress[n], False, n)
                            checker_progress[n] = None
        finally:
            for checker in checkers:
                checker.kill() if CLOSE_KILL else checker.terminate()
                checker.join()
                if CLOSE_KILL:
                    checker.close()
    else:
        current_thread.name = "Checker"
        # wait till after file sources are processed, since the working directory
        # will be changing
        opener.join()

        source = dir_queue.get()
        while source:
            result = False
            try:
                result = check_dir(source, os.getcwd())
            except Exception:
                log_exception(f"Checking {source!r} failed", logger)
            finally:
                process_result(source, result)
            source = dir_queue.get()


def get_urls(
    url_queue: queue.Queue,
    images: List[Tuple[str, Image]],
) -> None:
    """Processes URL sources from a/some separate thread(s)"""
    source = url_queue.get()
    while not interrupted.is_set() and source:
        log(f"Getting image from {source!r}", logger, verbose=True)
        try:
            images.append(
                (os.path.basename(source), Image(TermImage.from_url(source))),
            )
        # Also handles `ConnectionTimeout`
        except requests.exceptions.ConnectionError:
            log(f"Unable to get {source!r}", logger, _logging.ERROR)
        except URLNotFoundError as e:
            log(str(e), logger, _logging.ERROR)
        except PIL.UnidentifiedImageError as e:
            log(str(e), logger, _logging.ERROR)
        except Exception:
            log_exception(f"Getting {source!r} failed", logger, direct=True)
        else:
            log(f"Done getting {source!r}", logger, verbose=True)
        source = url_queue.get()


def open_files(
    file_queue: queue.Queue,
    images: List[Tuple[str, Image]],
) -> None:
    source = file_queue.get()
    while not interrupted.is_set() and source:
        log(f"Opening {source!r}", logger, verbose=True)
        try:
            images.append((source, Image(TermImage.from_file(source))))
        except PIL.UnidentifiedImageError as e:
            log(str(e), logger, _logging.ERROR)
        except OSError as e:
            log(f"Could not read {source!r}: {e}", logger, _logging.ERROR)
        except Exception:
            log_exception(f"Opening {source!r} failed", logger, direct=True)
        else:
            log(f"Done opening {source!r}", logger, verbose=True)
        source = file_queue.get()


def main() -> None:
    """CLI execution sub-entry-point"""
    global args, url_images, RECURSIVE, SHOW_HIDDEN

    parser = argparse.ArgumentParser(
        prog="term-img",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description="Display/Browse images in a terminal",
        epilog=""" \

'--' should be used to separate positional arguments that begin with an '-' \
from options/flags, to avoid ambiguity.
For example, `$ term-img [options] -- -image.jpg --image.png`

NOTES:
  1. The displayed image uses HEIGHT/2 lines, while the number of columns is dependent
     on the WIDTH and the FONT RATIO.
     The auto sizing is calculated such that the image always fits into the available
     terminal size (i.e terminal size minus allowances) except when `-S` is
     specified, which allows the image height to go beyond the terminal height.
  2. The size is multiplied by the scale on each axis respectively before the image
     is rendered. A scale value must be such that 0.0 < value <= 1.0.
  3. If `-S` is used without `-w` or `-h`, the size is automatically calculated such
     that the *rendered width* is exactly the *available* terminal width, assuming the
     *scale* equals 1, regardless of the font ratio.
     Also, `--v-allow` has no effect i.e vertical allowance is overriden.
  4. In CLI mode, only image sources are used, directory sources are skipped.
     Animated images are displayed only when animation is disabled (with `--no-anim`)
     or there's only one image source.
  5. Any image having more pixels than the specified maximum will be:
     - skipped, in CLI mode
     - replaced, in TUI mode, with a placeholder when displayed but can still be forced
       to display or viewed externally.
     Note that increasing this will have adverse effects on performance.
  6. Any event with a level lower than the specified one is not reported.
  7. Supports all image formats supported by `PIL.Image.open()`.
""",
        add_help=False,  # '-h' is used for HEIGHT
        allow_abbrev=False,  # Allow clustering of short options in 3.7
    )

    # General
    general = parser.add_argument_group("General Options")

    general.add_argument(
        "--help",
        action="help",
        help="Show this help message and exit",
    )
    general.add_argument(
        "--version",
        action="version",
        version=__version__,
        help="Show the program version and exit",
    )
    general.add_argument(
        "-F",
        "--font-ratio",
        type=float,
        metavar="N",
        default=font_ratio,
        help=(
            "Specify the width-to-height ratio of a character cell in your terminal "
            f"for proper image scaling (default: {font_ratio})"
        ),
    )

    anim_options = general.add_mutually_exclusive_group()
    anim_options.add_argument(
        "-f",
        "--frame-duration",
        type=float,
        metavar="N",
        help=(
            "Specify the time (in seconds) between frames for all animated images "
            "(default: Determined per image from it's metadata OR 0.1)"
        ),
    )
    anim_options.add_argument(
        "--no-anim",
        action="store_true",
        help=(
            "Disable image animation. Animated images are displayed as just their "
            "first frame."
        ),
    )

    mode_options = general.add_mutually_exclusive_group()
    mode_options.add_argument(
        "--cli",
        action="store_true",
        help=(
            "Do not the launch the TUI, instead draw all image sources "
            "to the terminal directly [4]"
        ),
    )
    mode_options.add_argument(
        "--tui",
        action="store_true",
        help="Always launch the TUI, even for a single image",
    )

    _alpha_options = parser.add_argument_group(
        "Transparency Options (General)",
        "NOTE: These are mutually exclusive",
    )
    alpha_options = _alpha_options.add_mutually_exclusive_group()
    alpha_options.add_argument(
        "--no-alpha",
        action="store_true",
        help="Disable image transparency (i.e black background)",
    )
    alpha_options.add_argument(
        "-A",
        "--alpha",
        type=float,
        metavar="N",
        default=_ALPHA_THRESHOLD,
        help=(
            "Alpha ratio above which pixels are taken as opaque (0 <= x < 1) "
            f"(default: {_ALPHA_THRESHOLD:f})"
        ),
    )
    alpha_options.add_argument(
        "-b",
        "--alpha-bg",
        metavar="COLOR",
        help=(
            "Hex color (without '#') with which transparent backgrounds should be "
            "replaced"
        ),
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
        help="Width of the image to be rendered (default: auto) [1]",
    )
    size_options.add_argument(
        "-h",
        "--height",
        type=int,
        metavar="N",
        help="Height of the image to be rendered (default: auto) [1]",
    )
    cli_options.add_argument(
        "--h-allow",
        type=int,
        default=0,
        metavar="N",
        help=(
            "Horizontal allowance i.e minimum number of columns to leave unused "
            "(default: 0)"
        ),
    )
    cli_options.add_argument(
        "--v-allow",
        type=int,
        default=2,
        metavar="N",
        help=(
            "Vertical allowance i.e minimum number of lines to leave unused "
            "(default: 2)"
        ),
    )
    cli_options.add_argument(
        "-S",
        "--scroll",
        action="store_true",
        help=("Allow the image height to go beyond the terminal height [3]"),
    )
    size_options.add_argument(
        "--fit-to-width",
        action="store_true",
        help=(
            "Automatically fit the image to the available terminal width "
            "(Equivalent to using `-S` without `-w` or `-h`)."
        ),
    )
    cli_options.add_argument(
        "-O",
        "--oversize",
        action="store_true",
        help=(
            "Allow the image size to go beyond the terminal size "
            "(To be used with `-w` or `-h`)"
        ),
    )
    cli_options.add_argument(
        "-s",
        "--scale",
        type=float,
        metavar="N",
        help="Scale of the image to be rendered (overrides `-x` and `-y`) [2]",
    )
    cli_options.add_argument(
        "-x",
        "--scale-x",
        type=float,
        metavar="N",
        default=1.0,
        help="x-axis scale of the image to be rendered (default: 1.0) [2]",
    )
    cli_options.add_argument(
        "-y",
        "--scale-y",
        type=float,
        metavar="N",
        default=1.0,
        help="y-axis scale of the image to be rendered (default: 1.0) [2]",
    )

    align_options = parser.add_argument_group("Alignment Options (CLI-only)")
    align_options.add_argument(
        "--no-align",
        action="store_true",
        help=(
            "Output image without alignment or padding. "
            "Overrides all other alignment options"
        ),
    )
    align_options.add_argument(
        "-H",
        "--h-align",
        choices=("left", "center", "right"),
        help="Horizontal alignment (default: center)",
    )
    align_options.add_argument(
        "--pad-width",
        metavar="N",
        type=int,
        help=(
            "No of columns within which to align the image "
            "(default: terminal width, minus horizontal allowance)"
        ),
    )
    align_options.add_argument(
        "-V",
        "--v-align",
        choices=("top", "middle", "bottom"),
        help="Vertical alignment (default: middle)",
    )
    align_options.add_argument(
        "--pad-height",
        metavar="N",
        type=int,
        help=(
            "No of lines within which to align the image "
            "(default: terminal height, minus vertical allowance)"
        ),
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
        help=(
            "Maximum amount of pixels in images to be displayed "
            f"(default: {max_pixels}) [5]"
        ),
    )

    # Performance
    perf_options = parser.add_argument_group("Performance Options (General)")
    default_checkers = max(
        (
            len(os.sched_getaffinity(0))
            if hasattr(os, "sched_getaffinity")
            else os.cpu_count() or 0
        )
        - 1,
        2,
    )
    perf_options.add_argument(
        "--checkers",
        type=int,
        metavar="N",
        default=default_checkers,
        help=(
            "Maximum number of sub-processes for checking directory sources "
            f"(default: {default_checkers})"
        ),
    )
    perf_options.add_argument(
        "--getters",
        type=int,
        metavar="N",
        default=4,
        help="Number of threads for downloading images from URL sources (default: 4)",
    )

    # Logging
    log_options_ = parser.add_argument_group(
        "Logging Options",
        "NOTE: These are mutually exclusive",
    )
    log_options = log_options_.add_mutually_exclusive_group()

    log_file = os.path.join(user_dir, "term_img.log")
    log_options_.add_argument(
        "-l",
        "--log",
        metavar="FILE",
        default=log_file,
        help=f"Specify a file to write logs to (default: {log_file})",
    )
    log_options.add_argument(
        "--log-level",
        metavar="LEVEL",
        choices=("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"),
        default="WARNING",
        help=(
            "Set logging level to any of DEBUG, INFO, WARNING, ERROR, CRITICAL "
            "(default: WARNING) [6]"
        ),
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
    RECURSIVE = args.recursive
    SHOW_HIDDEN = args.all

    init_log(
        args.log,
        getattr(_logging, args.log_level),
        args.debug,
        args.verbose,
        args.verbose_log,
    )

    for name, is_valid in config_options.items():
        var_name = name.replace(" ", "_")
        value = getattr(args, var_name, None)
        # Not all config options have corresponding command-line arguments
        if value is not None and not is_valid(value):
            notify.notify(
                f"Invalid {name} (got: {value})... Using config value.",
                level=notify.ERROR,
            )
            setattr(args, var_name, locals()[var_name])

    set_font_ratio(args.font_ratio)

    file_images, url_images, dir_images = [], [], []
    contents = {}
    absolute_sources = set()

    url_queue = queue.Queue()
    getters = [
        Thread(
            target=get_urls,
            args=(url_queue, url_images),
            name=f"Getter-{n}",
            daemon=True,
        )
        for n in range(1, args.getters + 1)
    ]
    for getter in getters:
        getter.start()

    file_queue = queue.Queue()
    opener = Thread(
        target=open_files,
        args=(file_queue, file_images),
        name="Opener",
        daemon=True,
    )
    opener.start()

    os_is_unix = sys.platform not in {"win32", "cygwin"}

    if os_is_unix:
        dir_queue = mp_Queue()
        check_manager = Thread(
            target=manage_checkers,
            args=(dir_queue, contents, dir_images, opener),
            name="CheckManager",
            daemon=True,
        )
        check_manager.start()

    log("Processing sources", logger, loading=True)
    for source in args.sources:
        absolute_source = (
            source if all(urlparse(source)[:3]) else os.path.abspath(source)
        )
        if absolute_source in absolute_sources:
            log(f"Source repeated: {absolute_source!r}", logger, verbose=True)
            continue
        absolute_sources.add(absolute_source)

        if all(urlparse(source)[:3]):  # Is valid URL
            url_queue.put(source)
        elif os.path.isfile(source):
            file_queue.put(source)
        elif os.path.isdir(source):
            if args.cli:
                log(f"Skipping directory {source!r}", logger, verbose=True)
                continue
            if not os_is_unix:
                dir_images = True
                continue
            dir_queue.put(source)
        else:
            log(f"{source!r} is invalid or does not exist", logger, _logging.ERROR)

    # Signal end of sources
    for _ in range(args.getters):
        url_queue.put(None)
    file_queue.put(None)
    if os_is_unix:
        for _ in range(args.checkers):
            dir_queue.put(None)

    for getter in getters:
        getter.join()
    opener.join()
    if os_is_unix:
        check_manager.join()

    notify.stop_loading()

    if not os_is_unix and dir_images:
        log(
            "Directory sources skipped, not supported on Windows!",
            logger,
            _logging.ERROR,
        )
        dir_images = []

    log("... Done!", logger)

    images = file_images + url_images + dir_images
    if not images:
        log("No valid source!", logger)
        return NO_VALID_SOURCE

    if args.cli or (
        not args.tui and len(images) == 1 and isinstance(images[0][1], Image)
    ):
        log("Running in CLI mode", logger, direct=False)

        show_name = len(args.sources) > 1
        err = False
        for entry in images:
            image = entry[1]._image
            if mul(*image._original_size) > args.max_pixels:
                log(
                    f"Has more than the maximum pixel-count, skipping: {entry[0]!r}",
                    logger,
                    level=_logging.WARNING,
                    verbose=True,
                )
                continue

            if not args.no_anim and image._is_animated and len(images) > 1:
                log(f"Skipping animated image: {entry[0]!r}", logger, verbose=True)
                continue

            if show_name:
                notify.notify("\n" + os.path.basename(entry[0]) + ":")
            try:
                image.set_size(
                    args.width,
                    args.height,
                    args.h_allow,
                    args.v_allow,
                    check_height=not (
                        args.fit_to_width or args.scroll or args.oversize
                    ),
                    check_width=not args.oversize,
                )
                image.scale = (
                    (args.scale_x, args.scale_y) if args.scale is None else args.scale
                )
                if args.frame_duration:
                    image.frame_duration = args.frame_duration

                image.draw(
                    *(
                        (None, 1, None, 1)
                        if args.no_align
                        else (
                            args.h_align,
                            args.pad_width,
                            args.v_align,
                            args.pad_height,
                        )
                    ),
                    (
                        None
                        if args.no_alpha
                        else args.alpha_bg and "#" + args.alpha_bg or args.alpha
                    ),
                    animate=not args.no_anim,
                    ignore_oversize=args.oversize,
                )

            # Handles `ValueError` and `.exceptions.InvalidSize`
            # raised by `TermImage.set_size()`, scaling value checks
            # or padding width/height checks.
            except ValueError as e:
                if isinstance(e, InvalidSize):
                    notify.notify(str(e), level=notify.ERROR)
                    err = True
                else:
                    log(str(e), logger, _logging.CRITICAL)
                    return FAILURE
        if err:
            return INVALID_SIZE
    elif os_is_unix:
        tui.init(args, images, contents)
    else:
        log(
            "The TUI is not supported on Windows! Try with `--cli`.",
            logger,
            _logging.CRITICAL,
        )
        return FAILURE

    return SUCCESS


logger = _logging.getLogger(__name__)

# Set from within `.__main__.main()`
interrupted = None

# Set from within `main()`
RECURSIVE = None
SHOW_HIDDEN = None
# # Used in other modules
args = None
url_images = None
