import io
import sys
from contextlib import contextmanager
from itertools import zip_longest
from types import MappingProxyType

import pytest

from term_image.exceptions import InvalidSizeError, RenderableError, RenderArgsError
from term_image.geometry import Size
from term_image.render import RenderIterator
from term_image.renderable import (
    Frame,
    FrameCount,
    FrameDuration,
    HAlign,
    Renderable,
    RenderArgs,
    RenderData,
    RenderFormat,
    RenderParam,
    VAlign,
)
from term_image.renderable._renderable import RenderableMeta

from .. import get_terminal_size

stdout = io.StringIO()
columns, lines = get_terminal_size()


@contextmanager
def capture_stdout():
    stdout.seek(0)
    stdout.truncate()
    sys.stdout = stdout
    try:
        yield
    finally:
        stdout.seek(0)
        stdout.truncate()


def draw_n_eol(height, frame_count, loops):
    return (height - 1) * frame_count * loops + 1


class TestClassCreation:
    def test_base(self):
        assert Renderable._ALL_EXPORTED_ATTRS == ()
        assert Renderable._ALL_RENDER_DATA == frozenset(
            {"size", "frame", "duration", "iteration"}
        )
        assert Renderable._ALL_RENDER_PARAMS == {}

    def test_not_a_subclass(self):
        with pytest.raises(RenderableError, match="'Foo' is not a subclass"):

            class Foo(metaclass=RenderableMeta):
                pass

    def test_attrs_only(self):
        class AttrsOnly(Renderable):
            _EXPORTED_ATTRS_ = ("_attr",)
            _EXPORTED_DESCENDANT_ATTRS_ = ("_desc",)

        assert sorted(AttrsOnly._ALL_EXPORTED_ATTRS) == sorted(("_attr", "_desc"))
        assert AttrsOnly._ALL_RENDER_DATA == Renderable._ALL_RENDER_DATA
        assert AttrsOnly._ALL_RENDER_PARAMS == Renderable._ALL_RENDER_PARAMS

    def test_data_only(self):
        class DataOnly(Renderable):
            _RENDER_DATA_ = frozenset({"data"})

        assert sorted(DataOnly._ALL_EXPORTED_ATTRS) == []
        assert DataOnly._ALL_RENDER_DATA == (
            Renderable._ALL_RENDER_DATA | frozenset({"data"})
        )
        assert DataOnly._ALL_RENDER_PARAMS == Renderable._ALL_RENDER_PARAMS

    def test_params_only(self):
        render_param = RenderParam(None)

        class ParamsOnly(Renderable):
            _RENDER_PARAMS_ = {"param": render_param}

        assert sorted(ParamsOnly._ALL_EXPORTED_ATTRS) == []
        assert ParamsOnly._ALL_RENDER_DATA == Renderable._ALL_RENDER_DATA
        assert ParamsOnly._ALL_RENDER_PARAMS == {
            **Renderable._ALL_RENDER_PARAMS,
            "param": render_param,
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


class TestRenderData:
    class A(Renderable):
        _RENDER_DATA_ = frozenset({"a"})

    def test_base(self):
        assert isinstance(Renderable._ALL_RENDER_DATA, frozenset)
        assert Renderable._ALL_RENDER_DATA == frozenset(
            {"size", "frame", "duration", "iteration"}
        )

    def test_cls(self):
        assert isinstance(self.A._ALL_RENDER_DATA, frozenset)
        assert self.A._ALL_RENDER_DATA == Renderable._ALL_RENDER_DATA | frozenset({"a"})

    def test_inheritance(self):
        class B(self.A):
            _RENDER_DATA_ = frozenset({"b"})

        assert B._ALL_RENDER_DATA == Renderable._ALL_RENDER_DATA | frozenset({"a", "b"})

        class C(B):
            _RENDER_DATA_ = frozenset({"c"})

        assert C._ALL_RENDER_DATA == (
            Renderable._ALL_RENDER_DATA | frozenset({"a", "b", "c"})
        )

    def test_multiple_inheritance(self):
        class B(Renderable):
            _RENDER_DATA_ = frozenset({"b"})

        class C(self.A, B):
            _RENDER_DATA_ = frozenset({"c"})

        assert C._ALL_RENDER_DATA == (
            Renderable._ALL_RENDER_DATA | frozenset({"a", "b", "c"})
        )

        class C(B, self.A):
            _RENDER_DATA_ = frozenset({"c"})

        assert C._ALL_RENDER_DATA == (
            Renderable._ALL_RENDER_DATA | frozenset({"a", "b", "c"})
        )

    class TestConflict:
        class A(Renderable):
            _RENDER_DATA_ = frozenset({"a"})

        def test_cls_vs_renderable(self):
            with pytest.raises(
                RenderableError, match="('size',).* 'B'.* conflict.* 'Renderable'"
            ):

                class B(Renderable):
                    _RENDER_DATA_ = frozenset({"size"})

        def test_cls_vs_base(self):
            with pytest.raises(RenderableError, match="('a',).* 'B'.* conflict.* 'A'"):

                class B(self.A):
                    _RENDER_DATA_ = frozenset({"a"})

        def test_cls_vs_base_of_base(self):
            class B(self.A):
                _RENDER_DATA_ = frozenset({"b"})

            with pytest.raises(RenderableError, match="('a',).* 'C'.* conflict.* 'A'"):

                class C(B):
                    _RENDER_DATA_ = frozenset({"a"})

        def test_base_vs_base(self):
            class B(Renderable):
                _RENDER_DATA_ = frozenset({"a"})

            with pytest.raises(RenderableError, match="('a',).* 'B'.* conflict.* 'A'"):

                class C(B, self.A):
                    pass

            with pytest.raises(RenderableError, match="('a',).* 'A'.* conflict.* 'B'"):

                class C(self.A, B):  # noqa: F811
                    pass


class TestRenderParams:
    class A(Renderable):
        render_param = RenderParam("a")
        _RENDER_PARAMS_ = {"a": render_param}

    def test_base(self):
        assert isinstance(Renderable._ALL_RENDER_PARAMS, MappingProxyType)
        assert Renderable._ALL_RENDER_PARAMS == {}

    def test_cls(self):
        assert isinstance(self.A._RENDER_PARAMS_, MappingProxyType)
        assert isinstance(self.A._ALL_RENDER_PARAMS, MappingProxyType)
        assert self.A._ALL_RENDER_PARAMS == {
            **Renderable._ALL_RENDER_PARAMS,
            "a": self.A.render_param,
        }

    def test_inheritance(self):
        class B(self.A):
            render_param = RenderParam("b")
            _RENDER_PARAMS_ = {"b": render_param}

        assert B._ALL_RENDER_PARAMS == {
            **Renderable._ALL_RENDER_PARAMS,
            "a": self.A.render_param,
            "b": B.render_param,
        }

        class C(B):
            render_param = RenderParam("c")
            _RENDER_PARAMS_ = {"c": render_param}

        assert C._ALL_RENDER_PARAMS == {
            **Renderable._ALL_RENDER_PARAMS,
            "a": self.A.render_param,
            "b": B.render_param,
            "c": C.render_param,
        }

    def test_multiple_inheritance(self):
        class B(Renderable):
            render_param = RenderParam("b")
            _RENDER_PARAMS_ = {"b": render_param}

        class C(self.A, B):
            render_param = RenderParam("c")
            _RENDER_PARAMS_ = {"c": render_param}

        assert C._ALL_RENDER_PARAMS == {
            **Renderable._ALL_RENDER_PARAMS,
            "a": self.A.render_param,
            "b": B.render_param,
            "c": C.render_param,
        }

        class C(B, self.A):
            render_param = RenderParam("c")
            _RENDER_PARAMS_ = {"c": render_param}

        assert C._ALL_RENDER_PARAMS == {
            **Renderable._ALL_RENDER_PARAMS,
            "b": B.render_param,
            "a": self.A.render_param,
            "c": C.render_param,
        }

    class TestConflict:
        class A(Renderable):
            render_param = RenderParam("a")
            _RENDER_PARAMS_ = {"a": render_param}

        def test_cls_vs_base(self):
            class B(self.A):
                render_param = RenderParam("b")
                _RENDER_PARAMS_ = {"a": render_param}

            assert B._ALL_RENDER_PARAMS == {
                **Renderable._ALL_RENDER_PARAMS,
                "a": B.render_param,
            }

        def test_cls_vs_base_of_base(self):
            class B(self.A):
                render_param = RenderParam("b")
                _RENDER_PARAMS_ = {"b": render_param}

            class C(B):
                render_param = RenderParam("c")
                _RENDER_PARAMS_ = {"a": render_param}

            assert C._ALL_RENDER_PARAMS == {
                **Renderable._ALL_RENDER_PARAMS,
                "a": C.render_param,
                "b": B.render_param,
            }

        def test_base_vs_base(self):
            class B(Renderable):
                render_param = RenderParam("b")
                _RENDER_PARAMS_ = {"a": render_param}

            class C(self.A, B):
                render_param = RenderParam("c")
                _RENDER_PARAMS_ = {"c": render_param}

            assert C._ALL_RENDER_PARAMS == {
                **Renderable._ALL_RENDER_PARAMS,
                "a": self.A.render_param,
                "c": C.render_param,
            }

            class C(B, self.A):
                render_param = RenderParam("c")
                _RENDER_PARAMS_ = {"c": render_param}

            assert C._ALL_RENDER_PARAMS == {
                **Renderable._ALL_RENDER_PARAMS,
                "a": B.render_param,
                "c": C.render_param,
            }


class Space(Renderable):
    render_size = Size(1, 1)

    def _render_(self, render_data, render_args):
        width, height = render_data.size
        return Frame(
            render_data.frame,
            render_data.duration,
            render_data.size,
            "\n".join((" " * width,) * height),
        )


class Char(Renderable):
    _RENDER_PARAMS_ = {"char": RenderParam(" ")}

    render_size = Size(1, 1)

    def _render_(self, render_data, render_args):
        width, height = render_data.size
        return Frame(
            render_data.frame,
            render_data.duration,
            render_data.size,
            "\n".join((render_args.char * width,) * height),
        )


class FrameNumberFill(Renderable):
    render_size = Size(1, 1)

    def __init__(self, size: Size):
        super().__init__(10, 1)
        self.render_size = size

    def _render_(self, render_data, render_args):
        width, height = render_data.size
        return Frame(
            render_data.frame,
            render_data.duration,
            render_data.size,
            "\n".join((str(render_data.frame) * width,) * height),
        )


class TestInit:
    def test_args(self):
        with pytest.raises(TypeError, match="'frame_count'"):
            Space(Ellipsis, 1)

        for value in (0, -1, -100):
            with pytest.raises(ValueError, match="'frame_count'"):
                Space(value, 1)

        with pytest.raises(TypeError, match="'frame_duration'"):
            Space(2, Ellipsis)

        for value in (0, -1, -100):
            with pytest.raises(ValueError, match="'frame_duration'"):
                Space(2, value)

    def test_ignore_frame_duration_for_non_animated(self):
        Space(1, Ellipsis)


class TestProperties:
    def test_animated(self):
        assert not Space(1, 1).animated

        for value in (2, FrameCount.INDEFINITE, FrameCount.POSTPONED):
            assert Space(value, 1).animated

    def test_frame_count(self):
        class PostponedSpace(Space):
            def __init__(self, frame_count):
                super().__init__(FrameCount.POSTPONED, 1)
                self.__frame_count = frame_count

            def _get_frame_count_(self):
                return self.__frame_count

        for value in (1, 2, FrameCount.INDEFINITE):
            assert Space(value, 1).frame_count == value

        space = Space(FrameCount.POSTPONED, 1)
        with pytest.raises(NotImplementedError):
            space.frame_count

        for value in (2, FrameCount.INDEFINITE):
            assert PostponedSpace(value).frame_count == value

    def test_frame_duration(self):
        for value in (1, 2, 100, FrameDuration.DYNAMIC):
            assert Space(1, value).frame_duration is None

        for value in (1, 2, 100, FrameDuration.DYNAMIC):
            assert Space(2, value).frame_duration == value

        space = Space(2, 1)

        with pytest.raises(TypeError, match="'frame_duration'"):
            space.frame_duration = Ellipsis

        for value in (0, -1, -100):
            with pytest.raises(ValueError, match="'frame_duration'"):
                space.frame_duration = value

        for value in (1, 2, 100, FrameDuration.DYNAMIC):
            space.frame_duration = value
            assert space.frame_duration == value


def test_iter():
    space = Space(1, 1)
    with pytest.raises(ValueError, match="not animated"):
        iter(space)

    r_iter = iter(Space(2, 1))
    assert isinstance(r_iter, RenderIterator)
    assert r_iter.loop == 1


def test_str():
    assert str(Space(1, 1)) == " "


class TestDraw:
    @capture_stdout()
    def test_args(self):
        for space in (Space(1, 1), Space(2, 1)):
            with pytest.raises(TypeError, match="'render_args'"):
                space.draw(Ellipsis)

            with pytest.raises(TypeError, match="'render_fmt'"):
                space.draw(render_fmt=Ellipsis)

            with pytest.raises(TypeError, match="'check_size'"):
                space.draw(check_size=Ellipsis)

            with pytest.raises(TypeError, match="'scroll'"):
                space.draw(scroll=Ellipsis)

    class TestNonAnimation:
        space = Space(1, 1)
        anim_space = Space(2, 1)
        char = Char(1, 1)

        @capture_stdout()
        def test_args_ignored(self):
            # ignored for non-animated renderables
            self.space.draw(animate=Ellipsis)
            self.space.draw(loops=Ellipsis)
            self.space.draw(cache=Ellipsis)

        @capture_stdout()
        def test_default(self):
            self.space.draw()
            assert stdout.getvalue().count("\n") == draw_n_eol(lines - 2, 1, 1)
            assert stdout.getvalue().endswith("\n")

        # Just ensures the argument is passed on and used appropriately.
        # The full tests are at `TestInitRender`.
        @capture_stdout()
        def test_render_args(self):
            self.char.draw(RenderArgs(Char, char="\u2850"))
            assert stdout.getvalue().count("\n") == draw_n_eol(lines - 2, 1, 1)
            assert stdout.getvalue().count("\u2850") == 1
            assert stdout.getvalue().endswith("\n")

        # Just ensures the argument is passed on and used appropriately.
        # The full tests are at `TestInitRender`.
        @capture_stdout()
        def test_render_fmt(self):
            self.space.draw(render_fmt=RenderFormat(3, 3))
            assert stdout.getvalue().count("\n") == draw_n_eol(3, 1, 1)
            assert stdout.getvalue().endswith("\n")

        def test_animate(self):
            with capture_stdout():
                self.space.draw()
                output = stdout.getvalue()

            with capture_stdout():
                self.space.draw(animate=True)
                assert output == stdout.getvalue()

            with capture_stdout():
                self.space.draw(animate=False)
                assert output == stdout.getvalue()

            with capture_stdout():
                self.anim_space.draw(animate=False)
                assert output == stdout.getvalue()

        # Just ensures the argument is passed on and used appropriately.
        # The full tests are at `TestInitRender`.
        class TestSizeValidation:
            space = Space(1, 1)

            @capture_stdout()
            def test_check_size(self):
                space = Space(1, 1)
                space.render_size = Size(columns + 1, 1)
                render_fmt = RenderFormat(columns + 1, 1)

                # Default
                with pytest.raises(InvalidSizeError, match="Render width"):
                    space.draw()
                with pytest.raises(InvalidSizeError, match="Padding width"):
                    self.space.draw(render_fmt=render_fmt)

                # True
                with pytest.raises(InvalidSizeError, match="Render width"):
                    space.draw(check_size=True)
                with pytest.raises(InvalidSizeError, match="Padding width"):
                    self.space.draw(render_fmt=render_fmt, check_size=True)

                # False
                space.draw(check_size=False)
                self.space.draw(render_fmt=render_fmt, check_size=False)

            @capture_stdout()
            def test_scroll(self):
                space = Space(1, 1)
                space.render_size = Size(1, lines + 1)
                render_fmt = RenderFormat(1, lines + 1)

                # Default
                with pytest.raises(InvalidSizeError, match="Render height"):
                    space.draw()
                with pytest.raises(InvalidSizeError, match="Padding height"):
                    self.space.draw(render_fmt=render_fmt)

                # False
                with pytest.raises(InvalidSizeError, match="Render height"):
                    space.draw(scroll=False)
                with pytest.raises(InvalidSizeError, match="Padding height"):
                    self.space.draw(render_fmt=render_fmt, scroll=False)

                # True
                self.space.draw(scroll=True)
                self.space.draw(render_fmt=render_fmt, scroll=True)

    class TestAnimation:
        anim_space = Space(2, 1)
        anim_char = Char(2, 1)

        @capture_stdout()
        def test_args(self):
            with pytest.raises(TypeError, match="'animate'"):
                self.anim_space.draw(animate=Ellipsis)

            with pytest.raises(TypeError, match="'loops'"):
                self.anim_space.draw(loops=Ellipsis)

            with pytest.raises(TypeError, match="'cache'"):
                self.anim_space.draw(cache=Ellipsis)

        # Just ensures the argument is passed on and used appropriately.
        # The full tests are at `TestInitRender`.
        @capture_stdout()
        def test_render_args(self):
            self.anim_char.draw(RenderArgs(Char, char="\u2850"), loops=1)
            assert stdout.getvalue().count("\n") == draw_n_eol(lines - 2, 2, 1)
            assert stdout.getvalue().count("\u2850") == 2
            assert stdout.getvalue().endswith("\n")

        # Just ensures the argument is passed on and used appropriately.
        # The full tests are at `TestInitRender`.
        @capture_stdout()
        def test_render_fmt(self):
            self.anim_space.draw(render_fmt=RenderFormat(3, 3), loops=1)
            assert stdout.getvalue().count("\n") == draw_n_eol(3, 2, 1)
            assert stdout.getvalue().endswith("\n")

        def test_animate(self):
            with capture_stdout():
                self.anim_space.draw(loops=1)
                output = stdout.getvalue()

            with capture_stdout():
                self.anim_space.draw(animate=True, loops=1)
                assert output == stdout.getvalue()

            with capture_stdout():
                self.anim_space.draw(animate=False, loops=1)
                assert output != stdout.getvalue()

        # Just ensures the argument is passed on and used appropriately.
        # The full tests are at `TestInitRender`.
        class TestSizeValidation:
            anim_space = Space(2, 1)

            @capture_stdout()
            def test_check_size(self):
                anim_space = Space(2, 1)
                anim_space.render_size = Size(columns + 1, 1)
                render_fmt = RenderFormat(columns + 1, 1)

                # Default
                with pytest.raises(InvalidSizeError, match="Render width"):
                    anim_space.draw()
                with pytest.raises(InvalidSizeError, match="Padding width"):
                    self.anim_space.draw(render_fmt=render_fmt)

                # True
                with pytest.raises(InvalidSizeError, match="Render width"):
                    anim_space.draw(check_size=True)
                with pytest.raises(InvalidSizeError, match="Padding width"):
                    self.anim_space.draw(render_fmt=render_fmt, check_size=True)

                # False
                with pytest.raises(InvalidSizeError, match="Render width"):
                    anim_space.draw(check_size=False)
                with pytest.raises(InvalidSizeError, match="Padding width"):
                    self.anim_space.draw(render_fmt=render_fmt, check_size=False)

            @capture_stdout()
            def test_scroll(self):
                anim_space = Space(2, 1)
                anim_space.render_size = Size(1, lines + 1)
                render_fmt = RenderFormat(1, lines + 1)

                # Default
                with pytest.raises(InvalidSizeError, match="Render height"):
                    anim_space.draw()
                with pytest.raises(InvalidSizeError, match="Padding height"):
                    self.anim_space.draw(render_fmt=render_fmt)

                # False
                with pytest.raises(InvalidSizeError, match="Render height"):
                    anim_space.draw(scroll=False)
                with pytest.raises(InvalidSizeError, match="Padding height"):
                    self.anim_space.draw(render_fmt=render_fmt, scroll=False)

                # True
                with pytest.raises(InvalidSizeError, match="Render height"):
                    anim_space.draw(scroll=True)
                with pytest.raises(InvalidSizeError, match="Padding height"):
                    self.anim_space.draw(render_fmt=render_fmt, scroll=True)

        class TestDefinite:
            # Can't test the default for definite frame count since it loops infinitely

            def test_loops(self):
                anim_space = Space(2, 1)
                for loops in (1, 2, 10):
                    with capture_stdout():
                        anim_space.draw(loops=loops)
                        assert stdout.getvalue().count("\n") == draw_n_eol(
                            lines - 2, 2, loops
                        )
                        assert stdout.getvalue().endswith("\n")

            def test_frame_count(self):
                for count in (2, 3, 10):
                    with capture_stdout():
                        Space(count, 1).draw(loops=1)
                        assert stdout.getvalue().count("\n") == draw_n_eol(
                            lines - 2, count, 1
                        )
                        assert stdout.getvalue().endswith("\n")

        class TestIndefinite:
            class IndefiniteSpace(Space):
                _RENDER_DATA_ = frozenset({"frames"})

                def __init__(self, frame_count):
                    super().__init__(FrameCount.INDEFINITE, 1)
                    self.__frame_count = frame_count

                def _render_(self, render_data, render_args):
                    if render_data.iteration:
                        next(render_data.frames)
                    return super()._render_(render_data, render_args)

                def _get_render_data_(self, *, iteration):
                    render_data = super()._get_render_data_(iteration=iteration)
                    render_data["frames"] = (
                        iter(range(self.__frame_count)) if iteration else None
                    )
                    return render_data

            @capture_stdout()
            def test_default(self):
                self.IndefiniteSpace(2).draw()
                assert stdout.getvalue().count("\n") == draw_n_eol(lines - 2, 2, 1)
                assert stdout.getvalue().endswith("\n")

            def test_loops(self):
                for loops in (1, 2, 10, -1):
                    with capture_stdout():
                        self.IndefiniteSpace(2).draw(loops=loops)
                        assert stdout.getvalue().count("\n") == draw_n_eol(
                            lines - 2, 2, 1
                        )
                        assert stdout.getvalue().endswith("\n")

            def test_frame_count(self):
                for count in (2, 3, 10):
                    with capture_stdout():
                        self.IndefiniteSpace(count).draw()
                        assert stdout.getvalue().count("\n") == draw_n_eol(
                            lines - 2, count, 1
                        )
                        assert stdout.getvalue().endswith("\n")


class TestRender:
    space = Space(1, 1)

    def test_args(self):
        with pytest.raises(TypeError, match="'render_args'"):
            self.space.render(Ellipsis)

        with pytest.raises(TypeError, match="'render_fmt'"):
            self.space.render(render_fmt=Ellipsis)

    def test_default(self):
        assert (
            self.space.render().render
            == " "
            == str(self.space)
            == self.space.render(None).render
            == self.space.render(render_fmt=RenderFormat(1, 1)).render
        )

    # Just ensures the argument is passed on and used appropriately.
    # The full tests are at `TestInitRender`.
    def test_render_args(self):
        char = Char(1, 1)
        for value in "123abc":
            assert char.render(RenderArgs(Char, char=value)).render == value

    # Just ensures the argument is passed on and used appropriately.
    # The full tests are at `TestInitRender`.
    def test_render_fmt(self):
        assert (
            self.space.render(render_fmt=RenderFormat(3, 3)).render == "   \n   \n   "
        )


class TestSeekTell:
    def test_definite(self):
        space = Space(10, 1)
        assert space.tell() == 0

        with pytest.raises(TypeError, match="'offset'"):
            space.seek(Ellipsis)

        with pytest.raises(ValueError, match="'offset'"):
            space.seek(-1)

        assert space.tell() == 0
        space.seek(1)
        assert space.tell() == 1
        space.seek(9)
        assert space.tell() == 9

        with pytest.raises(ValueError, match="'offset'"):
            space.seek(10)

        assert space.tell() == 9

    def test_indefinite(self):
        space = Space(FrameCount.INDEFINITE, 1)
        assert space.tell() == 0

        for value in (0, 1):
            with pytest.raises(RenderableError):
                space.seek(value)

        assert space.tell() == 0


class TestFormatRender:
    size = Size(5, 5)
    char = Char(1, 1)
    char.render_size = size
    char_render_args = RenderArgs(Char, char="#")
    render = char.render(char_render_args).render

    @staticmethod
    def check_padding(f_render, render_fmt, render, r_size, top, left, bottom, right):
        f_render = f_render.split("\n")
        render = render.split("\n")
        width, height = map(max, render_fmt.size, r_size)

        assert width - left - right == r_size.width
        assert height - top - bottom == r_size.height

        for line in f_render[:top]:
            assert line == " " * width

        for line, render_line in zip_longest(f_render[top : height - bottom], render):
            assert line[:left] == " " * left
            assert line[left : width - right] == render_line
            assert line[width - right :] == " " * right

        for line in f_render[height - bottom :]:
            assert line == " " * width

    def test_no_padding(self):
        for value in (1, 5):
            assert (
                self.char._format_render_(
                    self.render, self.size, RenderFormat(value, value)
                )
                == self.render
            )

    def test_padding(self):
        for render_fmt, dimensions in (
            # left
            (RenderFormat(7, 1, HAlign.LEFT, VAlign.MIDDLE), (0, 0, 0, 2)),
            (RenderFormat(10, 1, HAlign.LEFT, VAlign.MIDDLE), (0, 0, 0, 5)),
            # center
            (RenderFormat(7, 1, HAlign.CENTER, VAlign.MIDDLE), (0, 1, 0, 1)),
            (RenderFormat(10, 1, HAlign.CENTER, VAlign.MIDDLE), (0, 2, 0, 3)),
            # right
            (RenderFormat(7, 1, HAlign.RIGHT, VAlign.MIDDLE), (0, 2, 0, 0)),
            (RenderFormat(10, 1, HAlign.RIGHT, VAlign.MIDDLE), (0, 5, 0, 0)),
            # top
            (RenderFormat(1, 7, HAlign.CENTER, VAlign.TOP), (0, 0, 2, 0)),
            (RenderFormat(1, 10, HAlign.CENTER, VAlign.TOP), (0, 0, 5, 0)),
            # middle
            (RenderFormat(1, 7, HAlign.CENTER, VAlign.MIDDLE), (1, 0, 1, 0)),
            (RenderFormat(1, 10, HAlign.CENTER, VAlign.MIDDLE), (2, 0, 3, 0)),
            # bottom
            (RenderFormat(1, 7, HAlign.CENTER, VAlign.BOTTOM), (2, 0, 0, 0)),
            (RenderFormat(1, 10, HAlign.CENTER, VAlign.BOTTOM), (5, 0, 0, 0)),
            # left, top
            (RenderFormat(7, 10, HAlign.LEFT, VAlign.TOP), (0, 0, 5, 2)),
            (RenderFormat(10, 7, HAlign.LEFT, VAlign.TOP), (0, 0, 2, 5)),
            # left, middle
            (RenderFormat(7, 10, HAlign.LEFT, VAlign.MIDDLE), (2, 0, 3, 2)),
            (RenderFormat(10, 7, HAlign.LEFT, VAlign.MIDDLE), (1, 0, 1, 5)),
            # left, bottom
            (RenderFormat(7, 10, HAlign.LEFT, VAlign.BOTTOM), (5, 0, 0, 2)),
            (RenderFormat(10, 7, HAlign.LEFT, VAlign.BOTTOM), (2, 0, 0, 5)),
            # center, top
            (RenderFormat(7, 10, HAlign.CENTER, VAlign.TOP), (0, 1, 5, 1)),
            (RenderFormat(10, 7, HAlign.CENTER, VAlign.TOP), (0, 2, 2, 3)),
            # center, middle
            (RenderFormat(7, 10, HAlign.CENTER, VAlign.MIDDLE), (2, 1, 3, 1)),
            (RenderFormat(10, 7, HAlign.CENTER, VAlign.MIDDLE), (1, 2, 1, 3)),
            # center, bottom
            (RenderFormat(7, 10, HAlign.CENTER, VAlign.BOTTOM), (5, 1, 0, 1)),
            (RenderFormat(10, 7, HAlign.CENTER, VAlign.BOTTOM), (2, 2, 0, 3)),
            # right, top
            (RenderFormat(7, 10, HAlign.RIGHT, VAlign.TOP), (0, 2, 5, 0)),
            (RenderFormat(10, 7, HAlign.RIGHT, VAlign.TOP), (0, 5, 2, 0)),
            # right, middle
            (RenderFormat(7, 10, HAlign.RIGHT, VAlign.MIDDLE), (2, 2, 3, 0)),
            (RenderFormat(10, 7, HAlign.RIGHT, VAlign.MIDDLE), (1, 5, 1, 0)),
            # right, bottom
            (RenderFormat(7, 10, HAlign.RIGHT, VAlign.BOTTOM), (5, 2, 0, 0)),
            (RenderFormat(10, 7, HAlign.RIGHT, VAlign.BOTTOM), (2, 5, 0, 0)),
        ):
            self.check_padding(
                self.char._format_render_(self.render, self.size, render_fmt),
                render_fmt,
                self.render,
                self.size,
                *dimensions,
            )

    def test_render_size(self):
        char = Char(1, 1)
        render_fmt = RenderFormat(20, 20)

        for size, dimensions in (
            (Size(1, 2), (9, 9, 9, 10)),
            (Size(14, 11), (4, 3, 5, 3)),
        ):
            char.render_size = size
            render = char.render(self.char_render_args).render
            self.check_padding(
                char._format_render_(render, size, render_fmt),
                render_fmt,
                render,
                size,
                *dimensions,
            )


class TestGetRenderData:
    anim_space = Space(10, 1)

    def test_all(self):
        render_data = self.anim_space._get_render_data_(iteration=False)
        assert isinstance(render_data, dict)
        assert len(render_data) == 4
        assert render_data.keys() == {"size", "frame", "duration", "iteration"}

    def test_size(self):
        for value in (2, 10):
            self.anim_space.render_size = render_size = Size(value, value)
            size = self.anim_space._get_render_data_(iteration=False)["size"]
            assert isinstance(size, Size)
            assert size == render_size

    def test_frame(self):
        for value in (2, 8):
            self.anim_space.seek(value)
            frame = self.anim_space._get_render_data_(iteration=False)["frame"]
            assert isinstance(frame, int)
            assert frame == value

    def test_duration(self):
        for value in (2, 100, FrameDuration.DYNAMIC):
            self.anim_space.frame_duration = value
            duration = self.anim_space._get_render_data_(iteration=False)["duration"]
            assert isinstance(duration, (int, FrameDuration))
            assert duration == value

    def test_iteration(self):
        self.anim_space._get_render_data_(iteration=False)["iteration"] is False
        self.anim_space._get_render_data_(iteration=True)["iteration"] is True


class TestInitRender:
    space = Space(1, 1)
    anim_space = Space(2, 1)
    char = Char(1, 1)

    class TestReturnValue:
        space = Space(1, 1)

        def test_default(self):
            return_value = self.space._init_render_(lambda *_: None)

            assert isinstance(return_value, tuple)
            assert len(return_value) == 3

            renderer_return, render_size, render_fmt = return_value

            assert renderer_return is None
            assert isinstance(render_size, Size)
            assert render_fmt is None

        def test_renderer_return(self):
            for value in (None, 2, "", (), []):
                assert self.space._init_render_(lambda *_: value)[0] is value

        def test_render_size(self):
            space = Space(1, 1)
            for value in (1, 100):
                space.render_size = Size(value, value)
                render_size = space._init_render_(lambda *_: None)[1]

                assert isinstance(render_size, Size)
                assert render_size == Size(value, value)

        # See also: `TestInitRender.TestRenderFmt`
        def test_render_fmt(self):
            assert self.space._init_render_(lambda *_: None)[2] is None
            assert self.space._init_render_(lambda *_: None, render_fmt=None)[2] is None
            assert isinstance(
                self.space._init_render_(
                    lambda *_: None, render_fmt=RenderFormat(1, 1)
                )[2],
                RenderFormat,
            )

    def test_renderer(self):
        for renderable, render_cls in ((self.space, Space), (self.char, Char)):
            renderer_args = renderable._init_render_(lambda *args: args)[0]

            assert isinstance(renderer_args, tuple)
            assert len(renderer_args) == 2

            render_data, render_args = renderer_args

            assert isinstance(render_data, RenderData)
            assert render_data.render_cls is render_cls

            assert isinstance(render_args, RenderArgs)
            assert render_args.render_cls is render_cls

    # See also: `TestInitRender.test_iteration`
    def test_render_data(self):
        class Foo(Renderable):
            _RENDER_DATA_ = frozenset({"foo"})
            render_size = _render_ = None

            def __init__(self, value):
                super().__init__(1, 1)
                self.__value = value

            def _get_render_data_(self, *, iteration):
                return {
                    **super()._get_render_data_(iteration=iteration),
                    "foo": self.__value,
                }

        for value in (None, 1, " ", []):
            render_data = Foo(value)._init_render_(lambda *args: args)[0][0]

            assert isinstance(render_data, RenderData)
            assert render_data.render_cls is Foo
            assert "foo" in vars(render_data)
            assert render_data.foo is value

    class TestRenderArgs:
        char = Char(1, 1)

        def test_default(self):
            render_args = self.char._init_render_(lambda *args: args)[0][1]

            assert isinstance(render_args, RenderArgs)
            assert render_args.render_cls is Char
            assert render_args.char == " "

            assert (
                render_args == self.char._init_render_(lambda *args: args, None)[0][1]
            )

            assert (
                render_args
                == self.char._init_render_(lambda *args: args, RenderArgs(Char))[0][1]
            )

        def test_non_default(self):
            for value in "123abc":
                render_args = self.char._init_render_(
                    lambda *args: args, RenderArgs(Char, char=value)
                )[0][1]

                assert isinstance(render_args, RenderArgs)
                assert render_args.render_cls is Char
                assert render_args.char == value

        def test_compatibility(self):
            class A(Renderable):
                def __init__(self):
                    super().__init__(1, 1)

                render_size = _render_ = None

            class B(A):
                pass

            class C(A):
                pass

            # compatible
            for cls1, cls2 in (
                (A, Renderable),
                (A, A),
                (B, Renderable),
                (B, A),
                (B, B),
                (C, Renderable),
                (C, A),
                (C, C),
            ):
                (
                    cls1()._init_render_(lambda *args: args, RenderArgs(cls2))[0][1]
                    == RenderArgs(cls1)
                )

            # incompatible
            for cls1, cls2 in ((A, B), (A, C), (B, C), (C, B)):
                with pytest.raises(RenderArgsError, match="incompatible"):
                    cls1()._init_render_(lambda *_: None, RenderArgs(cls2))

    class TestRenderFmt:
        space = Space(1, 1)

        def test_default(self):
            assert self.space._init_render_(lambda *_: None)[2] is None
            assert self.space._init_render_(lambda *_: None, render_fmt=None)[2] is None

        def test_absolute(self):
            for value in (1, 100):
                render_fmt = self.space._init_render_(
                    lambda *_: None, render_fmt=RenderFormat(value, value)
                )[2]

                assert isinstance(render_fmt, RenderFormat)
                assert render_fmt == RenderFormat(value, value)

        def test_terminal_relative(self):
            for value in (0, -10):
                render_fmt = self.space._init_render_(
                    lambda *_: None, render_fmt=RenderFormat(value, value)
                )[2]

                assert isinstance(render_fmt, RenderFormat)
                assert render_fmt == RenderFormat(columns + value, lines + value)

        def test_align(self):
            for h_align, v_align in zip(HAlign, VAlign):
                render_fmt = self.space._init_render_(
                    lambda *_: None, render_fmt=RenderFormat(1, 1, h_align, v_align)
                )[2]

                assert isinstance(render_fmt, RenderFormat)
                assert render_fmt == RenderFormat(1, 1, h_align, v_align)

    def test_iteration(self):
        render_data = self.space._init_render_(lambda *args: args)[0][0]

        assert render_data.iteration is False

        for value in (False, True):
            render_data = self.space._init_render_(  # fmt: skip
                lambda *args: args, iteration=value
            )[0][0]

            assert render_data.iteration is value

    def test_finalize(self):
        render_data = self.space._init_render_(lambda *args: args)[0][0]

        assert render_data.finalized

        for value in (False, True):
            render_data = self.space._init_render_(  # fmt: skip
                lambda *args: args, finalize=value
            )[0][0]

            assert render_data.finalized is value

    class TestSizeValidation:
        space = Space(1, 1)

        class TestAnimationFalse:
            class TestCheckSize:
                def test_render_width(self):
                    anim_space = Space(2, 1)

                    # in range
                    anim_space.render_size = Size(columns, 1)
                    anim_space._init_render_(lambda *_: None, check_size=True)

                    # out of range
                    anim_space.render_size = Size(columns + 1, 1)

                    # # Default
                    anim_space._init_render_(lambda *_: None)

                    # # False
                    anim_space._init_render_(lambda *_: None, check_size=False)

                    # # True
                    with pytest.raises(InvalidSizeError, match="Render width"):
                        anim_space._init_render_(lambda *_: None, check_size=True)

                def test_padding_width(self):
                    anim_space = Space(2, 1)

                    # in range
                    anim_space._init_render_(
                        lambda *_: None,
                        render_fmt=RenderFormat(columns, 1),
                        check_size=True,
                    )

                    # out of range
                    render_fmt = RenderFormat(columns + 1, 1)

                    # # Default
                    anim_space._init_render_(
                        lambda *_: None,
                        render_fmt=render_fmt,
                    )

                    # # False
                    anim_space._init_render_(
                        lambda *_: None,
                        render_fmt=render_fmt,
                        check_size=False,
                    )

                    # # True
                    with pytest.raises(InvalidSizeError, match="Padding width"):
                        anim_space._init_render_(
                            lambda *_: None,
                            render_fmt=render_fmt,
                            check_size=True,
                        )

            class TestScroll:
                def test_render_height(self):
                    anim_space = Space(2, 1)

                    # in range
                    anim_space.render_size = Size(1, lines)
                    anim_space._init_render_(
                        lambda *_: None, check_size=True, scroll=False
                    )

                    # out of range
                    anim_space.render_size = Size(1, lines + 1)

                    # # Default
                    with pytest.raises(InvalidSizeError, match="Render height"):
                        anim_space._init_render_(lambda *_: None, check_size=True)

                    # # False
                    with pytest.raises(InvalidSizeError, match="Render height"):
                        anim_space._init_render_(
                            lambda *_: None, check_size=True, scroll=False
                        )

                    # # True
                    anim_space._init_render_(
                        lambda *_: None, check_size=True, scroll=True
                    )

                    # # ignored when check_size is False
                    anim_space._init_render_(
                        lambda *_: None, check_size=False, scroll=False
                    )

                def test_padding_height(self):
                    anim_space = Space(2, 1)

                    # in range
                    anim_space._init_render_(
                        lambda *_: None,
                        render_fmt=RenderFormat(1, lines),
                        check_size=True,
                        scroll=False,
                    )

                    # out of range
                    render_fmt = RenderFormat(1, lines + 1)

                    # # Default
                    with pytest.raises(InvalidSizeError, match="Padding height"):
                        anim_space._init_render_(
                            lambda *_: None,
                            render_fmt=render_fmt,
                            check_size=True,
                        )

                    # # False
                    with pytest.raises(InvalidSizeError, match="Padding height"):
                        anim_space._init_render_(
                            lambda *_: None,
                            render_fmt=render_fmt,
                            check_size=True,
                            scroll=False,
                        )

                    # # True
                    anim_space._init_render_(
                        lambda *_: None,
                        render_fmt=render_fmt,
                        check_size=True,
                        scroll=True,
                    )

                    # # ignored when check_size is False
                    anim_space._init_render_(
                        lambda *_: None,
                        render_fmt=render_fmt,
                        check_size=False,
                        scroll=False,
                    )

        class TestAnimationTrue:
            def test_check_size(self):
                anim_space = Space(2, 1)
                anim_space.render_size = Size(columns + 1, 1)

                with pytest.raises(InvalidSizeError, match="Render width"):
                    anim_space._init_render_(
                        lambda *_: None, animation=True, check_size=False
                    )

            def test_scroll(self):
                anim_space = Space(2, 1)
                anim_space.render_size = Size(1, lines + 1)

                with pytest.raises(InvalidSizeError, match="Render height"):
                    anim_space._init_render_(
                        lambda *_: None, animation=True, check_size=True, scroll=True
                    )
