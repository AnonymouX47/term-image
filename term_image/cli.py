"""Term-Image's CLI Implementation"""

from __future__ import annotations

import argparse
import logging as _logging
import os
import sys
from multiprocessing import Event as mp_Event, Queue as mp_Queue, Value
from operator import mul, setitem
from os.path import abspath, basename, exists, isdir, isfile, islink, realpath
from queue import Empty, Queue
from threading import Event, current_thread
from time import sleep
from typing import Any, Callable, Dict, Generator, List, Optional, Tuple, Union
from urllib.parse import urlparse

import PIL
import requests

from . import __version__, config, logging, notify, set_font_ratio, tui
from .config import config_options, store_config
from .exceptions import URLNotFoundError
from .exit_codes import FAILURE, INVALID_ARG, NO_VALID_SOURCE, SUCCESS
from .image import _ALPHA_THRESHOLD, TermImage
from .logging import Thread, init_log, log, log_exception
from .logging_multi import Process
from .tui.widgets import Image


def check_dir(
    dir: str, prev_dir: str = "..", *, _links: List[Tuple[str]] = None
) -> Optional[Dict[str, Union[bool, Dict[str, Union[bool, dict]]]]]:
    """Scan *dir* (and sub-directories, if '--recursive' was specified)
    and build the tree of directories [recursively] containing readable images.

    Args:
        - dir: Path to directory to be scanned.
        - prev_dir: Path (absolute or relative to *dir*) to set as working directory
          after scannning *dir* (default:  parent directory of *dir*).
        - _links: Tracks all symlinks from a *source* up **till** a subdirectory.

    Returns:
        - `None` if *dir* contains no readable images [recursively].
        - A dict representing the resulting directory tree whose items are:
          - a "/" key mapped to a ``True``. if *dir* contains image files
          - a directory name mapped to a dict of the same structure, for each non-empty
            sub-directory of *dir*

    NOTE:
        - If '--hidden' was specified, hidden (.[!.]*) images and subdirectories are
          considered.
        - `_depth` should always be initialized, at the module level, before calling
          this function.
    """
    global _depth

    _depth += 1
    try:
        os.chdir(dir)
    except OSError:
        log_exception(
            f"Could not access '{abspath(dir)}{os.sep}'",
            logger,
            direct=True,
        )
        return

    # Some directories can be changed to but cannot be listed
    try:
        entries = os.scandir()
    except OSError:
        log_exception(
            f"Could not get the contents of '{abspath('.')}{os.sep}'",
            logger,
            direct=True,
        )
        os.chdir(prev_dir)
        return

    empty = True
    content = {}
    for entry in entries:
        if not SHOW_HIDDEN and entry.name.startswith("."):
            continue
        try:
            is_file = entry.is_file()
            is_dir = entry.is_dir()
        except OSError:
            continue

        if is_file:
            if empty:
                try:
                    PIL.Image.open(entry.name)
                    empty = False
                    if not RECURSIVE:
                        break
                except Exception:
                    pass
        elif RECURSIVE and is_dir:
            if _depth > MAX_DEPTH:
                if not empty:
                    break
                continue

            result = None
            try:
                if entry.is_symlink():
                    path = realpath(entry)

                    # Eliminate cyclic symlinks
                    if os.getcwd().startswith(path) or (
                        _links and any(link[0].startswith(path) for link in _links)
                    ):
                        continue

                    if _source and _free_checkers.value:
                        _dir_queue.put((_source, _links.copy(), abspath(entry), _depth))
                    else:
                        _links.append((abspath(entry), path))
                        del path
                        # Return to the link's parent rather than the linked directory's
                        # parent
                        result = check_dir(entry.name, os.getcwd(), _links=_links)
                        _links.pop()
                else:
                    if _source and _free_checkers.value:
                        _dir_queue.put((_source, _links.copy(), abspath(entry), _depth))
                    else:
                        result = check_dir(entry.name, _links=_links)
            except OSError:
                pass

            if result:
                content[entry.name] = result

    # '/' is an invalid file/directory name on major platforms.
    # On platforms with root directory '/', it can never be the content of a directory.
    if not empty:
        content["/"] = True

    os.chdir(prev_dir)
    _depth -= 1
    return content or None


