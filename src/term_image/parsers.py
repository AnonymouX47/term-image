"""CLI argument parsers"""

import argparse
import sys

from . import __version__
from .config import config_options
from .image import ITerm2Image, Size

parser = argparse.ArgumentParser(
    prog="term-image",
    formatter_class=argparse.RawDescriptionHelpFormatter,
    description="Display/Browse images in a terminal",
    epilog=""" \

'--' should be used to separate positional arguments that begin with an '-' \
from options/flags, to avoid ambiguity.
For example, `$ term-image [options] -- -image.jpg --image.png`

Render Styles:
  auto: The best style is automatically determined based on the detected terminal
      support.
  kitty: Uses the kitty graphics protocol. Currently supported terminal emulators
      include (but might not be limited to):
      - Kitty >= 0.20.0
      - Konsole >= 22.04.0
  iterm2: Uses the iTerm2 inline image protocol. Currently supported terminal
      emulators include (but might not be limited to):
      - iTerm2
      - Konsole >= 22.04.0
      - WezTerm
  block: Uses unicode half blocks with 24-bit color escape codes to represent images
      with a density of two pixels per character cell.

  Using a terminal graphics-based style not supported by the active terminal is not
  allowed by default. To force a style that is normally unsupported, add the
  '--force-style' flag.

FOOTNOTES:
  1. Width and height are in units of columns and lines repectively.
     The "available terminal size" is the current terminal size minus allowances.
     By default (i.e if none of the sizing options is specified), the equivalent of
     `--original-size` is used if not larger than the available size, else `--fit`.
  2. The size is multiplied by the scale on respective axes when an image is rendered.
     A scale value must be such that 0.0 < value <= 1.0.
  3. In CLI mode, only image sources are used, directory sources are skipped.
     Animated images are displayed only when animation is disabled (with `--no-anim`),
     when there's only one image source or when using native animation of some render
     styles.
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
  6. 0 -> worst quality; smallest data size, 95 -> best quality; largest data size.
     Reduces render time & image data size and increases drawing speed on the terminal's
     end but at the cost of image quality and color reproduction. Useful for animations
     with high pixel density / color sparseness.
     This option only applies when an image is re-encoded and not read directly from
     file (see `--iterm2-no-read-from-file`). By default (i.e when disabled), PNG format
     is used for re-encoding images, which has less compression with better quality.
     JPEG format can only be used for non-transparent images but the transparency status
     of some images can not be correctly determined in an efficient way at render time.
     Thus, to ensure the JPEG format is always used for re-encoded images, disable
     transparency (`--no-alpha`) or set a background color (`-b/--alpha-bg`).
  7. By default, image data is used directly from file when no image manipulation is
     required. Otherwise, it's re-encoded in PNG (or JPEG, if enabled) format.
     Significantly reduces render time when applicable. This option does not apply to
     animations, native or not.
  8. Any event with a level lower than the specified one is not reported.
  9. Supports all image formats supported by `PIL.Image.open()`.
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
    "--query-timeout",
    type=float,
    metavar="N",
    help=(
        "Timeout (in seconds) for all terminal queries "
        f"(default: {config_options.query_timeout})"
    ),
)
general.add_argument(
    "-S",
    "--style",
    choices=("auto", "block", "iterm2", "kitty"),
    help=(
        f"Image render style (default: {config_options.style}). "
        'See "Render Styles" below'
    ),
)
general.add_argument(
    "--force-style",
    action="store_true",
    help=(
        "Use the specified render style even if it's reported as unsupported by "
        "the active terminal"
    ),
)

cell_ratio_options = general.add_mutually_exclusive_group()
cell_ratio_options.add_argument(
    "-C",
    "--cell-ratio",
    type=float,
    metavar="N",
    help=(
        "The width-to-height ratio of a character cell in the terminal, to "
        "preserve image aspect ratio (default: auto)"
    ),
)
cell_ratio_options.add_argument(
    "--auto-cell-ratio",
    action="store_true",
    help="Determine the cell ratio from the terminal, if possible (default)",
)

win_size_options = general.add_mutually_exclusive_group()
win_size_options.add_argument(
    "--swap-win-size",
    action="store_true",
    default=None,
    help=(
        "A workaround for 'auto cell ratio' on some terminal emulators (e.g older "
        "VTE-based ones) that wrongly report window dimensions swapped"
    ),
)
win_size_options.add_argument(
    "--no-swap-win-size",
    action="store_false",
    default=None,
    dest="swap_win_size",
    help="Unlike '--swap-win-size', use the reported window size as-is (default)",
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
        "The time (in seconds) between frames for all animated images "
        "(default: determined per image from the metadata OR 0.1)"
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
    metavar="N",
    help=(
        "Maximum frame count for animation frames to be cached (Better performance "
        f"at the cost of memory) (default: {config_options.anim_cache}) [5]"
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
    help="Disable image transparency (alpha channel is removed)",
)
alpha_options.add_argument(
    "-A",
    "--alpha",
    type=float,
    metavar="N",
    default=40 / 255,
    help=(
        "Alpha ratio above which pixels are taken as opaque (0 <= x < 1), "
        f"for text-based render styles (default: {40 / 255:f})"
    ),
)
alpha_options.add_argument(
    "-b",
    "--alpha-bg",
    nargs="?",
    const="",
    metavar="COLOR",
    help=(
        "Hex color (without '#') to replace transparent backgrounds with "
        "(omit `COLOR` to use the terminal's default BG color)"
    ),
)

# CLI-only
cli_options = parser.add_argument_group(
    "CLI-only Options",
    "These options apply only when there is only one valid image source or `--cli` "
    "is specified",
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
        "Vertical allowance i.e minimum number of lines to leave unused " "(default: 2)"
    ),
)
cli_options.add_argument(
    "--scroll",
    action="store_true",
    help=(
        "Allow an image's height to be greater than the terminal height. "
        "Not needed when `--fit-to-width` is specified."
    ),
)
cli_options.add_argument(
    "-O",
    "--oversize",
    action="store_true",
    help=(
        "Allow an image's size to be greater than the terminal size "
        "(To be used with `-w`, `-h` or `--original-size`)"
    ),
)
cli_options.add_argument(
    "-s",
    "--scale",
    type=float,
    metavar="N",
    help="Image scale (overrides `-x` and `-y`) [2]",
)
cli_options.add_argument(
    "-x",
    "--scale-x",
    type=float,
    metavar="N",
    default=1.0,
    help="Image x-axis scale (default: 1.0) [2]",
)
cli_options.add_argument(
    "-y",
    "--scale-y",
    type=float,
    metavar="N",
    default=1.0,
    help="Image y-axis scale (default: 1.0) [2]",
)
cli_options.add_argument(
    "--max-pixels-cli",
    action="store_true",
    help=("Apply '--max-pixels' in CLI mode"),
)

# Sizing
_size_options = parser.add_argument_group(
    "Sizing Options (CLI-only)",
    "These apply to all images and are mutually exclusive [1]",
)
size_options = _size_options.add_mutually_exclusive_group()
size_options.add_argument(
    "-w",
    "--width",
    type=int,
    metavar="N",
    help="Image width",
)
size_options.add_argument(
    "-h",
    "--height",
    type=int,
    metavar="N",
    help="Image height",
)
size_options.add_argument(
    "--fit",
    action="store_const",
    const=Size.FIT,
    dest="auto_size",
    help="Fit each image optimally within the available terminal size",
)
size_options.add_argument(
    "--fit-to-width",
    action="store_const",
    const=Size.FIT_TO_WIDTH,
    dest="auto_size",
    help=(
        "Fit each image to the available terminal width, "
        "`--v-allow` has no effect i.e vertical allowance is ignored"
    ),
)
size_options.add_argument(
    "--original-size",
    action="store_const",
    const=Size.ORIGINAL,
    dest="auto_size",
    help=(
        "Render each image using its original size (See `--oversize`, "
        "USE WITH CAUTION!)"
    ),
)

# # Alignment
align_options = parser.add_argument_group(
    "Alignment Options (CLI-only)",
    "These apply to all images",
)
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
        "Number of columns within which to align each image "
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
    help="Number of lines within which to align each image (default: none)",
)

# TUI-only
tui_options = parser.add_argument_group(
    "TUI-only Options",
    "These options apply only when there is at least one valid directory source, "
    "multiple valid sources or `--tui` is specified",
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
    help=(
        "Maximum amount of pixels in images to be displayed "
        f"(default: {config_options.max_pixels}) [4]"
    ),
)

perf_options.add_argument(
    "--checkers",
    type=int,
    metavar="N",
    help=(
        "Maximum number of sub-processes for checking directory sources (default: auto)"
    ),
)
perf_options.add_argument(
    "--getters",
    type=int,
    metavar="N",
    help=(
        "Number of threads for downloading images from URL sources "
        f"(default: {config_options.getters})"
    ),
)
perf_options.add_argument(
    "--grid-renderers",
    type=int,
    metavar="N",
    help=(
        "Number of subprocesses for rendering grid cells "
        f"(default: {config_options.grid_renderers})"
    ),
)

multi_options = perf_options.add_mutually_exclusive_group()
multi_options.add_argument(
    "--multi",
    action="store_true",
    default=None,
    help="Enable multiprocessing, if supported (default)",
)
multi_options.add_argument(
    "--no-multi",
    action="store_false",
    default=None,
    dest="multi",
    help="Disable multiprocessing",
)

# Config
config_options__ = parser.add_argument_group(
    "Config Options",
    "NOTE: These are mutually exclusive",
)
config_options_ = config_options__.add_mutually_exclusive_group()

config_options_.add_argument(
    "--config",
    metavar="FILE",
    help="The config file to use for this session (default: Searches XDG Base Dirs)",
)
config_options_.add_argument(
    "--no-config",
    action="store_true",
    help="Use the default configuration",
)

# Logging
log_options_ = parser.add_argument_group(
    "Logging Options",
    "NOTE: All these, except '-l/--log-file', are mutually exclusive",
)
log_options = log_options_.add_mutually_exclusive_group()

log_options_.add_argument(
    "-l",
    "--log-file",
    metavar="FILE",
    help=f"The file to write logs to (default: {config_options.log_file})",
)
log_options.add_argument(
    "--log-level",
    choices=("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"),
    default="WARNING",
    help="Logging level for the session (default: WARNING) [6]",
)
log_options.add_argument(
    "-q",
    "--quiet",
    action="store_true",
    help="No notifications, except fatal errors",
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

kitty_parser = argparse.ArgumentParser(add_help=False)
kitty_options = kitty_parser.add_argument_group(
    "Kitty Style Options",
    "These options apply only when the 'kitty' render style is used",
)
kitty_options.add_argument(
    "--kz",
    "--kitty-z-index",
    metavar="N",
    dest="z_index",
    default=0,
    type=int,
    help=(
        "Image stacking order [CLI-only]; `>= 0` -> above text, `< 0` -> below "
        "text, `< -(2**31)/2` -> below cells with non-default background "
        "(default: 0)"
    ),
)
kitty_options.add_argument(
    "--kc",
    "--kitty-compress",
    metavar="N",
    dest="compress",
    default=4,
    type=int,
    help=(
        "ZLIB compression level; 0 -> no compression, 1 -> best speed, "
        "9 -> best compression (default: 4)"
    ),
)

iterm2_parser = argparse.ArgumentParser(add_help=False)
iterm2_options = iterm2_parser.add_argument_group(
    "iTerm2 Style Options",
    "These options apply only when the 'iterm2' render style is used",
)
iterm2_options.add_argument(
    "--itn",
    "--iterm2-native",
    action="store_true",
    dest="native",
    help="Use iTerm2's native animation; Animations will not be skipped [CLI-only]",
)
iterm2_options.add_argument(
    "--itnm",
    "--iterm2-native-maxsize",
    metavar="N",
    dest="native_maxsize",
    default=ITerm2Image.NATIVE_ANIM_MAXSIZE,
    type=int,
    help=(
        "Maximum size (in bytes) of image data for native animation [CLI-only] "
        f"(default: {ITerm2Image.NATIVE_ANIM_MAXSIZE})"
    ),
)
iterm2_options.add_argument(
    "--itc",
    "--iterm2-compress",
    metavar="N",
    dest="compress",
    default=4,
    type=int,
    help=(
        "ZLIB compression level, for images re-encoded in PNG format "
        "0 -> no compression, 1 -> best speed, 9 -> best compression (default: 4)"
    ),
)
iterm2_options.add_argument(
    "--itjq",
    "--iterm2-jpeg-quality",
    metavar="N",
    dest="jpeg_quality",
    default=ITerm2Image.JPEG_QUALITY,
    type=int,
    help=(
        "JPEG compression status and quality; `< 0` -> disabled, `0 to 95` -> "
        f"quality (default: {ITerm2Image.JPEG_QUALITY}) [6]"
    ),
)
iterm2_options.add_argument(
    "--itnrff",
    "--iterm2-no-read-from-file",
    action="store_false",
    dest="read_from_file",
    help="Never use image data directly from file; always re-encode images [7]",
)

style_parsers = {"kitty": kitty_parser, "iterm2": iterm2_parser}

for style_parser in style_parsers.values():
    parser._actions.extend(style_parser._actions)
    parser._option_string_actions.update(style_parser._option_string_actions)
    parser._action_groups.extend(style_parser._action_groups)
    parser._mutually_exclusive_groups.extend(style_parser._mutually_exclusive_groups)
