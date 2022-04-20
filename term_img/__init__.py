"""Backwards-compatibility dummy for `term_image`"""

import warnings

from term_image import *
from term_image import __all__, __author__, __version__, version_info

warnings.filterwarnings("once", category=DeprecationWarning, module="term_img")
warnings.warn(
    "The top-level package has been renamed to `term_image` and will no longer "
    "be accessible via the name `term_img` as from version 1.0.0",
    DeprecationWarning,
)
