from __future__ import annotations

from itertools import zip_longest
from typing import Iterator

import pytest

from term_image.geometry import Size
from term_image.padding import AlignedPadding, ExactPadding
from term_image.render import FinalizedIteratorError, RenderIterator
from term_image.renderable import (
    DataNamespace,
    FrameCount,
    FrameDuration,
    IncompatibleRenderArgsError,
    Renderable,
    RenderArgs,
    Seek,
)

from ..renderable.test_renderable import (
    CacheSpace,
    Char,
    DummyFrame,
    FrameFill,
    IndefiniteSpace,
    Space,
)

# NOTE: Always keep in mind that frames are not actually rendered by `RenderIterator`.
# Hence, avoid testing the original data (fields defined by `Frame`) of rendered frames
# when what is actually required is contained in the render data and/or render args
# (which the `DummyFrame` subclass exposes).
#
# Cases where original frame data may be tested include (but may not be limited to):
#
# - when the frame returned may not be the original rendered by the renderable such as
#   when the render output is padded.
# - when comparing re-rendered frames such as with backward seeks or loop repetition.
#
# Also, any test that involves testing a **re-rendered** (via backward seek or loop
# repetition) frame or any field(s) of it (including extras
# added by `DummyFrame`) in a **definite** iteration must parametrize *cache* i.e test
# for both `cache=False` and `cache=True`. Any other test should be okay with the
# default (if not specifically a caching test).

# Renderables ==================================================================


class CacheChar(Char):
    def __init__(self, *args):
        self.n_renders = 0
        super().__init__(*args)

    def _render_(self, *args):
        self.n_renders += 1
        return super()._render_(*args)


class IndefiniteFrameFill(Renderable):
    size = Size(1, 1)

    def _get_render_size_(self):
        return self.size

    def __init__(self, size: Size):
        super().__init__(FrameCount.INDEFINITE, 1)
        self.size = size
        self.__frame_count = 10

    def _render_(self, render_data, render_args):
        data = render_data[Renderable]
        width, height = data.size
        frame_number = next(render_data[__class__].frames) if data.iteration else 0
        return DummyFrame(
            data.frame_offset,
            1 if data.duration is FrameDuration.DYNAMIC else data.duration,
            data.size,
            "\n".join((str(frame_number) * width,) * height),
            renderable=self,
            render_data=render_data,
            render_args=render_args,
        )

    def _get_render_data_(self, *, iteration):
        render_data = super()._get_render_data_(iteration=iteration)
        render_data[__class__].frames = (
            iter(range(self.__frame_count)) if iteration else None
        )
        return render_data


class IndefiniteFrameFillData(DataNamespace, render_cls=IndefiniteFrameFill):
    frames: Iterator[int] | None


class CacheFrameFill(FrameFill):
    def __init__(self, *args):
        self.n_renders = 0
        super().__init__(*args)

    def _render_(self, *args):
        self.n_renders += 1
        return super()._render_(*args)


space = Space(1, 1)
anim_space = Space(2, 1)
indefinite_space = IndefiniteSpace(1)
anim_char = Char(2, 1)
frame_fill = FrameFill(Size(1, 1))
indefinite_frame_fill = IndefiniteFrameFill(Size(1, 1))


# Utils ========================================================================


def get_loop_frames(renderable, cache=Ellipsis):
    frame_count = renderable.frame_count
    render_iter = (
        RenderIterator(renderable, loops=2)
        if cache is Ellipsis
        else RenderIterator(renderable, loops=2, cache=cache)
    )
    loop_1_frames = [next(render_iter) for _ in range(frame_count)]
    loop_2_frames = [next(render_iter) for _ in range(frame_count)]

    return loop_1_frames, loop_2_frames


# Tests ========================================================================

# # Constructor ==================================================================


class TestRenderable:
    def test_non_animated(self):
        with pytest.raises(ValueError, match="not animated"):
            RenderIterator(space)

    @pytest.mark.parametrize("renderable", [anim_space, frame_fill])
    def test_animated(self, renderable):
        render_iter = RenderIterator(renderable)
        frame = next(render_iter)
        assert frame.renderable is renderable
        assert frame.render_data.render_cls is type(renderable)
        assert frame.render_args.render_cls is type(renderable)


