from __future__ import annotations

import atexit
import io
import sys
from contextlib import contextmanager
from tempfile import TemporaryFile
from types import MappingProxyType, SimpleNamespace
from typing import Any, Iterator

import pytest

from term_image.ctlseqs import HIDE_CURSOR, SHOW_CURSOR
from term_image.geometry import Size
from term_image.padding import AlignedPadding, ExactPadding, HAlign, VAlign
from term_image.render import RenderIterator
from term_image.renderable import (
    ArgsNamespace,
    DataNamespace,
    Frame,
    FrameCount,
    FrameDuration,
    IncompatibleRenderArgsError,
    IndefiniteSeekError,
    NonAnimatedFrameDurationError,
    Renderable,
    RenderableError,
    RenderArgs,
    RenderData,
    RenderSizeOutofRangeError,
    Seek,
)

from .. import get_terminal_size

try:
    import pty
    import termios
except ImportError:
    OS_IS_UNIX = False
else:
    OS_IS_UNIX = True

STDOUT = io.StringIO()
COLUMNS, LINES = get_terminal_size()

# NOTE: Always keep in mind that frames are not actually rendered by `RenderIterator`.
# Hence, avoid testing the original data (fields defined by `Frame`) of rendered frames
# when what is actually required is contained in the render data and/or render args
# (which the `DummyFrame` subclass exposes).
#
# Cases where original frame data may be tested include (but may not be limited to):
#
# - when the frame returned may not be the original rendered by the renderable such as
#   when the render output is padded.

# ========================== Renderables ==========================


class Space(Renderable):
    size = Size(1, 1)

    def _get_render_size_(self):
        return self.size

    def _render_(self, render_data, render_args):
        data = render_data[Renderable]
        width, height = data.size
        return DummyFrame(
            data.frame_offset,
            1 if data.duration is FrameDuration.DYNAMIC else data.duration,
            data.size,
            "\n".join((" " * width,) * height),
            renderable=self,
            render_data=render_data,
            render_args=render_args,
        )


class IndefiniteSpace(Space):
    def __init__(self, frame_count):
        super().__init__(FrameCount.INDEFINITE, 1)
        self.__frame_count = frame_count

    def _render_(self, render_data, render_args):
        if render_data[Renderable].iteration:
            next(render_data[__class__].frames)
        return super()._render_(render_data, render_args)

    def _get_render_data_(self, *, iteration):
        render_data = super()._get_render_data_(iteration=iteration)
        render_data[__class__].frames = (
            iter(range(self.__frame_count)) if iteration else None
        )
        return render_data


class IndefiniteSpaceData(DataNamespace, render_cls=IndefiniteSpace):
    frames: Iterator[int] | None


class CacheSpace(Space):
    def __init__(self, *args):
        self.n_renders = 0
        super().__init__(*args)

    def _render_(self, *args):
        self.n_renders += 1
        return super()._render_(*args)


class Char(Renderable):
    size = Size(1, 1)

    def _get_render_size_(self):
        return self.size

    def _render_(self, render_data, render_args):
        data = render_data[Renderable]
        width, height = data.size
        return DummyFrame(
            data.frame_offset,
            1 if data.duration is FrameDuration.DYNAMIC else data.duration,
            data.size,
            "\n".join((render_args[Char].char * width,) * height),
            renderable=self,
            render_data=render_data,
            render_args=render_args,
        )


class CharArgs(ArgsNamespace, render_cls=Char):
    char: str = " "


class FrameFill(Renderable):
    size = Size(1, 1)

    def _get_render_size_(self):
        return self.size

    def __init__(self, size: Size):
        super().__init__(10, 1)
        self.size = size

    def _render_(self, render_data, render_args):
        data = render_data[Renderable]
        width, height = data.size
        return DummyFrame(
            data.frame_offset,
            1 if data.duration is FrameDuration.DYNAMIC else data.duration,
            data.size,
            "\n".join((str(data.frame_offset) * width,) * height),
            renderable=self,
            render_data=render_data,
            render_args=render_args,
        )


# ========================== Utils ==========================


class DummyFrame(Frame):
    _extra_data = {}

    def __new__(cls, *args, renderable, render_data, render_args):
        new = super().__new__(cls, *args)
        __class__._extra_data[id(new)] = (
            renderable,
            render_data,
            render_args,
            SimpleNamespace(**render_data[Renderable].as_dict()),
        )
        return new

    def __del__(self):
        del __class__._extra_data[id(self)]

    renderable = property(lambda self: __class__._extra_data[id(self)][0])
    render_data = property(lambda self: __class__._extra_data[id(self)][1])
    render_args = property(lambda self: __class__._extra_data[id(self)][2])
    data = property(lambda self: __class__._extra_data[id(self)][3])


@contextmanager
def capture_stdout():
    STDOUT.seek(0)
    STDOUT.truncate()
    sys.stdout = STDOUT
    try:
        yield
    finally:
        STDOUT.seek(0)
        STDOUT.truncate()


@contextmanager
def capture_stdout_pty():
    def write(string):
        type(slave).write(slave, string)
        buffer.write(string)

    master, slave = (open(fd, mode) for fd, mode in zip(pty.openpty(), "rw"))
    buffer = io.StringIO()
    slave.write = write
    sys.stdout = slave

    with master, slave:
        yield master, buffer


def anim_n_eol(render_height, padded_height, frame_count, loops):
    return (
        # first frame of the first loop, with padding
        (padded_height - 1)
        # remaining frames of the first loop
        + ((render_height - 1) * (frame_count - 1))
        # frames of the remaining loops
        + ((render_height - 1) * frame_count * (loops - 1))
    )


# ========================== Tests ==========================

# # Metaclass / Subclass Construction ============================================


