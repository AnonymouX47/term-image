import io
import sys
from contextlib import contextmanager

import pytest
import urwid
from PIL import Image

from term_image import _ctlseqs as ctlseqs
from term_image.image import BlockImage, ITerm2Image, KittyImage
from term_image.widget import UrwidImage, UrwidImageCanvas, UrwidImageScreen

from ... import get_terminal_name_version, set_terminal_name_version

pytest.importorskip("fcntl", reason="Urwid raw display requires `fcntl`")

_size = (30, 15)

python_file = "tests/images/python.png"
python_img = Image.open(python_file)
kitty_image = KittyImage(python_img)
trans = BlockImage.from_file("tests/images/trans.png")


class TestStartStop:
    def test_supported(self):
        buf = io.StringIO()
        screen = UrwidImageScreen(sys.__stdin__, buf)

        screen.start()
        start_output = buf.getvalue()
        buf.seek(0)
        buf.truncate()
        screen.stop()
        stop_output = buf.getvalue()

        assert start_output.endswith(ctlseqs.KITTY_DELETE_ALL)
        assert stop_output.startswith(ctlseqs.KITTY_DELETE_ALL)

    def test_not_supported(self):
        buf = io.StringIO()
        screen = UrwidImageScreen(sys.__stdin__, buf)

        KittyImage._supported = False
        try:
            screen.start()
            start_output = buf.getvalue()
            buf.seek(0)
            buf.truncate()
            screen.stop()
            stop_output = buf.getvalue()

            assert ctlseqs.KITTY_DELETE_ALL not in start_output
            assert ctlseqs.KITTY_DELETE_ALL not in stop_output
        finally:
            KittyImage._supported = True


def test_synced_output():
    widget = urwid.SolidFill("x")
    buf = io.StringIO()
    screen = UrwidImageScreen(sys.__stdin__, buf)
    screen.start()

    buf.seek(0)
    buf.truncate()
    screen.draw_screen(_size, widget.render(_size))
    output = buf.getvalue()

    assert output.startswith(ctlseqs.BEGIN_SYNCED_UPDATE)
    assert output.endswith(ctlseqs.END_SYNCED_UPDATE)


buf = io.StringIO()
screen = UrwidImageScreen(sys.__stdin__, buf)
screen.start()


@contextmanager
def setup_clear_buffers():
    from term_image.widget import urwid

    tty_buf = io.BytesIO()
    write_tty = urwid.write_tty
    urwid.write_tty = tty_buf.write
    buf.seek(0)
    buf.truncate()
    try:
        yield buf, tty_buf
    finally:
        buf.seek(0)
        buf.truncate()
        tty_buf.close()
        urwid.write_tty = write_tty