class TestRenderArgs:
    def test_default(self):
        render_iter = RenderIterator(anim_char)
        for frame in render_iter:
            assert frame.render_args == RenderArgs(Char)

    def test_non_default(self):
        render_iter = RenderIterator(anim_char, +Char.Args(char="#"))
        for frame in render_iter:
            assert frame.render_args == +Char.Args(char="#")

    def test_incompatible(self):
        with pytest.raises(IncompatibleRenderArgsError):
            RenderIterator(anim_space, RenderArgs(FrameFill))


class TestPadding:
    def test_default(self):
        render_iter = RenderIterator(frame_fill)
        for index, frame in enumerate(render_iter):
            assert frame.render_size == Size(1, 1)
            assert frame.render_output == str(index)

    def test_padded(self):
        render_iter = RenderIterator(frame_fill, padding=ExactPadding(1, 1, 1, 1))
        for index, frame in enumerate(render_iter):
            assert frame.render_size == Size(3, 3)
            assert frame.render_output == f"   \n {index} \n   "

    def test_unpadded(self):
        render_iter = RenderIterator(
            FrameFill(Size(5, 5)), padding=ExactPadding(0, 0, 0, 0)
        )
        for index, frame in enumerate(render_iter):
            assert frame.render_size == Size(5, 5)
            assert frame.render_output == "\n".join((str(index) * 5,) * 5)


class TestLoops:
    def test_invalid(self):
        with pytest.raises(ValueError, match="'loops'"):
            RenderIterator(anim_space, loops=0)

    class TestDefinite:
        def test_default(self):
            render_iter = RenderIterator(anim_space)
            assert len(tuple(render_iter)) == 2

        @pytest.mark.parametrize("loops", [1, 10])
        def test_finite(self, loops):
            render_iter = RenderIterator(anim_space, loops=loops)
            assert len(tuple(render_iter)) == 2 * loops

        @pytest.mark.parametrize("cache", [False, True])
        def test_repetition(self, cache):
            for loop_1_frame, loop_2_frame in zip(*get_loop_frames(frame_fill, cache)):
                assert loop_1_frame == loop_2_frame

    class TestIndefinite:
        def test_default(self):
            render_iter = RenderIterator(indefinite_space)
            assert len(tuple(render_iter)) == 1

        @pytest.mark.parametrize("loops", [1, 10, -1, -10])
        def test_ignored(self, loops):
            render_iter = RenderIterator(indefinite_space, loops=loops)
            assert len(tuple(render_iter)) == 1


class TestCache:
    @pytest.mark.parametrize("cache", [0, -1, -100])
    def test_invalid_cache_size(self, cache):
        with pytest.raises(ValueError, match="'cache'"):
            RenderIterator(anim_space, cache=cache)

    class TestDefinite:
        @pytest.mark.parametrize(
            "n_frames,cached,n_renders",
            [(99, True, 99), (100, True, 100), (101, False, 202)],
        )
        def test_default(self, n_frames, cached, n_renders):
            cache_space = CacheSpace(n_frames, 1)
            render_iter = RenderIterator(cache_space, loops=2)
            assert render_iter._cached is cached
            tuple(render_iter)
            assert cache_space.n_renders == n_renders

        def test_false(self):
            cache_frame_fill = CacheFrameFill(Size(1, 1))
            render_iter = RenderIterator(cache_frame_fill, loops=2, cache=False)
            assert render_iter._cached is False

            # First loop
            frames = []
            for _ in range(10):
                frames.append(next(render_iter))
                assert cache_frame_fill.n_renders == len(frames)

            # Second loop
            for n_renders, frame in enumerate(frames, 11):
                assert next(render_iter) is not frame
                assert cache_frame_fill.n_renders == n_renders

        class TestTrue:
            def test_without_padding(self):
                cache_frame_fill = CacheFrameFill(Size(1, 1))
                render_iter = RenderIterator(cache_frame_fill, loops=2, cache=True)
                assert render_iter._cached is True

                # First loop
                frames = []
                for _ in range(10):
                    frames.append(next(render_iter))
                    assert cache_frame_fill.n_renders == len(frames)

                # Second loop
                for frame in frames:
                    assert next(render_iter) is frame
                    assert cache_frame_fill.n_renders == 10

            def test_with_padding(self):
                cache_frame_fill = CacheFrameFill(Size(1, 1))
                render_iter = RenderIterator(
                    cache_frame_fill, padding=ExactPadding(1), loops=2, cache=True
                )
                assert render_iter._cached is True

                # First loop
                frames = []
                for _ in range(10):
                    frames.append(next(render_iter))
                    assert cache_frame_fill.n_renders == len(frames)

                # Second loop
                for frame in frames:
                    assert next(render_iter) == frame
                    assert cache_frame_fill.n_renders == 10

        @pytest.mark.parametrize(
            "cache,cached,n_renders", [(9, False, 20), (10, True, 10), (11, True, 10)]
        )
        def test_cache_size(self, cache, cached, n_renders):
            cache_frame_fill = CacheFrameFill(Size(1, 1))
            render_iter = RenderIterator(cache_frame_fill, loops=2, cache=cache)
            assert render_iter._cached is cached
            tuple(render_iter)
            assert cache_frame_fill.n_renders == n_renders

    class TestIndefinite:
        @pytest.mark.parametrize("n_frames", [99, 100, 101])
        def test_default(self, n_frames):
            render_iter = RenderIterator(IndefiniteSpace(n_frames))
            assert render_iter._cached is False

        @pytest.mark.parametrize("cache", [False, True, 9, 10, 11])
        def test_ignored(self, cache):
            render_iter = RenderIterator(indefinite_frame_fill, cache=cache)
            assert render_iter._cached is False


