from __future__ import annotations

from itertools import zip_longest
from typing import Iterator

import pytest

from term_image.exceptions import RenderArgsError, RenderIteratorError
from term_image.geometry import Size
from term_image.render import RenderIterator
from term_image.renderable import (
    Frame,
    FrameCount,
    Renderable,
    RenderArgs,
    RenderData,
    RenderFormat,
)

from ..renderable.test_renderable import Char, IndefiniteSpace, Space


class FrameFill(Renderable):
    render_size = Size(1, 1)

    def __init__(self, size: Size):
        super().__init__(10, 1)
        self.render_size = size

    def _render_(self, render_data, render_args):
        data = render_data[Renderable]
        width, height = data.size
        return Frame(
            data.frame,
            data.duration,
            data.size,
            "\n".join((str(data.frame) * width,) * height),
        )


class IndefiniteFrameFill(Renderable):
    render_size = Size(1, 1)

    def __init__(self, size: Size):
        super().__init__(FrameCount.INDEFINITE, 1)
        self.render_size = size
        self.__frame_count = 10

    def _render_(self, render_data, render_args):
        data = render_data[Renderable]
        width, height = data.size
        frame_number = next(render_data[__class__].frames) if data.iteration else 0
        return Frame(
            data.frame,
            data.duration,
            data.size,
            "\n".join((str(frame_number) * width,) * height),
        )

    def _get_render_data_(self, *, iteration):
        render_data = super()._get_render_data_(iteration=iteration)
        render_data[__class__].frames = (
            iter(range(self.__frame_count)) if iteration else None
        )
        return render_data

    class _Data_(RenderData.Namespace):
        frames: Iterator[int] | None


space = Space(1, 1)
anim_space = Space(2, 1)
indefinite_space = IndefiniteSpace(1)
anim_char = Char(2, 1)
frame_fill = FrameFill(Size(1, 1))
indefinite_frame_fill = IndefiniteFrameFill(Size(1, 1))


def get_loop_frames(renderable, cache, frame_count=None):
    frame_count = frame_count or renderable.frame_count
    render_iter = RenderIterator(renderable, loops=2, cache=cache)
    loop_1_frames = [next(render_iter) for _ in range(frame_count)]
    loop_2_frames = [next(render_iter) for _ in range(frame_count)]

    return loop_1_frames, loop_2_frames


def test_args():
    with pytest.raises(TypeError, match="'renderable'"):
        RenderIterator(Ellipsis)
    with pytest.raises(ValueError, match="not animated"):
        RenderIterator(space)

    with pytest.raises(TypeError, match="'render_args'"):
        RenderIterator(anim_space, Ellipsis)
    with pytest.raises(RenderArgsError, match="incompatible"):
        RenderIterator(anim_space, RenderArgs(FrameFill))

    with pytest.raises(TypeError, match="'render_fmt'"):
        RenderIterator(anim_space, render_fmt=Ellipsis)

    with pytest.raises(TypeError, match="'loops'"):
        RenderIterator(anim_space, loops=Ellipsis)
    with pytest.raises(ValueError, match="'loops'"):
        RenderIterator(anim_space, loops=0)

    with pytest.raises(TypeError, match="'cache'"):
        RenderIterator(anim_space, cache=Ellipsis)
    for value in (0, -1, -100):
        with pytest.raises(ValueError, match="'cache'"):
            RenderIterator(anim_space, cache=value)


def test_renderable():
    render_iter = RenderIterator(anim_space)
    assert next(render_iter).render == " "

    render_iter = RenderIterator(frame_fill)
    assert next(render_iter).render == "0"


class TestRenderArgs:
    def test_default(self):
        render_iter = RenderIterator(anim_char)
        for frame in render_iter:
            assert frame.render == " "

    def test_non_default(self):
        render_iter = RenderIterator(anim_char, +Char.Args(char="#"))
        for frame in render_iter:
            assert frame.render == "#"


