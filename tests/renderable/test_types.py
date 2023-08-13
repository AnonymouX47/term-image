import os
from typing import Any

import pytest

from term_image.exceptions import RenderArgsError, RenderDataError, RenderFormatError
from term_image.geometry import Size
from term_image.renderable import (
    Frame,
    HAlign,
    Renderable,
    RenderArgs,
    RenderData,
    RenderFormat,
    RenderParam,
    VAlign,
)


class Foo(Renderable):
    _RENDER_DATA_ = frozenset({"foo", "bar"})

    class Args(RenderArgs.Namespace):
        foo: Any = "FOO"
        bar: Any = "BAR"


class TestFrame:
    def test_is_tuple(self):
        frame = Frame(None, None, None, None)
        assert isinstance(frame, tuple)
        assert len(frame) == 4

    class TestFields:
        def test_number(self):
            for value in (0, 10):
                frame = Frame(value, None, None, None)
                assert frame.number is value

        def test_duration(self):
            for value in (1, 100):
                frame = Frame(None, value, None, None)
                assert frame.duration is value

        def test_size(self):
            for value in (Size(1, 3), Size(100, 30)):
                frame = Frame(None, None, value, None)
                assert frame.size is value

        def test_render(self):
            for value in (" ", " " * 10):
                frame = Frame(None, None, None, value)
                assert frame.render is value

    def test_immutability(self):
        frame = Frame(None, None, None, None)
        for attr in ("number", "duration", "size", "render"):
            with pytest.raises(AttributeError):
                setattr(frame, attr, Ellipsis)

            with pytest.raises(AttributeError):
                delattr(frame, attr)

    def test_str(self):
        for value in (" ", " " * 10):
            frame = Frame(None, None, None, value)
            assert str(frame) is value is frame.render


class TestRenderParam:
    def test_is_tuple(self):
        render_param = RenderParam(None)
        assert isinstance(render_param, tuple)
        assert len(render_param) == 5

    class TestFields:
        def test_default(self):
            for value in (None, Ellipsis):
                render_param = RenderParam(value)
                assert render_param.default is value
                render_param = RenderParam(default=value)
                assert render_param.default is value

        def test_type_check(self):
            for value in (None, lambda cls, value: True):
                render_param = RenderParam(None, value)
                assert render_param.type_check is value
                render_param = RenderParam(None, type_check=value)
                assert render_param.type_check is value

        def test_type_msg(self):
            for value in (None, "invalid type"):
                render_param = RenderParam(None, None, value)
                assert render_param.type_msg is value
                render_param = RenderParam(None, type_msg=value)
                assert render_param.type_msg is value

        def test_value_check(self):
            for value in (None, lambda cls, value: True):
                render_param = RenderParam(None, None, None, value)
                assert render_param.value_check is value
                render_param = RenderParam(None, value_check=value)
                assert render_param.value_check is value

        def test_value_msg(self):
            for value in (None, "invalid value"):
                render_param = RenderParam(None, None, None, None, value)
                assert render_param.value_msg is value
                render_param = RenderParam(None, value_msg=value)
                assert render_param.value_msg is value

    def test_immutability(self):
        render_param = RenderParam(None)
        for attr in ("default", "type_check", "type_msg", "value_check", "value_msg"):
            with pytest.raises(AttributeError):
                setattr(render_param, attr, Ellipsis)

            with pytest.raises(AttributeError):
                delattr(render_param, attr)