class TestMeta:
    def test_not_a_subclass(self):
        with pytest.raises(RenderableError, match="'Foo' is not a subclass"):

            class Foo(metaclass=type(Renderable)):
                pass

    class TestRenderArgs:
        def test_base(self):
            assert "_ALL_DEFAULT_ARGS" in Renderable.__dict__
            assert isinstance(Renderable._ALL_DEFAULT_ARGS, MappingProxyType)
            assert Renderable._ALL_DEFAULT_ARGS == {}

        def test_default(self):
            class Foo(Renderable):
                pass

            assert Foo.Args is None
            assert "_ALL_DEFAULT_ARGS" in Foo.__dict__
            assert isinstance(Foo._ALL_DEFAULT_ARGS, MappingProxyType)
            assert Foo._ALL_DEFAULT_ARGS == Renderable._ALL_DEFAULT_ARGS

        class TestInheritance:
            class A(Renderable):
                pass

            class AArgs(ArgsNamespace, render_cls=A):
                a: None = None

            def test_parent_with_no_args(self):
                class B(Renderable):
                    pass

                class C(B):
                    pass

                assert C._ALL_DEFAULT_ARGS == {
                    **Renderable._ALL_DEFAULT_ARGS,
                }

            def test_parent_with_args(self):
                class B(self.A):
                    pass

                assert B._ALL_DEFAULT_ARGS == {
                    **Renderable._ALL_DEFAULT_ARGS,
                    self.A: self.A.Args(),
                }

            def test_multi_level(self):
                class B(self.A):
                    pass

                class BArgs(ArgsNamespace, render_cls=B):
                    b: None = None

                class C(B):
                    pass

                assert C._ALL_DEFAULT_ARGS == {
                    **Renderable._ALL_DEFAULT_ARGS,
                    self.A: self.A.Args(),
                    B: B.Args(),
                }

            def test_multiple(self):
                class B(Renderable):
                    pass

                class BArgs(ArgsNamespace, render_cls=B):
                    b: None = None

                class C(self.A, B):
                    pass

                assert C._ALL_DEFAULT_ARGS == {
                    **Renderable._ALL_DEFAULT_ARGS,
                    self.A: self.A.Args(),
                    B: B.Args(),
                }

            def test_complex(self):
                class B(self.A):
                    pass

                class BArgs(ArgsNamespace, render_cls=B):
                    b: None = None

                class C(self.A):
                    pass

                class CArgs(ArgsNamespace, render_cls=C):
                    c: None = None

                class D(B, C):
                    pass

                class DArgs(ArgsNamespace, render_cls=D):
                    d: None = None

                class E(Renderable):
                    pass

                class EArgs(ArgsNamespace, render_cls=E):
                    e: None = None

                class F(D, E):
                    pass

                assert F._ALL_DEFAULT_ARGS == {
                    **Renderable._ALL_DEFAULT_ARGS,
                    self.A: self.A.Args(),
                    B: B.Args(),
                    C: C.Args(),
                    D: D.Args(),
                    E: E.Args(),
                }

        def test_optimization_default_namespaces_interned(self):
            class A(Renderable):
                pass

            class AArgs(ArgsNamespace, render_cls=A):
                a: None = None

            class B(A):
                pass

            class BArgs(ArgsNamespace, render_cls=B):
                b: None = None

            class C(B):
                pass

            assert A._ALL_DEFAULT_ARGS[A] is B._ALL_DEFAULT_ARGS[A]
            assert A._ALL_DEFAULT_ARGS[A] is C._ALL_DEFAULT_ARGS[A]
            assert B._ALL_DEFAULT_ARGS[B] is C._ALL_DEFAULT_ARGS[B]

    class TestRenderData:
        def test_base(self):
            assert "_RENDER_DATA_MRO" in Renderable.__dict__
            assert isinstance(Renderable._RENDER_DATA_MRO, MappingProxyType)
            assert Renderable._RENDER_DATA_MRO == {Renderable: Renderable._Data_}

        def test_default(self):
            class Foo(Renderable):
                pass

            assert Foo._Data_ is None
            assert "_RENDER_DATA_MRO" in Foo.__dict__
            assert isinstance(Foo._RENDER_DATA_MRO, MappingProxyType)
            assert Foo._RENDER_DATA_MRO == Renderable._RENDER_DATA_MRO

        class TestInheritance:
            class A(Renderable):
                pass

            class AData(DataNamespace, render_cls=A):
                a: None = None

            def test_parent_with_no_data(self):
                class B(Renderable):
                    pass

                class C(B):
                    pass

                assert C._RENDER_DATA_MRO == {
                    **Renderable._RENDER_DATA_MRO,
                }

            def test_parent_with_data(self):
                class B(self.A):
                    pass

                assert B._RENDER_DATA_MRO == {
                    **Renderable._RENDER_DATA_MRO,
                    self.A: self.A._Data_,
                }

            def test_multi_level(self):
                class B(self.A):
                    pass

                class BData(DataNamespace, render_cls=B):
                    b: None = None

                class C(B):
                    pass

                assert C._RENDER_DATA_MRO == {
                    **Renderable._RENDER_DATA_MRO,
                    self.A: self.A._Data_,
                    B: B._Data_,
                }

            def test_multiple(self):
                class B(Renderable):
                    pass

                class BData(DataNamespace, render_cls=B):
                    b: None = None

                class C(self.A, B):
                    pass

                assert C._RENDER_DATA_MRO == {
                    **Renderable._RENDER_DATA_MRO,
                    self.A: self.A._Data_,
                    B: B._Data_,
                }

            def test_complex(self):
                class B(self.A):
                    pass

                class BData(DataNamespace, render_cls=B):
                    b: None = None

                class C(self.A):
                    pass

                class CData(DataNamespace, render_cls=C):
                    c: None = None

                class D(B, C):
                    pass

                class DData(DataNamespace, render_cls=D):
                    d: None = None

                class E(Renderable):
                    pass

                class EData(DataNamespace, render_cls=E):
                    e: None = None

                class F(D, E):
                    pass

                assert F._RENDER_DATA_MRO == {
                    **Renderable._RENDER_DATA_MRO,
                    self.A: self.A._Data_,
                    B: B._Data_,
                    C: C._Data_,
                    D: D._Data_,
                    E: E._Data_,
                }

    class TestExportedAttrs:
        class A(Renderable):
            _EXPORTED_ATTRS_ = ("a",)
            _EXPORTED_DESCENDANT_ATTRS_ = ("A",)

        def test_base(self):
            assert isinstance(Renderable._ALL_EXPORTED_ATTRS, tuple)
            assert Renderable._ALL_EXPORTED_ATTRS == ()

        def test_cls(self):
            assert isinstance(self.A._ALL_EXPORTED_ATTRS, tuple)
            assert sorted(self.A._ALL_EXPORTED_ATTRS) == sorted(("a", "A"))

        def test_inheritance(self):
            class B(self.A):
                _EXPORTED_ATTRS_ = ("b",)
                _EXPORTED_DESCENDANT_ATTRS_ = ("B",)

            assert sorted(B._ALL_EXPORTED_ATTRS) == sorted(("b", "A", "B"))

            class C(B):
                _EXPORTED_ATTRS_ = ("c",)
                _EXPORTED_DESCENDANT_ATTRS_ = ("C",)

            assert sorted(C._ALL_EXPORTED_ATTRS) == sorted(("c", "A", "B", "C"))

        def test_multiple_inheritance(self):
            class B(Renderable):
                _EXPORTED_ATTRS_ = ("b",)
                _EXPORTED_DESCENDANT_ATTRS_ = ("B",)

            class C(self.A, B):
                _EXPORTED_ATTRS_ = ("c",)
                _EXPORTED_DESCENDANT_ATTRS_ = ("C",)

            assert sorted(C._ALL_EXPORTED_ATTRS) == sorted(("c", "A", "B", "C"))

            class C(B, self.A):
                _EXPORTED_ATTRS_ = ("c",)
                _EXPORTED_DESCENDANT_ATTRS_ = ("C",)

            assert sorted(C._ALL_EXPORTED_ATTRS) == sorted(("c", "A", "B", "C"))

        class TestConflict:
            class A(Renderable):
                _EXPORTED_ATTRS_ = ("a",)
                _EXPORTED_DESCENDANT_ATTRS_ = ("A",)

            def test_cls_vs_base(self):
                class B(self.A):
                    _EXPORTED_ATTRS_ = ("a",)
                    _EXPORTED_DESCENDANT_ATTRS_ = ("A",)

                assert sorted(B._ALL_EXPORTED_ATTRS) == sorted(("a", "A"))

            def test_cls_vs_base_of_base(self):
                class B(self.A):
                    _EXPORTED_ATTRS_ = ("b",)
                    _EXPORTED_DESCENDANT_ATTRS_ = ("B",)

                class C(B):
                    _EXPORTED_ATTRS_ = ("a",)
                    _EXPORTED_DESCENDANT_ATTRS_ = ("A",)

                assert sorted(C._ALL_EXPORTED_ATTRS) == sorted(("a", "A", "B"))

            def test_base_vs_base(self):
                class B(Renderable):
                    _EXPORTED_ATTRS_ = ("a",)
                    _EXPORTED_DESCENDANT_ATTRS_ = ("A",)

                class C(self.A, B):
                    _EXPORTED_ATTRS_ = ("c",)
                    _EXPORTED_DESCENDANT_ATTRS_ = ("C",)

                assert sorted(C._ALL_EXPORTED_ATTRS) == sorted(("c", "A", "C"))

                class C(B, self.A):
                    _EXPORTED_ATTRS_ = ("c",)
                    _EXPORTED_DESCENDANT_ATTRS_ = ("C",)

                assert sorted(C._ALL_EXPORTED_ATTRS) == sorted(("c", "A", "C"))

            def test_specific_vs_descendant(self):
                class B(self.A):
                    _EXPORTED_ATTRS_ = ("A",)

                assert sorted(B._ALL_EXPORTED_ATTRS) == sorted(("A",))