# # Attributes ===================================================================


class TestLoop:
    class TestDefinite:
        class TestStart:
            def test_default(self):
                render_iter = RenderIterator(anim_space)
                assert render_iter.loop == 1

            @pytest.mark.parametrize("loops", [10, -10])
            def test_non_default(self, loops):
                render_iter = RenderIterator(anim_space, loops=loops)
                assert render_iter.loop == loops

        def test_end(self):
            render_iter = RenderIterator(anim_space)
            tuple(render_iter)
            assert render_iter.loop == 0

            render_iter = RenderIterator(anim_space, loops=10)
            tuple(render_iter)
            assert render_iter.loop == 0

        class TestCountdown:
            def test_finite(self):
                render_iter = RenderIterator(anim_space, loops=10)
                assert render_iter.loop == 10

                for value in range(10, 0, -1):
                    for _ in range(2):
                        next(render_iter)
                        assert render_iter.loop == value

                with pytest.raises(StopIteration):
                    next(render_iter)
                assert render_iter.loop == 0

            def test_infinite(self):
                render_iter = RenderIterator(anim_space, loops=-1)
                assert render_iter.loop == -1

                for _ in range(10):
                    for _ in range(2):
                        next(render_iter)
                        assert render_iter.loop == -1

        def test_after_seek(self):
            render_iter = RenderIterator(frame_fill, loops=2)

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
        class TestStart:
            def test_default(self):
                render_iter = RenderIterator(indefinite_space)
                assert render_iter.loop == 1

            @pytest.mark.parametrize("loops", [10, -10])
            def test_non_default(self, loops):
                render_iter = RenderIterator(indefinite_space, loops=loops)
                assert render_iter.loop == 1

        class TestEnd:
            def test_default(self):
                render_iter = RenderIterator(indefinite_space)
                tuple(render_iter)
                assert render_iter.loop == 0

            @pytest.mark.parametrize("loops", [10, -10])
            def test_non_default(self, loops):
                render_iter = RenderIterator(indefinite_space, loops=loops)
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


# # Methods ======================================================================


def test_iter():
    render_iter = RenderIterator(anim_space)
    assert iter(render_iter) is render_iter


class TestNext:
    anim_space_seeked = Space(2, 1)
    anim_space_seeked.seek(1)

    @pytest.mark.parametrize("renderable", [anim_space, anim_space_seeked])
    def test_definite(self, renderable):
        render_iter = RenderIterator(renderable)

        for number in range(2):
            frame = next(render_iter)
            assert frame.data.frame_offset == number
            assert frame.data.seek_whence is Seek.START

        with pytest.raises(StopIteration, match="ended"):
            next(render_iter)
        with pytest.raises(StopIteration, match="finalized"):
            next(render_iter)

    def test_indefinite(self):
        render_iter = RenderIterator(IndefiniteSpace(2))

        frame = next(render_iter)
        assert frame.data.frame_offset == 0
        assert frame.data.seek_whence is Seek.START

        frame = next(render_iter)
        assert frame.data.frame_offset == 0
        assert frame.data.seek_whence is Seek.CURRENT

        with pytest.raises(StopIteration, match="ended"):
            next(render_iter)
        with pytest.raises(StopIteration, match="finalized"):
            next(render_iter)

    def test_error(self):
        class ErrorSpace(Space):
            def _render_(self, render_data, render_args):
                if render_data[Renderable].frame_offset == 1:
                    assert False
                return super()._render_(render_data, render_args)

        render_iter = RenderIterator(ErrorSpace(2, 1))
        next(render_iter)
        with pytest.raises(AssertionError):
            next(render_iter)
        with pytest.raises(StopIteration, match="finalized"):
            next(render_iter)

    def test_finalized(self):
        render_iter = RenderIterator(anim_space)
        render_iter.close()
        with pytest.raises(StopIteration, match="finalized"):
            next(render_iter)