def check_dirs(
    checker_no: int,
    content_queue: mp_Queue,
    content_updated: mp_Event,
    dir_queue: mp_Queue,
    progress_queue: mp_Queue,
    progress_updated: mp_Event,
    free_checkers: Value,
    globals_: Dict[str, Any],
) -> None:
    """Checks a directory source in a newly **spawned** child process.

    Intended as the *target* of a **spawned** process to parallelize directory checks.
    """
    global _depth, _source

    globals().update(globals_, _free_checkers=free_checkers, _dir_queue=dir_queue)

    NO_CHECK = (None,) * 3
    while True:
        try:
            source, links, subdir, _depth = dir_queue.get_nowait()
        except KeyboardInterrupt:
            progress_queue.put((checker_no, NO_CHECK))
            raise
        except Empty:
            progress_updated.wait()
            progress_queue.put((checker_no, NO_CHECK))
            with free_checkers:
                free_checkers.value += 1
            try:
                source, links, subdir, _depth = dir_queue.get()
            finally:
                with free_checkers:
                    free_checkers.value -= 1

        if not subdir:
            break

        _source = source or subdir
        if not source:
            log(f"Checking {subdir!r}", logger, verbose=True)

        content_path = get_content_path(source, links, subdir)
        if islink(subdir):
            links.append((subdir, realpath(subdir)))
        progress_updated.wait()
        progress_queue.put((checker_no, (source, content_path, _depth)))
        result = None
        try:
            result = check_dir(subdir, _links=links)
        except Exception:
            log_exception(f"Checking {content_path!r} failed", logger, direct=True)
        finally:
            content_updated.wait()
            content_queue.put((source, content_path, result))


def get_content_path(source: str, links: List[Tuple[str]], subdir: str) -> str:
    """Returns the original path from *source* to *subdir*, collapsing all symlinks
    in-between.
    """
    if not (source and links):
        return subdir

    links = iter(links)
    absolute, prev_real = next(links)
    path = source + absolute[len(source) :]
    for absolute, real in links:
        path += absolute[len(prev_real) :]
        prev_real = real
    path += subdir[len(prev_real) :]

    return path


def get_links(source: str, subdir: str) -> List[Tuple[str, str]]:
    """Returns a list of all symlinks (and the directories they point to) between
    *source* and *subdir*.
    """
    if not source:
        return [(subdir, realpath(subdir))] if islink(subdir) else []

    links = [(source, realpath(source))] if islink(source) else []
    # Strips off the basename in case it's a link
    path = os.path.dirname(subdir[len(source) + 1 :])
    if path:
        cwd = os.getcwd()
        os.chdir(source)
        for dir in path.split(os.sep):
            if islink(dir):
                links.append((abspath(dir), realpath(dir)))
            os.chdir(dir)
        os.chdir(cwd)

    return links