# # Constructor ==================================================================


class TestInit:
    @pytest.mark.parametrize("n_frames", [0, -1, -100])
    def test_invalid_frame_count(self, n_frames):
        with pytest.raises(ValueError, match="'frame_count'"):
            Space(n_frames, 1)

    class TestFrameDuration:
        @pytest.mark.parametrize("duration", [0, -1, -100])
        def test_invalid(self, duration):
            with pytest.raises(ValueError, match="'frame_duration'"):
                Space(2, duration)

        def test_ignored_for_non_animated(self):
            Space(1, -1)


# # Attributes ===================================================================


class TestAnimated:
    def test_non_animated(self):
        assert Space(1, 1).animated is False

    @pytest.mark.parametrize("n_frames", [2, *FrameCount])
    def test_animated(self, n_frames):
        assert Space(n_frames, 1).animated is True


# # Properties ===================================================================


class TestFrameCount:
    @pytest.mark.parametrize("n_frames", [1, 2, FrameCount.INDEFINITE])
    def test_non_postponed(self, n_frames):
        assert Space(n_frames, 1).frame_count == n_frames

    class TestPostponed:
        class PostponedSpace(Space):
            def __init__(self, frame_count):
                super().__init__(FrameCount.POSTPONED, 1)
                self.__frame_count = frame_count

            def _get_frame_count_(self):
                return self.__frame_count

        def test_not_implemented(self):
            space = Space(FrameCount.POSTPONED, 1)
            with pytest.raises(NotImplementedError):
                space.frame_count

        @pytest.mark.parametrize("n_frames", [2, FrameCount.INDEFINITE])
        def test_implemented(self, n_frames):
            assert self.PostponedSpace(n_frames).frame_count == n_frames


class TestFrameDuration:
    @pytest.mark.parametrize("duration", [1, 100, FrameDuration.DYNAMIC])
    def test_get(self, duration):
        assert Space(1, duration).frame_duration is None
        assert Space(2, duration).frame_duration == duration

    class TestSet:
        space = Space(1, 1)

        @pytest.mark.parametrize("duration", [100, FrameDuration.DYNAMIC, 0, -100])
        def test_non_animated(self, duration):
            with pytest.raises(NonAnimatedFrameDurationError):
                self.space.frame_duration = duration

            assert self.space.frame_duration is None

        class TestAnimated:
            anim_space = Space(2, 1)

            @pytest.mark.parametrize("duration", [2, 100, FrameDuration.DYNAMIC])
            def test_valid(self, duration):
                self.anim_space.frame_duration = duration
                assert self.anim_space.frame_duration == duration

            @pytest.mark.parametrize("duration", [0, -1, -100])
            def test_invalid(self, duration):
                with pytest.raises(ValueError, match="'frame_duration'"):
                    self.anim_space.frame_duration = duration


def test_render_size():
    space = Space(1, 1)
    assert space.render_size == Size(1, 1)

    space.size = Size(100, 100)
    assert space.render_size == Size(100, 100)


# # Methods ======================================================================


class TestIter:
    def test_non_animated(self):
        char = Char(1, 1)
        with pytest.raises(ValueError, match="not animated"):
            iter(char)

    def test_animated(self):
        anim_char = Char(2, 1)
        render_iter = iter(anim_char)
        assert isinstance(render_iter, RenderIterator)
        assert render_iter.loop == 1  # loop count

        frame = next(render_iter)
        assert frame.renderable is anim_char  # renderable
        assert frame.render_data.render_cls is Char  # render data
        assert frame.render_args == RenderArgs(Char)  # default render args
        assert frame.render_size == Size(1, 1)  # no padding
        assert frame.render_output == " "  # no padding

        render_iter.seek(0)
        assert next(render_iter) is not frame  # no caching


class TestStr:
    class RenderChar(Char):
        def _render_(self, render_data, render_args):
            self.render_data = render_data
            self.render_args = render_args
            return super()._render_(render_data, render_args)

    def test_default_render_args(self):
        render_char = self.RenderChar(1, 1)
        str(render_char)
        assert render_char.render_args == RenderArgs(self.RenderChar)

    @pytest.mark.parametrize("offset", [0, 5, 9])
    def test_frame_number(self, offset):
        anim_render_char = self.RenderChar(10, 1)
        anim_render_char.seek(offset)
        str(anim_render_char)
        assert anim_render_char.render_data[Renderable].frame_offset == offset


