# Changelog
All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]
### Fixed
- `AttributeError` in some top-level functions ([497d9b7])
- Formatting of some `ValueError` exception messages ([d296a31])

### Added
- `term_image.geometry` submodule ([#96]).
  - `term_image.geometry.Size`.

### Changed
- `term_image.utils.get_cell_size()` now returns `term_image.geometry.Size` instances in place of tuples ([#96]).


[#96]: https://github.com/AnonymouX47/term-image/pull/96
[497d9b7]: https://github.com/AnonymouX47/term-image/commit/497d9b70dd74605e6589b81bea2fcac22efc684b
[d296a31]: https://github.com/AnonymouX47/term-image/commit/d296a3110882449f6717959400abbc5fa1bd0891


## [0.7.0] - 2023-06-05
### Fixed
- Jagged edges with `LINES` render method of kitty and iterm2 render styles ([4d27055]).

### Added
- `UrwidImageScreen.clear_images()` ([08f4e4d], [8b895ce]).
- `term_image.utils.get_cell_size()` to the public API ([#87]).
- Support for terminal size-relative frame sizes ([#89]).
- Manual sizing ([#89]).
  - Allows setting both width and height explicitly via:
    - `BaseImage.set_size()`
    - `BaseImage.size`
- Support for terminal size-relative padding ([#91]).
- `ANIM` render method to the `iterm2` render style ([#92]).
- `term_image.exceptions.RenderError` ([#94]).

### Changed
- `KeyboardInterrupt` is no longer raised when `SIGINT` is used to end an animation ([fa47742]).
- `UrwidImageScreen.clear()` now clears images also ([ed3baa3]).
- Improved terminal cell size computation ([#87]).
- **(BREAKING!)** `InvalidSizeError` no longer inherits from `ValueError` ([26ea969]).
- **(BREAKING!)** `UrwidImage` now raises `UrwidImageError` instead of `ValueError` when rendered as a fixed widget ([a612b59]).
- **(BREAKING!)** Setting image size with `Size.FIT_TO_WIDTH` no longer influences size validation ([#89]).
- **(BREAKING!)** Redefined `BaseImage.set_size()` ([#89]).
  - Now allows specifying both *width* and *height* but only as integers.
    - No longer raises `ValueError`.
    - Now raises `TypeError` when both *width* and *height* are not `None` but not both are integers.
  - Redefined the *maxsize* parameter as *frame_size*.
    - No longer accepts `None`.
    - Now accepts non-positive integer tuple elements.
  - No longer raises `ValueError`: Available size too small.
  - No longer checks if the resulting size fits into a given frame size when *width* or *height* is also given as an integer.
    - No longer raises `InvalidSizeError`.
- **(BREAKING!)** Redefined *pad_width* and *pad_height* formatting parameters ([#91]).
  - No longer accept `None`.
  - Now accept non-positive integers.
  - Changed default values to `0` and `-2` respectively.
- **(BREAKING!)** Changed `N` to `A` in the *method* field of the `iterm2` style-speific render format specification ([#92]).
- **(BREAKING!)** `term_image.exceptions.StyleError` is now raised instead of style-specific exceptions ([#93]).
- **(BREAKING!)** `term_image.exceptions.RenderError` is now raised for errors that occur during rendering ([#94]).
- **(BREAKING!)** `BaseImage.forced_support` can no longer be set via instances ([#95]).
- **(BREAKING!)** `ITerm2Image.native_anim_max_bytes` can no longer be set or deleted via instances ([#95]).

### Removed
- `UrwidImage.clear_all()` ([08f4e4d]) and `UrwidImage.clear()` ([8b895ce]).
  - Replaced by `UrwidImageScreen.clear_images()`.
- Image scaling ([#88]).
  - *scale* parameter of `BaseImage`, `BaseImage.from_file()`, `BaseImage.from_url()`, etc.
  - `scale`, `scale_x` and `scale_y` properties of `BaseImage`.
  - Replaced by manual sizing ([#89]).
- Image sizing allowance ([#89]).
  - *h_allow* and *v_allow* parameters of `BaseImage.set_size()`.
  - Replaced by terminal size-relative frame sizes ([#89]) and padding ([#91]).
- *native* and *stall_native* `iterm2` style-specific render parameters ([#92]).
  - Replaced by the `ANIM` render method.
- Style-specific exceptions ([#93]).
  - `GraphicsImageError`
  - `TextImageError`
  - `BlockImageError`
  - `ITerm2ImageError`
  - `KittyImageError`
- Render style name property and custom render style class string representation ([7d673dd]).
  - `<Style>Image.style`
  - `str(<Style>Image)`
- `term_image.image.ImageMeta` from the public API ([9168d17]).

[#87]: https://github.com/AnonymouX47/term-image/pull/87
[#88]: https://github.com/AnonymouX47/term-image/pull/88
[#89]: https://github.com/AnonymouX47/term-image/pull/89
[#91]: https://github.com/AnonymouX47/term-image/pull/91
[#92]: https://github.com/AnonymouX47/term-image/pull/92
[#93]: https://github.com/AnonymouX47/term-image/pull/93
[#94]: https://github.com/AnonymouX47/term-image/pull/94
[#95]: https://github.com/AnonymouX47/term-image/pull/95
[08f4e4d]: https://github.com/AnonymouX47/term-image/commit/08f4e4d1514313bbd4278dadde46d21d0b11ed1f
[fa47742]: https://github.com/AnonymouX47/term-image/commit/fa477424c83474256d4972c4b2cdd4a765bc1cda
[ed3baa3]: https://github.com/AnonymouX47/term-image/commit/ed3baa38d7621720c007f4662f89d7abadd76ec3
[26ea969]: https://github.com/AnonymouX47/term-image/commit/26ea969ab7a36994bce6b75ce73ee699a085934e
[a612b59]: https://github.com/AnonymouX47/term-image/commit/a612b5916778c1dea5d97fa2e7344251e9d8c33c
[4d27055]: https://github.com/AnonymouX47/term-image/commit/4d27055ab1729cb93bbf4bb4531a0157b8cf513f
[7d673dd]: https://github.com/AnonymouX47/term-image/commit/7d673ddbdf7913ae4d134e98bb81fa3fce9701ff
[9168d17]: https://github.com/AnonymouX47/term-image/commit/9168d17ace06b09153b0424c52b7052b746f7165
[8b895ce]: https://github.com/AnonymouX47/term-image/commit/8b895ce80cb1b7b1e692e98afd87ecb8c145f40c


## [0.6.1] - 2023-04-30
### Fixed
- Terminal queries during synced updates by `UrwidImageScreen` ([7191885]).
- Multi-process synchronization ([238777b]).
- `UrwidImage` instances with kitty-style images ([2006052]).
- Ignored exception during `UrwidImage` finalization on Python 3.7 ([4c19c11]).

[7191885]: https://github.com/AnonymouX47/term-image/commit/71918852bf1ca5cd42f3ec4cf72a35eb878ffb3c
[238777b]: https://github.com/AnonymouX47/term-image/commit/238777badfa50418edce5aedc3a88e247f24cc5d
[2006052]: https://github.com/AnonymouX47/term-image/commit/20060520c2d9ad4fc9445bf911b796c5cdf49161
[4c19c11]: https://github.com/AnonymouX47/term-image/commit/4c19c1173dd942923945bfbea02f8a1f3459ea14


## [0.6.0] - 2023-03-30
### Fixed
- Resource leaks via unclosed PIL image instances ([cdc6650]).
- Unhandled initialization of images with null-sized PIL image instances ([54665f8]).
- 'iterm2' render output on non-Konsole terminal emulators when rendered height is `1`, for WHOLE render method and native animations ([f82aef0]).
- Uppercase letters in hex BG colors being flagged as invalid ([b4533d5]).

### Added
- `term_image.image.auto_image_class()` ([538d408] in [#70], [45898e8]).
- `BaseImage.forced_support` for render style forced support ([5979612] in [#70], [889a4ca]).
- `term_image.DEFAULT_QUERY_TIMEOUT` ([be603f7] in [#70], [#82]).
- New utilities in `term_image.utils` ([#70]):
  - `get_terminal_name_version()`
  - `get_terminal_size()`
  - `read_tty_all()`
  - `write_tty()`
- Support for clearing *kitty* images by z-index ([97eceab]).
- Support for clearing *iterm2* images on konsole by intersection with cursor position ([807a9ec]).
- Widgets and related classes to display images with [urwid](https://urwid.org) ([#73]).
  - `term_image.widget` subpackage
  - `term_image.widget.UrwidImage`
  - `term_image.widget.UrwidImageCanvas`
  - `term_image.widget.UrwidImageScreen`
    - Support for terminal-synchronized output ([#80]).
- Support for path-like objects as image sources ([f359d4e]).

### Changed
- **(BREAKING!)** Redefined `KittyImage.clear()` ([97eceab]).
- **(BREAKING!)** Changed the valid values for the `z_index` style-specific parameter of the *kitty* render style ([#74]).
- Computed image size and `image.rendered_size` (regardless of the value of `image.scale`) can no longer be null (contain `0`) ([#78]).
  - No more "Image size or scale too small" error at render time.
- **(BREAKING!)** Redefined gloabl settings and moved all to package top-level ([#82]).
  - `term_image.utils.set_query_timeout()` -> `term_image.set_query_timeout()`
  - `term_image.utils.DISABLE_QUERIES` -> `term_image.disable_queries()` and `term_image.enable_queries()`
  - `term_image.utils.SWAP_WIN_SIZE` -> `term_image.enable_win_size_swap()` and `term_image.disable_win_size_swap()`
- Removed restrictions on iterm2 native animation ([#84]).
- Replaced `ITerm2Image` class variables with class and class/instance properties ([c4050bd]).
  - `JPEG_QUALITY` -> `jpeg_quality`
  - `NATIVE_ANIM_MAXSIZE` -> `native_anim_max_bytes`
  - `READ_FROM_FILE` -> `read_from_file`
- Store downloaded image files in an OS/env-specific temporary directory ([1750e75]).

### Removed
- The CLI and TUI ([#72]).
- `term_image.utils.read_tty()` from the public API ([#70]).

[#70]: https://github.com/AnonymouX47/term-image/pull/70
[#72]: https://github.com/AnonymouX47/term-image/pull/72
[#73]: https://github.com/AnonymouX47/term-image/pull/73
[#74]: https://github.com/AnonymouX47/term-image/pull/74
[#78]: https://github.com/AnonymouX47/term-image/pull/78
[#80]: https://github.com/AnonymouX47/term-image/pull/80
[#82]: https://github.com/AnonymouX47/term-image/pull/82
[#84]: https://github.com/AnonymouX47/term-image/pull/84
[b4533d5]: https://github.com/AnonymouX47/term-image/commit/b4533d5697d41fe0742c2ac895077da3b8d889dc
[97eceab]: https://github.com/AnonymouX47/term-image/commit/97eceab77e7448a18281aa6edb3fa8ec9e6564c5
[807a9ec]: https://github.com/AnonymouX47/term-image/commit/807a9ecad717e46621a5214dbf849369d3afbc0b
[cdc6650]: https://github.com/AnonymouX47/term-image/commit/cdc665021cc293b0fb5c0519177287752ef64dc4
[54665f8]: https://github.com/AnonymouX47/term-image/commit/54665f8a1ceb60107b6ae2cc098ef8652d4dabbe
[f82aef0]: https://github.com/AnonymouX47/term-image/commit/f82aef0c0fc59832a2979a26b70e575a01c08910
[c4050bd]: https://github.com/AnonymouX47/term-image/commit/c4050bdcb7a642baa0d03560b392f5add9d9d399
[889a4ca]: https://github.com/AnonymouX47/term-image/commit/889a4ca154c05e5f86ed1dc53158b588b6e525a8
[538d408]: https://github.com/AnonymouX47/term-image/pull/70/commits/538d408c8c4aed8ed7e65bd439eb955992a227ea
[5979612]: https://github.com/AnonymouX47/term-image/pull/70/commits/59796123d4861ae8d1a8bfd6dc5c5ebf2d030ded
[be603f7]: https://github.com/AnonymouX47/term-image/pull/70/commits/be603f7817ebd11f9ad4a7de093eadd47dafe05a
[1750e75]: https://github.com/AnonymouX47/term-image/commit/1750e75950de83e0b926ca7b5b670c906e80ccad
[f359d4e]: https://github.com/AnonymouX47/term-image/commit/f359d4edcb1be0f1021b56c1d18f54fde302c3b2
[45898e8]: https://github.com/AnonymouX47/term-image/commit/45898e80eebd976fb839d1d0476bb4a6e431bd68


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


[Unreleased]: https://github.com/AnonymouX47/term-image/compare/v0.7.0...HEAD
[0.7.0]: https://github.com/AnonymouX47/term-image/compare/v0.6.0...v0.7.0
[0.6.1]: https://github.com/AnonymouX47/term-image/compare/v0.6.0...v0.6.1
[0.6.0]: https://github.com/AnonymouX47/term-image/compare/v0.5.0...v0.6.0
[0.5.0]: https://github.com/AnonymouX47/term-image/compare/v0.4.0...v0.5.0
[0.4.1]: https://github.com/AnonymouX47/term-image/compare/v0.4.0...v0.4.1
[0.4.0]: https://github.com/AnonymouX47/term-image/compare/v0.3.0...v0.4.0
[0.3.1]: https://github.com/AnonymouX47/term-image/compare/v0.3.0...v0.3.1
[0.3.0]: https://github.com/AnonymouX47/term-image/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/AnonymouX47/term-image/compare/v0.1.1...v0.2.0
[0.1.1]: https://github.com/AnonymouX47/term-image/releases/tag/v0.1.1