class TestRenderArgs:
    def test_args(self):
        with pytest.raises(TypeError, match="'render_cls'"):
            RenderArgs(Ellipsis)

        with pytest.raises(TypeError, match="second argument"):
            RenderArgs(Renderable, Ellipsis)

        with pytest.raises(TypeError, match=r"'namespaces\[0\]'"):
            RenderArgs(Renderable, RenderArgs(Renderable), Ellipsis)

        with pytest.raises(TypeError, match=r"'namespaces\[1\]'"):
            RenderArgs(Foo, Foo.Args(), Ellipsis)

    def test_base(self):
        render_args = RenderArgs(Renderable)
        assert render_args.render_cls is Renderable
        assert tuple(render_args) == ()

    def test_render_cls(self):
        render_args = RenderArgs(Foo)
        assert render_args.render_cls is Foo

    class TestNamespaces:
        class TestCompatibility:
            class A(Renderable):
                class Args(RenderArgs.Namespace):
                    foo: None = None

            class B(A):
                class Args(RenderArgs.Namespace):
                    foo: None = None

            class C(A):
                class Args(RenderArgs.Namespace):
                    foo: None = None

            def test_compatible(self):
                for cls1, cls2 in (
                    (self.A, self.A),
                    (self.B, self.A),
                    (self.B, self.B),
                    (self.C, self.A),
                    (self.C, self.C),
                ):
                    assert RenderArgs(cls1, cls2.Args()) == RenderArgs(cls1)

            def test_incompatible(self):
                for cls1, cls2 in (
                    (self.A, self.B),
                    (self.A, self.C),
                    (self.B, self.C),
                    (self.C, self.B),
                ):
                    with pytest.raises(RenderArgsError, match="incompatible"):
                        RenderArgs(cls1, cls2.Args())

        def test_default(self):
            render_args = RenderArgs(Foo)
            assert render_args[Foo] == Foo.Args()
            assert render_args[Foo] == Foo.Args("FOO", "BAR")

        def test_non_default(self):
            namespace = Foo.Args("bar", "foo")
            render_args = RenderArgs(Foo, namespace)
            assert render_args[Foo] is namespace

        def test_multiple_with_same_render_cls(self):
            namespace_foo = Foo.Args(foo="bar")
            namespace_bar = Foo.Args(bar="foo")

            render_args = RenderArgs(Foo, namespace_foo, namespace_bar)
            assert render_args[Foo] is namespace_bar

            render_args = RenderArgs(Foo, namespace_bar, namespace_foo)
            assert render_args[Foo] is namespace_foo

    class TestInitRenderArgs:
        class TestCompatibility:
            class A(Renderable):
                pass

            class B(A):
                pass

            class C(A):
                pass

            def test_compatible(self):
                for cls1, cls2 in (
                    (self.A, Renderable),
                    (self.A, self.A),
                    (self.B, Renderable),
                    (self.B, self.A),
                    (self.B, self.B),
                    (self.C, Renderable),
                    (self.C, self.A),
                    (self.C, self.C),
                ):
                    assert RenderArgs(cls1, RenderArgs(cls2)) == RenderArgs(cls1)

            def test_incompatible(self):
                for cls1, cls2 in (
                    (Renderable, self.A),
                    (Renderable, self.B),
                    (Renderable, self.C),
                    (self.A, self.B),
                    (self.A, self.C),
                    (self.B, self.C),
                    (self.C, self.B),
                ):
                    with pytest.raises(RenderArgsError, match="incompatible"):
                        RenderArgs(cls1, RenderArgs(cls2))

        def test_default(self):
            render_args = RenderArgs(Foo)
            assert render_args[Foo] == Foo.Args()
            assert render_args == RenderArgs(Foo, None)

        def test_non_default(self):
            init_render_args = RenderArgs(Foo, Foo.Args("bar", "foo"))
            render_args = RenderArgs(Foo, init_render_args)
            assert render_args == init_render_args
            assert render_args[Foo] == Foo.Args("bar", "foo")
            assert render_args[Foo] is init_render_args[Foo]

    def test_namespace_precedence(self):
        class A(Renderable):
            class Args(RenderArgs.Namespace):
                a: int = 1

        class B(A):
            class Args(RenderArgs.Namespace):
                b: int = 2

        class C(B):
            class Args(RenderArgs.Namespace):
                c: int = 3

        init_render_args = RenderArgs(B, A.Args(10), B.Args(20))
        namespace = A.Args(100)
        render_args = RenderArgs(C, init_render_args, namespace)

        assert render_args[A] is namespace
        assert render_args[B] is init_render_args[B]
        assert render_args[C] is RenderArgs(C)[C]  # default

    def test_immutability(self):
        render_args = RenderArgs(Foo)
        with pytest.raises(TypeError):
            render_args[Foo] = Foo.Args()

    def test_equality(self):
        class Bar(Renderable):
            class Args(RenderArgs.Namespace):
                bar: str = "BAR"

        class Baz(Bar):
            class Args(RenderArgs.Namespace):
                baz: str = "BAZ"

        bar_args = RenderArgs(Bar)
        assert bar_args == RenderArgs(Bar)
        assert bar_args == RenderArgs(Bar, Bar.Args())

        bar_args_bar = RenderArgs(Bar, Bar.Args("bar"))
        assert bar_args_bar == RenderArgs(Bar, Bar.Args("bar"))
        assert bar_args_bar != bar_args

        baz_args = RenderArgs(Baz)
        assert baz_args == RenderArgs(Baz)
        assert baz_args == RenderArgs(Baz, Bar.Args())
        assert baz_args == RenderArgs(Baz, Baz.Args())
        assert baz_args == RenderArgs(Baz, Bar.Args(), Baz.Args())
        assert baz_args == RenderArgs(Baz, Baz.Args(), Bar.Args())
        assert baz_args != bar_args
        assert baz_args != bar_args_bar

        baz_args_bar = RenderArgs(Baz, Bar.Args("bar"))
        assert baz_args_bar == RenderArgs(Baz, Bar.Args("bar"))
        assert baz_args_bar == RenderArgs(Baz, Bar.Args("bar"), Baz.Args())
        assert baz_args_bar == RenderArgs(Baz, Baz.Args(), Bar.Args("bar"))
        assert baz_args_bar != bar_args
        assert baz_args_bar != bar_args_bar
        assert baz_args_bar != baz_args

        baz_args_baz = RenderArgs(Baz, Baz.Args("baz"))
        assert baz_args_baz == RenderArgs(Baz, Baz.Args("baz"))
        assert baz_args_baz == RenderArgs(Baz, Bar.Args(), Baz.Args("baz"))
        assert baz_args_baz == RenderArgs(Baz, Baz.Args("baz"), Bar.Args())
        assert baz_args_baz != bar_args
        assert baz_args_baz != bar_args_bar
        assert baz_args_baz != baz_args
        assert baz_args_baz != baz_args_bar

        baz_args_bar_baz = RenderArgs(Baz, Bar.Args("bar"), Baz.Args("baz"))
        assert baz_args_bar_baz == RenderArgs(Baz, Bar.Args("bar"), Baz.Args("baz"))
        assert baz_args_bar_baz == RenderArgs(Baz, Baz.Args("baz"), Bar.Args("bar"))
        assert baz_args_bar_baz != bar_args
        assert baz_args_bar_baz != bar_args_bar
        assert baz_args_bar_baz != baz_args
        assert baz_args_bar_baz != baz_args_bar
        assert baz_args_bar_baz != baz_args_baz

    def test_getitem(self):
        class Bar(Foo):
            pass

        class Baz(Bar):
            pass

        render_args = RenderArgs(Bar)

        with pytest.raises(TypeError, match="'render_cls'"):
            render_args[Ellipsis]

        with pytest.raises(RenderArgsError, match="no render arguments"):
            render_args[Bar]

        with pytest.raises(RenderArgsError, match="'Bar' is not a subclass of 'Baz'"):
            render_args[Baz]

        assert isinstance(render_args[Foo], Foo.Args)

    def test_hash(self):
        foo_args_default = RenderArgs(Foo)
        assert hash(foo_args_default) == hash(RenderArgs(Foo))

        foo_args_foo_bar = RenderArgs(Foo, Foo.Args(foo="bar", bar="foo"))
        assert hash(foo_args_foo_bar) == hash(
            RenderArgs(Foo, Foo.Args(foo="bar", bar="foo"))
        )

        foo_args = RenderArgs(Foo, Foo.Args(foo=[]))
        with pytest.raises(TypeError):
            hash(foo_args)

    def test_iter(self):
        class A(Renderable):
            class Args(RenderArgs.Namespace):
                foo: None = None

        class B(A):
            class Args(RenderArgs.Namespace):
                foo: None = None

        class C(B):
            class Args(RenderArgs.Namespace):
                foo: None = None

        assert [*RenderArgs(A)] == [A.Args()]
        assert [*RenderArgs(B)] == [A.Args(), B.Args()]
        assert [*RenderArgs(C)] == [A.Args(), B.Args(), C.Args()]

    class TestUpdate:
        def test_args(self):
            class Bar(Renderable):
                pass

            class Baz(Bar):
                pass

            render_args = RenderArgs(Foo)

            with pytest.raises(TypeError, match="first argument"):
                render_args.update(Ellipsis)

            with pytest.raises(TypeError, match="positional argument"):
                render_args.update(Foo, Ellipsis)

            with pytest.raises(TypeError, match="keyword argument"):
                render_args.update(Foo.Args(), foo=Ellipsis)

            # propagated

            with pytest.raises(TypeError, match=r"'namespaces\[1\]'"):
                render_args.update(Foo.Args(), Ellipsis)

            with pytest.raises(RenderArgsError, match="not a subclass"):
                render_args.update(Bar)

            with pytest.raises(RenderArgsError, match="no render arguments"):
                RenderArgs(Baz).update(Bar)

            with pytest.raises(RenderArgsError, match="Unknown .* field"):
                render_args.update(Foo, x=Ellipsis)

        def test_namespaces(self):
            render_args = RenderArgs(Foo)
            namespace = Foo.Args(foo="bar", bar="foo")
            assert render_args.update(namespace) == RenderArgs(Foo, namespace)
            assert render_args.update(namespace)[Foo] is namespace

            render_args = +Foo.Args(foo="bar")
            namespace = Foo.Args(bar="foo")
            assert render_args.update(Foo.Args()) == RenderArgs(Foo)
            assert render_args.update(namespace) == RenderArgs(Foo, namespace)
            assert render_args.update(namespace)[Foo] is namespace

            render_args = +Foo.Args(bar="foo")
            namespace = Foo.Args(foo="bar")
            assert render_args.update(Foo.Args()) == RenderArgs(Foo)
            assert render_args.update(namespace) == RenderArgs(Foo, namespace)
            assert render_args.update(namespace)[Foo] is namespace

        def test_multiple_namespaces_with_same_render_cls(self):
            args_foo = Foo.Args(foo="bar")
            args_bar = Foo.Args(bar="foo")
            render_args = RenderArgs(Foo)

            assert render_args.update(args_foo, args_bar)[Foo] is args_bar
            assert render_args.update(args_bar, args_foo)[Foo] is args_foo

        def test_render_args(self):
            render_args = +Foo.Args(foo="bar")
            assert render_args.update(Foo) == render_args
            assert render_args.update(Foo, foo="bar") == render_args
            assert render_args.update(Foo, foo="foo") == +Foo.Args(foo="foo")
            assert render_args.update(Foo, bar="foo") == +Foo.Args(foo="bar", bar="foo")

    class TestOptimizations:
        class TestDefaultsInterned:
            class Bar(Foo):
                pass

            def test_true_positives(self):
                assert RenderArgs(Renderable) is RenderArgs(Renderable)
                assert RenderArgs(Foo) is RenderArgs(Foo)

                render_args = RenderArgs(self.Bar)

                assert render_args is RenderArgs(self.Bar)
                assert render_args is RenderArgs(self.Bar, RenderArgs(Renderable))
                assert render_args is RenderArgs(self.Bar, RenderArgs(Foo))
                assert render_args is RenderArgs(self.Bar, render_args)

            def test_likely_false_positives(self):
                class Baz(Foo):
                    pass

                with pytest.raises(RenderArgsError, match="incompatible"):
                    RenderArgs(self.Bar, RenderArgs(Baz))

            def test_subclass(self):
                class SubRenderArgs(RenderArgs):
                    pass

                render_args = SubRenderArgs(Renderable)
                assert isinstance(render_args, SubRenderArgs)
                assert render_args is SubRenderArgs(Renderable)

                render_args = SubRenderArgs(Foo)
                assert isinstance(render_args, SubRenderArgs)
                assert render_args is SubRenderArgs(Foo)

        def test_init_render_args_with_same_render_cls_and_without_namespaces(self):
            class Bar(Foo):
                pass

            namespace = Foo.Args(foo="bar", bar="foo")

            foo_render_args = RenderArgs(Foo, namespace)
            assert RenderArgs(Foo, foo_render_args) is foo_render_args

            bar_render_args = RenderArgs(Bar, namespace)
            assert RenderArgs(Bar, bar_render_args) is bar_render_args