def test_close():
    render_iter = RenderIterator(anim_space)
    render_data = render_iter._render_data
    assert render_data.finalized is False

    render_iter.close()

    assert not hasattr(render_iter, "_render_data")
    assert render_data.finalized is True


class TestSeek:
    class TestDefinite:
        anim_space_seeked = Space(2, 1)
        anim_space_seeked.seek(1)

        @pytest.mark.parametrize("renderable", [anim_space, anim_space_seeked])
        def test_start(self, renderable):
            render_iter = RenderIterator(renderable)
            data = render_iter._render_data[Renderable]
            assert data.frame_offset == 0
            assert data.seek_whence is Seek.START

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
            render_iter = RenderIterator(frame_fill)
            data = render_iter._render_data[Renderable]
            render_iter.seek(4)  # For CURRENT-relative
            next(render_iter)  # next = 5

            render_iter.seek(offset, whence)
            assert data.frame_offset == frame_no
            assert data.seek_whence is Seek.START

            next(render_iter)
            assert data.frame_offset == frame_no + 1
            assert data.seek_whence is Seek.START

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
            render_iter = RenderIterator(frame_fill)
            data = render_iter._render_data[Renderable]
            render_iter.seek(4)  # For CURRENT-relative
            next(render_iter)  # next = 5

            with pytest.raises(ValueError, match="'offset'"):
                render_iter.seek(offset, whence)

            assert data.frame_offset == 5
            assert data.seek_whence is Seek.START

        @pytest.mark.parametrize(
            "seek_ops,final_offset,final_whence",
            [
                # Non-cumulative
                ([(5, Seek.START), (3, Seek.START)], 3, Seek.START),
                ([(2, Seek.START), (-3, Seek.END)], 6, Seek.START),
                ([(-2, Seek.END), (2, Seek.START)], 2, Seek.START),
                ([(-5, Seek.END), (-2, Seek.END)], 7, Seek.START),
                # # next=5
                ([(3, Seek.CURRENT), (6, Seek.START)], 6, Seek.START),
                ([(-3, Seek.CURRENT), (6, Seek.START)], 6, Seek.START),
                ([(2, Seek.CURRENT), (-5, Seek.END)], 4, Seek.START),
                ([(-2, Seek.CURRENT), (-5, Seek.END)], 4, Seek.START),
                # Cumulative
                ([(5, Seek.START), (3, Seek.CURRENT)], 8, Seek.START),
                ([(7, Seek.START), (-3, Seek.CURRENT)], 4, Seek.START),
                ([(-5, Seek.END), (-2, Seek.CURRENT)], 2, Seek.START),
                ([(-7, Seek.END), (2, Seek.CURRENT)], 4, Seek.START),
                # # next=5
                ([(2, Seek.CURRENT), (2, Seek.CURRENT)], 9, Seek.START),
                ([(3, Seek.CURRENT), (-3, Seek.CURRENT)], 5, Seek.START),
                ([(-3, Seek.CURRENT), (3, Seek.CURRENT)], 5, Seek.START),
                ([(-2, Seek.CURRENT), (-2, Seek.CURRENT)], 1, Seek.START),
            ],
        )
        def test_consecutive_seek(self, seek_ops, final_offset, final_whence):
            render_iter = RenderIterator(frame_fill)
            data = render_iter._render_data[Renderable]
            render_iter.seek(4)  # For initially CURRENT-relative
            next(render_iter)  # next = 5

            for offset, whence in seek_ops:
                render_iter.seek(offset, whence)

            assert data.frame_offset == final_offset
            assert data.seek_whence is final_whence

        @pytest.mark.parametrize(
            "frames_before,offset,frames_after",
            [(0, 9, 1), (3, 7, 3), (7, 4, 6), (10, 0, 10)],
        )
        def test_end_after_seek(self, frames_before, offset, frames_after):
            render_iter = RenderIterator(frame_fill)

            for _ in range(frames_before):
                next(render_iter)
            render_iter.seek(offset)
            for _ in range(frames_after):
                next(render_iter)

            with pytest.raises(StopIteration, match="ended"):
                next(render_iter)

        def test_uncached_frames(self):
            render_iter = RenderIterator(frame_fill, cache=False)
            frames = [next(render_iter) for _ in range(10)]
            render_iter.seek(0)
            for old_frame, new_frame in zip_longest(frames, render_iter):
                assert old_frame is not new_frame

        def test_cached_frames(self):
            render_iter = RenderIterator(frame_fill, cache=True)
            frames = [next(render_iter) for _ in range(10)]
            render_iter.seek(0)
            for old_frame, new_frame in zip_longest(frames, render_iter):
                assert old_frame is new_frame

        def test_previously_skipped_frame_is_cached(self):
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
        def test_start(self):
            render_iter = RenderIterator(indefinite_space)
            data = render_iter._render_data[Renderable]
            assert data.frame_offset == 0
            assert data.seek_whence is Seek.START

        @pytest.mark.parametrize(
            "whence,offset",
            [
                (Seek.START, 0),
                (Seek.START, 1),
                (Seek.START, 9),
                (Seek.CURRENT, -5),
                (Seek.CURRENT, -1),
                (Seek.CURRENT, 0),
                (Seek.CURRENT, 1),
                (Seek.CURRENT, 4),
                (Seek.END, -9),
                (Seek.END, -1),
                (Seek.END, 0),
                # out of range of available frames but valid seek ops
                (Seek.START, 10),
                (Seek.CURRENT, -6),
                (Seek.CURRENT, 5),
                (Seek.END, -10),
            ],
        )
        def test_in_range(self, whence, offset):
            render_iter = RenderIterator(indefinite_frame_fill)
            data = render_iter._render_data[Renderable]
            render_iter.seek(4)  # For CURRENT-relative
            next(render_iter)  # next = 5

            render_iter.seek(offset, whence)
            assert data.frame_offset == offset
            assert data.seek_whence is whence

            next(render_iter)
            assert data.frame_offset == 0
            assert data.seek_whence is Seek.CURRENT

        @pytest.mark.parametrize("whence,offset", [(Seek.START, -1), (Seek.END, 1)])
        def test_out_of_range(self, whence, offset):
            render_iter = RenderIterator(indefinite_frame_fill)
            data = render_iter._render_data[Renderable]
            render_iter.seek(4)  # For CURRENT-relative
            next(render_iter)  # next = 5

            with pytest.raises(ValueError, match="'offset'"):
                render_iter.seek(offset, whence)

            assert data.frame_offset == 0
            assert data.seek_whence is Seek.CURRENT

        @pytest.mark.parametrize(
            "seek_ops,final_offset,final_whence",
            [
                # All non-cumulative
                ([(5, Seek.START), (3, Seek.START)], 3, Seek.START),
                ([(2, Seek.START), (-3, Seek.END)], -3, Seek.END),
                ([(5, Seek.START), (3, Seek.CURRENT)], 3, Seek.CURRENT),
                ([(7, Seek.START), (-3, Seek.CURRENT)], -3, Seek.CURRENT),
                ([(-2, Seek.END), (2, Seek.START)], 2, Seek.START),
                ([(-5, Seek.END), (-2, Seek.END)], -2, Seek.END),
                ([(-5, Seek.END), (-2, Seek.CURRENT)], -2, Seek.CURRENT),
                ([(-7, Seek.END), (2, Seek.CURRENT)], 2, Seek.CURRENT),
                ([(3, Seek.CURRENT), (6, Seek.START)], 6, Seek.START),
                ([(-3, Seek.CURRENT), (6, Seek.START)], 6, Seek.START),
                ([(2, Seek.CURRENT), (-5, Seek.END)], -5, Seek.END),
                ([(-2, Seek.CURRENT), (-5, Seek.END)], -5, Seek.END),
                ([(2, Seek.CURRENT), (2, Seek.CURRENT)], 2, Seek.CURRENT),
                ([(3, Seek.CURRENT), (-3, Seek.CURRENT)], -3, Seek.CURRENT),
                ([(-3, Seek.CURRENT), (3, Seek.CURRENT)], 3, Seek.CURRENT),
                ([(-2, Seek.CURRENT), (-2, Seek.CURRENT)], -2, Seek.CURRENT),
            ],
        )
        def test_consecutive_seek(self, seek_ops, final_offset, final_whence):
            render_iter = RenderIterator(indefinite_frame_fill)
            data = render_iter._render_data[Renderable]
            render_iter.seek(4)  # For initially CURRENT-relative
            next(render_iter)  # next = 5

            for offset, whence in seek_ops:
                render_iter.seek(offset, whence)

            assert data.frame_offset == final_offset
            assert data.seek_whence is final_whence

    def test_finalized(self):
        render_iter = RenderIterator(anim_space)
        render_iter.close()
        with pytest.raises(FinalizedIteratorError, match="finalized"):
            render_iter.seek(0)


