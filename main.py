from PIL import Image
im = Image.open('pfp.jpg', 'r').resize((24, 24))
width, height = im.size
pixel_values = list(im.getdata())

                    
# print(pixel_values)
# # # # # # import sys

def colored(r, g, b, text):
    return "\033[38;2;{};{};{}m{} \033[38;2;255;255;255m".format(r, g, b, text)

width, height = im.size
l = len(pixel_values)

img_s = ""
for index, element in enumerate(pixel_values):
    if not isinstance(element, (tuple, list)):
        continue
    try:
        r, g, b, _ = element
    except:
        r, g, b = element
    if index % width == 0:
        print("")
    sys.stdout.write(colored(r, g, b, '\u2584'))