class TestRenderFmt:
    def test_default(self):
        render_iter = RenderIterator(frame_fill)
        for index, frame in enumerate(render_iter):
            assert frame.size == Size(1, 1)
            assert frame.render == str(index)

    def test_greater_than_render_size(self):
        render_iter = RenderIterator(frame_fill, render_fmt=RenderFormat(3, 3))
        for index, frame in enumerate(render_iter):
            assert frame.size == Size(3, 3)
            assert frame.render == f"   \n {index} \n   "

    def test_less_than_render_size(self):
        render_iter = RenderIterator(FrameFill(Size(5, 5)))
        for index, frame in enumerate(render_iter):
            assert frame.size == Size(5, 5)
            assert frame.render == "\n".join((str(index) * 5,) * 5)


class TestLoops:
    class TestDefinite:
        def test_default(self):
            for cache in (False, True):
                print(f"cache={cache}")
                render_iter = RenderIterator(anim_space)
                assert len(tuple(render_iter)) == 2

        def test_finite(self):
            for cache in (False, True):
                print(f"cache={cache}")
                for value in (1, 2, 10):
                    render_iter = RenderIterator(anim_space, loops=value, cache=cache)
                    assert len(tuple(render_iter)) == 2 * value

    class TestIndefinite:
        def test_default(self):
            render_iter = RenderIterator(indefinite_space)
            assert len(tuple(render_iter)) == 1

        def test_ignored(self):
            for value in (1, 10, -1, -10):
                render_iter = RenderIterator(indefinite_space, loops=value)
                assert len(tuple(render_iter)) == 1


class TestCache:
    class TestDefinite:
        def test_default(self):
            for frame_count in (2, 100):
                render_iter = RenderIterator(Space(frame_count, 1), loops=2)
                loop_1_frames = [next(render_iter) for _ in range(frame_count)]
                loop_2_frames = [next(render_iter) for _ in range(frame_count)]

                for loop_1_frame, loop_2_frame in zip(loop_1_frames, loop_2_frames):
                    assert loop_1_frame is loop_2_frame

            for frame_count in (101, 200):
                render_iter = RenderIterator(Space(frame_count, 1), loops=2)
                loop_1_frames = [next(render_iter) for _ in range(frame_count)]
                loop_2_frames = [next(render_iter) for _ in range(frame_count)]

                for loop_1_frame, loop_2_frame in zip(loop_1_frames, loop_2_frames):
                    assert loop_1_frame is not loop_2_frame

        def test_false(self):
            for loop_1_frame, loop_2_frame in zip(*get_loop_frames(frame_fill, False)):
                assert loop_1_frame is not loop_2_frame

        def test_true(self):
            for loop_1_frame, loop_2_frame in zip(*get_loop_frames(frame_fill, True)):
                assert loop_1_frame is loop_2_frame

        def test_less_than_frame_count(self):
            for loop_1_frame, loop_2_frame in zip(*get_loop_frames(frame_fill, 9)):
                assert loop_1_frame is not loop_2_frame

        def test_equal_to_frame_count(self):
            for loop_1_frame, loop_2_frame in zip(*get_loop_frames(frame_fill, 10)):
                assert loop_1_frame is loop_2_frame

        def test_greater_than_frame_count(self):
            for loop_1_frame, loop_2_frame in zip(*get_loop_frames(frame_fill, 11)):
                assert loop_1_frame is loop_2_frame

    class TestIndefinite:
        def test_default(self):
            for frame_count in (2, 100, 101, 200):
                render_iter = RenderIterator(IndefiniteSpace(frame_count))
                assert "cached=False" in repr(render_iter)

        def test_ignored(self):
            for frame_count in (False, True, 9, 10, 11):
                render_iter = RenderIterator(indefinite_frame_fill)
                assert "cached=False" in repr(render_iter)