class TestDraw:
    """See also: `TestInitRender` and `TestAnimate`."""

    class TestNonAnimation:
        class RenderChar(Char):
            def _render_(self, render_data, render_args):
                self.render_data = render_data
                self.render_args = render_args
                return super()._render_(render_data, render_args)

        space = Space(1, 1)
        anim_space = Space(2, 1)
        char = Char(1, 1)

        @capture_stdout()
        def test_args_ignored_for_non_animated(self):
            self.space.draw(loops=0)
            self.space.draw(cache=-1)

        @capture_stdout()
        def test_args_ignored_for_animated_when_animate_is_false(self):
            self.anim_space.draw(animate=False, loops=0)
            self.anim_space.draw(animate=False, cache=-1)

        @capture_stdout()
        def test_default(self):
            render_char = self.RenderChar(1, 1)
            render_char.draw()
            assert render_char.render_args == RenderArgs(self.RenderChar)
            assert STDOUT.getvalue().count("\n") == LINES - 2
            assert STDOUT.getvalue().endswith("\n")

        class TestRenderArgs:
            class RenderChar(Char):
                def _render_(self, render_data, render_args):
                    self.render_args = render_args
                    return super()._render_(render_data, render_args)

            def test_incompatible(self):
                with pytest.raises(IncompatibleRenderArgsError):
                    self.RenderChar(1, 1).draw(RenderArgs(Space))

            @capture_stdout()
            def test_compatible(self):
                render_char = self.RenderChar(1, 1)
                char_args = Char.Args("#")
                render_char.draw(+char_args)
                assert render_char.render_args == RenderArgs(self.RenderChar, char_args)
                assert STDOUT.getvalue().count("\n") == LINES - 2
                assert STDOUT.getvalue().endswith("\n")

        @capture_stdout()
        def test_padding(self):
            self.space.draw(padding=AlignedPadding(3, 3))
            assert STDOUT.getvalue().count("\n") == 3
            assert STDOUT.getvalue().endswith("\n")

        def test_animate(self):
            with capture_stdout():
                self.space.draw()
                output = STDOUT.getvalue()
                assert output.count("\n") == LINES - 2

            with capture_stdout():
                self.space.draw(animate=True)
                assert output == STDOUT.getvalue()

            with capture_stdout():
                self.space.draw(animate=False)
                assert output == STDOUT.getvalue()

            with capture_stdout():
                self.anim_space.draw(animate=False)
                assert output == STDOUT.getvalue()

        class TestCheckSize:
            space = Space(1, 1)
            space_large = Space(1, 1)
            space_large.size = Size(COLUMNS + 1, 1)
            padding = AlignedPadding(COLUMNS + 1, 1)

            @capture_stdout()
            def test_default(self):
                with pytest.raises(
                    RenderSizeOutofRangeError, match="Padded render width"
                ):
                    self.space_large.draw()
                with pytest.raises(
                    RenderSizeOutofRangeError, match="Padded render width"
                ):
                    self.space.draw(padding=self.padding)

            @capture_stdout()
            def test_true(self):
                with pytest.raises(
                    RenderSizeOutofRangeError, match="Padded render width"
                ):
                    self.space_large.draw(check_size=True)
                with pytest.raises(
                    RenderSizeOutofRangeError, match="Padded render width"
                ):
                    self.space.draw(padding=self.padding, check_size=True)

            @capture_stdout()
            def test_false(self):
                self.space_large.draw(check_size=False)
                self.space.draw(padding=self.padding, check_size=False)

        class TestAllowScroll:
            space = Space(1, 1)
            space_large = Space(1, 1)
            space_large.size = Size(1, LINES + 1)
            padding = AlignedPadding(1, LINES + 1)

            @capture_stdout()
            def test_default(self):
                with pytest.raises(
                    RenderSizeOutofRangeError, match="Padded render height"
                ):
                    self.space_large.draw()
                with pytest.raises(
                    RenderSizeOutofRangeError, match="Padded render height"
                ):
                    self.space.draw(padding=self.padding)

            @capture_stdout()
            def test_false(self):
                with pytest.raises(
                    RenderSizeOutofRangeError, match="Padded render height"
                ):
                    self.space_large.draw(allow_scroll=False)
                with pytest.raises(
                    RenderSizeOutofRangeError, match="Padded render height"
                ):
                    self.space.draw(padding=self.padding, allow_scroll=False)

            @capture_stdout()
            def test_true(self):
                self.space_large.draw(allow_scroll=True)
                self.space.draw(padding=self.padding, allow_scroll=True)

        @pytest.mark.skipif(not OS_IS_UNIX, reason="Not supported on non-Unix")
        class TestEchoInput:
            class EchoSpace(Space):
                def __init__(self):
                    super().__init__(1, 1)

                def _render_(self, *args):
                    attr = termios.tcgetattr(sys.stdout.fileno())
                    self.echoed = bool(attr[3] & termios.ECHO)
                    return super()._render_(*args)

            @capture_stdout_pty()
            def test_default(self):
                echo_space = self.EchoSpace()
                echo_space.draw()
                assert echo_space.echoed is False

            @pytest.mark.parametrize("echo_input", [False, True])
            @capture_stdout_pty()
            def test_non_default(self, echo_input):
                echo_space = self.EchoSpace()
                echo_space.draw(echo_input=echo_input)
                assert echo_space.echoed is echo_input

        @pytest.mark.parametrize("offset", [0, 5, 9])
        def test_frame_number(self, offset):
            anim_render_char = self.RenderChar(10, 1)
            anim_render_char.seek(offset)
            anim_render_char.draw(animate=False)
            assert anim_render_char.render_data[Renderable].frame_offset == offset

        class TestHandleInterruptedDraw:
            class InterruptedChar(Char):
                interrupted = False

                def __init__(self):
                    super().__init__(1, 1)

                def _handle_interrupted_draw_(self, render_data, render_args, output):
                    self.interrupted_args = SimpleNamespace(
                        render_data=render_data,
                        render_args=render_args,
                        output=output,
                    )
                    self.interrupted = True

            def interrupted_write(string):
                raise KeyboardInterrupt

            interrupted_io_1 = io.StringIO()
            interrupted_io_1.write = interrupted_write
            interrupted_io_2 = io.StringIO()
            interrupted_io_2.write = interrupted_write

            @capture_stdout()
            def test_uninterrupted(self):
                interrupted_char = self.InterruptedChar()
                interrupted_char.draw(RenderArgs(self.InterruptedChar), ExactPadding())
                assert interrupted_char.interrupted is False

            @pytest.mark.parametrize(
                "render_args,output",
                [
                    (RenderArgs(InterruptedChar), interrupted_io_1),
                    (RenderArgs(InterruptedChar, Char.Args("#")), interrupted_io_2),
                ],
            )
            def test_interrupted(self, render_args, output):
                interrupted_char = self.InterruptedChar()
                sys.stdout = output

                try:
                    interrupted_char.draw(render_args)
                except KeyboardInterrupt:
                    pass

                assert interrupted_char.interrupted is True
                assert (
                    interrupted_char.interrupted_args.render_data.render_cls
                    is self.InterruptedChar
                )
                assert interrupted_char.interrupted_args.render_args is render_args
                assert interrupted_char.interrupted_args.output is output

    class TestAnimation:
        class AnimateChar(Char):
            def _animate_(
                self, render_data, render_args, padding, loops, cache, output
            ):
                self.anim_args = SimpleNamespace(
                    render_data=render_data,
                    render_args=render_args,
                    padding=padding,
                    loops=loops,
                    cache=cache,
                    output=output,
                )

        @capture_stdout()
        def test_default(self):
            animate_char = self.AnimateChar(2, 1)
            animate_char.draw()
            assert animate_char.anim_args.render_data.render_cls is self.AnimateChar
            assert animate_char.anim_args.render_args == RenderArgs(self.AnimateChar)
            assert animate_char.anim_args.padding == AlignedPadding(COLUMNS, LINES - 2)
            assert animate_char.anim_args.loops == -1
            assert animate_char.anim_args.cache == 100
            assert animate_char.anim_args.output is sys.stdout
            assert STDOUT.getvalue().count("\n") == 1
            assert STDOUT.getvalue().endswith("\n")

        @capture_stdout()
        def test_non_default(self):
            animate_char = self.AnimateChar(2, 1)
            render_args = RenderArgs(self.AnimateChar, Char.Args("#"))
            animate_char.draw(+Char.Args("#"), ExactPadding(), loops=2, cache=False)
            assert animate_char.anim_args.render_data.render_cls is self.AnimateChar
            assert animate_char.anim_args.render_args == render_args
            assert animate_char.anim_args.padding == ExactPadding()
            assert animate_char.anim_args.loops == 2
            assert animate_char.anim_args.cache is False
            assert animate_char.anim_args.output is sys.stdout
            assert STDOUT.getvalue().count("\n") == 1
            assert STDOUT.getvalue().endswith("\n")

        def test_incompatible_render_args(self):
            char = Char(2, 1)
            with pytest.raises(IncompatibleRenderArgsError):
                char.draw(RenderArgs(Space))

        def test_animate(self):
            anim_space = Space(2, 1)

            with capture_stdout():
                anim_space.draw(loops=1)
                output = STDOUT.getvalue()
                assert output.count("\n") == anim_n_eol(1, LINES - 2, 1, 1) + 1

            with capture_stdout():
                anim_space.draw(animate=True, loops=1)
                assert output == STDOUT.getvalue()

            with capture_stdout():
                anim_space.draw(animate=False, loops=1)
                assert output != STDOUT.getvalue()
                assert (
                    STDOUT.getvalue().count("\n") == anim_n_eol(1, LINES - 2, 1, 1) + 1
                )

        class TestCheckSize:
            anim_space = Space(2, 1)
            anim_space_large = Space(2, 1)
            anim_space_large.size = Size(COLUMNS + 1, 1)
            padding = AlignedPadding(COLUMNS + 1, 1)

            @capture_stdout()
            def test_default(self):
                with pytest.raises(
                    RenderSizeOutofRangeError, match="Padded render width"
                ):
                    self.anim_space_large.draw()
                with pytest.raises(
                    RenderSizeOutofRangeError, match="Padded render width"
                ):
                    self.anim_space.draw(padding=self.padding)

            @capture_stdout()
            def test_true(self):
                with pytest.raises(
                    RenderSizeOutofRangeError, match="Padded render width"
                ):
                    self.anim_space_large.draw(check_size=True)
                with pytest.raises(
                    RenderSizeOutofRangeError, match="Padded render width"
                ):
                    self.anim_space.draw(padding=self.padding, check_size=True)

            @capture_stdout()
            def test_false(self):
                with pytest.raises(
                    RenderSizeOutofRangeError, match="Padded render width"
                ):
                    self.anim_space_large.draw(check_size=False)
                with pytest.raises(
                    RenderSizeOutofRangeError, match="Padded render width"
                ):
                    self.anim_space.draw(padding=self.padding, check_size=False)

        class TestAllowScroll:
            anim_space = Space(2, 1)
            anim_space_large = Space(2, 1)
            anim_space_large.size = Size(1, LINES + 1)
            padding = AlignedPadding(1, LINES + 1)

            @capture_stdout()
            def test_default(self):
                with pytest.raises(
                    RenderSizeOutofRangeError, match="Padded render height"
                ):
                    self.anim_space_large.draw()
                with pytest.raises(
                    RenderSizeOutofRangeError, match="Padded render height"
                ):
                    self.anim_space.draw(padding=self.padding)

            @capture_stdout()
            def test_false(self):
                with pytest.raises(
                    RenderSizeOutofRangeError, match="Padded render height"
                ):
                    self.anim_space_large.draw(allow_scroll=False)
                with pytest.raises(
                    RenderSizeOutofRangeError, match="Padded render height"
                ):
                    self.anim_space.draw(padding=self.padding, allow_scroll=False)

            @capture_stdout()
            def test_true(self):
                with pytest.raises(
                    RenderSizeOutofRangeError, match="Padded render height"
                ):
                    self.anim_space_large.draw(allow_scroll=True)
                with pytest.raises(
                    RenderSizeOutofRangeError, match="Padded render height"
                ):
                    self.anim_space.draw(padding=self.padding, allow_scroll=True)

        @pytest.mark.skipif(not OS_IS_UNIX, reason="Not supported on non-Unix")
        class TestEchoInput:
            class AnimEchoSpace(Space):
                def __init__(self):
                    super().__init__(2, 1)

                def _animate_(self, *args, **kwargs):
                    attr = termios.tcgetattr(sys.stdout.fileno())
                    self.echoed = bool(attr[3] & termios.ECHO)

            @capture_stdout_pty()
            def test_default(self):
                anim_echo_space = self.AnimEchoSpace()
                anim_echo_space.draw(loops=1)
                assert anim_echo_space.echoed is False

            @pytest.mark.parametrize("echo_input", [False, True])
            @capture_stdout_pty()
            def test_non_default(self, echo_input):
                anim_echo_space = self.AnimEchoSpace()
                anim_echo_space.draw(loops=1, echo_input=echo_input)
                assert anim_echo_space.echoed is echo_input

    @pytest.mark.skipif(not OS_IS_UNIX, reason="Cannot test on non-Unix")
    @pytest.mark.parametrize("renderable", [Space(1, 1), Space(2, 1)])
    class TestHideCursor:
        class TestInTerminal:
            def test_default(self, renderable):
                with capture_stdout_pty() as (_, buffer):
                    renderable.draw(loops=1)
                    output = buffer.getvalue()
                    assert output.startswith(HIDE_CURSOR)
                    assert output.count(HIDE_CURSOR) == 1
                    assert output.endswith(SHOW_CURSOR)
                    assert output.count(SHOW_CURSOR) == 1

            @pytest.mark.parametrize("hide_cursor", [False, True])
            def test_non_default(self, renderable, hide_cursor):
                with capture_stdout_pty() as (_, buffer):
                    renderable.draw(loops=1, hide_cursor=hide_cursor)
                    output = buffer.getvalue()
                    assert (output.startswith(HIDE_CURSOR)) is hide_cursor
                    assert output.count(HIDE_CURSOR) == hide_cursor
                    assert (output.endswith(SHOW_CURSOR)) is hide_cursor
                    assert output.count(SHOW_CURSOR) == hide_cursor

        @pytest.mark.parametrize("hide_cursor", [False, True])
        @capture_stdout()
        def test_not_in_terminal(self, renderable, hide_cursor):
            renderable.draw(loops=1, hide_cursor=hide_cursor)
            output = STDOUT.getvalue()
            assert HIDE_CURSOR not in output
            assert SHOW_CURSOR not in output


