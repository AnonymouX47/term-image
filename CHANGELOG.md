# Changelog
All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]


## [0.3.0] - 2022-04-26
### Fixed
- [lib] Fixed the *scroll* parameter of `TermImage.draw()` ([#29](https://github.com/AnonymouX47/term-image/pull/29)).
- [tui] Fixed TUI crashing when "max notifications" config option is set to `0`.
- [cli,tui] Fixed handling of some errors in the viewer ([#33](https://github.com/AnonymouX47/term-image/pull/33)).

### Changed
- Renamed the project, CLI executable, top-level package and user directory ([#28](https://github.com/AnonymouX47/term-image/pull/28))
- [lib] Changed sizing units to columns and lines ([#29](https://github.com/AnonymouX47/term-image/pull/29)).
- [lib] Padding width is now validated only when drawing to the terminal (via `TermImage.draw()`) ([#32](https://github.com/AnonymouX47/term-image/pull/32)).
- [cli,tui] Updated the viewer's exit codes ([#33](https://github.com/AnonymouX47/term-image/pull/33)).
- [test] Updated and re-organized the test suite ([#31](https://github.com/AnonymouX47/term-image/pull/31)).

### Deprecated
- [lib] Deprecated top-level package name `term_img` ([#28](https://github.com/AnonymouX47/term-image/pull/28)).

### Removed
- [lib] Removed "size too small" check and exception when setting size ([#29](https://github.com/AnonymouX47/term-image/pull/29)).


## [0.2.0] - 2022-04-16
### Fixed
- [lib] Size validation is no longer forced for non-animated drawing of animated images.
- [cli] Properly handled unexpected exceptions while processing file and URL sources.
- [cli] All error messages are written directly to the console go to STDERR.
- [cli] Fixed deadblock when the program exits immediately after parsing arguments.
- [cli] "Opening ..." logs and notifications for file sources.
- [tui] Fixed switching back to the normal buffer after the TUI exits on some terminals.
- [tui] Greatly reduced delay in displaying grids.
- [tui] The grid cell in focus now retains focus, no matter the changes in grid or cell size.
- [cli,tui] Handled indirectly cyclic symlinks.
- [cli,tui,config] Corrected all platform-dependent path separators.

### Added
- [lib] `term_img.image.ImageIterator` for efficient iteration over rendered frames of animated images.
- [lib] Iteration support for `TermImage`.
- [lib] *scroll*, *repeat* and *cached* parameters to `TermImage.draw()`.
- [cli] Parallel and concurrent processing of sources, using multiprocessing and multithreading.
- [cli] Command-line argument value checks.
- [cli] `INVALID_ARG` exit code for invalid command-line argument values.
- [cli] `--max-pixels-cli` to apply "max pixels" config and `--max-pixels` in CLI mode.
- [cli] `--reset-config` to restore default configurations.
- [cli] Animation-related command-line options: `--repeat`, `--anim-cache`, `--cache-all-anim`, `--cache-no-anim`.
- [cli] Performance-related command-line options: `--checkers`, `--getters`, `--grid-renderers`, `--no-multi`.
- [tui] Menu list numbering/count.
- [tui] Asynchronous updating of the menu list and grid views.
- [tui] Asynchronous and gradual rendering of grid cells.
- [tui] Asynchronous image rendering.
- [tui] Implemented "Force Render" action in view contexts for animated images.
- [tui] Progress indication.
- [cli,tui] Maximum recursion depth functionality with -d | --max-depth`.
- [cli,tui] QUIET mode with `-q | --quiet`.
- [cli,tui] Separate color for WARNING-level console notifications.
- [cli,tui] `processName` and `threadName` log fields (only at DEBUG logging level).
- [cli,tui] Full exception log when a session is terminated due to an exception.
- [config] New config options: `anim cache`, `log file`, `max notifications`, `checkers`, `getters` and `grid renderers`.
- [cli,config] Descriptive error messages for config options (and the correspoding command-line options, if there is).

### Changed
- Bumped Pillow minimum version to 9.1.0 (because of [Pillow #6077](https://github.com/python-pillow/Pillow/pull/6077))
- Bumped requirement versions:
  - Pillow -> 9.1.0
  - requests -> 2.27.1
  - black -> 22.3.0
- [lib] The cursor is now hidden while drawing images.
- [lib] `TermImage.source` now gives the absolute file path for file-sourced instances instead of the real path.
- [lib] Deferred frame count computation till `TermImage.n_frames` is first invoked.
- [lib] Animated image frame duration is now derived from the image metadata, if available.
- [lib] The names and semantics of some parameters of `TermImage.set_size()`:
  - `check_height` -> `fit_to_width`
  - `check_width` -> `fit_to_height`
- [lib] Renamed `ignore_oversize` paramter of `TermImage.draw()` to `check_size` and modified the semantics accordingly.
- [lib,cli,tui] Improved image animation performance.
- [lib,cli,tui] Automatic caching of animation frames is now based on number of frames.
- [cli] The current working directory is used if no source is specified.
- [cli] Allowed abbreviation of options and clustering in Python 3.7.
- [cli] Modified the semantics of `--scroll`, `--fit-to-width` and `--oversize`.
- [cli] Optimized non-recursive directory checks.
- [cli] File and URL sources are now processed concurrently.
- [cli] Directory sources are now processed in parallel with one another and with file and URL sources, if supported.
  - Otherwise they are processed sequentially with one another and concurrently with file and URL sources.
- [cli] Disabled processing of directory sources on Windows, since the TUI is not supported.
- [tui] Faulty image loads are now reported only once per image, per directory scan.
- [tui] Changed entry sorting and grouping order.
- [tui] Improved grid display and grid cell rendering performance.
- [tui] Improved directory scanning and entry sorting performance.
- [cli,tui] Using absolute paths in place of real paths; Better handling of symlinks.
- [cli,tui] Upgraded the logging system.
- [config] Stylized config messages.
- [config] Improved config update routine.
- [config] Limited `cell width` option to the range `30 <= x <= 50`.
- [tui,config] Prepended the symbols of all uppercase keys with '⇧' (U+21e7)

### Removed
- [lib] size validation when setting render size based on the terminal size.
- [lib,cli,tui] Support for Python 3.6.
- [config] `frame duration` config option.


## [0.1.1] - 2022-01-29
### Added
- First official release


[Unreleased]: https://github.com/AnonymouX47/term-image/compare/v0.3.0...HEAD
[0.3.0]: https://github.com/AnonymouX47/term-image/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/AnonymouX47/term-image/compare/v0.1.1...v0.2.0
[0.1.1]: https://github.com/AnonymouX47/term-image/releases/tag/v0.1.1