class TestFrameCount:
    def test_definite(self):
        for cache in (False, True):
            print(f"cache={cache}")
            for value in (2, 10):
                render_iter = RenderIterator(Space(value, 1))
                assert len(tuple(render_iter)) == value

    def test_indefinite(self):
        for value in (2, 10):
            render_iter = RenderIterator(IndefiniteSpace(value))
            assert len(tuple(render_iter)) == value


class TestFrames:
    size = Size(1, 1)

    def test_definite(self):
        for cache in (False, True):
            print(f"cache={cache}")
            render_iter = RenderIterator(frame_fill, cache=cache)
            for index, frame in enumerate(render_iter):
                assert frame.number == index
                assert frame.render == str(index)

    def test_indefinite(self):
        render_iter = RenderIterator(indefinite_frame_fill)
        for index, frame in enumerate(render_iter):
            assert frame.number == 0
            assert frame.render == str(index)


def test_repetition():
    for cache in (False, True):
        print(f"cache={cache}")
        for loop_1_frame, loop_2_frame in zip(*get_loop_frames(frame_fill, cache)):
            assert loop_1_frame == loop_2_frame


class TestLoop:
    class TestDefinite:
        def test_start(self):
            render_iter = RenderIterator(anim_space)
            assert render_iter.loop == 1

            for value in (10, -1, -10):
                render_iter = RenderIterator(anim_space, loops=value)
                assert render_iter.loop == value

        def test_end(self):
            for cache in (False, True):
                print(f"cache={cache}")

                render_iter = RenderIterator(anim_space)
                tuple(render_iter)
                assert render_iter.loop == 0

                render_iter = RenderIterator(anim_space, loops=10, cache=cache)
                tuple(render_iter)
                assert render_iter.loop == 0

        class TestCountdown:
            def test_finite(self):
                for cache in (False, True):
                    print(f"cache={cache}")

                    render_iter = RenderIterator(anim_space, loops=10, cache=cache)
                    assert render_iter.loop == 10

                    for value in range(10, 0, -1):
                        for _ in range(2):
                            next(render_iter)
                            assert render_iter.loop == value

                    with pytest.raises(StopIteration):
                        next(render_iter)
                    assert render_iter.loop == 0

            def test_infinite(self):
                for cache in (False, True):
                    print(f"cache={cache}")

                    render_iter = RenderIterator(anim_space, loops=-1, cache=cache)
                    assert render_iter.loop == -1

                    for _ in range(10):
                        for _ in range(2):
                            next(render_iter)
                            assert render_iter.loop == -1

        def test_after_seek(self):
            for cache in (False, True):
                print(f"cache={cache}")

                render_iter = RenderIterator(frame_fill, loops=2, cache=cache)

                render_iter.seek(9)
                next(render_iter)
                assert render_iter.loop == 2

                render_iter.seek(0)
                next(render_iter)
                assert render_iter.loop == 2

                render_iter.seek(9)
                next(render_iter)
                assert render_iter.loop == 2

                next(render_iter)
                assert render_iter.loop == 1

    class TestIndefinite:
        def test_start(self):
            render_iter = RenderIterator(indefinite_space)
            assert render_iter.loop == 1

            for value in (1, 10, -1, -10):
                render_iter = RenderIterator(indefinite_space, loops=value)
                assert render_iter.loop == 1

        def test_end(self):
            render_iter = RenderIterator(indefinite_space)
            tuple(render_iter)
            assert render_iter.loop == 0

            for value in (1, 10, -1, -10):
                render_iter = RenderIterator(indefinite_space, loops=value)
                tuple(render_iter)
                assert render_iter.loop == 0

        def test_countdown(self):
            render_iter = RenderIterator(indefinite_space)
            assert render_iter.loop == 1

            next(render_iter)
            assert render_iter.loop == 1

            with pytest.raises(StopIteration):
                next(render_iter)
            assert render_iter.loop == 0