class TestRender:
    """Just ensures the arguments is passed on and used appropriately.

    See also: `TestInitRender`.
    """

    char = Char(1, 1)

    def test_default(self):
        frame = self.char.render()
        assert frame.render_data.render_cls is Char
        assert frame.render_args == RenderArgs(Char)
        assert frame == self.char.render(None)
        assert frame == self.char.render(padding=ExactPadding())
        assert frame == self.char.render(padding=AlignedPadding(1, 1))

    class TestRenderArgs:
        char = Char(1, 1)

        def test_incompatible(self):
            with pytest.raises(IncompatibleRenderArgsError):
                self.char.render(RenderArgs(Space))

        def test_compatible(self):
            frame = self.char.render(+Char.Args("#"))
            assert frame.render_args == +Char.Args("#")

    def test_padding(self):
        frame = self.char.render(padding=AlignedPadding(3, 3))
        assert frame.render_size == Size(3, 3)
        assert frame.render_output == "   \n   \n   "

    @pytest.mark.parametrize("offset", [0, 5, 9])
    def test_frame_number(self, offset):
        anim_char = Char(10, 1)
        anim_char.seek(offset)
        assert anim_char.render().data.frame_offset == offset


class TestSeekTell:
    indefinite_space = Space(FrameCount.INDEFINITE, 1)

    class TestDefinite:
        anim_space = Space(10, 1)

        @pytest.mark.parametrize(
            "whence,offset,frame_no",
            [
                (Seek.START, 0, 0),
                (Seek.START, 1, 1),
                (Seek.START, 9, 9),
                (Seek.CURRENT, -5, 0),
                (Seek.CURRENT, -1, 4),
                (Seek.CURRENT, 0, 5),
                (Seek.CURRENT, 1, 6),
                (Seek.CURRENT, 4, 9),
                (Seek.END, -9, 0),
                (Seek.END, -1, 8),
                (Seek.END, 0, 9),
            ],
        )
        def test_in_range(self, whence, offset, frame_no):
            self.anim_space.seek(5)  # For CURRENT-relative
            assert self.anim_space.tell() == 5

            assert self.anim_space.seek(offset, whence) == frame_no
            assert self.anim_space.tell() == frame_no

        @pytest.mark.parametrize(
            "whence,offset",
            [
                (Seek.START, -1),
                (Seek.START, 10),
                (Seek.CURRENT, -6),
                (Seek.CURRENT, 5),
                (Seek.END, -10),
                (Seek.END, 1),
            ],
        )
        def test_out_of_range(self, whence, offset):
            self.anim_space.seek(5)  # For CURRENT-relative
            assert self.anim_space.tell() == 5

            with pytest.raises(ValueError, match="'offset'"):
                self.anim_space.seek(offset, whence)

            assert self.anim_space.tell() == 5

    @pytest.mark.parametrize("offset", [-1, 0, 1])
    @pytest.mark.parametrize("whence", Seek)
    def test_indefinite(self, offset, whence):
        assert self.indefinite_space.tell() == 0

        with pytest.raises(IndefiniteSeekError):
            self.indefinite_space.seek(offset, whence)

        assert self.indefinite_space.tell() == 0


