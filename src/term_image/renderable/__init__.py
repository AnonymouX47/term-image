"""
.. The Renderable API
"""

from __future__ import annotations

__all__ = (
    "Renderable",
    "RenderArgs",
    "ArgsNamespace",
    "RenderData",
    "DataNamespace",
    "RenderableData",
    "Frame",
    "FrameCount",
    "FrameDuration",
    "Seek",
    "RenderableError",
    "IndefiniteSeekError",
    "RenderError",
    "RenderSizeOutofRangeError",
    "RenderArgsDataError",
    "RenderArgsError",
    "RenderDataError",
    "IncompatibleArgsNamespaceError",
    "IncompatibleRenderArgsError",
    "NoArgsNamespaceError",
    "NoDataNamespaceError",
    "NonAnimatedRenderableError",
    "UnassociatedNamespaceError",
    "UninitializedDataFieldError",
    "UnknownArgsFieldError",
    "UnknownDataFieldError",
    "OptionalPaddingT",
)

from ._enum import FrameCount, FrameDuration, Seek
from ._exceptions import (
    IndefiniteSeekError,
    NonAnimatedRenderableError,
    RenderableError,
    RenderError,
    RenderSizeOutofRangeError,
)
from ._renderable import OptionalPaddingT, Renderable, RenderableData
from ._types import (
    ArgsNamespace,
    DataNamespace,
    Frame,
    IncompatibleArgsNamespaceError,
    IncompatibleRenderArgsError,
    NoArgsNamespaceError,
    NoDataNamespaceError,
    RenderArgs,
    RenderArgsDataError,
    RenderArgsError,
    RenderData,
    RenderDataError,
    UnassociatedNamespaceError,
    UninitializedDataFieldError,
    UnknownArgsFieldError,
    UnknownDataFieldError,
)