def test_iter():
    render_iter = RenderIterator(anim_space)
    assert iter(render_iter) is render_iter


class TestNext:
    def test_iteration(self):
        for renderable in (anim_space, IndefiniteSpace(2)):
            render_iter = RenderIterator(renderable)

            for number in range(2):
                assert isinstance(next(render_iter), Frame)

            with pytest.raises(StopIteration, match="ended"):
                next(render_iter)

            with pytest.raises(StopIteration, match="finalized"):
                next(render_iter)

    def test_error(self):
        class ErrorSpace(Space):
            def _render_(self, render_data, render_args):
                if render_data[Renderable].frame == 1:
                    assert False
                return super()._render_(render_data, render_args)

        render_iter = RenderIterator(ErrorSpace(2, 1))

        assert isinstance(next(render_iter), Frame)

        with pytest.raises(AssertionError):
            next(render_iter)

        with pytest.raises(StopIteration, match="finalized"):
            next(render_iter)

    # See also: TestClose.test_next


class TestClose:
    def test_next(self):
        render_iter = RenderIterator(anim_space)
        render_iter.close()
        with pytest.raises(StopIteration, match="finalized"):
            next(render_iter)

    def test_seek(self):
        render_iter = RenderIterator(anim_space)
        render_iter.close()
        with pytest.raises(RenderIteratorError, match="finalized"):
            render_iter.seek(0)


class TestSeek:
    def test_args(self):
        render_iter = RenderIterator(anim_space)
        with pytest.raises(TypeError, match="offset"):
            render_iter.seek(Ellipsis)

    class TestDefinite:
        def test_arg_offset(self):
            render_iter = RenderIterator(anim_space)
            for value in (2, -1):
                with pytest.raises(ValueError, match="offset"):
                    render_iter.seek(value)

        def test_absolute(self):
            for cache in (False, True):
                print(f"cache={cache}")

                render_iter = RenderIterator(frame_fill, cache=cache)
                assert next(render_iter).number == 0

                render_iter.seek(9)
                assert next(render_iter).number == 9

                render_iter.seek(6)
                render_iter.seek(4)
                assert next(render_iter).number == 4
                assert next(render_iter).number == 5

                render_iter.seek(3)
                render_iter.seek(7)
                assert next(render_iter).number == 7
                assert next(render_iter).number == 8

                render_iter.seek(0)
                assert next(render_iter).number == 0
                assert next(render_iter).number == 1

                render_iter.seek(9)
                assert next(render_iter).number == 9

                with pytest.raises(StopIteration, match="ended"):
                    next(render_iter)

        def test_uncached(self):
            render_iter = RenderIterator(frame_fill, cache=False)
            frames = [next(render_iter) for _ in range(10)]
            render_iter.seek(0)
            for old_frame, new_frame in zip_longest(frames, render_iter):
                assert old_frame is not new_frame

        def test_cached(self):
            render_iter = RenderIterator(frame_fill, cache=True)
            frames = [next(render_iter) for _ in range(10)]
            render_iter.seek(0)
            for old_frame, new_frame in zip_longest(frames, render_iter):
                assert old_frame is new_frame

        def test_cache_skipped_frame(self):
            render_iter = RenderIterator(frame_fill, cache=True)
            render_iter.seek(9)
            next(render_iter)

            render_iter.seek(5)
            frame_5 = next(render_iter)

            render_iter.seek(9)
            next(render_iter)

            render_iter.seek(5)
            assert next(render_iter) is frame_5

    class TestIndefinite:
        def test_arg_offset(self):
            render_iter = RenderIterator(indefinite_frame_fill)
            for value in (1, -1):
                with pytest.raises(ValueError, match="Non-zero .* INDEFINITE"):
                    render_iter.seek(value)

        def test_absolute(self):
            render_iter = RenderIterator(indefinite_frame_fill)
            frame = next(render_iter)
            assert frame.number == 0
            assert frame.render == "0"

            for render in "123456789":
                render_iter.seek(0)
                frame = next(render_iter)
                assert frame.number == 0
                assert frame.render == render

            with pytest.raises(StopIteration, match="ended"):
                next(render_iter)

    # See also: TestClose.test_seek