class TestAnimate:
    class AnimateChar(Char):
        def _render_(self, render_data, render_args):
            assert render_data is self.render_data
            assert render_args is self.render_args
            return super()._render_(render_data, render_args)

    animate_char = AnimateChar(2, 1)
    render_data = animate_char._get_render_data_(iteration=True)
    render_data[Renderable].duration = 0
    render_args = RenderArgs(AnimateChar)
    padding = ExactPadding()

    anim_space = Space(2, 1)
    with capture_stdout():
        anim_space._animate_(
            anim_space._get_render_data_(iteration=True),
            RenderArgs(Space),
            padding,
            1,
            False,
            STDOUT,
        )
        expected_output = STDOUT.getvalue()

    @pytest.mark.parametrize(
        "render_data",
        [
            animate_char._get_render_data_(iteration=True),
            animate_char._get_render_data_(iteration=True),
        ],
    )
    @capture_stdout()
    def test_render_data(self, render_data):
        self.animate_char.render_data = render_data
        self.animate_char.render_args = self.render_args
        self.animate_char._animate_(
            render_data,
            self.render_args,
            self.padding,
            1,
            False,
            STDOUT,
        )
        assert not STDOUT.getvalue().endswith("\n")

    @pytest.mark.parametrize(
        "render_args",
        [RenderArgs(AnimateChar), RenderArgs(AnimateChar, Char.Args("#"))],
    )
    @capture_stdout()
    def test_render_args(self, render_args):
        self.animate_char.render_data = self.render_data
        self.animate_char.render_args = render_args
        self.animate_char._animate_(
            self.render_data,
            render_args,
            self.padding,
            1,
            False,
            STDOUT,
        )
        assert not STDOUT.getvalue().endswith("\n")

    @pytest.mark.parametrize(
        "padding,padded_height", [(ExactPadding(), 1), (AlignedPadding(3, 3), 3)]
    )
    @capture_stdout()
    def test_padding(self, padding, padded_height):
        self.anim_space._animate_(
            self.anim_space._get_render_data_(iteration=True),
            RenderArgs(Space),
            padding,
            1,
            False,
            STDOUT,
        )
        assert STDOUT.getvalue().count("\n") == anim_n_eol(1, padded_height, 2, 1)
        assert not STDOUT.getvalue().endswith("\n")

    @pytest.mark.parametrize("loops", [1, 2, 10])
    class TestLoops:
        anim_space = Space(2, 1)
        render_data = anim_space._get_render_data_(iteration=True)
        render_data[Renderable].duration = 0
        definite_args = (render_data, RenderArgs(Space), AlignedPadding(3, 3))
        indefinite_args = (RenderArgs(IndefiniteSpace), AlignedPadding(3, 3))

        @capture_stdout()
        def test_definite(self, loops):
            self.anim_space._animate_(*self.definite_args, loops, False, STDOUT)
            assert STDOUT.getvalue().count("\n") == anim_n_eol(1, 3, 2, loops)
            assert not STDOUT.getvalue().endswith("\n")

        @capture_stdout()
        def test_indefinite(self, loops):
            indefinite_space = IndefiniteSpace(2)
            render_data = indefinite_space._get_render_data_(iteration=True)
            render_data[Renderable].duration = 0
            indefinite_space._animate_(
                render_data, *self.indefinite_args, loops, False, STDOUT
            )
            assert STDOUT.getvalue().count("\n") == anim_n_eol(1, 3, 2, 1)
            assert not STDOUT.getvalue().endswith("\n")

    @pytest.mark.parametrize(
        "cache, n_renders", [(False, 8), (True, 4), (3, 8), (4, 4), (5, 4)]
    )
    def test_cache(self, cache, n_renders):
        cache_space = CacheSpace(4, 1)
        render_data = cache_space._get_render_data_(iteration=True)
        render_data[Renderable].duration = 0
        cache_space._animate_(
            render_data, RenderArgs(Space), AlignedPadding(3, 3), 2, cache, STDOUT
        )
        assert cache_space.n_renders == n_renders

    # The *newline* argument to `TemporaryFile` prevents any "\r" written to the file
    # from being read back as "\n".
    temp_file = TemporaryFile("w+", newline="")
    atexit.register(lambda: TestAnimate.temp_file.close())

    @pytest.mark.parametrize("output", [io.StringIO(), temp_file])
    def test_output(self, output):
        self.anim_space._animate_(
            self.anim_space._get_render_data_(iteration=True),
            RenderArgs(Space),
            self.padding,
            1,
            False,
            output,
        )
        output.seek(0)
        assert output.read() == self.expected_output

    @pytest.mark.parametrize("n_frames", [2, 3, 10])
    class TestFrameCount:
        definite_args = (RenderArgs(Space), AlignedPadding(3, 3))
        indefinite_args = (RenderArgs(IndefiniteSpace), AlignedPadding(3, 3))

        @capture_stdout()
        def test_definite(self, n_frames):
            anim_space = Space(n_frames, 1)
            render_data = anim_space._get_render_data_(iteration=True)
            render_data[Renderable].duration = 0
            anim_space._animate_(render_data, *self.definite_args, 1, False, STDOUT)
            assert STDOUT.getvalue().count("\n") == anim_n_eol(1, 3, n_frames, 1)
            assert not STDOUT.getvalue().endswith("\n")

        @capture_stdout()
        def test_indefinite(self, n_frames):
            indefinite_space = IndefiniteSpace(n_frames)
            render_data = indefinite_space._get_render_data_(iteration=True)
            render_data[Renderable].duration = 0
            indefinite_space._animate_(
                render_data, *self.indefinite_args, 1, False, STDOUT
            )
            assert STDOUT.getvalue().count("\n") == anim_n_eol(1, 3, n_frames, 1)
            assert not STDOUT.getvalue().endswith("\n")

    class TestClearFrame:
        class ClearFrameChar(Char):
            n_clears = 0

            def _clear_frame_(self, render_data, render_args, cursor_x, output):
                assert render_data is self.clear_frame_args.render_data
                assert render_args is self.clear_frame_args.render_args
                assert cursor_x == self.clear_frame_args.cursor_x
                assert output is self.clear_frame_args.output

                # The next frame to be drawn should already be rendered.
                # Hence, the next frame to be rendered by the iterator (the value
                # of `frame_offset`) will be the frame after that, which is also
                # **two frames after the frame to be cleared**. Hence, the `-2`.
                cleared_frame_offset = render_data[Renderable].frame_offset - 2
                if cleared_frame_offset < 0:  # frame from previous loop
                    cleared_frame_offset += self.frame_count

                # Each time `_clear_frame_()` is called, it **should've** been called
                # exactly `n_clears = x + <multiple-of-frame-count>` times earlier
                # where `x` is the offset of the frame to be cleared (see above).
                # Note that `n_clears` is incremented after this. Hence, the value
                # at this point is the number of previous calls.
                assert cleared_frame_offset == self.n_clears % self.frame_count

                self.n_clears += 1

        @pytest.mark.parametrize(
            "n_frames,render_args,cursor_x,loops,output",
            [
                (2, RenderArgs(ClearFrameChar), 1, 1, STDOUT),
                (10, RenderArgs(ClearFrameChar, Char.Args("#")), 3, 2, io.StringIO()),
            ],
        )
        @capture_stdout()
        def test(self, n_frames, render_args, cursor_x, loops, output):
            clear_frame_char = self.ClearFrameChar(n_frames, 1)
            render_data = clear_frame_char._get_render_data_(iteration=True)
            render_data[Renderable].duration = 0
            clear_frame_char.clear_frame_args = SimpleNamespace(
                render_data=render_data,
                render_args=render_args,
                cursor_x=cursor_x,
                output=output,
            )

            clear_frame_char._animate_(
                render_data,
                render_args,
                ExactPadding(cursor_x - 1),
                loops,
                True,
                output,
            )
            # The overall last frame is not cleared.
            assert clear_frame_char.n_clears == n_frames * loops - 1

    class TestHandleInterruptedDraw:
        class InterruptedFrameFill(FrameFill):
            interrupted = False

            def __init__(self):
                # The width is crucial for the markers for the write method wrappers
                super().__init__(Size(10, 1))

            def _handle_interrupted_draw_(self, render_data, render_args, output):
                self.interrupted_args = SimpleNamespace(
                    render_data=render_data,
                    render_args=render_args,
                    output=output,
                )
                self.interrupted = True

        class InterruptedFrameFillArgs(ArgsNamespace, render_cls=InterruptedFrameFill):
            foo: bool = False

        def wrap_write(write_method, marker=None):
            def write_wrapper(string):
                if not marker or marker in string:
                    raise KeyboardInterrupt
                return write_method(string)

            return write_wrapper

        frame_0_io = io.StringIO()
        frame_0_io.write = wrap_write(frame_0_io.write, "0000000000")
        frame_9_io = io.StringIO()
        frame_9_io.write = wrap_write(frame_9_io.write, "9999999999")

        @capture_stdout()
        def test_uninterrupted(self):
            interrupted_frame_fill = self.InterruptedFrameFill()
            render_data = interrupted_frame_fill._get_render_data_(iteration=True)
            render_data[Renderable].duration = 0

            interrupted_frame_fill._animate_(
                render_data,
                RenderArgs(self.InterruptedFrameFill),
                ExactPadding(),
                1,
                True,
                STDOUT,
            )
            assert interrupted_frame_fill.interrupted is False

        @pytest.mark.parametrize(
            "render_args,output,frame_interrupted",
            [
                (RenderArgs(InterruptedFrameFill), frame_0_io, 0),
                (+InterruptedFrameFill.Args(True), frame_9_io, 9),
            ],
        )
        @capture_stdout()
        def test_interrupted(self, render_args, output, frame_interrupted):
            interrupted_frame_fill = self.InterruptedFrameFill()
            render_data = interrupted_frame_fill._get_render_data_(iteration=True)
            render_data[Renderable].duration = 0

            interrupted_frame_fill._animate_(
                render_data,
                render_args,
                ExactPadding(),
                1,
                True,
                output,
            )
            assert interrupted_frame_fill.interrupted is True
            assert interrupted_frame_fill.interrupted_args.render_data is render_data
            assert interrupted_frame_fill.interrupted_args.render_args is render_args
            assert interrupted_frame_fill.interrupted_args.output is output
            assert render_data[Renderable].frame_offset == frame_interrupted + 1