class TestRenderData:
    base_render_data_dict = dict(
        zip(("size", "frame", "duration", "iteration"), (None,) * 4)
    )
    foo_render_data_dict = dict(**base_render_data_dict, foo="FOO", bar="BAR")
    foo_render_data = RenderData(Foo, **foo_render_data_dict)

    def test_args(self):
        with pytest.raises(TypeError, match="'render_cls'"):
            RenderArgs(Ellipsis)

    def test_base(self):
        render_data = RenderData(Renderable, **self.base_render_data_dict)
        assert render_data.render_cls is Renderable
        assert vars(render_data) == self.base_render_data_dict
        assert render_data.size is None
        assert render_data.frame is None
        assert render_data.duration is None
        assert render_data.iteration is None

    def test_render_cls(self):
        assert self.foo_render_data.render_cls is Foo

    def test_unknown(self):
        with pytest.raises(RenderDataError, match="Unknown .* 'baz'"):
            RenderData(Foo, baz=None)

    def test_incomplete(self):
        with pytest.raises(RenderDataError, match="Incomplete"):
            RenderData(Renderable)
        with pytest.raises(RenderDataError, match="Incomplete"):
            RenderData(Foo, **self.base_render_data_dict)
        with pytest.raises(RenderDataError, match="Incomplete"):
            RenderData(Foo, **self.base_render_data_dict, foo=None)
        with pytest.raises(RenderDataError, match="Incomplete"):
            RenderData(Foo, **self.base_render_data_dict, bar=None)

    def test_attrs(self):
        assert vars(self.foo_render_data) == self.foo_render_data_dict
        assert self.foo_render_data.foo == "FOO"
        assert self.foo_render_data.bar == "BAR"

    def test_getattr(self):
        with pytest.raises(AttributeError, match="Unknown .* 'baz'"):
            self.foo_render_data.baz

    def test_setattr(self):
        render_data = RenderData(Foo, **self.foo_render_data_dict)

        with pytest.raises(AttributeError, match="Unknown .* 'baz'"):
            render_data.baz = "BAZ"

        render_data.foo = "bar"
        assert render_data.foo == "bar"

    def test_delattr(self):
        render_data = RenderData(Foo, **self.foo_render_data_dict)
        with pytest.raises(AttributeError, match="Can't delete"):
            del render_data.foo

    def test_finalized(self):
        render_data = RenderData(Foo, **self.foo_render_data_dict)
        assert render_data.finalized is False
        render_data.finalize()
        assert render_data.finalized is True

    def test_finalize(self):
        class Bar(Foo):
            @classmethod
            def _finalize_render_data_(cls, render_data):
                render_data.bar = render_data.foo

        render_data = RenderData(Bar, **self.foo_render_data_dict)
        assert render_data.foo == "FOO"
        assert render_data.bar == "BAR"

        render_data.finalize()

        assert render_data.foo == "FOO"
        assert render_data.bar == "FOO"

        # Calls `_finalize_render_data_` only the first time

        render_data.foo = "bar"

        assert render_data.foo == "bar"
        assert render_data.bar == "FOO"


