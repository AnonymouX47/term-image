import sys
import os

from image import DrawImage
from colr import color


class ImageCLI(object):
    def create_error_message(self, message, suggestion=None, is_fatal=True):
        print(color(message, "red"))
        if suggestion:
            print(color(suggestion, "yellow"))
        sys.exit() if is_fatal else None

    def parse_arguments(self):
        command, parameters = "", {}
        for index, argument in enumerate(sys.argv[1:]):
            if index == 0:
                command = argument
                continue
            is_valid_parameter = argument.startswith("--")
            if not is_valid_parameter:
                self.create_error_message(
                    f"Invalid parameter: {argument}", "Use -- in the beginning of key"
                )
            slices = argument.split("=")
            key, value = slices[0][2:], "=".join(slices[1:])
            if len(key.strip()) == 0:
                self.create_error_message("Empty values")
            parameters.setdefault(key, value)
        return command, parameters

    def display_image(self):
        command, parameters = self.parse_arguments()
        self.draw_image(command, parameters)

    def draw_image(self, filename, parameters):
        size = self.create_size_tuple(parameters.get("size") or "50x50")
        if not size:
            self.create_error_message(
                f"Invalid size parameter: {parameters.get('size')}"
            )
        try:
            DrawImage(filename, size).draw_image() if os.path.isfile(
                filename
            ) else DrawImage.from_url(filename, size).draw_image()
        except Exception as exception:
            self.create_error_message(exception.__str__())

    def create_size_tuple(self, size_string):
        slices = size_string.split("x")
        try:
            tuple_size = tuple(map(lambda element: int(element), slices))[:2]
            return tuple_size if len(tuple_size) == 2 else None
        except Exception as exception:
            return None


def main():
    cli = ImageCLI()
    cli.display_image()
