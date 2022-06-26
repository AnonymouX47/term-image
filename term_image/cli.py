"""Term-Image's CLI Implementation"""

from __future__ import annotations

import logging as _logging
import os
import sys
import warnings
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

from . import (
    FontRatio,
    TermImageWarning,
    config,
    logging,
    notify,
    set_font_ratio,
    tui,
    utils,
)
from .config import config_options, store_config
from .exceptions import StyleError, TermImageError, URLNotFoundError
from .exit_codes import FAILURE, INVALID_ARG, NO_VALID_SOURCE, SUCCESS
from .image import BlockImage, ITerm2Image, KittyImage, _best_style
from .logging import Thread, init_log, log, log_exception
from .logging_multi import Process
from .tui.widgets import Image
from .utils import (
    CSI,
    OS_IS_UNIX,
    clear_queue,
    get_terminal_size,
    set_query_timeout,
    write_tty,
)


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
        if interrupted and interrupted.is_set():
            break
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
                interrupted.is_set()  # MainThread has been interrupted
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
                clear_queue(dir_queue)
                clear_queue(content_queue)
                clear_queue(progress_queue)
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
        while not interrupted.is_set() and source:
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
                elif not interrupted.is_set() and result is None:
                    log(f"{source!r} is empty", logger)
            _, links, source, _depth = dir_queue.get()

        if interrupted.is_set():
            clear_queue(dir_queue)


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
    ImageClass: type,
) -> None:
    """Processes URL sources from a/some separate thread(s)"""
    source = url_queue.get()
    while not interrupted.is_set() and source:
        log(f"Getting image from {source!r}", logger, verbose=True)
        try:
            images.append((basename(source), Image(ImageClass.from_url(source))))
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

    if interrupted.is_set():
        clear_queue(url_queue)


def open_files(
    file_queue: Queue,
    images: List[Tuple[str, Image]],
    ImageClass: type,
) -> None:
    source = file_queue.get()
    while not interrupted.is_set() and source:
        log(f"Opening {source!r}", logger, verbose=True)
        try:
            images.append((source, Image(ImageClass.from_file(source))))
        except PIL.UnidentifiedImageError as e:
            log(str(e), logger, _logging.ERROR)
        except OSError as e:
            log(f"Could not read {source!r}: {e}", logger, _logging.ERROR)
        except Exception:
            log_exception(f"Opening {source!r} failed", logger, direct=True)
        source = file_queue.get()

    if interrupted.is_set():
        clear_queue(file_queue)


