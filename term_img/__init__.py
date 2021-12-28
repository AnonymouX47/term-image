"""term-img Package Top-Level"""

__all__ = ("TermImage", "set_font_ratio", "get_font_ratio")

from .image import TermImage


def get_font_ratio() -> float:
    """Return the set libray-wide font ratio"""
    return _font_ratio


def set_font_ratio(ratio: float) -> None:
    """Set the library-wide font ratio

    The given value should be the aspect ratio of your terminal's font
    i.e `width / height` of a single character cell.
    This value is taken into consideration when rendering images in order for images
    drawn to the terminal to have a proper scale.
    If you can't determine this value from your terminal's configuration,
    you might have to try different values till you get a good fit.
    Normally, this value should be between 0 and 1, but not close to either boundary.
    """
    from . import image

    global _font_ratio

    if not isinstance(ratio, float):
        raise TypeError(f"Font ratio must be a float (got: {type(ratio).__name__})")
    if ratio <= 0:
        raise ValueError(f"Font ratio must be positive (got: {ratio})")

    # cell-size == width * height
    # font-ratio == width / height
    # There are two pixels vertically arranged in one character cell
    # pixel-size == width * height/2
    # pixel-ratio == width / (height/2) == 2 * (width / height) == 2 * font-ratio
    _font_ratio = ratio
    image._pixel_ratio = 2 * ratio


set_font_ratio(0.5)  # Default
