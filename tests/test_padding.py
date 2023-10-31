import os

import pytest

from term_image.ctlseqs import CURSOR_FORWARD
from term_image.geometry import RawSize, Size
from term_image.padding import (
    AlignedPadding,
    ExactPadding,
    HAlign,
    Padding,
    RelativePaddingDimensionError,
    VAlign,
)


class ConcretePadding(Padding):
    def __init__(self, dimensions=(0,) * 4, fill=" "):
        super().__init__(fill)
        self.dimensions = dimensions

    def _get_exact_dimensions_(self, render_size):
        return self.dimensions


class TestPadding:
    def test_is_abstract(self):
        with pytest.raises(TypeError, match="abstract"):
            Padding()

    def test_fill(self):
        assert ConcretePadding().fill == " "
        assert ConcretePadding(fill="#").fill == "#"
        assert ConcretePadding(fill="").fill == ""

    @pytest.mark.parametrize(
        "dimensions,render_size,padded_size",
        [
            ((0, 0, 0, 0), Size(1, 1), Size(1, 1)),
            ((1, 0, 0, 0), Size(1, 1), Size(2, 1)),
            ((0, 1, 0, 0), Size(1, 1), Size(1, 2)),
            ((0, 0, 1, 0), Size(1, 1), Size(2, 1)),
            ((0, 0, 0, 1), Size(1, 1), Size(1, 2)),
            ((1, 1, 1, 1), Size(1, 1), Size(3, 3)),
            ((1, 1, 1, 1), Size(1, 2), Size(3, 4)),
            ((1, 1, 1, 1), Size(2, 1), Size(4, 3)),
            ((1, 1, 1, 1), Size(2, 2), Size(4, 4)),
        ],
    )
    def test_get_padded_size(self, dimensions, render_size, padded_size):
        padding = ConcretePadding(dimensions)
        assert padding.get_padded_size(render_size) == padded_size

    class TestPad:
        @pytest.mark.parametrize(
            "render_size,render,padded_render",
            [
                (Size(1, 1), "#", "   \n # \n   "),
                (Size(1, 2), "#\n#", "   \n # \n # \n   "),
                (Size(2, 1), "##", "    \n ## \n    "),
                (Size(2, 2), "##\n##", "    \n ## \n ## \n    "),
            ],
        )
        def test_render_and_render_size(self, render_size, render, padded_render):
            padding = ConcretePadding((1, 1, 1, 1))
            assert padding.pad(render, render_size) == padded_render

        class TestFill:
            def test_default(self):
                padding = ConcretePadding((1, 1, 1, 1))
                assert padding.pad("#", Size(1, 1)) == "   \n # \n   "

            @pytest.mark.parametrize(
                "fill,padded_render",
                [
                    ("+", "+++\n+#+\n+++"),
                    ("-", "---\n-#-\n---"),
                ],
            )
            def test_non_empty(self, fill, padded_render):
                padding = ConcretePadding((1, 1, 1, 1), fill)
                assert padding.pad("#", Size(1, 1)) == padded_render

            def test_empty(self):
                padding = ConcretePadding((1, 1, 1, 1), "")
                assert padding.pad("#", Size(1, 1)) == (
                    f"{CURSOR_FORWARD % 3}\n{CURSOR_FORWARD % 1}"
                    f"#{CURSOR_FORWARD % 1}\n{CURSOR_FORWARD % 3}"
                )

        class TestDimensions:
            @pytest.mark.parametrize(
                "dimensions,padded_render",
                [
                    ((0, 0, 0, 0), "#"),
                    ((1, 0, 0, 0), " #"),
                    ((0, 1, 0, 0), " \n#"),
                    ((0, 0, 1, 0), "# "),
                    ((0, 0, 0, 1), "#\n "),
                    ((1, 1, 1, 1), "   \n # \n   "),
                ],
            )
            def test_non_empty(self, dimensions, padded_render):
                padding = ConcretePadding(dimensions)
                assert padding.pad("#", Size(1, 1)) == padded_render

            @pytest.mark.parametrize(
                "dimensions,padded_render",
                [
                    ((0, 0, 0, 0), "#"),
                    ((1, 0, 0, 0), f"{CURSOR_FORWARD % 1}#"),
                    ((0, 1, 0, 0), f"{CURSOR_FORWARD % 1}\n#"),
                    ((0, 0, 1, 0), f"#{CURSOR_FORWARD % 1}"),
                    ((0, 0, 0, 1), f"#\n{CURSOR_FORWARD % 1}"),
                    (
                        (1, 1, 1, 1),
                        (
                            f"{CURSOR_FORWARD % 3}\n{CURSOR_FORWARD % 1}"
                            f"#{CURSOR_FORWARD % 1}\n{CURSOR_FORWARD % 3}"
                        ),
                    ),
                ],
            )
            def test_empty(self, dimensions, padded_render):
                padding = ConcretePadding(dimensions, "")
                assert padding.pad("#", Size(1, 1)) == padded_render

    @pytest.mark.parametrize(
        "dimensions,fill",
        [
            ((0, 0, 0, 0), " "),
            ((1, 1, 1, 1), "#"),
            ((1, 2, 3, 4), "*"),
        ],
    )
    def test_to_exact(self, dimensions, fill):
        padding = ConcretePadding(dimensions, fill)
        assert padding.to_exact(Size(1, 1)) == ExactPadding(*dimensions, fill)


