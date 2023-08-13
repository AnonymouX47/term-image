import os
from typing import Any

import pytest

from term_image.exceptions import (
    RenderArgsDataError,
    RenderArgsError,
    RenderDataError,
    RenderFormatError,
)
from term_image.geometry import Size
from term_image.renderable import (
    Frame,
    HAlign,
    Renderable,
    RenderArgs,
    RenderData,
    RenderFormat,
    VAlign,
)

# from term_image.renderable._types import RenderArgsData
RenderArgsData = RenderArgs.__base__


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


class TestNamespaceMeta:
    def test_multiple_namespace_bases(self):
        class A(RenderArgsData.Namespace):
            a: None

        class B(RenderArgsData.Namespace):
            b: None

        with pytest.raises(RenderArgsDataError, match="Multiple .* baseclasses"):

            class C(A, B):
                pass

    class TestFields:
        def test_no_field(self):
            with pytest.raises(RenderArgsDataError, match="No field"):

                class Namespace(RenderArgsData.Namespace):
                    pass

        def test_define(self):
            class Namespace(RenderArgsData.Namespace):
                foo: None
                bar: None

            assert Namespace.__dict__["__slots__"] == ("foo", "bar")
            assert Namespace.get_fields() == {"foo": None, "bar": None}

        def test_inherit(self):
            class A(RenderArgsData.Namespace):
                a: None
                b: None

            class B(A):
                pass

            assert B.__dict__["__slots__"] == ()
            assert B.get_fields() == {"a": None, "b": None}

        def test_inherit_and_define(self):
            class A(RenderArgsData.Namespace):
                a: None
                b: None

            with pytest.raises(RenderArgsDataError, match="inherit and define"):

                class B(A):
                    c: None
                    d: None

        def test_inherit_false(self):
            class A(RenderArgsData.Namespace):
                a: None
                b: None

            class B(A, inherit=False):
                c: None
                d: None

            assert B.__dict__["__slots__"] == ("c", "d")
            assert B.get_fields() == {"c": None, "d": None}

            with pytest.raises(RenderArgsDataError, match="No field"):

                class B(A, inherit=False):
                    pass

    class TestRenderCls:
        def test_association(self):
            class Namespace(RenderArgsData.Namespace):
                foo: None

            assert Namespace.get_render_cls() is None

            Namespace._RENDER_CLS = Renderable
            assert Namespace.get_render_cls() is Renderable

        class TestInheritTrue:
            def test_subclass_before(self):
                class A(RenderArgsData.Namespace):
                    a: None

                class B(A):
                    pass

                assert B.get_render_cls() is None

                A._RENDER_CLS = Renderable
                assert B.get_render_cls() is Renderable

            def test_subclass_after(self):
                class A(RenderArgsData.Namespace):
                    a: None

                A._RENDER_CLS = Renderable

                class B(A):
                    pass

                assert B.get_render_cls() is Renderable

        class TestInheritFalse:
            def test_subclass_before(self):
                class A(RenderArgsData.Namespace):
                    a: None

                class B(A, inherit=False):
                    b: None

                assert B.get_render_cls() is None

                A._RENDER_CLS = Renderable
                assert B.get_render_cls() is None

            def test_subclass_after(self):
                class A(RenderArgsData.Namespace):
                    a: None

                A._RENDER_CLS = Renderable

                class B(A, inherit=False):
                    b: None

                assert B.get_render_cls() is None

    def test_non_optional_constructor_parameters(self):
        with pytest.raises(TypeError, match="non-optional parameter"):

            class Namespace(RenderArgsData.Namespace):
                foo: None

                def __init__(self, foo):
                    super().__init__(foo)