class TestSetFrameDuration:
    anim_space = Space(5, 1)

    @pytest.mark.parametrize("duration", [0, -1])
    def test_args(self, duration):
        render_iter = RenderIterator(self.anim_space)
        with pytest.raises(ValueError, match="duration"):
            render_iter.set_frame_duration(duration)

    def test_iteration(self):
        render_iter = RenderIterator(self.anim_space)
        assert next(render_iter).data.duration == 1

        render_iter.set_frame_duration(10)
        assert next(render_iter).data.duration == 10
        assert next(render_iter).data.duration == 10

        render_iter.set_frame_duration(FrameDuration.DYNAMIC)
        assert next(render_iter).data.duration is FrameDuration.DYNAMIC
        assert next(render_iter).data.duration is FrameDuration.DYNAMIC

    def test_before_seek(self):
        render_iter = RenderIterator(self.anim_space)
        assert next(render_iter).data.duration == 1

        render_iter.set_frame_duration(10)
        render_iter.seek(3)
        assert next(render_iter).data.duration == 10

    def test_after_seek(self):
        render_iter = RenderIterator(self.anim_space)
        assert next(render_iter).data.duration == 1

        render_iter.seek(3)
        render_iter.set_frame_duration(10)
        assert next(render_iter).data.duration == 10

    def test_cache_update(self):
        cache_space = CacheSpace(2, 1)
        render_iter = RenderIterator(cache_space, cache=True)
        old_frame = next(render_iter)
        assert cache_space.n_renders == 1
        assert old_frame.data.duration == 1

        render_iter.seek(0)
        assert next(render_iter) is old_frame
        assert cache_space.n_renders == 1

        render_iter.seek(0)
        render_iter.set_frame_duration(10)
        new_frame = next(render_iter)
        assert cache_space.n_renders == 2
        assert new_frame is not old_frame
        assert new_frame.data.duration == 10

        render_iter.seek(0)
        assert next(render_iter) is new_frame
        assert cache_space.n_renders == 2

    def test_finalized(self):
        render_iter = RenderIterator(anim_space)
        render_iter.close()
        with pytest.raises(FinalizedIteratorError, match="finalized"):
            render_iter.set_frame_duration(10)


