from term_image.geometry import Size
from term_image.renderable import Frame


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