class TestSetRenderArgs:
    anim_char = Char(4, 1)

    def test_args(self):
        render_iter = RenderIterator(self.anim_char)
        with pytest.raises(TypeError, match="render_args"):
            render_iter.set_render_args(Ellipsis)
        with pytest.raises(RenderArgsError, match="incompatible"):
            render_iter.set_render_args(RenderArgs(Space))

    def test_iteration(self):
        render_iter = RenderIterator(self.anim_char)
        assert next(render_iter).render == " "

        render_iter.set_render_args(+Char.Args(char="#"))
        assert next(render_iter).render == "#"

        render_iter.set_render_args(+Char.Args(char="$"))
        assert next(render_iter).render == "$"
        assert next(render_iter).render == "$"

    def test_before_seek(self):
        for cache in (False, True):
            print(f"cache={cache}")

            render_iter = RenderIterator(self.anim_char, cache=cache)
            assert next(render_iter).render == " "

            render_iter.set_render_args(+Char.Args(char="#"))
            render_iter.seek(0)
            assert next(render_iter).render == "#"

    def test_after_seek(self):
        for cache in (False, True):
            print(f"cache={cache}")

            render_iter = RenderIterator(self.anim_char, cache=cache)
            assert next(render_iter).render == " "

            render_iter.seek(0)
            render_iter.set_render_args(+Char.Args(char="#"))
            assert next(render_iter).render == "#"

    def test_cache_update(self):
        render_iter = RenderIterator(self.anim_char, cache=True)
        old_frame = next(render_iter)
        assert old_frame.render == " "

        render_iter.seek(0)
        assert next(render_iter) is old_frame

        render_iter.seek(0)
        render_iter.set_render_args(+Char.Args(char="#"))
        new_frame = next(render_iter)
        assert new_frame is not old_frame
        assert new_frame.render == "#"

        render_iter.seek(0)
        assert next(render_iter) is new_frame


class TestSetRenderFmt:
    anim_char = Char(4, 1)
    render_args = +Char.Args(char="#")

    def test_args(self):
        render_iter = RenderIterator(self.anim_char, self.render_args)
        with pytest.raises(TypeError, match="render_fmt"):
            render_iter.set_render_fmt(Ellipsis)

    def test_iteration(self):
        render_iter = RenderIterator(self.anim_char, self.render_args)
        frame = next(render_iter)
        assert frame.size == Size(1, 1)
        assert frame.render == "#"

        render_iter.set_render_fmt(RenderFormat(3, 1))
        frame = next(render_iter)
        assert frame.size == Size(3, 1)
        assert frame.render == " # "

        render_iter.set_render_fmt(RenderFormat(3, 3))
        frame = next(render_iter)
        assert frame.size == Size(3, 3)
        assert frame.render == "   \n # \n   "

        frame = next(render_iter)
        assert frame.size == Size(3, 3)
        assert frame.render == "   \n # \n   "

    def test_before_seek(self):
        for cache in (False, True):
            print(f"cache={cache}")

            render_iter = RenderIterator(self.anim_char, self.render_args, cache=cache)
            frame = next(render_iter)
            assert frame.size == Size(1, 1)
            assert frame.render == "#"

            render_iter.set_render_fmt(RenderFormat(3, 1))
            render_iter.seek(0)
            frame = next(render_iter)
            assert frame.size == Size(3, 1)
            assert frame.render == " # "

    def test_after_seek(self):
        for cache in (False, True):
            print(f"cache={cache}")

            render_iter = RenderIterator(self.anim_char, self.render_args, cache=cache)
            frame = next(render_iter)
            assert frame.size == Size(1, 1)
            assert frame.render == "#"

            render_iter.seek(0)
            render_iter.set_render_fmt(RenderFormat(3, 1))
            frame = next(render_iter)
            assert frame.size == Size(3, 1)
            assert frame.render == " # "

    def test_cache_update(self):
        render_iter = RenderIterator(self.anim_char, self.render_args, cache=True)
        old_frame = next(render_iter)
        assert old_frame.size == Size(1, 1)
        assert old_frame.render == "#"

        render_iter.seek(0)
        assert next(render_iter) is old_frame

        render_iter.seek(0)
        render_iter.set_render_fmt(RenderFormat(3, 1))
        new_frame = next(render_iter)
        assert new_frame is not old_frame
        assert new_frame.size == Size(3, 1)
        assert new_frame.render == " # "

        render_iter.seek(0)
        assert next(render_iter) is new_frame