def main() -> None:
    """CLI execution sub-entry-point"""
    from .parsers import parser, style_parsers

    global args, url_images, MAX_DEPTH, RECURSIVE, SHOW_HIDDEN

    warnings.filterwarnings("error", "", TermImageWarning, "term_image.image.iterm2")

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

    args = parser.parse_args()
    MAX_DEPTH = args.max_depth
    RECURSIVE = args.recursive
    SHOW_HIDDEN = args.all

    if args.reset_config:
        store_config(default=True)
        sys.exit(SUCCESS)

    force_cli_mode = not sys.stdout.isatty() and not args.cli
    if force_cli_mode:
        args.cli = True

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

    set_query_timeout(args.query_timeout)
    utils.SWAP_WIN_SIZE = args.swap_win_size

    if args.auto_font_ratio:
        args.font_ratio = None
    try:
        set_font_ratio(args.font_ratio or FontRatio.FULL_AUTO)
    except TermImageError:
        notify.notify(
            "Auto font ratio is not supported in the active terminal or on this "
            "platform, using 0.5. It can be set otherwise using `-F | --font-ratio`.",
            level=notify.WARNING,
        )
        args.font_ratio = 0.5

    ImageClass = {
        "auto": None,
        "kitty": KittyImage,
        "iterm2": ITerm2Image,
        "block": BlockImage,
    }[args.style]
    if not ImageClass:
        ImageClass = _best_style()
    args.style = ImageClass.__name__[:-5].lower()

    if args.force_style or args.style == config.style != "auto":
        ImageClass.is_supported()  # Some classes need to set some attributes
        ImageClass._supported = True
    else:
        try:
            ImageClass(None)
        except StyleError:  # Instantiation isn't permitted
            write_tty(f"{CSI}1K\r".encode())  # Erase emitted APCs
            log(
                f"The {args.style!r} render style is not supported in the current "
                "terminal! To use it anyways, add '--force-style'.",
                logger,
                level=_logging.CRITICAL,
            )
            return FAILURE
        except TypeError:  # Instantiation is permitted
            if not ImageClass.is_supported():  # Also sets any required attributes
                write_tty(f"{CSI}1K\r".encode())  # Erase emitted APCs
                log(
                    f"The {args.style!r} render style might not be fully supported in "
                    "the current terminal... using it anyways.",
                    logger,
                    level=_logging.WARNING,
                )

    # Some APCs (e.g kitty's) used for render style support detection get emitted on
    # some non-supporting terminal emulators
    write_tty(f"{CSI}1K\r".encode())  # Erase emitted APCs

    log(f"Using {args.style!r} render style", logger, verbose=True)
    style_parser = style_parsers.get(args.style)
    style_args = vars(style_parser.parse_known_args()[0]) if style_parser else {}

    if args.style == "iterm2":
        ITerm2Image.JPEG_QUALITY = style_args.pop("jpeg_quality")
        ITerm2Image.NATIVE_ANIM_MAXSIZE = style_args.pop("native_maxsize")
        ITerm2Image.READ_FROM_FILE = style_args.pop("read_from_file")

    try:
        style_args = ImageClass._check_style_args(style_args)
    except ValueError as e:
        notify.notify(str(e), level=notify.CRITICAL)
        return INVALID_ARG

    if force_cli_mode:
        log(
            "Output is not a terminal, forcing CLI mode!",
            logger,
            level=_logging.WARNING,
        )

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
            args=(url_queue, url_images, ImageClass),
            name=f"Getter-{n}",
        )
        for n in range(1, args.getters + 1)
    ]
    getters_started = False

    file_queue = Queue()
    opener = Thread(
        target=open_files,
        args=(file_queue, file_images, ImageClass),
        name="Opener",
    )
    opener_started = False

    if OS_IS_UNIX and not args.cli:
        dir_queue = mp_Queue() if logging.MULTI and args.checkers > 1 else Queue()
        dir_queue.sources_finished = False
        check_manager = Thread(
            target=manage_checkers,
            args=(dir_queue, contents, dir_images),
            name="CheckManager",
        )
    checkers_started = False

    for source in sources:
        if source in unique_sources:
            log(f"Source repeated: {source!r}", logger, verbose=True)
            continue
        unique_sources.add(source)

        if all(urlparse(source)[:3]):  # Is valid URL
            if not getters_started:
                for getter in getters:
                    getter.start()
                getters_started = True
            url_queue.put(source)
        elif isfile(source):
            if not opener_started:
                opener.start()
                opener_started = True
            file_queue.put(source)
        elif isdir(source):
            if args.cli:
                log(f"Skipping directory {source!r}", logger, verbose=True)
                continue
            if not OS_IS_UNIX:
                dir_images = True
                continue
            if not checkers_started:
                check_manager.start()
                checkers_started = True
            dir_queue.put(("", [], source, 0))
        else:
            log(f"{source!r} is invalid or does not exist", logger, _logging.ERROR)

    # Signal end of sources
    if getters_started:
        for _ in range(args.getters):
            url_queue.put(None)
    if opener_started:
        file_queue.put(None)
    if checkers_started:
        if logging.MULTI and args.checkers > 1:
            dir_queue.sources_finished = True
        else:
            dir_queue.put((None,) * 4)

    interrupt = None
    while True:
        try:
            if getters_started:
                for getter in getters:
                    getter.join()
            if opener_started:
                opener.join()
            if checkers_started:
                check_manager.join()
            break
        except KeyboardInterrupt as e:  # Ensure logs are in correct order
            if not interrupt:  # keep the first
                interrupted.set()
                interrupt = e
    if interrupt:
        raise interrupt from None

    notify.stop_loading()
    while notify.is_loading():
        pass

    if not OS_IS_UNIX and dir_images:
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

        if style_args.get("native") and len(images) > 1:
            style_args["stall_native"] = False

        show_name = len(args.sources) > 1
        for entry in images:
            image = entry[1]._ti_image
            if args.max_pixels_cli and mul(*image._original_size) > args.max_pixels:
                log(
                    f"Has more than the maximum pixel-count, skipping: {entry[0]!r}",
                    logger,
                    level=_logging.WARNING,
                    verbose=True,
                )
                continue

            if (
                not args.no_anim
                and image._is_animated
                and not style_args.get("native")
                and len(images) > 1
            ):
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

                if args.style == "kitty":
                    image.set_render_method(
                        "lines"
                        if ImageClass._KITTY_VERSION and image._is_animated
                        else "whole"
                    )
                elif args.style == "iterm2":
                    image.set_render_method(
                        "whole"
                        if (
                            ImageClass._TERM == "konsole"
                            # Always applies to non-native animations also
                            or image.rendered_height <= get_terminal_size()[1]
                        )
                        else "lines"
                    )

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
                        else (
                            args.alpha if args.alpha_bg is None else "#" + args.alpha_bg
                        )
                    ),
                    scroll=args.scroll,
                    animate=not args.no_anim,
                    repeat=args.repeat,
                    cached=(
                        not args.cache_no_anim
                        and (args.cache_all_anim or args.anim_cache)
                    ),
                    check_size=not args.oversize,
                    **style_args,
                )

            # Handles `ValueError` and `.exceptions.InvalidSizeError`
            # raised by `BaseImage.set_size()`, scaling value checks
            # or padding width/height checks.
            except (ValueError, StyleError, TermImageWarning) as e:
                notify.notify(str(e), level=notify.ERROR)
    elif OS_IS_UNIX:
        notify.end_loading()
        tui.init(args, style_args, images, contents, ImageClass)
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