class TestAlignedPadding:
    @pytest.mark.parametrize("width", [1, 10, 0, -10])
    def test_width(self, width):
        assert AlignedPadding(width, 1).width == width

    @pytest.mark.parametrize("height", [1, 10, 0, -10])
    def test_height(self, height):
        assert AlignedPadding(1, height).height == height

    class TestHAlign:
        def test_default(self):
            assert AlignedPadding(1, 1).h_align is HAlign.CENTER

        @pytest.mark.parametrize("h_align", HAlign)
        def test_non_default(self, h_align):
            assert AlignedPadding(1, 1, h_align).h_align is h_align

    class TestVAlign:
        def test_default(self):
            assert AlignedPadding(1, 1).v_align is VAlign.MIDDLE

        @pytest.mark.parametrize("v_align", VAlign)
        def test_non_default(self, v_align):
            assert AlignedPadding(1, 1, v_align=v_align).v_align is v_align
            assert AlignedPadding(1, 1, v_align=v_align).v_align is v_align

    def test_fill(self):
        assert AlignedPadding(1, 1).fill == " "
        assert AlignedPadding(1, 1, fill="#").fill == "#"
        assert AlignedPadding(1, 1, fill="").fill == ""

    @pytest.mark.parametrize(
        "width,height,relative",
        [
            (1, 1, False),
            (10, 1, False),
            (1, 5, False),
            (10, 5, False),
            (0, 1, True),
            (1, -1, True),
            (0, 0, True),
            (-5, -10, True),
        ],
    )
    def test_relative(self, width, height, relative):
        assert AlignedPadding(width, height).relative is relative

    @pytest.mark.parametrize("width,height", [(1, 10), (-1, -10)])
    def test_size(self, width, height):
        assert AlignedPadding(width, height).size == RawSize(width, height)

    class TestGetPaddedSize:
        @pytest.mark.parametrize("width,height", [(0, 0), (-1, 10)])
        def test_relative(self, width, height):
            padding = AlignedPadding(width, height)
            with pytest.raises(RelativePaddingDimensionError):
                padding.get_padded_size(Size(1, 1))

        @pytest.mark.parametrize(
            "width,height,render_size,padded_size",
            [
                (1, 1, Size(1, 1), Size(1, 1)),
                (2, 1, Size(1, 1), Size(2, 1)),
                (1, 2, Size(1, 1), Size(1, 2)),
                (2, 2, Size(1, 1), Size(2, 2)),
                (2, 2, Size(2, 2), Size(2, 2)),
                (2, 1, Size(2, 2), Size(2, 2)),
                (1, 2, Size(2, 2), Size(2, 2)),
                (1, 1, Size(2, 2), Size(2, 2)),
                (1, 1, Size(2, 2), Size(2, 2)),
                (3, 1, Size(1, 1), Size(3, 1)),
                (1, 3, Size(1, 1), Size(1, 3)),
                (3, 3, Size(1, 1), Size(3, 3)),
                (1, 1, Size(3, 3), Size(3, 3)),
                (3, 3, Size(3, 3), Size(3, 3)),
                (100, 200, Size(1, 1), Size(100, 200)),
                (1, 1, Size(200, 100), Size(200, 100)),
            ],
        )
        def test_absolute(self, width, height, render_size, padded_size):
            padding = AlignedPadding(width, height)
            assert padding.get_padded_size(render_size) == padded_size

            padding = AlignedPadding(width, height, HAlign.LEFT, VAlign.TOP)
            assert padding.get_padded_size(render_size) == padded_size

            padding = AlignedPadding(width, height, HAlign.RIGHT, VAlign.BOTTOM)
            assert padding.get_padded_size(render_size) == padded_size

    class TestResolve:
        terminal_size = os.terminal_size((80, 30))

        @pytest.mark.parametrize("dimension", [1, 100])
        def test_absolute(self, dimension):
            padding = AlignedPadding(dimension, dimension)
            assert padding.resolve(self.terminal_size) is padding

        @pytest.mark.parametrize(
            "relative,absolute",
            zip((0, -1, -78, -79, -80, -100), (80, 79, 2, 1, 1, 1)),
        )
        def test_relative_width(self, relative, absolute):
            padding = AlignedPadding(relative, 1).resolve(self.terminal_size)
            assert padding.width == absolute

        @pytest.mark.parametrize(
            "relative,absolute",
            zip((0, -1, -28, -29, -30, -100), (30, 29, 2, 1, 1, 1)),
        )
        def test_relative_height(self, relative, absolute):
            padding = AlignedPadding(1, relative).resolve(self.terminal_size)
            assert padding.height == absolute

        @pytest.mark.parametrize(
            "relative,absolute",
            zip(
                zip((0, -1, -78, -79, -80, -100), (0, -1, -28, -29, -30, -100)),
                zip((80, 79, 2, 1, 1, 1), (30, 29, 2, 1, 1, 1)),
            ),
        )
        def test_relative_both(self, relative, absolute):
            padding = AlignedPadding(*relative).resolve(self.terminal_size)
            assert padding.size == absolute

        @pytest.mark.parametrize("h_align", HAlign)
        def test_h_align(self, h_align):
            padding = AlignedPadding(0, 0, h_align).resolve(self.terminal_size)
            assert padding.h_align == h_align

        @pytest.mark.parametrize("v_align", VAlign)
        def test_v_align(self, v_align):
            padding = AlignedPadding(0, 0, v_align=v_align).resolve(self.terminal_size)
            assert padding.v_align == v_align

        @pytest.mark.parametrize("fill", ["#", "*"])
        def test_fill(self, fill):
            padding = AlignedPadding(0, 0, fill=fill).resolve(self.terminal_size)
            assert padding.fill == fill

    class TestGetExactDimensions:
        @pytest.mark.parametrize("width,height", [(0, 0), (-1, 10)])
        def test_relative(self, width, height):
            padding = AlignedPadding(width, height)
            with pytest.raises(RelativePaddingDimensionError):
                padding._get_exact_dimensions_(Size(1, 1))

        class TestHorizontal:
            @pytest.mark.parametrize(
                "width,left,right", [(1, 0, 0), (5, 0, 0), (7, 0, 2), (8, 0, 3)]
            )
            def test_left(self, width, left, right):
                padding = AlignedPadding(width, 1, HAlign.LEFT)
                assert padding._get_exact_dimensions_(Size(5, 5)) == (left, 0, right, 0)

            @pytest.mark.parametrize(
                "width,left,right", [(1, 0, 0), (5, 0, 0), (7, 1, 1), (8, 1, 2)]
            )
            def test_center(self, width, left, right):
                padding = AlignedPadding(width, 1, HAlign.CENTER)
                assert padding._get_exact_dimensions_(Size(5, 5)) == (left, 0, right, 0)

            @pytest.mark.parametrize(
                "width,left,right", [(1, 0, 0), (5, 0, 0), (7, 2, 0), (8, 3, 0)]
            )
            def test_right(self, width, left, right):
                padding = AlignedPadding(width, 1, HAlign.RIGHT)
                assert padding._get_exact_dimensions_(Size(5, 5)) == (left, 0, right, 0)

        class TestVertical:
            @pytest.mark.parametrize(
                "height,top,bottom", [(1, 0, 0), (5, 0, 0), (7, 0, 2), (8, 0, 3)]
            )
            def test_top(self, height, top, bottom):
                padding = AlignedPadding(1, height, v_align=VAlign.TOP)
                assert padding._get_exact_dimensions_(Size(5, 5)) == (0, top, 0, bottom)

            @pytest.mark.parametrize(
                "height,top,bottom", [(1, 0, 0), (5, 0, 0), (7, 1, 1), (8, 1, 2)]
            )
            def test_middle(self, height, top, bottom):
                padding = AlignedPadding(1, height, v_align=VAlign.MIDDLE)
                assert padding._get_exact_dimensions_(Size(5, 5)) == (0, top, 0, bottom)

            @pytest.mark.parametrize(
                "height,top,bottom", [(1, 0, 0), (5, 0, 0), (7, 2, 0), (8, 3, 0)]
            )
            def test_bottom(self, height, top, bottom):
                padding = AlignedPadding(1, height, v_align=VAlign.BOTTOM)
                assert padding._get_exact_dimensions_(Size(5, 5)) == (0, top, 0, bottom)

    def test_immutability(self):
        padding = AlignedPadding(1, 1)
        # Known
        with pytest.raises(AttributeError):
            padding.fill = Ellipsis
        # Unknown
        with pytest.raises(AttributeError):
            padding.foo = Ellipsis

    @pytest.mark.parametrize(
        "args1,kwargs1,args2,kwargs2",
        [
            ((1, 1), {}, (1, 1), {}),
            ((-1, 1), {}, (-1, 1), {}),
            ((0, 0), {}, (0, 0, HAlign.CENTER, VAlign.MIDDLE, " "), {}),
            ((1, 2, HAlign.LEFT, VAlign.BOTTOM), {}) * 2,
            (
                (1, 2, HAlign.LEFT, VAlign.BOTTOM),
                {},
                (),
                dict(width=1, height=2, h_align=HAlign.LEFT, v_align=VAlign.BOTTOM),
            ),
            ((5, 2), {}, (5,), dict(height=2)),
            ((1, 1), {}, (1, 1), dict(fill=" ")),
            ((1, 1, HAlign.CENTER, VAlign.MIDDLE, "#"), {}, (1, 1), dict(fill="#")),
            ((1, 1), dict(fill="*"), (1, 1), dict(fill="*")),
        ],
    )
    def test_equality(self, args1, kwargs1, args2, kwargs2):
        assert AlignedPadding(*args1, **kwargs1) == AlignedPadding(*args2, **kwargs2)

    @pytest.mark.parametrize(
        "args1,kwargs1,args2,kwargs2",
        [
            ((1, 1), {}, (1, 0, HAlign.CENTER, VAlign.MIDDLE, " "), {}),
            ((1, 2), {}, (2, 2), {}),
            ((1, 2), {}, (1, 3), {}),
            ((1, 2), {}, (1, 2, HAlign.LEFT, VAlign.MIDDLE), {}),
            ((1, 2), {}, (1, 2, HAlign.CENTER, VAlign.BOTTOM), {}),
            ((1, 1), {}, (1, 1), dict(fill="#")),
            ((1, 1), dict(fill="#"), (1, 1), dict(fill="*")),
        ],
    )
    def test_unequality(self, args1, kwargs1, args2, kwargs2):
        assert AlignedPadding(*args1, **kwargs1) != AlignedPadding(*args2, **kwargs2)


