# Configuration file for the Sphinx documentation builder.
#
# This file only contains a selection of the most common options. For a full
# list see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

from term_image import __version__

# -- Path setup --------------------------------------------------------------

# If extensions (or modules to document with autodoc) are in another directory,
# add these directories to sys.path here. If the directory is relative to the
# documentation root, use os.path.abspath to make it absolute, like shown here.
# sys.path.insert(0, os.path.abspath("../../src"))

# -- Project information -----------------------------------------------------

project = "term-image"
copyright = "2022, Toluwaleke Ogundipe"
author = "Toluwaleke Ogundipe"
release = __version__


# -- General configuration ---------------------------------------------------

# Add any Sphinx extension module names here, as strings. They can be
# extensions coming with Sphinx (named 'sphinx.ext.*') or your custom
# ones.
extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.napoleon",
    "sphinx.ext.viewcode",
    "sphinx.ext.intersphinx",
    "sphinx_toolbox.github",
    "sphinx_toolbox.sidebar_links",
    "sphinx_toolbox.more_autosummary",
]

# Add any paths that contain templates here, relative to this directory.
templates_path = []

# List of patterns, relative to source directory, that match files and
# directories to ignore when looking for source files.
# This pattern also affects html_static_path and html_extra_path.
exclude_patterns = []


# -- Options for HTML output -------------------------------------------------

# The theme to use for HTML and HTML Help pages.  See the documentation for
# a list of builtin themes.
html_theme = "furo"

# Theme options are theme-specific and customize the look and feel of a theme
# further.  For a list of options available for each theme, see the
# documentation.
html_theme_options = {
    "light_logo": "logo.png",
    "dark_logo": "logo.png",
}

# Add any paths that contain custom static files (such as style sheets) here,
# relative to this directory. They are copied after the builtin static files,
# so a file named "default.css" will overwrite the builtin "default.css".
html_static_path = ["resources"]

# The name of an image file (within the static path) to use as favicon of the
# docs.  This file should be a Windows icon file (.ico) being 16x16 or 32x32
# pixels large.
html_favicon = "resources/logo.ico"


# -- Options for extensions ----------------------------------------------

# # -- sphinx-autodoc -----------------------------------------------------
autodoc_default_options = {
    "members": True,
    "show-inheritance": True,
    "member-order": "bysource",
    "autosummary": True,
    "autosummary-nosignatures": True,
}
autodoc_typehints = "description"
autodoc_typehints_format = "fully-qualified"
autodoc_typehints_description_target = "documented"
autodoc_member_order = "bysource"

# # -- sphinx-intersphinx ----------------------------------------------
intersphinx_mapping = {
    "python": ("https://docs.python.org/3", None),
    "pillow": ("https://pillow.readthedocs.io/en/stable/", None),
    "requests": ("https://requests.readthedocs.io/en/stable/", None),
    "urwid": ("https://urwid.org", None),
}

# # -- sphinx_toolbox-github ----------------------------------------------
github_username = "AnonymouX47"
github_repository = "term-image"

# # -- sphinx_toolbox-more_autosummary ----------------------------------------------
autodocsumm_member_order = "bysource"


# -- Others options ----------------------------------------------------------
toc_object_entries = False


# -- Event handlers -------------------------------------------------------------


def autodocssumm_grouper(app, what, name, obj, section, parent):
    from enum import EnumMeta
    from types import FunctionType

    from term_image.utils import ClassInstanceMethod

    if isinstance(obj, EnumMeta):
        return "Enumerations"
    elif isinstance(obj, type) and issubclass(obj, Warning):
        return "Warnings"
    elif isinstance(parent, type):
        obj = vars(parent)[name.rpartition(".")[2]]
        if isinstance(obj, property):
            return "Properties"
        elif isinstance(obj, FunctionType):
            return "Instance Methods"
        elif isinstance(obj, ClassInstanceMethod):
            return "Class-Instance Methods"
        elif isinstance(obj, classmethod):
            return "Class Methods"
        elif isinstance(obj, staticmethod):
            return "Static Methods"


def setup(app):
    app.connect("autodocsumm-grouper", autodocssumm_grouper)