class TestSetRenderSize:
    anim_char = Char(4, 1)

    def test_args(self):
        render_iter = RenderIterator(self.anim_char)
        with pytest.raises(TypeError, match="render_size"):
            render_iter.set_render_size(Ellipsis)
        for value in (0, -1):
            with pytest.raises(ValueError, match="render_size"):
                render_iter.set_render_size(Size(value, 1))
            with pytest.raises(ValueError, match="render_size"):
                render_iter.set_render_size(Size(1, value))

    def test_iteration(self):
        render_iter = RenderIterator(self.anim_char)
        frame = next(render_iter)
        assert frame.size == Size(1, 1)
        assert frame.render == " "

        render_iter.set_render_size(Size(3, 1))
        frame = next(render_iter)
        assert frame.size == Size(3, 1)
        assert frame.render == "   "

        render_iter.set_render_size(Size(3, 3))
        frame = next(render_iter)
        assert frame.size == Size(3, 3)
        assert frame.render == "   \n   \n   "

        frame = next(render_iter)
        assert frame.size == Size(3, 3)
        assert frame.render == "   \n   \n   "

    def test_before_seek(self):
        for cache in (False, True):
            print(f"cache={cache}")

            render_iter = RenderIterator(self.anim_char, cache=cache)
            frame = next(render_iter)
            assert frame.size == Size(1, 1)
            assert frame.render == " "

            render_iter.set_render_size(Size(3, 1))
            render_iter.seek(0)
            frame = next(render_iter)
            assert frame.size == Size(3, 1)
            assert frame.render == "   "

    def test_after_seek(self):
        for cache in (False, True):
            print(f"cache={cache}")

            render_iter = RenderIterator(self.anim_char, cache=cache)
            frame = next(render_iter)
            assert frame.size == Size(1, 1)
            assert frame.render == " "

            render_iter.seek(0)
            render_iter.set_render_size(Size(3, 1))
            frame = next(render_iter)
            assert frame.size == Size(3, 1)
            assert frame.render == "   "

    def test_cache_update(self):
        render_iter = RenderIterator(self.anim_char, cache=True)
        old_frame = next(render_iter)
        assert old_frame.size == Size(1, 1)
        assert old_frame.render == " "

        render_iter.seek(0)
        assert next(render_iter) is old_frame

        render_iter.seek(0)
        render_iter.set_render_size(Size(3, 1))
        new_frame = next(render_iter)
        assert new_frame is not old_frame
        assert new_frame.size == Size(3, 1)
        assert new_frame.render == "   "

        render_iter.seek(0)
        assert next(render_iter) is new_frame


