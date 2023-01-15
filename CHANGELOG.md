# Changelog
All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]
### Fixed
- [lib,cli] Uppercase letters in hex BG colors being flagged as invalid ([b4533d5])

[b4533d5]: https://github.com/AnonymouX47/term-image/commit/b4533d5697d41fe0742c2ac895077da3b8d889dc


## [0.5.0] - 2023-01-09
### Fixed
- [lib] Race condition in `term_image.utils.lock_tty()` multi-process integration ([#66]).
- [cli,config] `--log-file` and "log file" validation ([#69]).
- [cli,config] Render style force condition ([#67]).
- [tui] TUI crash when menu or grid has zero rows ([4219010]).
- [tui] Image canvas trim calculations for grid cells ([30ed143]).
- [config] Initialization/Updating of TUI keybindings ([#69]).

### Added
- [lib] `term_image.image.Size` enumeration ([#64]).
  - Implemented "original size" image sizing.
- [lib] `term_image.utils.DISABLE_QUERIES` to disable terminal queries ([#66]).
- [lib] Multi-process synchronization for terminal window size caching ([#66]).
  - Significant effect (positive) on cell ratio and image size computation when using multiprocessing.
- [lib] `clear()` method to each of `KittyImage` and `Iterm2Image` ([#67]).
- [lib] Render style metaclass `.image.ImageMeta` with a `style` property ([#67]).
- [lib] Auto cell ratio support status override; `AutoCellRatio.is_supported` ([#68])
- [cli] `--fit` and `--original-size` CL options ([#64]).
- [config] Support for partial configs ([#69]).
- [config] An upper limit of 5 for the "max notifications" option ([#69]).
- [cli,config] `--config` and `--no-config` CL options ([#69]).

### Changed
- [lib] **(BREAKING!)** Changed the default value of `size`, `width` and `height` properties to `Size.FIT` ([#64]).
- [lib] Updated `BaseImage.set_size()` ([#64]).
  - **(BREAKING!)** Removed *fit_to_width* and *fit_to_height* parameters.
  - Now accepts `Size` enum mumbers.
  - Refer to the linked PR for others.
- [lib] Moved `TermImageWarning` from the top-level into `term_image.exceptions`.
- [lib] Refactored and improved various utilities ([#66]).
  - `TermImageWarning` is now issued instead of `Userwarning` when not running in a terminal or multi-process synchronization is unsupported.
- [lib] `str(ImageClass)` now returns the name of the render style (or category) ([#67]).
- [lib] **(BREAKING!)** Changed `FontRatio` -> `AutoCellRatio` ([#68])
  - Renamed modes `AUTO` -> `FIXED` and `FULL_AUTO` -> `DYNAMIC`
- [cli] Changed default sizing to `Size.AUTO` ([#64]).
- [cli] Changed default padding height to `1` i.e no vertical padding ([#64]).
- [tui] Changed sizing to `Size.AUTO` for all images ([#64]).
- [tui] An image/frame is re-rendered only when its size changes, regardless of the canvas size ([#64]).
- [config] Now respects the XDG Base Directories Specification ([#69]).
- [config] User config is now initialized after command-line arguments have been parsed ([#69]).
- [config] Renamed "no multi" to "multi" ([#69]).
- **(BREAKING!)** "FONT ratio" -> "CELL ratio" ([#68])
  - `term_image.get_font_ratio()` -> `term_image.get_cell_ratio()`
  - `term_image.set_font_ratio()` -> `term_image.set_cell_ratio()`
  - `-F/--font-ratio` -> `-C/--cell-ratio`
  - `--auto-font-ratio` -> `--auto-cell-ratio`
  - config option "font ratio" -> "cell ratio"
  - etc...

### Removed
- [lib] `term_image.image.TermImage`.
- [lib] `TermImageException` and `InvalidSize` from `term_image.exceptions`.
- [lib] Top-level package `term_img`.

[#64]: https://github.com/AnonymouX47/term-image/pull/64
[#66]: https://github.com/AnonymouX47/term-image/pull/66
[#67]: https://github.com/AnonymouX47/term-image/pull/67
[#68]: https://github.com/AnonymouX47/term-image/pull/68
[#69]: https://github.com/AnonymouX47/term-image/pull/69
[4219010]: https://github.com/AnonymouX47/term-image/commit/4219010dc40981f99b2a63fafbf382ddc0cb895d
[30ed143]: https://github.com/AnonymouX47/term-image/commit/30ed14312eb5c0667ab76897bc183511b62367e1


## [0.4.1] - 2022-07-30
### Added
- [tui] Handling for exceptions raised while rendering animation frames.
- [docs] Interface stability status notice.

### Fixed
- [lib] `term_image.image.ImageSource` enum.
- [lib] Accidental closure of the PIL image instance being used by an `ImageIterator` instance.
- [lib] `ImageIterator` now caches frames by the image's rendered size, not the unscaled size.
- [lib] `ImageIterator.seek()` now raises `TermImageError` after the iterator has been exhausted/finalized.
- [lib] Placement of linebreaks in image bottom padding.
- [lib] Fixed some utilities.
- [cli] Errors in CLI help text.
- [tui] Handling of crashes in the TUI, particularly when multiprocessing is enabled.
- [tui] Image and animation rendering.

See the commit messages for [0.4.1] for the full logs.


## [0.4.0] - 2022-06-27
### Fixed
- [lib] Directly adjusting image seek position no longer affects iteration with `ImageIterator` ([#42]).
- [lib] BG colors not being drawn when equal to the terminal's default BG color, with 'block' render style on the Kitty terminal emulator ([#54]).
- [cli] Handling of `SIGINT` while processing sources ([#56]).
- [tui] Intensive performance drop while populating large image grids ([#41]).
- [tui] Navigation across animated images ([#42]).
  - No more waiting for the first frame to be rendered before moving on.
- [tui] Deadlocks and some exceptions raised upon exiting the TUI ([#43]).

### Added
- [lib] A common interface to be shared across all image classes ([#34]).
- [lib] `BaseImage`, the baseclass of all image classes ([#34]).
- [lib] `is_supported()` class method for render style support detection ([#34]).
- [lib] `term_image.utils` submodule. ([#34], [#36])
- [lib] Convenience functions for automatic render style selection ([#37]).
  - `AutoImage()`, `from_file()` and `from_url()` in `term_image.image`.
- [lib] `BaseImage.source_type` property ([#38]).
- [lib] `KittyImage` class ([#39]).
- [lib] Support for multiple render methods per render style via `BaseImage.set_render_method()` ([#39]).
- [lib] Non-linear image iteration via `ImageIterator.seek()` ([#42]).
- [lib] Image category subclasses (of `BaseImage`), `TextImage` and `GraphicsImage` ([#44]).
- [lib] Automatic font ratio computation ([#45]).
- [lib] `term_image.FontRatio` enumeration class ([#45]).
- [lib] Support for style-specific parameters and format specification ([#47]).
- [lib] Style-specific exception classes ([#47]).
- [lib] `ITerm2Image` class, `iterm2` render style; Support for the iTerm2 inline image protocol ([#50]).
- [lib] `term_image.TermImageWarning`; pacage specific warning category ([#50]).
- [lib] Auto background color i.e using the terminal's default BG color for transparent images ([#54]).
- [lib] `ImageIterator.loop_no` property ([7de6b4a]).
- [cli] `--style` command-line option for render style selection ([#37]).
- [cli] `kitty` render style choice for the `--style` command-line option ([#39]).
- [cli] `--force-style` to bypass render style support checks ([#44]).
- [cli] `--auto-font-ratio` for automatic font ratio determination ([#45]).
- [cli] Support for style-specific options ([#47]).
- [cli] `--kz/--kitty-z-index` 'kitty' style-specific option ([#49]).
- [cli] `iterm2` render style choice for the `--style` command-line option ([#50]).
- [cli] `--itn/--iterm2-native` and `--itn-max/--iterm2-native-maxsize` style-specific CL options for 'iterm2' native animation ([#50]).
- [cli] `--kc/--kitty-compress` 'kitty' style-specific option ([#51]).
- [cli] `--query-timeout` command-line option ([3b658f3]).
- [cli] `--itc/--iterm2-compress`, `--itjq/--iterm2-jpeg-quality` and `--itnrff/iterm2-no-read-from-file` style-specific command-line options ([#55]).
- [cli] `-multi` command-line option ([2c2d240]).
- [cli] `--swap_win_size` and `--no-swap_win_size` command-line options ([4f9178f]).
- [tui] Concurrent/Parallel frame rendering for TUI animations ([#42]).
- [tui] Key codes in the help menu ([bd87a3b]).
- [cli,tui] `no multi`, `query timeout` and `style` config options ([2c2d240]).
- [cli,tui] Attempt to set window title at startup ([5a2976a]).
- [cli,tui] `swap win size` config option ([4f9178f]).
- [lib,cli,tui] Support for the Kitty terminal graphics protocol ([#39]).
- [lib,cli,tui] Automatic render style selection based on the detected terminal support ([#37]).

### Changed
- [lib] `TermImage` is now a subclass of `BaseImage` ([#34]).
- [lib] Instantiation via the class constructor now initializes the seek position of animated images to the current seek position of the given PIL image ([#34]).
- [lib] On UNIX, the library now attempts to determine the proper terminal device to use when standard streams are redirected to files or pipes ([#36]).
- [lib] `BaseImage.source` now raises `TermImageException` when invoked after the instance has been finalized ([#38]).
- [lib] Improved `repr()` of image instances ([#38]).
- [lib] Direct baseclass of `TermImage` to `TextImage` ([#44]).
- [lib] `TermImage` to `BlockImage` ([#46]).
- [lib] Exception naming scheme ([#46]).
  - `TermImageException` to `TermImageError`.
  - `InvalidSize` to `InvalidSizError`.
- [lib] Image resampling method from `BICUBIC` to `BOX` ([#54]).
- [lib] Transparent renders in text-based styles are now partially blended with the terminal's BG color ([#54]).
- [lib] Optimized image render data computation and image formatting ([#54]).
- [cli] `-S` from `--scroll` to `--style` ([#44]).
- [cli] CLI mode is now forced when output is not a TTY ([#56]).
- [cli,tui] Changed default value of `font ratio` config option to `null` ([#45]).
- [cli,tui] Improved startup speed and source processing ([#56]).
- [cli,tui] Improved config error handling ([#56]).

### Deprecated
- [lib] `term_image.image.TermImage` ([#46]).
- [lib] `TermImageException` and `InvalidSize` in `term_image.exceptions` ([#46]).

[#34]: https://github.com/AnonymouX47/term-image/pull/34
[#36]: https://github.com/AnonymouX47/term-image/pull/36
[#37]: https://github.com/AnonymouX47/term-image/pull/37
[#38]: https://github.com/AnonymouX47/term-image/pull/38
[#39]: https://github.com/AnonymouX47/term-image/pull/39
[#41]: https://github.com/AnonymouX47/term-image/pull/41
[#42]: https://github.com/AnonymouX47/term-image/pull/42
[#43]: https://github.com/AnonymouX47/term-image/pull/43
[#44]: https://github.com/AnonymouX47/term-image/pull/44
[#45]: https://github.com/AnonymouX47/term-image/pull/45
[#46]: https://github.com/AnonymouX47/term-image/pull/46
[#47]: https://github.com/AnonymouX47/term-image/pull/47
[#49]: https://github.com/AnonymouX47/term-image/pull/49
[#50]: https://github.com/AnonymouX47/term-image/pull/50
[#51]: https://github.com/AnonymouX47/term-image/pull/51
[#54]: https://github.com/AnonymouX47/term-image/pull/54
[#55]: https://github.com/AnonymouX47/term-image/pull/55
[#56]: https://github.com/AnonymouX47/term-image/pull/56
[3b658f3]: https://github.com/AnonymouX47/term-image/commit/3b658f388db8e36bc8f4d42c77375cd7c3593d4b
[7de6b4a]: https://github.com/AnonymouX47/term-image/commit/7de6b4a3173dd70c89d38d3851be9c7dceae4ab7
[2c2d240]: https://github.com/AnonymouX47/term-image/commit/2c2d240f25154d7d9491a7cbc943b6f5811a408d
[5a2976a]: https://github.com/AnonymouX47/term-image/commit/5a2976abe913f7039be8dc98eee90283a2d5883d
[bd87a3b]: https://github.com/AnonymouX47/term-image/commit/bd87a3b7d44273112387b3a6b864c601c8b77a52
[4f9178f]: https://github.com/AnonymouX47/term-image/commit/4f9178f8260c95c4b521b27b6924bd14fb4cc4ed


## [0.3.1] - 2022-05-04
### Fixed
- [cli,tui] Fixed image viewer crash on Python 3.7.


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


[Unreleased]: https://github.com/AnonymouX47/term-image/compare/v0.5.0...HEAD
[0.5.0]: https://github.com/AnonymouX47/term-image/compare/v0.4.0...v0.5.0
[0.4.1]: https://github.com/AnonymouX47/term-image/compare/v0.4.0...v0.4.1
[0.4.0]: https://github.com/AnonymouX47/term-image/compare/v0.3.0...v0.4.0
[0.3.1]: https://github.com/AnonymouX47/term-image/compare/v0.3.0...v0.3.1
[0.3.0]: https://github.com/AnonymouX47/term-image/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/AnonymouX47/term-image/compare/v0.1.1...v0.2.0
[0.1.1]: https://github.com/AnonymouX47/term-image/releases/tag/v0.1.1