class TestExactPadding:
    @pytest.mark.parametrize("field_name", ["left", "top", "right", "bottom"])
    def test_non_negative_dimensions_only(self, field_name):
        with pytest.raises(ValueError, match=f"{field_name!r}"):
            ExactPadding(**{field_name: -1})

    def test_left(self):
        assert ExactPadding().left == 0
        assert ExactPadding(10).left == 10

    def test_top(self):
        assert ExactPadding().top == 0
        assert ExactPadding(top=10).top == 10

    def test_right(self):
        assert ExactPadding().right == 0
        assert ExactPadding(right=10).right == 10

    def test_bottom(self):
        assert ExactPadding().bottom == 0
        assert ExactPadding(bottom=10).bottom == 10

    def test_fill(self):
        assert ExactPadding(1, 1).fill == " "
        assert ExactPadding(1, 1, fill="#").fill == "#"
        assert ExactPadding(1, 1, fill="").fill == ""

    @pytest.mark.parametrize("dimensions", [(0, 0, 0, 0), (1, 2, 3, 4), (5, 5, 5, 5)])
    def test_dimensions(self, dimensions):
        padding = ExactPadding(*dimensions)
        assert padding.dimensions == dimensions

    @pytest.mark.parametrize("dimensions", [(0, 0, 0, 0), (1, 2, 3, 4), (5, 5, 5, 5)])
    def test_get_exact_dimensions(self, dimensions):
        padding = ExactPadding(*dimensions)
        assert padding._get_exact_dimensions_(Size(5, 5)) == dimensions

    def test_immutability(self):
        padding = ExactPadding()
        # Known
        with pytest.raises(AttributeError):
            padding.fill = Ellipsis
        # Unknown
        with pytest.raises(AttributeError):
            padding.foo = Ellipsis

    @pytest.mark.parametrize(
        "args1,kwargs1,args2,kwargs2",
        [
            ((), {}, (), {}),
            ((), {}, (0, 0, 0, 0, " "), {}),
            ((1, 2, 3, 4), {}, (1, 2, 3, 4), {}),
            ((1, 2, 3, 4), {}, (), dict(right=3, bottom=4, top=2, left=1)),
            ((5, 2), {}, (5,), dict(top=2)),
            ((), {}, (), dict(fill=" ")),
            ((0, 0, 0, 0, "#"), {}, (), dict(fill="#")),
            ((), dict(fill="*"), (), dict(fill="*")),
        ],
    )
    def test_equality(self, args1, kwargs1, args2, kwargs2):
        assert ExactPadding(*args1, **kwargs1) == ExactPadding(*args2, **kwargs2)

    @pytest.mark.parametrize(
        "args1,kwargs1,args2,kwargs2",
        [
            ((), {}, (0, 0, 1, 0, " "), {}),
            ((1, 2, 3, 4), {}, (2, 2, 3, 4), {}),
            ((1, 2, 3, 4), {}, (1, 3, 3, 4), {}),
            ((1, 2, 3, 4), {}, (1, 2, 4, 4), {}),
            ((1, 2, 3, 4), {}, (1, 2, 3, 5), {}),
            ((), {}, (), dict(fill="#")),
            ((), dict(fill="#"), (), dict(fill="*")),
        ],
    )
    def test_unequality(self, args1, kwargs1, args2, kwargs2):
        assert ExactPadding(*args1, **kwargs1) != ExactPadding(*args2, **kwargs2)