class TestGetRenderData:
    anim_space = Space(10, 1)

    def test_render_data(self):
        render_data = self.anim_space._get_render_data_(iteration=False)
        assert render_data.render_cls is Space
        # Serves as a reminder to add tests for new fields
        assert len(render_data[Renderable].as_dict()) == 5

    @pytest.mark.parametrize("render_size", [Size(2, 2), Size(10, 10)])
    def test_size(self, render_size):
        self.anim_space.size = render_size
        render_data = self.anim_space._get_render_data_(iteration=False)
        size = render_data[Renderable].size
        assert size == render_size

    class TestFrameOffsetAndSeekWhence:
        @pytest.mark.parametrize("offset", [0, 5, 9])
        def test_definite(self, offset):
            anim_space = Space(10, 1)
            anim_space.seek(offset)
            render_data = anim_space._get_render_data_(iteration=False)
            assert render_data[Renderable].frame_offset == offset
            assert render_data[Renderable].seek_whence == Seek.START

        def test_indefinite(self):
            render_data = IndefiniteSpace(2)._get_render_data_(iteration=False)
            assert render_data[Renderable].frame_offset == 0
            assert render_data[Renderable].seek_whence == Seek.START

    @pytest.mark.parametrize("duration", [1, 100, FrameDuration.DYNAMIC])
    def test_duration(self, duration):
        self.anim_space.frame_duration = duration
        render_data = self.anim_space._get_render_data_(iteration=False)
        duration = render_data[Renderable].duration
        assert duration == duration

    @pytest.mark.parametrize("iteration", [False, True])
    def test_iteration(self, iteration):
        render_data = self.anim_space._get_render_data_(iteration=iteration)
        assert render_data[Renderable].iteration is iteration