class TestFromRenderData:
    def test_args(self):
        render_data = anim_space._get_render_data_(iteration=True)
        finalized_render_data = anim_space._get_render_data_(iteration=True)
        finalized_render_data.finalize()

        with pytest.raises(TypeError, match="'renderable'"):
            RenderIterator._from_render_data_(Ellipsis, render_data)
        with pytest.raises(ValueError, match="not animated"):
            RenderIterator._from_render_data_(space, render_data)

        with pytest.raises(TypeError, match="'render_data'"):
            RenderIterator._from_render_data_(anim_space, Ellipsis)
        with pytest.raises(ValueError, match="'Space'"):
            RenderIterator._from_render_data_(
                anim_space, anim_char._get_render_data_(iteration=True)
            )
        with pytest.raises(ValueError, match="iteration"):
            RenderIterator._from_render_data_(
                anim_space, anim_space._get_render_data_(iteration=False)
            )
        with pytest.raises(ValueError, match="finalized"):
            RenderIterator._from_render_data_(anim_space, finalized_render_data)

        with pytest.raises(TypeError, match="'render_args'"):
            RenderIterator._from_render_data_(
                anim_space, render_data, render_args=Ellipsis
            )
        with pytest.raises(RenderArgsError, match="incompatible"):
            RenderIterator._from_render_data_(
                anim_space, render_data, render_args=RenderArgs(FrameFill)
            )

        with pytest.raises(TypeError, match="'render_fmt'"):
            RenderIterator._from_render_data_(
                anim_space, render_data, render_fmt=Ellipsis
            )

        with pytest.raises(TypeError, match="'finalize'"):
            RenderIterator._from_render_data_(
                anim_space, render_data, finalize=Ellipsis
            )

    def test_render_data(self):
        render_data = anim_space._get_render_data_(iteration=True)
        assert render_data[Renderable].frame == 0
        assert render_data[Renderable].size == Size(1, 1)
        assert render_data[Renderable].duration == 1

        render_data[Renderable].size = Size(3, 3)
        render_iter = RenderIterator._from_render_data_(anim_space, render_data)
        assert next(render_iter).size == Size(3, 3)

        render_data[Renderable].duration = 100
        assert next(render_iter).duration == 100

    class TestFinalize:
        def test_default(self):
            render_data = anim_space._get_render_data_(iteration=True)
            render_iter = RenderIterator._from_render_data_(anim_space, render_data)
            render_iter.close()
            assert render_data.finalized is True

        def test_non_default(self):
            for value in (False, True):
                render_data = anim_space._get_render_data_(iteration=True)
                render_iter = RenderIterator._from_render_data_(
                    anim_space, render_data, finalize=value
                )
                render_iter.close()
                assert render_data.finalized is value

    class TestRenderArgs:
        def test_default(self):
            render_iter = RenderIterator._from_render_data_(
                anim_char, anim_char._get_render_data_(iteration=True)
            )
            for frame in render_iter:
                assert frame.render == " "

        def test_non_default(self):
            render_iter = RenderIterator._from_render_data_(
                anim_char,
                anim_char._get_render_data_(iteration=True),
                +Char.Args(char="#"),
            )
            for frame in render_iter:
                assert frame.render == "#"

    class TestRenderFmt:
        def test_default(self):
            render_iter = RenderIterator._from_render_data_(
                frame_fill, frame_fill._get_render_data_(iteration=True)
            )
            for index, frame in enumerate(render_iter):
                assert frame.size == Size(1, 1)
                assert frame.render == str(index)

        def test_greater_than_render_size(self):
            render_iter = RenderIterator._from_render_data_(
                frame_fill,
                frame_fill._get_render_data_(iteration=True),
                render_fmt=RenderFormat(3, 3),
            )
            for index, frame in enumerate(render_iter):
                assert frame.size == Size(3, 3)
                assert frame.render == f"   \n {index} \n   "

        def test_less_than_render_size(self):
            frame_fill = FrameFill(Size(5, 5))
            render_iter = RenderIterator._from_render_data_(
                frame_fill, frame_fill._get_render_data_(iteration=True)
            )
            for index, frame in enumerate(render_iter):
                assert frame.size == Size(5, 5)
                assert frame.render == "\n".join((str(index) * 5,) * 5)