def manage_checkers(
    dir_queue: Union[Queue, mp_Queue],
    contents: Dict[str, Union[bool, Dict]],
    images: List[Tuple[str, Generator]],
) -> None:
    """Manages the processing of directory sources in parallel using multiple processes.

    If multiprocessing is not supported on the host platform, the sources are processed
    serially in the current thread of execution, after all file sources have been
    processed.
    """
    global _depth

    def process_result(
        source: str,
        subdir: str,
        result: Union[None, bool, Dict[str, Union[bool, Dict]]],
        n: int = -1,
    ) -> None:
        if n > -1:
            exitcode = -checkers[n].exitcode
            log(
                f"Checker-{n} was terminated "
                + (f"by signal {exitcode} " if exitcode else "")
                + (f"while checking {subdir!r}" if subdir else ""),
                logger,
                _logging.ERROR,
                direct=False,
            )
            if subdir:
                dir_queue.put(
                    (
                        source,
                        get_links(source, subdir),
                        os.path.join(
                            realpath(os.path.dirname(subdir)), basename(subdir)
                        ),
                        result,
                    )
                )
            return

        if result:
            if source not in contents:
                contents[source] = {}
            update_contents(source, contents[source], subdir, result)
        elif not source and subdir not in contents:
            # Marks a potentially empty source
            # If the source is actually empty the dict stays empty
            contents[subdir] = {}

    if logging.MULTI and args.checkers > 1:
        content_queue = mp_Queue()
        content_updated = mp_Event()
        progress_queue = mp_Queue()
        progress_updated = mp_Event()
        free_checkers = Value("i")
        globals_ = {
            name: globals()[name] for name in ("MAX_DEPTH", "RECURSIVE", "SHOW_HIDDEN")
        }

        checkers = [
            Process(
                name=f"Checker-{n}",
                target=check_dirs,
                args=(
                    n,
                    content_queue,
                    content_updated,
                    dir_queue,
                    progress_queue,
                    progress_updated,
                    free_checkers,
                    globals_,
                ),
            )
            for n in range(args.checkers)
        ]

        for checker in checkers:
            checker.start()

        NO_CHECK = (None,) * 3
        try:
            contents[""] = contents
            content_updated.set()
            checks_in_progress = [NO_CHECK] * args.checkers
            progress_updated.set()

            # Wait until at least one checker starts processing a directory
            setitem(checks_in_progress, *progress_queue.get())

            while not (
                interrupted.is_set()  # MainThread has been interruped
                or not any(checks_in_progress)  # All checkers are dead
                # All checks are done
                or (
                    # No check in progress
                    all(not check or check == NO_CHECK for check in checks_in_progress)
                    # All sources have been passed in
                    and dir_queue.sources_finished
                    # All sources and branched-off subdirectories have been processed
                    and dir_queue.empty()
                    # All progress updates have been processed
                    and progress_queue.empty()
                    # All results have been processed
                    and content_queue.empty()
                )
            ):
                content_updated.clear()
                while not content_queue.empty():
                    process_result(*content_queue.get())
                content_updated.set()

                progress_updated.clear()
                while not progress_queue.empty():
                    setitem(checks_in_progress, *progress_queue.get())
                progress_updated.set()

                for n, checker in enumerate(checkers):
                    if checks_in_progress[n] and not checker.is_alive():
                        # Ensure it's actually the last source processed by the dead
                        # process that's taken into account.
                        progress_updated.clear()
                        while not progress_queue.empty():
                            setitem(checks_in_progress, *progress_queue.get())
                        progress_updated.set()

                        if checks_in_progress[n]:  # Externally terminated
                            process_result(*checks_in_progress[n], n)
                            checks_in_progress[n] = None

                sleep(0.01)  # Allow queue sizes to be updated
        finally:
            if interrupted.is_set():
                return

            if not any(checks_in_progress):
                logging.log(
                    "All checkers were terminated, checking directory sources failed!",
                    logger,
                    _logging.ERROR,
                )
                contents.clear()
                return

            for check in checks_in_progress:
                if check:
                    dir_queue.put((None,) * 4)
            for checker in checkers:
                checker.join()
            del contents[""]
            for source, result in tuple(contents.items()):
                if result:
                    images.append((source, ...))
                else:
                    del contents[source]
                    logging.log(f"{source!r} is empty", logger)
    else:
        current_thread.name = "Checker"

        _, links, source, _depth = dir_queue.get()
        while source:
            log(f"Checking {source!r}", logger, verbose=True)
            if islink(source):
                links.append((source, realpath(source)))
            result = False
            try:
                result = check_dir(source, os.getcwd(), _links=links)
            except Exception:
                log_exception(f"Checking {source!r} failed", logger, direct=True)
            finally:
                if result:
                    source = abspath(source)
                    contents[source] = result
                    images.append((source, ...))
                elif result is None:
                    log(f"{source!r} is empty", logger)
            _, links, source, _depth = dir_queue.get()


def update_contents(
    dir: str,
    contents: Dict[str, Union[bool, Dict]],
    subdir: str,
    subcontents: Dict[str, Union[bool, Dict]],
):
    """Updates a directory's content tree with the content tree of a subdirectory."""

    def update_dict(base: dict, update: dict):
        for key in update:
            # "/" can be in *base* if the directory's parent was re-checked
            if key in base and key != "/":
                update_dict(base[key], update[key])
            else:
                base[key] = update[key]

    path = subdir[len(dir) + 1 :].split(os.sep) if dir else [subdir]
    target = path.pop()

    path_iter = iter(path)
    for branch in path_iter:
        try:
            contents = contents[branch]
        except KeyError:
            contents[branch] = {}
            contents = contents[branch]
            break
    for branch in path_iter:
        contents[branch] = {}
        contents = contents[branch]
    if target in contents:
        update_dict(contents[target], subcontents)
    else:
        contents[target] = subcontents


def get_urls(
    url_queue: Queue,
    images: List[Tuple[str, Image]],
) -> None:
    """Processes URL sources from a/some separate thread(s)"""
    source = url_queue.get()
    while not interrupted.is_set() and source:
        log(f"Getting image from {source!r}", logger, verbose=True)
        try:
            images.append((basename(source), Image(TermImage.from_url(source))))
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
    file_queue: Queue,
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
        source = file_queue.get()


