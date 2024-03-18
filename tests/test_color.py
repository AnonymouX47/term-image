import pytest

from term_image.color import Color


class TestColor:
    @pytest.mark.parametrize("value", [-1, 256])
    def test_out_of_range(self, value):
        with pytest.raises(ValueError, match="'r'"):
            Color(value, 0, 0)
        with pytest.raises(ValueError, match="'g'"):
            Color(0, value, 0)
        with pytest.raises(ValueError, match="'b'"):
            Color(0, 0, value)
        with pytest.raises(ValueError, match="'a'"):
            Color(0, 0, 0, value)

    @pytest.mark.parametrize("value", [0, 127, 255])
    class TestInRange:
        def test_r(self, value):
            color = Color(value, 0, 0)
            assert color.r == value

        def test_g(self, value):
            color = Color(0, value, 0)
            assert color.g == value

        def test_b(self, value):
            color = Color(0, 0, value)
            assert color.b == value

        def test_a(self, value):
            color = Color(0, 0, 0, value)
            assert color.a == value

    def test_a_default(self):
        color = Color(0, 0, 0)
        assert color.a == 255

    def test_is_tuple(self):
        color = Color(255, 127, 1, 0)
        assert isinstance(color, tuple)
        assert len(color) == 4
        assert color == (255, 127, 1, 0)
        assert color[0] == 255
        assert color[1] == 127
        assert color[2] == 1
        assert color[3] == 0

    @pytest.mark.parametrize(
        "rgba,hex",
        [
            ((0, 0, 0, 0), "#00000000"),
            ((0, 10, 127, 255), "#000a7fff"),
            ((255, 255, 255, 255), "#ffffffff"),
        ],
    )
    def test_hex(self, rgba, hex):
        color = Color(*rgba)
        assert color.hex == hex

    @pytest.mark.parametrize(
        "rgba,rgb",
        [
            ((0, 0, 0, 0), (0, 0, 0)),
            ((0, 10, 127, 255), (0, 10, 127)),
            ((255, 255, 255, 255), (255, 255, 255)),
        ],
    )
    def test_rgb(self, rgba, rgb):
        color = Color(*rgba)
        assert color.rgb == rgb

    @pytest.mark.parametrize(
        "rgb,hex",
        [
            ((0, 0, 0), "#000000"),
            ((0, 10, 127), "#000a7f"),
            ((255, 255, 255), "#ffffff"),
        ],
    )
    def test_rgb_hex(self, rgb, hex):
        color = Color(*rgb)
        assert color.rgb_hex == hex

    class TestFromHex:
        @pytest.mark.parametrize("hex", ["", "#", "#000", "#ffff", "#12345", "abcdefg"])
        def test_invalid(self, hex):
            with pytest.raises(ValueError):
                Color.from_hex(hex)

        class TestRGBA:
            @pytest.mark.parametrize(
                "hex,rgba",
                [
                    ("#00000000", (0, 0, 0, 0)),
                    ("#000a7fff", (0, 10, 127, 255)),
                    ("#ffffffff", (255, 255, 255, 255)),
                ],
            )
            def test_with_pound(self, hex, rgba):
                color = Color.from_hex(hex)
                assert color == Color(*rgba)

            @pytest.mark.parametrize(
                "hex,rgba",
                [
                    ("00000000", (0, 0, 0, 0)),
                    ("000a7fff", (0, 10, 127, 255)),
                    ("ffffffff", (255, 255, 255, 255)),
                ],
            )
            def test_without_pound(self, hex, rgba):
                color = Color.from_hex(hex)
                assert color == Color(*rgba)

            @pytest.mark.parametrize("hex", ["#0abc7def", "#0aBc7DeF", "#0ABC7DEF"])
            def test_case_insensitive(self, hex):
                assert Color.from_hex(hex) == Color(0x0A, 0xBC, 0x7D, 0xEF)

        class TestRGB:
            @pytest.mark.parametrize(
                "hex,rgba",
                [
                    ("#000000", (0, 0, 0, 255)),
                    ("#000a7f", (0, 10, 127, 255)),
                    ("#ffffff", (255, 255, 255, 255)),
                ],
            )
            def test_with_pound(self, hex, rgba):
                color = Color.from_hex(hex)
                assert color == Color(*rgba)

            @pytest.mark.parametrize(
                "hex,rgba",
                [
                    ("000000", (0, 0, 0, 255)),
                    ("000a7f", (0, 10, 127, 255)),
                    ("ffffff", (255, 255, 255, 255)),
                ],
            )
            def test_without_pound(self, hex, rgba):
                color = Color.from_hex(hex)
                assert color == Color(*rgba)

            @pytest.mark.parametrize("hex", ["#abcdef", "#aBcDeF", "#ABCDEF"])
            def test_case_insensitive(self, hex):
                assert Color.from_hex(hex) == Color(0xAB, 0xCD, 0xEF)

    class TestNew:
        def test_instance_type(self):
            class SubColor(Color):
                pass

            assert type(Color._new(0, 0, 0)) is Color
            assert type(SubColor._new(0, 0, 0)) is SubColor

        @pytest.mark.parametrize(
            "rgba", [(0, 0, 0), (0, 1, 127), (0, 0, 0, 0), (255, 255, 255, 127)]
        )
        def test_equal_to_normally_constructed(self, rgba):
            assert Color._new(*rgba) == Color(*rgba)