class TestSetPadding:
    anim_char = Char(5, 1)
    render_args = +Char.Args(char="#")

    def test_iteration(self):
        render_iter = RenderIterator(self.anim_char, self.render_args)
        frame = next(render_iter)
        assert frame.render_size == Size(1, 1)
        assert frame.render_output == "#"

        render_iter.set_padding(AlignedPadding(3, 1))
        frame = next(render_iter)
        assert frame.render_size == Size(3, 1)
        assert frame.render_output == " # "
        frame = next(render_iter)
        assert frame.render_size == Size(3, 1)
        assert frame.render_output == " # "

        render_iter.set_padding(ExactPadding(1, 1, 1, 1))
        frame = next(render_iter)
        assert frame.render_size == Size(3, 3)
        assert frame.render_output == "   \n # \n   "
        frame = next(render_iter)
        assert frame.render_size == Size(3, 3)
        assert frame.render_output == "   \n # \n   "

    def test_before_seek(self):
        render_iter = RenderIterator(self.anim_char, self.render_args)
        frame = next(render_iter)
        assert frame.render_size == Size(1, 1)
        assert frame.render_output == "#"

        render_iter.set_padding(AlignedPadding(3, 1))
        render_iter.seek(3)
        frame = next(render_iter)
        assert frame.render_size == Size(3, 1)
        assert frame.render_output == " # "

    def test_after_seek(self):
        render_iter = RenderIterator(self.anim_char, self.render_args)
        frame = next(render_iter)
        assert frame.render_size == Size(1, 1)
        assert frame.render_output == "#"

        render_iter.seek(3)
        render_iter.set_padding(AlignedPadding(3, 1))
        frame = next(render_iter)
        assert frame.render_size == Size(3, 1)
        assert frame.render_output == " # "

    def test_cache_not_updated(self):
        cache_frame_fill = CacheFrameFill(Size(1, 1))
        render_iter = RenderIterator(
            cache_frame_fill, padding=ExactPadding(1), cache=True
        )

        old_frame = next(render_iter)
        assert cache_frame_fill.n_renders == 1
        assert old_frame.render_size == Size(2, 1)
        assert old_frame.render_output == " 0"

        render_iter.seek(0)
        render_iter.set_padding(AlignedPadding(3, 1))

        new_frame = next(render_iter)
        assert cache_frame_fill.n_renders == 1
        assert new_frame != old_frame
        assert new_frame.render_size == Size(3, 1)
        assert new_frame.render_output == " 0 "

    def test_finalized(self):
        render_iter = RenderIterator(anim_space)
        render_iter.close()
        with pytest.raises(FinalizedIteratorError, match="finalized"):
            render_iter.set_padding(ExactPadding())