def main() -> None:
    """CLI execution sub-entry-point"""
    global args, url_images, MAX_DEPTH, RECURSIVE, SHOW_HIDDEN

    def check_arg(
        name: str,
        check: Callable[[Any], Any],
        msg: str,
        exceptions: Tuple[Exception] = None,
        *,
        fatal: bool = True,
    ) -> bool:
        """Performs generic argument value checks and outputs the given message if the
        argument value is invalid.

        Returns:
            ``True`` if valid, otherwise ``False``.

        If *exceptions* is :
          - not given or ``None``, the argument is invalid only if ``check(arg)``
            returns a falsy value.
          - given, the argument is invalid if ``check(arg)`` raises one of the given
            exceptions. It's also invalid if it raises any other exception but the
            error message is different.
        """
        value = getattr(args, name)
        if exceptions:
            valid = False
            try:
                check(value)
                valid = True
            except exceptions:
                pass
            except Exception:
                log_exception(
                    f"--{name.replace('_', '-')}: Invalid! See the logs",
                    direct=True,
                    fatal=True,
                )
        else:
            valid = check(value)

        if not valid:
            notify.notify(
                f"--{name.replace('_', '-')}: {msg} (got: {value!r})",
                level=notify.CRITICAL if fatal else notify.ERROR,
            )

        return bool(valid)

    parser = argparse.ArgumentParser(
        prog="term-image",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description="Display/Browse images in a terminal",
        epilog=""" \

'--' should be used to separate positional arguments that begin with an '-' \
from options/flags, to avoid ambiguity.
For example, `$ term-image [options] -- -image.jpg --image.png`

NOTES:
  1. The displayed image uses HEIGHT/2 lines, while the number of columns is dependent
     on the WIDTH and the FONT RATIO.
     The auto sizing is calculated such that the image always fits into the available
     terminal size (i.e terminal size minus allowances) except when `-S` is
     specified, which allows the image height to go beyond the terminal height.
  2. The size is multiplied by the scale on each axis respectively before the image
     is rendered. A scale value must be such that 0.0 < value <= 1.0.
  3. In CLI mode, only image sources are used, directory sources are skipped.
     Animated images are displayed only when animation is disabled (with `--no-anim`)
     or when there's only one image source.
  4. Any image having more pixels than the specified maximum will be:
     - skipped, in CLI mode, if '--max-pixels-cli' is specified.
     - replaced, in TUI mode, with a placeholder when displayed but can still be forced
       to display or viewed externally.
     Note that increasing this should not have any effect on general performance
     (i.e navigation, etc) but the larger an image is, the more the time and memory
     it'll take to render it. Thus, a large image might delay the rendering of other
     images to be rendered immediately after it.
  5. Frames will not be cached for any animation with more frames than this value.
     Memory usage depends on the frame count per image, not this maximum count.
  6. Any event with a level lower than the specified one is not reported.
  7. Supports all image formats supported by `PIL.Image.open()`.
     See https://pillow.readthedocs.io/en/latest/handbook/image-file-formats.html for
     details.
""",
        add_help=False,  # '-h' is used for HEIGHT
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
        "--reset-config",
        action="store_true",
        help="Restore default config and exit (Overwrites the config file)",
    )
    general.add_argument(
        "-F",
        "--font-ratio",
        type=float,
        metavar="N",
        default=config.font_ratio,
        help=(
            "Specify the width-to-height ratio of a character cell in your terminal "
            f"for proper image scaling (default: {config.font_ratio})"
        ),
    )
    mode_options = general.add_mutually_exclusive_group()
    mode_options.add_argument(
        "--cli",
        action="store_true",
        help=(
            "Do not the launch the TUI, instead draw all image sources "
            "to the terminal directly [3]"
        ),
    )
    mode_options.add_argument(
        "--tui",
        action="store_true",
        help="Always launch the TUI, even for a single image",
    )

    # # Animation
    anim_options = parser.add_argument_group("Animation Options (General)")
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
        "-R",
        "--repeat",
        type=int,
        default=-1,
        metavar="N",
        help=(
            "Number of times to repeat all frames of an animated image; A negative "
            "count implies an infinite loop (default: -1)"
        ),
    )

    anim_cache_options = anim_options.add_mutually_exclusive_group()
    anim_cache_options.add_argument(
        "--anim-cache",
        type=int,
        default=config.anim_cache,
        metavar="N",
        help=(
            "Maximum frame count for animation frames to be cached (Better performance "
            f"at the cost of memory) (default: {config.anim_cache}) [5]"
        ),
    )
    anim_cache_options.add_argument(
        "--cache-all-anim",
        action="store_true",
        help=(
            "Cache frames for all animations (Beware, uses up a lot of memory for "
            "animated images with very high frame count)"
        ),
    )
    anim_cache_options.add_argument(
        "--cache-no-anim",
        action="store_true",
        help="Disable frame caching (Less memory usage but reduces performance)",
    )

    anim_options.add_argument(
        "--no-anim",
        action="store_true",
        help=(
            "Disable image animation. Animated images are displayed as just their "
            "first frame."
        ),
    )

    # # Transparency
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
        help=(
            "Allow the image height to go beyond the terminal height. "
            "Not needed when `--fit-to-width` is specified."
        ),
    )
    size_options.add_argument(
        "--fit-to-width",
        action="store_true",
        help=(
            "Automatically fit the image to the available terminal width. "
            "`--v-allow` has no effect i.e vertical allowance is overriden."
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
    cli_options.add_argument(
        "--max-pixels-cli",
        action="store_true",
        help=("Apply '--max-pixels' in CLI mode"),
    )

    # # Alignment
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
        (
            "These options apply only when there is at least one valid directory source"
            "or multiple valid sources"
        ),
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
        "-d",
        "--max-depth",
        type=int,
        metavar="N",
        default=sys.getrecursionlimit() - 50,
        help=f"Maximum recursion depth (default: {sys.getrecursionlimit() - 50})",
    )

    # Performance
    perf_options = parser.add_argument_group("Performance Options (General)")
    perf_options.add_argument(
        "--max-pixels",
        type=int,
        metavar="N",
        default=config.max_pixels,
        help=(
            "Maximum amount of pixels in images to be displayed "
            f"(default: {config.max_pixels}) [4]"
        ),
    )

    perf_options.add_argument(
        "--checkers",
        type=int,
        metavar="N",
        default=config.checkers,
        help=(
            "Maximum number of sub-processes for checking directory sources "
            f"(default: {config.checkers})"
        ),
    )
    perf_options.add_argument(
        "--getters",
        type=int,
        metavar="N",
        default=config.getters,
        help=(
            "Number of threads for downloading images from URL sources "
            "(default: {config.getters})"
        ),
    )
    perf_options.add_argument(
        "--grid-renderers",
        type=int,
        metavar="N",
        default=config.grid_renderers,
        help=(
            "Number of subprocesses for rendering grid cells "
            "(default: {config.grid_renderers})"
        ),
    )
    perf_options.add_argument(
        "--no-multi",
        action="store_true",
        help="Disable multiprocessing",
    )

    # Logging
    log_options_ = parser.add_argument_group(
        "Logging Options",
        "NOTE: These are mutually exclusive",
    )
    log_options = log_options_.add_mutually_exclusive_group()

    log_options_.add_argument(
        "-l",
        "--log-file",
        metavar="FILE",
        default=config.log_file,
        help=f"Specify a file to write logs to (default: {config.log_file})",
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
        "-q",
        "--quiet",
        action="store_true",
        help="No notifications, except fatal and config errors",
    )
    log_options.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="More detailed event reporting. Also sets logging level to INFO",
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
        nargs="*",
        metavar="source",
        help=(
            "Path(s) to local image(s) and/or directory(s) OR URLs. "
            "If no source is given, the current working directory is used."
        ),
    )

    args = parser.parse_args()
    MAX_DEPTH = args.max_depth
    RECURSIVE = args.recursive
    SHOW_HIDDEN = args.all

    if args.reset_config:
        store_config(default=True)
        sys.exit(SUCCESS)

    init_log(
        (
            args.log_file
            if config_options["log file"][0](args.log_file)
            else config.log_file
        ),
        getattr(_logging, args.log_level),
        args.debug,
        args.no_multi,
        args.quiet,
        args.verbose,
        args.verbose_log,
    )

    for details in (
        ("frame_duration", lambda x: x is None or x > 0.0, "must be greater than zero"),
        ("max_depth", lambda x: x > 0, "must be greater than zero"),
        (
            "max_depth",
            lambda x: (
                x + 50 > sys.getrecursionlimit() and sys.setrecursionlimit(x + 50)
            ),
            "too high",
            (RecursionError, OverflowError),
        ),
        ("repeat", lambda x: x != 0, "must be non-zero"),
    ):
        if not check_arg(*details):
            return INVALID_ARG

    for name, (is_valid, msg) in config_options.items():
        var_name = name.replace(" ", "_")
        value = getattr(args, var_name, None)
        # Not all config options have corresponding command-line arguments
        if value is not None and not is_valid(value):
            arg_name = f"--{name.replace(' ', '-')}"
            notify.notify(
                f"{arg_name}: {msg} (got: {value!r})",
                level=notify.ERROR,
            )
            notify.notify(
                f"{arg_name}: Using config value: {getattr(config, var_name)!r}",
                level=notify.WARNING,
            )
            setattr(args, var_name, getattr(config, var_name))

    set_font_ratio(args.font_ratio)

    log("Processing sources", logger, loading=True)

    file_images, url_images, dir_images = [], [], []
    contents = {}
    sources = [
        abspath(source) if exists(source) else source for source in args.sources or "."
    ]
    unique_sources = set()

    url_queue = Queue()
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

    file_queue = Queue()
    opener = Thread(
        target=open_files,
        args=(file_queue, file_images),
        name="Opener",
        daemon=True,
    )
    opener.start()

    os_is_unix = sys.platform not in {"win32", "cygwin"}

    if os_is_unix and not args.cli:
        dir_queue = mp_Queue() if logging.MULTI and args.checkers > 1 else Queue()
        dir_queue.sources_finished = False
        check_manager = Thread(
            target=manage_checkers,
            args=(dir_queue, contents, dir_images),
            name="CheckManager",
            daemon=True,
        )
        check_manager.start()

    for source in sources:
        if source in unique_sources:
            log(f"Source repeated: {source!r}", logger, verbose=True)
            continue
        unique_sources.add(source)

        if all(urlparse(source)[:3]):  # Is valid URL
            url_queue.put(source)
        elif isfile(source):
            file_queue.put(source)
        elif isdir(source):
            if args.cli:
                log(f"Skipping directory {source!r}", logger, verbose=True)
                continue
            if not os_is_unix:
                dir_images = True
                continue
            dir_queue.put(("", [], source, 0))
        else:
            log(f"{source!r} is invalid or does not exist", logger, _logging.ERROR)

    # Signal end of sources
    for _ in range(args.getters):
        url_queue.put(None)
    file_queue.put(None)
    if os_is_unix and not args.cli:
        if logging.MULTI and args.checkers > 1:
            dir_queue.sources_finished = True
        else:
            dir_queue.put((None,) * 4)

    for getter in getters:
        getter.join()
    opener.join()
    if os_is_unix and not args.cli:
        check_manager.join()

    notify.stop_loading()
    while notify.is_loading():
        pass

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
        for entry in images:
            image = entry[1]._image
            if args.max_pixels_cli and mul(*image._original_size) > args.max_pixels:
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
                notify.notify("\n" + basename(entry[0]) + ":")
            try:
                image.set_size(
                    args.width,
                    args.height,
                    args.h_allow,
                    args.v_allow,
                    fit_to_width=args.fit_to_width,
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
                    scroll=args.scroll,
                    animate=not args.no_anim,
                    repeat=args.repeat,
                    cached=(
                        not args.cache_no_anim
                        and (args.cache_all_anim or args.anim_cache)
                    ),
                    check_size=not args.oversize,
                )

            # Handles `ValueError` and `.exceptions.InvalidSize`
            # raised by `TermImage.set_size()`, scaling value checks
            # or padding width/height checks.
            except ValueError as e:
                notify.notify(str(e), level=notify.ERROR)
    elif os_is_unix:
        notify.end_loading()
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

# Initially set from within `.__main__.main()`
# Will be updated from `.logging.init_log()` if multiprocessing is enabled
interrupted: Union[None, Event, mp_Event] = None

# The annotations below are put in comments for compatibility with Python 3.7
# as it doesn't allow names declared as `global` within functions to be annotated.

# Used by `check_dir()`
_depth = None  #: int

# Set from within `check_dirs()`; Hence, only set in "Checker-?" processes
_dir_queue = None  #: Union[None, Queue, mp_Queue]
_free_checkers = None  #: Optional[Value]
_source = None  #: Optional[str]

# Set from within `main()`
MAX_DEPTH = None  #: Optional[int]
RECURSIVE = None  #: Optional[bool]
SHOW_HIDDEN = None  #: Optional[bool]
# # Used in other modules
args = None  #: Optional[argparse.Namespace]
url_images = None  #: Optional[list]