class TestInitRender:
    class TestRenderer:
        space = Space(1, 1)
        char = Char(1, 1)

        class Foo(Renderable):
            _render_ = None

            def _get_render_size_(self):
                return Size(1, 1)

            def __init__(self, data):
                super().__init__(1, 1)
                self.__data = data

            def _get_render_data_(self, *, iteration):
                render_data = super()._get_render_data_(iteration=iteration)
                render_data[__class__].foo = self.__data
                return render_data

        class FooData(DataNamespace, render_cls=Foo):
            foo: Any

        @pytest.mark.parametrize("renderable", [space, char])
        def test_arguments(self, renderable):
            renderer_args = renderable._init_render_(lambda *args: args)[0]
            assert isinstance(renderer_args, tuple)
            assert len(renderer_args) == 2

            render_data, render_args = renderer_args
            assert isinstance(render_data, RenderData)
            assert render_data.render_cls is type(renderable)
            assert isinstance(render_args, RenderArgs)
            assert render_args.render_cls is type(renderable)

        # See also: `TestInitRender.TestIteration`
        @pytest.mark.parametrize("data", [None, Ellipsis, " ", []])
        def test_render_data(self, data):
            render_data = self.Foo(data)._init_render_(lambda *args: args)[0][0]

            assert isinstance(render_data, RenderData)
            assert render_data.render_cls is self.Foo
            assert render_data[self.Foo].foo is data

        # See `TestInitRender.TestRenderArgs`

        @pytest.mark.parametrize("value", [None, Ellipsis, " ", []])
        def test_return_value(self, value):
            assert self.space._init_render_(lambda *_: value)[0] is value

    class TestRenderArgs:
        char = Char(1, 1)

        def test_default(self):
            assert self.char._init_render_(lambda *args: args)[0][1] == RenderArgs(Char)

        @pytest.mark.parametrize(
            "in_args, out_args",
            [
                (None, RenderArgs(Char)),
                (RenderArgs(Renderable), RenderArgs(Char)),
                (RenderArgs(Char), RenderArgs(Char)),
                (+Char.Args("#"), +Char.Args("#")),
            ],
        )
        def test_compatible(self, in_args, out_args):
            render_args = self.char._init_render_(lambda *args: args, in_args)[0][1]
            assert render_args == out_args

        def test_incompatible(self):
            with pytest.raises(IncompatibleRenderArgsError):
                self.char._init_render_(lambda *_: None, RenderArgs(Space))

    class TestPadding:
        space = Space(1, 1)

        def test_default(self):
            assert self.space._init_render_(lambda *_: None)[1] is None

        def test_none(self):
            assert self.space._init_render_(lambda *_: None, padding=None)[1] is None

        @pytest.mark.parametrize(
            "orig_padding", [ExactPadding(), ExactPadding(1, 2, 3, 4, "#")]
        )
        def test_exact(self, orig_padding):
            padding = self.space._init_render_(lambda *_: None, padding=orig_padding)[1]
            assert padding is orig_padding

        @pytest.mark.parametrize(
            "orig_padding",
            [
                AlignedPadding(1, 2, HAlign.LEFT, VAlign.TOP),
                AlignedPadding(3, 3, fill="#"),
                AlignedPadding(20, 10, HAlign.RIGHT, VAlign.BOTTOM),
            ],
        )
        def test_aligned_absolute(self, orig_padding):
            padding = self.space._init_render_(lambda *_: None, padding=orig_padding)[1]
            assert padding is orig_padding

        @pytest.mark.parametrize(
            "orig_padding",
            [
                AlignedPadding(0, -1, HAlign.LEFT, VAlign.TOP),
                AlignedPadding(1, 0, fill="#"),
                AlignedPadding(-1, 10, HAlign.RIGHT, VAlign.BOTTOM),
            ],
        )
        def test_aligned_relative(self, orig_padding):
            padding = self.space._init_render_(lambda *_: None, padding=orig_padding)[1]
            assert padding == orig_padding.resolve(get_terminal_size())

    class TestIteration:
        space = Space(1, 1)

        def test_default(self):
            render_data = self.space._init_render_(lambda *args: args)[0][0]
            assert render_data[Renderable].iteration is False

        @pytest.mark.parametrize("iteration", [False, True])
        def test_non_default(self, iteration):
            render_data = self.space._init_render_(  # fmt: skip
                lambda *args: args, iteration=iteration
            )[0][0]
            assert render_data[Renderable].iteration is iteration

    class TestFinalize:
        space = Space(1, 1)

        def test_default(self):
            render_data = self.space._init_render_(lambda *args: args)[0][0]
            assert render_data.finalized

        @pytest.mark.parametrize("finalize", [False, True])
        def test_non_default(self, finalize):
            render_data = self.space._init_render_(  # fmt: skip
                lambda *args: args, finalize=finalize
            )[0][0]
            assert render_data.finalized is finalize

    class TestCheckSize:
        class TestRenderWidth:
            anim_space = Space(2, 1)

            def test_in_range(self):
                self.anim_space.size = Size(COLUMNS, 1)
                self.anim_space._init_render_(lambda *_: None, check_size=True)

            def test_out_of_range(self):
                self.anim_space.size = Size(COLUMNS + 1, 1)

                # Default
                self.anim_space._init_render_(lambda *_: None)

                # False
                self.anim_space._init_render_(lambda *_: None, check_size=False)

                # True
                with pytest.raises(RenderSizeOutofRangeError, match="Render width"):
                    self.anim_space._init_render_(lambda *_: None, check_size=True)

        class TestPaddedWidth:
            anim_space = Space(2, 1)

            def test_in_range(self):
                self.anim_space._init_render_(
                    lambda *_: None,
                    padding=AlignedPadding(COLUMNS, 1),
                    check_size=True,
                )

            def test_out_of_range(self):
                padding = AlignedPadding(COLUMNS + 1, 1)

                # Default
                self.anim_space._init_render_(lambda *_: None, padding=padding)

                # False
                self.anim_space._init_render_(
                    lambda *_: None, padding=padding, check_size=False
                )

                # True
                with pytest.raises(
                    RenderSizeOutofRangeError, match="Padded render width"
                ):
                    self.anim_space._init_render_(
                        lambda *_: None,
                        padding=padding,
                        check_size=True,
                    )

    class TestAllowScroll:
        class TestRenderHeight:
            anim_space = Space(2, 1)

            def test_in_range(self):
                self.anim_space.size = Size(1, LINES)
                self.anim_space._init_render_(
                    lambda *_: None, check_size=True, allow_scroll=False
                )

            def test_out_of_range(self):
                self.anim_space.size = Size(1, LINES + 1)

                # Default
                with pytest.raises(RenderSizeOutofRangeError, match="Render height"):
                    self.anim_space._init_render_(lambda *_: None, check_size=True)

                # False
                with pytest.raises(RenderSizeOutofRangeError, match="Render height"):
                    self.anim_space._init_render_(
                        lambda *_: None, check_size=True, allow_scroll=False
                    )

                # True
                self.anim_space._init_render_(
                    lambda *_: None, check_size=True, allow_scroll=True
                )

                # ignored when check_size is False
                self.anim_space._init_render_(
                    lambda *_: None, check_size=False, allow_scroll=False
                )

        class TestPaddedHeight:
            anim_space = Space(2, 1)

            def test_in_range(self):
                self.anim_space._init_render_(
                    lambda *_: None,
                    padding=AlignedPadding(1, LINES),
                    check_size=True,
                    allow_scroll=False,
                )

            def test_out_of_range(self):
                padding = AlignedPadding(1, LINES + 1)

                # Default
                with pytest.raises(
                    RenderSizeOutofRangeError, match="Padded render height"
                ):
                    self.anim_space._init_render_(
                        lambda *_: None, padding=padding, check_size=True
                    )

                # False
                with pytest.raises(
                    RenderSizeOutofRangeError, match="Padded render height"
                ):
                    self.anim_space._init_render_(
                        lambda *_: None,
                        padding=padding,
                        check_size=True,
                        allow_scroll=False,
                    )

                # True
                self.anim_space._init_render_(
                    lambda *_: None,
                    padding=padding,
                    check_size=True,
                    allow_scroll=True,
                )

                # ignored when check_size is False
                self.anim_space._init_render_(
                    lambda *_: None,
                    padding=padding,
                    check_size=False,
                    allow_scroll=False,
                )