class TestSetRenderArgs:
    anim_char = Char(5, 1)

    def test_incompatible(self):
        render_iter = RenderIterator(self.anim_char)
        with pytest.raises(IncompatibleRenderArgsError):
            render_iter.set_render_args(RenderArgs(Space))

    def test_iteration(self):
        render_iter = RenderIterator(self.anim_char)
        assert next(render_iter).render_args == RenderArgs(Char)

        render_iter.set_render_args(+Char.Args(char="#"))
        assert next(render_iter).render_args == +Char.Args(char="#")
        assert next(render_iter).render_args == +Char.Args(char="#")

        render_iter.set_render_args(+Char.Args(char="$"))
        assert next(render_iter).render_args == +Char.Args(char="$")
        assert next(render_iter).render_args == +Char.Args(char="$")

    def test_before_seek(self):
        render_iter = RenderIterator(self.anim_char)
        assert next(render_iter).render_args == RenderArgs(Char)

        render_iter.set_render_args(+Char.Args(char="#"))
        render_iter.seek(3)
        assert next(render_iter).render_args == +Char.Args(char="#")

    def test_after_seek(self):
        render_iter = RenderIterator(self.anim_char)
        assert next(render_iter).render_args == RenderArgs(Char)

        render_iter.seek(3)
        render_iter.set_render_args(+Char.Args(char="#"))
        assert next(render_iter).render_args == +Char.Args(char="#")

    def test_cache_update(self):
        cache_char = CacheChar(2, 1)
        render_iter = RenderIterator(cache_char, cache=True)
        old_frame = next(render_iter)
        assert cache_char.n_renders == 1
        assert old_frame.render_args == RenderArgs(CacheChar)

        render_iter.seek(0)
        assert cache_char.n_renders == 1
        assert next(render_iter) is old_frame

        render_iter.seek(0)
        render_iter.set_render_args(+Char.Args(char="#"))
        new_frame = next(render_iter)
        assert cache_char.n_renders == 2
        assert new_frame is not old_frame
        assert new_frame.render_args == RenderArgs(CacheChar, Char.Args(char="#"))

        render_iter.seek(0)
        assert next(render_iter) is new_frame
        assert cache_char.n_renders == 2

    def test_finalized(self):
        render_iter = RenderIterator(anim_space)
        render_iter.close()
        with pytest.raises(FinalizedIteratorError, match="finalized"):
            render_iter.set_render_args(RenderArgs(Space))


class TestSetRenderSize:
    anim_space = Space(5, 1)

    def test_iteration(self):
        render_iter = RenderIterator(self.anim_space)
        assert next(render_iter).data.size == Size(1, 1)

        render_iter.set_render_size(Size(3, 1))
        assert next(render_iter).data.size == Size(3, 1)
        assert next(render_iter).data.size == Size(3, 1)

        render_iter.set_render_size(Size(3, 3))
        assert next(render_iter).data.size == Size(3, 3)
        assert next(render_iter).data.size == Size(3, 3)

    def test_before_seek(self):
        render_iter = RenderIterator(self.anim_space)
        assert next(render_iter).data.size == Size(1, 1)

        render_iter.set_render_size(Size(3, 1))
        render_iter.seek(3)
        assert next(render_iter).data.size == Size(3, 1)

    def test_after_seek(self):
        render_iter = RenderIterator(self.anim_space)
        assert next(render_iter).data.size == Size(1, 1)

        render_iter.seek(3)
        render_iter.set_render_size(Size(3, 1))
        assert next(render_iter).data.size == Size(3, 1)

    def test_cache_update(self):
        cache_space = CacheSpace(2, 1)
        render_iter = RenderIterator(cache_space, cache=True)
        old_frame = next(render_iter)
        assert cache_space.n_renders == 1
        assert old_frame.data.size == Size(1, 1)

        render_iter.seek(0)
        assert next(render_iter) is old_frame
        assert cache_space.n_renders == 1

        render_iter.seek(0)
        render_iter.set_render_size(Size(3, 1))
        new_frame = next(render_iter)
        assert cache_space.n_renders == 2
        assert new_frame is not old_frame
        assert new_frame.data.size == Size(3, 1)

        render_iter.seek(0)
        assert next(render_iter) is new_frame
        assert cache_space.n_renders == 2

    def test_finalized(self):
        render_iter = RenderIterator(anim_space)
        render_iter.close()
        with pytest.raises(FinalizedIteratorError, match="finalized"):
            render_iter.set_render_size(Size(1, 1))