class TestClearImages:
    class TestNowFalse:
        def test_single(self):
            image_ws = [UrwidImage(kitty_image) for _ in range(4)]
            for image_w in image_ws:
                with setup_clear_buffers() as (buf, tty_buf):
                    screen.clear_images(image_w)
                    assert (
                        buf.getvalue()
                        == ctlseqs.KITTY_DELETE_Z_INDEX % image_w._ti_z_index
                    )
                    assert tty_buf.getvalue() == b""

        def test_multiple(self):
            image_ws = [UrwidImage(kitty_image) for _ in range(4)]
            with setup_clear_buffers() as (buf, tty_buf):
                screen.clear_images(*image_ws)
                assert buf.getvalue() == "".join(
                    ctlseqs.KITTY_DELETE_Z_INDEX % image_w._ti_z_index
                    for image_w in image_ws
                )
                assert tty_buf.getvalue() == b""

        def test_multiple_not_kitty(self):
            image_ws = [UrwidImage(trans) for _ in range(4)]
            with setup_clear_buffers() as (buf, tty_buf):
                screen.clear_images(*image_ws)
                assert buf.getvalue() == ""
                assert tty_buf.getvalue() == b""

        def test_all(self):
            with setup_clear_buffers() as (buf, tty_buf):
                screen.clear_images()
                assert buf.getvalue() == ctlseqs.KITTY_DELETE_ALL
                assert tty_buf.getvalue() == b""

    class TestNowTrue:
        def test_single(self):
            image_ws = [UrwidImage(kitty_image) for _ in range(4)]
            for image_w in image_ws:
                with setup_clear_buffers() as (buf, tty_buf):
                    screen.clear_images(image_w, now=True)
                    assert buf.getvalue() == ""
                    assert (
                        tty_buf.getvalue()
                        == ctlseqs.KITTY_DELETE_Z_INDEX_b % image_w._ti_z_index
                    )

        def test_multiple(self):
            image_ws = [UrwidImage(kitty_image) for _ in range(4)]
            with setup_clear_buffers() as (buf, tty_buf):
                screen.clear_images(*image_ws, now=True)
                assert buf.getvalue() == ""
                assert tty_buf.getvalue() == b"".join(
                    ctlseqs.KITTY_DELETE_Z_INDEX_b % image_w._ti_z_index
                    for image_w in image_ws
                )

        def test_multiple_not_kitty(self):
            image_ws = [UrwidImage(trans) for _ in range(4)]
            with setup_clear_buffers() as (buf, tty_buf):
                screen.clear_images(*image_ws, now=True)
                assert buf.getvalue() == ""
                assert tty_buf.getvalue() == b""

        def test_all(self):
            with setup_clear_buffers() as (buf, tty_buf):
                screen.clear_images(now=True)
                assert buf.getvalue() == ""
                assert tty_buf.getvalue() == ctlseqs.KITTY_DELETE_ALL_b

    def test_not_supported(self):
        image_ws = [UrwidImage(kitty_image) for _ in range(4)]
        try:
            KittyImage._supported = False
            with setup_clear_buffers() as (buf, tty_buf):
                screen.clear_images(*image_ws)
                assert buf.getvalue() == ""
                assert tty_buf.getvalue() == b""

                screen.clear_images(*image_ws, now=True)
                assert buf.getvalue() == ""
                assert tty_buf.getvalue() == b""
        finally:
            KittyImage._supported = True

    def test_not_supported_all(self):
        try:
            KittyImage._supported = False
            with setup_clear_buffers() as (buf, tty_buf):
                screen.clear_images()
                assert buf.getvalue() == ""
                assert tty_buf.getvalue() == b""

                screen.clear_images(now=True)
                assert buf.getvalue() == ""
                assert tty_buf.getvalue() == b""
        finally:
            KittyImage._supported = True

    def test_disguise_state(self):
        image_w = UrwidImage(kitty_image)
        assert image_w._ti_disguise_state == 0

        with setup_clear_buffers():
            for value in (1, 2, 0, 1, 2, 0, 1):
                screen.clear_images(image_w)
                assert image_w._ti_disguise_state == value

    def test_disguise_state_all(self):
        try:
            UrwidImageCanvas._ti_disguise_state = 0
            with setup_clear_buffers():
                for value in (1, 2, 0, 1, 2, 0, 1):
                    screen.clear_images()
                    assert UrwidImageCanvas._ti_disguise_state == value
        finally:
            UrwidImageCanvas._ti_disguise_state = 0


block_image_w = UrwidImage(BlockImage(python_img))
kitty_image_w = UrwidImage(KittyImage(python_img))
iterm2_image_w = UrwidImage(ITerm2Image(python_img))

divider = urwid.SolidFill("\u2500")
kitty_list_box = urwid.ListBox(
    [urwid.Pile([("pack", kitty_image_w), (1, divider)] * 3)]
)
iterm2_list_box = urwid.ListBox(
    [urwid.Pile([("pack", iterm2_image_w), (1, divider)] * 3)]
)
bottom_w = urwid.Columns(
    [urwid.LineBox(kitty_list_box), urwid.LineBox(iterm2_list_box)]
)
top_w = urwid.LineBox(urwid.SolidFill("x"))
widget = urwid.Overlay(
    top_w,
    bottom_w,
    "center",
    10,
    "top",
    5,
)