class TestNamespace:
    class Namespace(RenderArgsData.Namespace):
        _RENDER_CLS = Renderable
        foo: int
        bar: int

    def test_cannot_instantiate_unassociated(self):
        class Namespace(RenderArgsData.Namespace):
            foo: None

        with pytest.raises(TypeError, match="Cannot instantiate"):
            Namespace()

    def test_as_dict(self):
        namespace = self.Namespace(dict(foo=1, bar=2))
        assert namespace.as_dict() == dict(foo=1, bar=2)

    def test_as_tuple(self):
        namespace = self.Namespace(dict(foo=1, bar=2))
        assert namespace.as_tuple() == (1, 2)

    def test_get_fields(self):
        namespace = self.Namespace(dict(foo=1, bar=2))
        assert self.Namespace.get_fields() == dict(foo=None, bar=None)
        assert namespace.get_fields() == dict(foo=None, bar=None)

    def test_get_render_cls(self):
        class Namespace(RenderArgsData.Namespace):
            foo: None

        assert Namespace.get_render_cls() is None

        Namespace._RENDER_CLS = Renderable
        assert Namespace.get_render_cls() is Renderable

        namespace = Namespace(dict(foo=None))
        assert namespace.get_render_cls() is Renderable


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


class TestArgsNamespaceMeta:
    class TestFields:
        def test_no_default(self):
            with pytest.raises(RenderArgsError, match="'bar' .* no default"):

                class Namespace(RenderArgs.Namespace):
                    foo: None = None
                    bar: None
                    baz: None = None

        def test_defaults(self):
            class Namespace(RenderArgs.Namespace):
                foo: str = "FOO"
                bar: str = "BAR"

            Namespace.get_fields() == dict(foo="FOO", bar="BAR")