class TestFromRenderData:
    def test_args(self):
        render_data = anim_space._get_render_data_(iteration=True)
        finalized_render_data = anim_space._get_render_data_(iteration=True)
        finalized_render_data.finalize()

        with pytest.raises(ValueError, match="not animated"):
            RenderIterator._from_render_data_(space, render_data)

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

        with pytest.raises(IncompatibleRenderArgsError):
            RenderIterator._from_render_data_(
                anim_space, render_data, render_args=RenderArgs(FrameFill)
            )

    def test_render_data(self):
        render_data = frame_fill._get_render_data_(iteration=True)
        render_iter = RenderIterator._from_render_data_(frame_fill, render_data)
        assert next(render_iter).render_data is render_data

    class TestFinalize:
        def test_default(self):
            render_data = anim_space._get_render_data_(iteration=True)
            render_iter = RenderIterator._from_render_data_(anim_space, render_data)
            render_iter.close()
            assert render_data.finalized is True

        @pytest.mark.parametrize("finalize", [False, True])
        def test_non_default(self, finalize):
            render_data = anim_space._get_render_data_(iteration=True)
            render_iter = RenderIterator._from_render_data_(
                anim_space, render_data, finalize=finalize
            )
            render_iter.close()
            assert render_data.finalized is finalize

    class TestRenderArgs:
        def test_default(self):
            render_iter = RenderIterator._from_render_data_(
                anim_char, anim_char._get_render_data_(iteration=True)
            )
            for frame in render_iter:
                assert frame.render_args == RenderArgs(Char)

        def test_non_default(self):
            render_iter = RenderIterator._from_render_data_(
                anim_char,
                anim_char._get_render_data_(iteration=True),
                +Char.Args(char="#"),
            )
            for frame in render_iter:
                assert frame.render_args == +Char.Args(char="#")

    class TestPadding:
        def test_default(self):
            render_iter = RenderIterator._from_render_data_(
                frame_fill, frame_fill._get_render_data_(iteration=True)
            )
            for index, frame in enumerate(render_iter):
                assert frame.render_size == Size(1, 1)
                assert frame.render_output == str(index)

        def test_padded(self):
            render_iter = RenderIterator._from_render_data_(
                frame_fill,
                frame_fill._get_render_data_(iteration=True),
                padding=ExactPadding(1, 1, 1, 1),
            )
            for index, frame in enumerate(render_iter):
                assert frame.render_size == Size(3, 3)
                assert frame.render_output == f"   \n {index} \n   "

        def test_unpadded(self):
            frame_fill = FrameFill(Size(5, 5))
            render_iter = RenderIterator._from_render_data_(
                frame_fill,
                frame_fill._get_render_data_(iteration=True),
                padding=ExactPadding(0, 0, 0, 0),
            )
            for index, frame in enumerate(render_iter):
                assert frame.render_size == Size(5, 5)
                assert frame.render_output == "\n".join((str(index) * 5,) * 5)


# # Others =======================================================================


class TestFrameCount:
    class TestDefinite:
        @pytest.mark.parametrize("n_frames", [2, 10])
        def test_unseeked(self, n_frames):
            render_iter = RenderIterator(Space(n_frames, 1))
            assert len(tuple(render_iter)) == n_frames

        @pytest.mark.parametrize("frame_number", [2, 4])
        def test_seeked(self, frame_number):
            anim_space = Space(5, 1)
            anim_space.seek(frame_number)
            render_iter = RenderIterator(anim_space)
            assert len(tuple(render_iter)) == 5

    @pytest.mark.parametrize("n_frames", [2, 10])
    def test_indefinite(self, n_frames):
        render_iter = RenderIterator(IndefiniteSpace(n_frames))
        assert len(tuple(render_iter)) == n_frames
