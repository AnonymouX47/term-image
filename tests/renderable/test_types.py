import pytest

from term_image.exceptions import RenderArgsError
from term_image.geometry import Size
from term_image.renderable import Frame, Renderable, RenderArgs, RenderParam


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


class Foo(Renderable):
    _RENDER_PARAMS_ = {"foo": RenderParam("FOO"), "bar": RenderParam("BAR")}


class TestRenderArgs:
    base_args_dict = {}

    def test_args(self):
        with pytest.raises(TypeError, match="'render_cls'"):
            RenderArgs(Ellipsis)

        with pytest.raises(TypeError, match="'init_render_args'"):
            RenderArgs(Renderable, Ellipsis)

    def test_base(self):
        render_args = RenderArgs(Renderable)
        assert render_args.render_cls is Renderable
        assert vars(render_args) == self.base_args_dict

    def test_render_cls(self):
        assert RenderArgs(Foo).render_cls is Foo

    class TestRenderArgs:
        class Bar(Renderable):
            _RENDER_PARAMS_ = {
                "a": RenderParam(1),
                "b": RenderParam(
                    2,
                    lambda cls, val: isinstance(val, int),
                    None,
                    lambda cls, val: val > 0,
                    None,
                ),
                "c": RenderParam(
                    3,
                    lambda cls, val: isinstance(val, float),
                    "must be a float",
                    lambda cls, val: val < 0,
                    "must be negative",
                ),
            }

        def test_unknown(self):
            with pytest.raises(RenderArgsError, match="Unknown"):
                RenderArgs(self.Bar, d=None)

        def test_type_check(self):
            # valid
            RenderArgs(self.Bar, b=10, c=-10.0)
            for value in (Ellipsis, 10, 10.0):
                RenderArgs(self.Bar, a=value)

            # invalid
            with pytest.raises(TypeError, match="Invalid type for 'b'"):
                RenderArgs(self.Bar, b=10.0)

        def test_type_msg(self):
            with pytest.raises(TypeError, match="Invalid type for 'b'"):
                RenderArgs(self.Bar, b=10.0)
            with pytest.raises(TypeError, match="must be a float"):
                RenderArgs(self.Bar, c=10)

        def test_value_check(self):
            # valid
            RenderArgs(self.Bar, b=10, c=-10.0)
            for value in (0, 10, -10, 0.0, 10.0, -10.0):
                RenderArgs(self.Bar, a=value)

            # invalid
            with pytest.raises(ValueError, match="Invalid value for 'b'"):
                RenderArgs(self.Bar, b=0)

        def test_value_msg(self):
            with pytest.raises(ValueError, match="Invalid value for 'b'"):
                RenderArgs(self.Bar, b=0)
            with pytest.raises(ValueError, match="must be negative"):
                RenderArgs(self.Bar, c=0.0)

        def test_default(self):
            render_args = RenderArgs(self.Bar)
            assert vars(render_args) == dict(
                **TestRenderArgs.base_args_dict, a=1, b=2, c=3
            )
            assert render_args.a == 1
            assert render_args.b == 2
            assert render_args.c == 3

        def test_non_default(self):
            render_args = RenderArgs(self.Bar, a=Ellipsis, b=10, c=-10.0)
            assert vars(render_args) == dict(
                **TestRenderArgs.base_args_dict, a=Ellipsis, b=10, c=-10.0
            )
            assert render_args.a is Ellipsis
            assert render_args.b == 10
            assert render_args.c == -10.0

    class TestInitRenderArgs:
        class TestCompatibility:
            class A(Renderable):
                def __init__(self):
                    super().__init__(1, 1)

                render_size = _render_ = None

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
                    (self.A, self.B),
                    (self.A, self.C),
                    (self.B, self.C),
                    (self.C, self.B),
                ):
                    with pytest.raises(RenderArgsError, match="incompatible"):
                        RenderArgs(cls1, RenderArgs(cls2))

        def test_default(self):
            render_args = RenderArgs(Foo)
            assert vars(render_args) == dict(
                **TestRenderArgs.base_args_dict, foo="FOO", bar="BAR"
            )
            assert render_args.foo == "FOO"
            assert render_args.bar == "BAR"
            assert render_args == RenderArgs(Foo, None)

        def test_non_default(self):
            init_render_args = RenderArgs(Foo, foo="bar", bar="foo")
            render_args = RenderArgs(Foo, init_render_args)
            assert vars(render_args) == dict(
                **TestRenderArgs.base_args_dict, foo="bar", bar="foo"
            )
            assert render_args.foo == "bar"
            assert render_args.bar == "foo"

    def test_arg_value_precedence(self):
        class A(Renderable):
            _RENDER_PARAMS_ = {"a": RenderParam(1)}

        class B(A):
            _RENDER_PARAMS_ = {"b": RenderParam(2)}

        class C(B):
            _RENDER_PARAMS_ = {"c": RenderParam(3)}

        # default
        render_args = RenderArgs(C)
        assert render_args.a == 1
        assert render_args.b == 2
        assert render_args.c == 3

        init_render_args = RenderArgs(B, a=10, b=20)
        render_args = RenderArgs(C, init_render_args, a=100)
        assert render_args.a == 100  # from *render_args*
        assert render_args.b == 20  # from *init_render_args*
        assert render_args.c == 3  # default

    def test_equality(self):
        foo_args_default = RenderArgs(Foo)
        assert foo_args_default == foo_args_default
        assert foo_args_default == RenderArgs(Foo)
        assert foo_args_default == RenderArgs(Foo, foo_args_default)
        assert foo_args_default == RenderArgs(Foo, foo="FOO", bar="BAR")

        foo_args_foo = RenderArgs(Foo, foo="bar")
        assert foo_args_foo == RenderArgs(Foo, foo="bar")
        assert foo_args_foo == RenderArgs(Foo, foo="bar", bar="BAR")
        assert foo_args_foo == RenderArgs(Foo, foo_args_foo)
        assert foo_args_foo == RenderArgs(Foo, foo_args_foo, bar="BAR")
        assert foo_args_foo != foo_args_default

        foo_args_bar = RenderArgs(Foo, bar="foo")
        assert foo_args_bar == RenderArgs(Foo, bar="foo")
        assert foo_args_bar == RenderArgs(Foo, foo="FOO", bar="foo")
        assert foo_args_bar == RenderArgs(Foo, foo_args_bar)
        assert foo_args_bar == RenderArgs(Foo, foo_args_bar, foo="FOO")
        assert foo_args_bar != foo_args_default
        assert foo_args_bar != foo_args_foo

        foo_args_foo_bar = RenderArgs(Foo, foo="bar", bar="foo")
        assert foo_args_foo_bar == RenderArgs(Foo, foo="bar", bar="foo")
        assert foo_args_foo_bar == RenderArgs(Foo, foo_args_foo, bar="foo")
        assert foo_args_foo_bar == RenderArgs(Foo, foo_args_bar, foo="bar")
        assert foo_args_foo_bar == RenderArgs(Foo, foo_args_foo_bar)
        assert foo_args_foo_bar != foo_args_default
        assert foo_args_foo_bar != foo_args_foo
        assert foo_args_foo_bar != foo_args_bar

    def test_hash(self):
        foo_args_default = RenderArgs(Foo)
        assert hash(foo_args_default) == hash(RenderArgs(Foo))

        foo_args_foo = RenderArgs(Foo, foo="bar")
        foo_args_foo_bar = RenderArgs(Foo, foo="bar", bar="foo")
        assert hash(foo_args_foo_bar) == hash(RenderArgs(Foo, foo_args_foo, bar="foo"))

        foo_args = RenderArgs(Foo, foo=[])
        with pytest.raises(TypeError):
            hash(foo_args)

    def test_getattr(self):
        render_args = RenderArgs(Foo)
        with pytest.raises(AttributeError, match="Unknown"):
            render_args.baz

    def test_setattr(self):
        render_args = RenderArgs(Foo)
        with pytest.raises(AttributeError, match="Can't set"):
            render_args.foo = Ellipsis

    def test_delattr(self):
        render_args = RenderArgs(Foo)
        with pytest.raises(AttributeError, match="Can't delete"):
            del render_args.foo

    def test_copy(self):
        render_args = RenderArgs(Foo, foo="bar")

        assert render_args.copy() is render_args

        assert render_args.copy(foo="bar") is not render_args
        assert render_args.copy(foo="bar") == render_args

        assert render_args.copy(foo="foo") != render_args
        assert render_args.copy(foo="foo") == RenderArgs(Foo, foo="foo")

        assert render_args.copy(bar="foo") != render_args
        assert render_args.copy(bar="foo") == RenderArgs(Foo, foo="bar", bar="foo")

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
                render_args = RenderArgs(self.Bar)

                assert render_args is not RenderArgs(
                    self.Bar, RenderArgs(Foo, foo="bar")
                )
                assert render_args is not RenderArgs(
                    self.Bar, RenderArgs(self.Bar, bar="foo")
                )

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

        class TestInitRenderArgsWithSameRenderClsAndWithoutRenderArgs:
            class Bar(Foo):
                pass

            def test_true_positives(self):
                bar_args_foo = RenderArgs(self.Bar, foo="bar")
                assert RenderArgs(self.Bar, bar_args_foo) is bar_args_foo

                bar_args_bar = RenderArgs(self.Bar, bar="foo")
                assert RenderArgs(self.Bar, bar_args_bar) is bar_args_bar

                bar_args_foo_bar = RenderArgs(self.Bar, foo="bar", bar="foo")
                assert RenderArgs(self.Bar, bar_args_foo_bar) is bar_args_foo_bar

            def test_likely_false_positives(self):
                foo_args_foo = RenderArgs(Foo, foo="bar")
                bar_args_foo = RenderArgs(self.Bar, foo="bar")

                assert RenderArgs(self.Bar, foo_args_foo) == bar_args_foo
                assert RenderArgs(self.Bar, foo_args_foo) is not bar_args_foo