class TestArgsNamespace:
    class Bar(Renderable):
        class Args(RenderArgs.Namespace):
            foo: str = "FOO"
            bar: str = "BAR"

    Namespace = Bar.Args

    class TestConstructor:
        class Bar(Renderable):
            class Args(RenderArgs.Namespace):
                foo: str = "FOO"
                bar: str = "BAR"
                baz: str = "BAZ"

        Namespace = Bar.Args

        def test_args(self):
            with pytest.raises(TypeError, match="'Bar' defines 3 .* 4 .* given"):
                self.Namespace("", "", "", "")

            with pytest.raises(RenderArgsError, match=r"Unknown .* \('dude',\)"):
                self.Namespace(dude="dude")

            with pytest.raises(TypeError, match=r"Got multiple .* \('foo',\)"):
                self.Namespace("foo", foo="foo")

        def test_default(self):
            namespace = self.Namespace()
            assert namespace.as_dict() == dict(foo="FOO", bar="BAR", baz="BAZ")

        def test_render_args(self):
            namespace = self.Namespace("foo")
            assert namespace.as_dict() == dict(foo="foo", bar="BAR", baz="BAZ")

            namespace = self.Namespace("foo", "bar")
            assert namespace.as_dict() == dict(foo="foo", bar="bar", baz="BAZ")

            namespace = self.Namespace("foo", "bar", "baz")
            assert namespace.as_dict() == dict(foo="foo", bar="bar", baz="baz")

        def test_render_kwargs(self):
            namespace = self.Namespace(foo="foo")
            assert namespace.as_dict() == dict(foo="foo", bar="BAR", baz="BAZ")

            namespace = self.Namespace(bar="bar")
            assert namespace.as_dict() == dict(foo="FOO", bar="bar", baz="BAZ")

            namespace = self.Namespace(baz="baz")
            assert namespace.as_dict() == dict(foo="FOO", bar="BAR", baz="baz")

            namespace = self.Namespace(foo="foo", bar="bar")
            assert namespace.as_dict() == dict(foo="foo", bar="bar", baz="BAZ")

            namespace = self.Namespace(foo="foo", baz="baz")
            assert namespace.as_dict() == dict(foo="foo", bar="BAR", baz="baz")

            namespace = self.Namespace(bar="bar", baz="baz")
            assert namespace.as_dict() == dict(foo="FOO", bar="bar", baz="baz")

            namespace = self.Namespace(foo="foo", bar="bar", baz="baz")
            assert namespace.as_dict() == dict(foo="foo", bar="bar", baz="baz")

            # Out of order
            namespace = self.Namespace(bar="bar", baz="baz", foo="foo")
            assert namespace.as_dict() == dict(foo="foo", bar="bar", baz="baz")

        def test_render_args_kwargs(self):
            namespace = self.Namespace("foo", bar="bar")
            assert namespace.as_dict() == dict(foo="foo", bar="bar", baz="BAZ")

            namespace = self.Namespace("foo", baz="baz")
            assert namespace.as_dict() == dict(foo="foo", bar="BAR", baz="baz")

            namespace = self.Namespace("foo", bar="bar", baz="baz")
            assert namespace.as_dict() == dict(foo="foo", bar="bar", baz="baz")

            namespace = self.Namespace("foo", "bar", baz="baz")
            assert namespace.as_dict() == dict(foo="foo", bar="bar", baz="baz")

    def test_getattr(self):
        namespace = self.Namespace()
        with pytest.raises(AttributeError, match="'baz'"):
            namespace.baz

    def test_setattr(self):
        namespace = self.Namespace()
        for attr in ("foo", "bar"):
            with pytest.raises(AttributeError):
                setattr(namespace, attr, Ellipsis)

    def test_delattr(self):
        namespace = self.Namespace()
        for attr in ("foo", "bar"):
            with pytest.raises(AttributeError):
                delattr(namespace, attr)

    def test_equality(self):
        namespace_default = self.Namespace()
        assert namespace_default == self.Namespace()
        assert namespace_default == self.Namespace("FOO", "BAR")

        namespace_foo = self.Namespace(foo="foo")
        assert namespace_foo == self.Namespace("foo", "BAR")
        assert namespace_foo == self.Namespace(foo="foo")
        assert namespace_foo != namespace_default

        namespace_bar = self.Namespace(bar="bar")
        assert namespace_bar == self.Namespace("FOO", "bar")
        assert namespace_bar == self.Namespace(bar="bar")
        assert namespace_bar != namespace_default
        assert namespace_bar != namespace_foo

        namespace_foo_bar = self.Namespace("foo", "bar")
        assert namespace_foo_bar == self.Namespace("foo", "bar")
        assert namespace_foo_bar == self.Namespace(foo="foo", bar="bar")
        assert namespace_foo_bar != namespace_default
        assert namespace_foo_bar != namespace_foo
        assert namespace_foo_bar != namespace_bar

    def test_hash(self):
        namespace_default = self.Namespace()
        assert hash(namespace_default) == hash(self.Namespace())

        namespace_foo_bar = self.Namespace("foo", "bar")
        assert hash(namespace_foo_bar) == hash(self.Namespace("foo", "bar"))

        namespace = self.Namespace([])
        with pytest.raises(TypeError):
            hash(namespace)

    class TestOr:
        class A(Renderable):
            class Args(RenderArgs.Namespace):
                a: int = 0

        class B(A):
            class Args(RenderArgs.Namespace):
                b: int = 0

        class C(A):
            class Args(RenderArgs.Namespace):
                c: int = 0

        def test_invalid_type(self):
            A = TestArgsNamespace.TestOr.A
            a = A.Args()

            with pytest.raises(TypeError):
                a | Ellipsis

        class TestNamespace:
            def test_same_render_cls(self):
                A = TestArgsNamespace.TestOr.A
                a1, a2 = A.Args(1), A.Args(2)

                assert a2 | a1 == RenderArgs(A, a1)
                assert a1 | a2 == RenderArgs(A, a2)

            # Render class of *other* is a child of that of *self*
            def test_compatible_child_render_cls(self):
                A = TestArgsNamespace.TestOr.A
                B = TestArgsNamespace.TestOr.B
                C = TestArgsNamespace.TestOr.C
                a, b, c = A.Args(1), B.Args(2), C.Args(3)

                assert a | b == RenderArgs(B, a, b)
                assert a | c == RenderArgs(C, a, c)

            # Render class of *other* is a parent of that of *self*
            def test_compatible_parent_render_cls(self):
                A = TestArgsNamespace.TestOr.A
                B = TestArgsNamespace.TestOr.B
                C = TestArgsNamespace.TestOr.C
                a, b, c = A.Args(1), B.Args(2), C.Args(3)

                assert b | a == RenderArgs(B, a, b)
                assert c | a == RenderArgs(C, a, c)

            def test_incompatible_render_cls(self):
                B = TestArgsNamespace.TestOr.B
                C = TestArgsNamespace.TestOr.C
                b, c = B.Args(2), C.Args(3)

                with pytest.raises(RenderArgsError):
                    b | c

                with pytest.raises(RenderArgsError):
                    c | b

        class TestRenderArgs:
            # Render class of *other* is a child of that of *self*
            def test_compatible_child_render_cls(self):
                A = TestArgsNamespace.TestOr.A
                B = TestArgsNamespace.TestOr.B
                C = TestArgsNamespace.TestOr.C
                a, b, c = A.Args(1), B.Args(2), C.Args(3)

                assert a | RenderArgs(B, b) == RenderArgs(B, a, b)
                assert a | RenderArgs(C, c) == RenderArgs(C, a, c)

            # Render class of *other* is a parent of that of *self*
            def test_compatible_parent_render_cls(self):
                A = TestArgsNamespace.TestOr.A
                B = TestArgsNamespace.TestOr.B
                C = TestArgsNamespace.TestOr.C
                a, b, c = A.Args(1), B.Args(2), C.Args(3)

                assert b | RenderArgs(A, a) == RenderArgs(B, a, b)
                assert c | RenderArgs(A, a) == RenderArgs(C, a, c)

            def test_incompatible_render_cls(self):
                B = TestArgsNamespace.TestOr.B
                C = TestArgsNamespace.TestOr.C
                b, c = B.Args(2), C.Args(3)

                with pytest.raises(RenderArgsError):
                    b | RenderArgs(C)

                with pytest.raises(RenderArgsError):
                    c | RenderArgs(B)

    def test_pos(self):
        assert +self.Namespace() == RenderArgs(self.Bar)
        assert +self.Namespace("bar", "foo") == RenderArgs(
            self.Bar, self.Namespace("bar", "foo")
        )

    class TestRor:
        """The reflected operation is invoked if either:

        * type(RHS) is a subclass of type(LHS) and provides a different implementation
          of the reflected operation, or
        * type(LHS) does not implement the [non-reflected] operation against type(RHS)
          i.e `LHS.__non_reflected__(RHS)` returns `NotImplemented`.
        """

        def test_invalid_type(self):
            class A(Renderable):
                class Args(RenderArgs.Namespace):
                    a: int = 0

            a = A.Args()
            with pytest.raises(TypeError):
                Ellipsis | a

        class TestNamespace:
            def test_same_render_cls(self):
                class A(Renderable):
                    class Args(RenderArgs.Namespace):
                        a: int = 0

                    class SubArgs(Args):
                        def __ror__(self, other):  # See docstring of `TestRor`
                            return super().__ror__(other)

                a, a_sub = A.Args(1), A.SubArgs(2)
                assert a | a_sub == RenderArgs(A, a_sub)

            # Render class of *other* is a child of that of *self*
            def test_compatible_child_render_cls(self):
                class ArgsC(RenderArgs.Namespace):
                    c: int = 0

                class ArgsB(ArgsC, inherit=False):
                    b: int = 0

                class ArgsA(ArgsC, inherit=False):
                    a: int = 0

                    def __ror__(self, other):  # See docstring of `TestRor`
                        return super().__ror__(other)

                class A(Renderable):
                    Args = ArgsA

                class B(A):
                    Args = ArgsB

                class C(A):
                    Args = ArgsC

                a, b, c = A.Args(1), B.Args(2), C.Args(3)
                assert b | a == RenderArgs(B, a, b)
                assert c | a == RenderArgs(C, a, c)

            # Render class of *other* is a parent of that of *self*
            def test_compatible_parent_render_cls(self):
                class A(Renderable):
                    class Args(RenderArgs.Namespace):
                        a: int = 0

                class B(A):
                    class Args(A.Args, inherit=False):
                        b: int = 0

                        def __ror__(self, other):  # See docstring of `TestRor`
                            return super().__ror__(other)

                class C(A):
                    class Args(A.Args, inherit=False):
                        c: int = 0

                        def __ror__(self, other):  # See docstring of `TestRor`
                            return super().__ror__(other)

                a, b, c = A.Args(1), B.Args(2), C.Args(3)
                assert a | b == RenderArgs(B, a, b)
                assert a | c == RenderArgs(C, a, c)

            def test_incompatible_render_cls(self):
                class B(Renderable):
                    class Args(RenderArgs.Namespace):
                        b: int = 0

                class C(Renderable):
                    class Args(B.Args, inherit=False):
                        c: int = 0

                        def __ror__(self, other):  # See docstring of `TestRor`
                            return super().__ror__(other)

                b, c = B.Args(2), C.Args(3)
                with pytest.raises(RenderArgsError):
                    b | c

        class TestRenderArgs:
            class A(Renderable):
                class Args(RenderArgs.Namespace):
                    a: int = 0

            class B(A):
                class Args(RenderArgs.Namespace):
                    b: int = 0

            class C(A):
                class Args(RenderArgs.Namespace):
                    c: int = 0

            # Render class of *other* is a child of that of *self*
            def test_compatible_child_render_cls(self):
                A, B, C = self.A, self.B, self.C
                a, b, c = A.Args(1), B.Args(2), C.Args(3)

                assert RenderArgs(B, b) | a == RenderArgs(B, a, b)
                assert RenderArgs(C, c) | a == RenderArgs(C, a, c)

            # Render class of *other* is a parent of that of *self*
            def test_compatible_parent_render_cls(self):
                A, B, C = self.A, self.B, self.C
                a, b, c = A.Args(1), B.Args(2), C.Args(3)

                assert RenderArgs(A, a) | b == RenderArgs(B, a, b)
                assert RenderArgs(A, a) | c == RenderArgs(C, a, c)

            def test_incompatible_render_cls(self):
                B, C = self.B, self.C
                b, c = B.Args(2), C.Args(3)

                with pytest.raises(RenderArgsError):
                    RenderArgs(C) | b

                with pytest.raises(RenderArgsError):
                    RenderArgs(B) | c

    class TestToRenderArgs:
        class Bar(Foo):
            class Args(RenderArgs.Namespace):
                bar: str = "BAR"

        class Baz(Bar):
            class Args(RenderArgs.Namespace):
                baz: str = "BAZ"

        args_default = Bar.Args()
        args = Bar.Args("bar")

        def test_default(self):
            assert self.args_default.to_render_args() == RenderArgs(self.Bar)
            assert self.args_default.to_render_args(None) == RenderArgs(self.Bar)

            assert self.args.to_render_args() == RenderArgs(self.Bar, self.args)
            assert self.args.to_render_args(None) == RenderArgs(self.Bar, self.args)

        def test_compatible(self):
            assert self.args_default.to_render_args(self.Bar) == RenderArgs(self.Bar)
            assert self.args_default.to_render_args(self.Baz) == RenderArgs(self.Baz)

            assert self.args.to_render_args(self.Bar) == RenderArgs(self.Bar, self.args)
            assert self.args.to_render_args(self.Baz) == RenderArgs(self.Baz, self.args)

        def test_incompatible(self):
            with pytest.raises(
                RenderArgsError, match=r"'namespaces\[0\]' .* incompatible"
            ):
                self.args_default.to_render_args(Foo)

            with pytest.raises(
                RenderArgsError, match=r"'namespaces\[0\]' .* incompatible"
            ):
                self.args.to_render_args(Foo)

    def test_update(self):
        namespace = self.Namespace()
        assert namespace.update() == self.Namespace()
        assert namespace.update(foo="bar") == self.Namespace("bar")
        assert namespace.update(bar="foo") == self.Namespace(bar="foo")
        assert namespace.update(foo="bar", bar="foo") == self.Namespace("bar", "foo")

        namespace_foo = self.Namespace("bar")
        assert namespace_foo.update() == self.Namespace("bar")
        assert namespace_foo.update(foo="baz") == self.Namespace("baz")
        assert namespace_foo.update(bar="foo") == self.Namespace("bar", "foo")
        assert namespace_foo.update(foo="baz", bar="baz") == self.Namespace(
            "baz", "baz"
        )

        namespace_bar = self.Namespace(bar="foo")
        assert namespace_bar.update() == self.Namespace(bar="foo")
        assert namespace_bar.update(bar="baz") == self.Namespace(bar="baz")
        assert namespace_bar.update(foo="bar") == self.Namespace("bar", "foo")
        assert namespace_bar.update(foo="baz", bar="baz") == self.Namespace(
            "baz", "baz"
        )

        with pytest.raises(RenderArgsError, match=r"Unknown .* \('baz',\)"):
            namespace.update(baz=Ellipsis)


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