class TestRenderFormat:
    def test_args(self):
        with pytest.raises(TypeError, match="'width'"):
            RenderFormat(Ellipsis, 1)

        with pytest.raises(TypeError, match="'height'"):
            RenderFormat(1, Ellipsis)

        with pytest.raises(TypeError, match="'h_align'"):
            RenderFormat(1, 1, Ellipsis)

        with pytest.raises(TypeError, match="'v_align'"):
            RenderFormat(1, 1, HAlign.LEFT, Ellipsis)

    class TestFields:
        def test_width(self):
            for value in (-1, 0, 1):
                render_fmt = RenderFormat(value, 1)
                assert render_fmt.width == value

        def test_height(self):
            for value in (-1, 0, 1):
                render_fmt = RenderFormat(1, value)
                assert render_fmt.height == value

        def test_h_align(self):
            for value in HAlign:
                render_fmt = RenderFormat(1, 1, value)
                assert render_fmt.h_align is value

        def test_v_align(self):
            for value in VAlign:
                render_fmt = RenderFormat(1, 1, v_align=value)
                assert render_fmt.v_align is value

        class TestRelative:
            def test_false(self):
                for value in (1, 100):
                    render_fmt = RenderFormat(value, 1)
                    assert render_fmt.relative is False

                    render_fmt = RenderFormat(1, value)
                    assert render_fmt.relative is False

                    render_fmt = RenderFormat(value, value)
                    assert render_fmt.relative is False

            def test_true(self):
                for value in (0, -1, -100):
                    render_fmt = RenderFormat(value, 1)
                    assert render_fmt.relative is True

                    render_fmt = RenderFormat(1, value)
                    assert render_fmt.relative is True

                    render_fmt = RenderFormat(value, value)
                    assert render_fmt.relative is True

    def test_immutability(self):
        render_fmt = RenderFormat(1, 1)
        for field in ("width", "height", "h_align", "v_align", "relative"):
            with pytest.raises(AttributeError):
                setattr(render_fmt, field, Ellipsis)

            with pytest.raises(AttributeError):
                delattr(render_fmt, field)

    def test_size(self):
        for value in (-1, 0, 1):
            render_fmt = RenderFormat(value, 1)
            assert render_fmt.size == Size(value, 1)

        for value in (-1, 0, 1):
            render_fmt = RenderFormat(1, value)
            assert render_fmt.size == Size(1, value)

    class TestAbsolute:
        terminal_size = os.terminal_size((80, 30))

        def test_args(self):
            render_fmt = RenderFormat(0, 1)
            with pytest.raises(TypeError, match="'terminal_size'"):
                render_fmt.absolute(Ellipsis)

        def test_non_relative(self):
            for value in (1, 100):
                render_fmt = RenderFormat(value, 1)
                assert render_fmt.absolute(self.terminal_size) is render_fmt

        def test_terminal_relative(self):
            for relative, absolute in zip(
                (0, -1, -78, -79, -80, -100), (80, 79, 2, 1, 1, 1)
            ):
                render_fmt = RenderFormat(relative, 1)
                assert render_fmt.relative is True

                render_fmt_abs = render_fmt.absolute(self.terminal_size)
                assert render_fmt_abs.relative is False
                assert render_fmt_abs == RenderFormat(absolute, 1)

            for relative, absolute in zip(
                (0, -1, -28, -29, -30, -100), (30, 29, 2, 1, 1, 1)
            ):
                render_fmt = RenderFormat(1, relative)
                assert render_fmt.relative is True

                render_fmt_abs = render_fmt.absolute(self.terminal_size)
                assert render_fmt_abs.relative is False
                assert render_fmt_abs == RenderFormat(1, absolute)

    class TestGetFormattedSize:
        def test_args(self):
            render_fmt = RenderFormat(1, 1)
            with pytest.raises(TypeError, match="'render_size'"):
                render_fmt.get_formatted_size(Ellipsis)
            with pytest.raises(ValueError, match="'render_size'"):
                render_fmt.get_formatted_size(Size(0, 1))
            with pytest.raises(ValueError, match="'render_size'"):
                render_fmt.get_formatted_size(Size(1, 0))

        def test_relative(self):
            for render_fmt in (RenderFormat(0, 1), RenderFormat(1, 0)):
                with pytest.raises(RenderFormatError):
                    render_fmt.get_formatted_size(Size(1, 1))

        def test_formatted_size(self):
            render_size = Size(5, 5)

            for padding_size, formatted_size in (
                # padding size < render size
                ((1, 1), Size(5, 5)),
                ((1, 5), Size(5, 5)),
                ((5, 1), Size(5, 5)),
                ((5, 5), Size(5, 5)),
                # padding size > render size
                ((6, 6), Size(6, 6)),
                ((6, 10), Size(6, 10)),
                ((10, 6), Size(10, 6)),
                ((10, 10), Size(10, 10)),
                # mixed
                ((1, 10), Size(5, 10)),
                ((10, 1), Size(10, 5)),
            ):
                render_fmt = RenderFormat(*padding_size)
                assert render_fmt.get_formatted_size(render_size) == formatted_size