class TestAutoClearImages:
    def test_image_cviews(self):
        assert screen._ti_image_cviews == frozenset()
        screen.draw_screen(_size, widget.render(_size))
        assert isinstance(screen._ti_image_cviews, frozenset)

    def test_move_top_widget(self):
        _terminal_name_version = get_terminal_name_version()
        try:
            set_terminal_name_version("konsole")
            # Setup
            buf.seek(0)
            buf.truncate()
            widget.top_w = top_w
            kitty_list_box.shift_focus(_size, 0)
            iterm2_list_box.shift_focus(_size, 0)

            widget.top = 2
            widget._invalidate()
            canv = widget.render(_size)
            # print(b"\n".join(canv.text).decode())
            screen.draw_screen(_size, canv)

            assert len(screen._ti_image_cviews) == 6
            assert {(row, col) for _, row, col, *_ in screen._ti_image_cviews} == {
                (2, 2),
                (2, 17),
                (3, 2),
                (3, 21),
                (9, 2),
                (9, 17),
            }

            prev_image_cviews = screen._ti_image_cviews
            widget.top += 1
            widget._invalidate()
            canv = widget.render(_size)
            # print(b"\n".join(canv.text).decode())
            screen.draw_screen(_size, canv)

            assert len(screen._ti_image_cviews) == 6
            assert prev_image_cviews != screen._ti_image_cviews
            # The two lower cviews should be unchanged
            assert len(prev_image_cviews & screen._ti_image_cviews) == 2
            assert {(row, col) for _, row, col, *_ in screen._ti_image_cviews} == {
                (2, 2),
                (2, 17),
                (4, 2),
                (4, 21),
                (9, 2),
                (9, 17),
            }

            prev_image_cviews = screen._ti_image_cviews
            widget.top = 5
            widget._invalidate()
            canv = widget.render(_size)
            # print(b"\n".join(canv.text).decode())
            screen.draw_screen(_size, canv)

            assert len(screen._ti_image_cviews) == 8
            assert prev_image_cviews != screen._ti_image_cviews
            # All cviews should be changed
            assert len(prev_image_cviews & screen._ti_image_cviews) == 0
            assert {(row, col) for _, row, col, *_ in screen._ti_image_cviews} == {
                (2, 2),
                (2, 17),
                (6, 2),
                (6, 21),
                (9, 2),
                (9, 21),
                (11, 2),
                (11, 17),
            }

            prev_image_cviews = screen._ti_image_cviews
            widget.top = 8
            widget._invalidate()
            canv = widget.render(_size)
            # print(b"\n".join(canv.text).decode())
            screen.draw_screen(_size, canv)

            assert len(screen._ti_image_cviews) == 6
            assert prev_image_cviews != screen._ti_image_cviews
            # All cviews should be changed
            assert len(prev_image_cviews & screen._ti_image_cviews) == 0
            assert {(row, col) for _, row, col, *_ in screen._ti_image_cviews} == {
                (2, 2),
                (2, 17),
                (9, 2),
                (9, 21),
                (14, 2),
                (14, 17),
            }

        finally:
            set_terminal_name_version(*_terminal_name_version)

    # FIXME: Figure out why the listbox insets are not scrolling the listbox by the
    # expected number of rows
    def test_scroll_listboxes(self):
        _terminal_name_version = get_terminal_name_version()
        try:
            set_terminal_name_version("konsole")
            # Setup
            buf.seek(0)
            buf.truncate()
            widget.top_w = top_w
            widget.top = 5
            kitty_list_box.shift_focus(_size, 0)
            iterm2_list_box.shift_focus(_size, 0)
            widget._invalidate()
            screen.draw_screen(_size, widget.render(_size))

            prev_image_cviews = screen._ti_image_cviews
            kitty_list_box.shift_focus(_size, -3)
            canv = widget.render(_size)
            # print(b"\n".join(canv.text).decode())
            screen.draw_screen(_size, canv)

            assert len(screen._ti_image_cviews) == 8
            assert prev_image_cviews != screen._ti_image_cviews
            # All images (4 cviews) on the right should remain unchanged
            assert len(prev_image_cviews & screen._ti_image_cviews) == 4
            assert {(row, col) for _, row, col, *_ in screen._ti_image_cviews} == {
                (2, 2),
                (2, 17),
                (6, 2),
                (6, 21),
                (8, 2),
                (9, 21),
                (11, 2),
                (11, 17),
            }
            assert {
                (row, col)
                for _, row, col, *_ in prev_image_cviews & screen._ti_image_cviews
            } == {
                (2, 17),
                (6, 21),
                (9, 21),
                (11, 17),
            }

            prev_image_cviews = screen._ti_image_cviews
            iterm2_list_box.shift_focus(_size, -9)
            canv = widget.render(_size)
            # print(b"\n".join(canv.text).decode())
            screen.draw_screen(_size, canv)

            assert len(screen._ti_image_cviews) == 8
            assert prev_image_cviews != screen._ti_image_cviews
            # All images (4 cviews) on the left should remain unchanged
            assert len(prev_image_cviews & screen._ti_image_cviews) == 4
            assert {(row, col) for _, row, col, *_ in screen._ti_image_cviews} == {
                (2, 2),
                (2, 17),
                (6, 2),
                (6, 21),
                (8, 2),
                (11, 2),
                (11, 17),
                (13, 17),
            }
            assert {
                (row, col)
                for _, row, col, *_ in prev_image_cviews & screen._ti_image_cviews
            } == {
                (2, 2),
                (6, 2),
                (8, 2),
                (11, 2),
            }

        finally:
            set_terminal_name_version(*_terminal_name_version)

    def test_change_top_widget(self):
        _terminal_name_version = get_terminal_name_version()
        try:
            set_terminal_name_version("konsole")
            # Setup
            buf.seek(0)
            buf.truncate()
            widget.top_w = top_w
            widget.top = 5
            kitty_list_box.shift_focus(_size, 0)
            iterm2_list_box.shift_focus(_size, 0)
            screen.draw_screen(_size, widget.render(_size))

            # kitty image in the top widget
            prev_image_cviews = screen._ti_image_cviews
            widget.top_w = kitty_image_w
            widget._invalidate()
            canv = widget.render(_size)
            # print(b"\n".join(canv.text).decode())
            screen.draw_screen(_size, canv)

            assert len(screen._ti_image_cviews) == 9
            assert prev_image_cviews != screen._ti_image_cviews
            assert len(screen._ti_image_cviews - prev_image_cviews) == 1
            assert (*(screen._ti_image_cviews - prev_image_cviews),)[0][1:3] == (6, 11)

            # block image in the top widget
            prev_image_cviews = screen._ti_image_cviews
            widget.top_w = block_image_w
            widget._invalidate()
            canv = widget.render(_size)
            # print(b"\n".join(canv.text).decode())
            screen.draw_screen(_size, canv)

            assert len(screen._ti_image_cviews) == 8
            assert prev_image_cviews != screen._ti_image_cviews
            assert len(prev_image_cviews - screen._ti_image_cviews) == 1
            assert (*(prev_image_cviews - screen._ti_image_cviews),)[0][1:3] == (6, 11)

            # iterm2 image in the top widget
            prev_image_cviews = screen._ti_image_cviews
            widget.top_w = iterm2_image_w
            widget._invalidate()
            canv = widget.render(_size)
            # print(b"\n".join(canv.text).decode())
            screen.draw_screen(_size, canv)

            assert len(screen._ti_image_cviews) == 9
            assert prev_image_cviews != screen._ti_image_cviews
            assert len(screen._ti_image_cviews - prev_image_cviews) == 1
            assert (*(screen._ti_image_cviews - prev_image_cviews),)[0][1:3] == (6, 11)

        finally:
            set_terminal_name_version(*_terminal_name_version)

    def test_iterm2_not_on_konsole(self):
        _terminal_name_version = get_terminal_name_version()
        try:
            set_terminal_name_version("wezterm")
            # Setup
            buf.seek(0)
            buf.truncate()
            widget.top_w = top_w
            widget.top = 5
            kitty_list_box.shift_focus(_size, 0)
            iterm2_list_box.shift_focus(_size, 0)

            widget._invalidate()
            canv = widget.render(_size)  # noqa: F841
            # print(b"\n".join(canv.text).decode())
            screen.draw_screen(_size, canv)

            # The images on the right are of iterm2 style but not on konsole
            assert len(screen._ti_image_cviews) == 4
            assert {(row, col) for _, row, col, *_ in screen._ti_image_cviews} == {
                (2, 2),
                (6, 2),
                (9, 2),
                (11, 2),
            }

        finally:
            set_terminal_name_version(*_terminal_name_version)
