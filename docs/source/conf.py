# Configuration file for the Sphinx documentation builder.
#
# For the full list of configuration options, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

from term_image import __version__, utils

# -- Path setup --------------------------------------------------------------

# If extensions (or modules to document with autodoc) are in another directory,
# add these directories to sys.path here. If the directory is relative to the
# documentation root, use os.path.abspath to make it absolute, like shown here.
# sys.path.insert(0, os.path.abspath("../../src"))

# -- Project information -----------------------------------------------------
project = "Term-Image"
copyright = "2022, Toluwaleke Ogundipe"
author = "Toluwaleke Ogundipe"
release = __version__

# -- General configuration ---------------------------------------------------
extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.napoleon",
    "sphinx.ext.viewcode",
    "sphinx.ext.intersphinx",
    "sphinx_toolbox.github",
    "sphinx_toolbox.sidebar_links",
    "sphinx_toolbox.more_autosummary",
]
toc_object_entries = False

# -- Options for HTML output -------------------------------------------------
html_theme = "furo"
html_logo = "resources/logo.png"
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
autodoc_inherit_docstrings = False

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

# -- Event handlers -------------------------------------------------------------


def autodocssumm_grouper(app, what, name, obj, section, parent):
    from enum import EnumMeta
    from types import FunctionType

    if isinstance(obj, EnumMeta):
        return "Enumerations"
    elif isinstance(obj, type) and issubclass(obj, Warning):
        return "Warnings"
    elif isinstance(parent, type):
        obj = vars(parent)[name.rpartition(".")[2]]
        if isinstance(obj, utils.ClassProperty):
            return "Class Properties"
        elif isinstance(obj, utils.ClassInstanceProperty):
            return "Class/Instance Properties"
        elif isinstance(obj, property):
            return "Instance Properties"
        elif isinstance(obj, FunctionType):
            return "Instance Methods"
        elif isinstance(obj, utils.ClassInstanceMethod):
            return "Class/Instance Methods"
        elif isinstance(obj, classmethod):
            return "Class Methods"
        elif isinstance(obj, staticmethod):
            return "Static Methods"


def setup(app):
    app.connect("autodocsumm-grouper", autodocssumm_grouper)


# -- Extras -----------------------------------------------------------

# The overidding `__get__()`s do not return the descriptor itself
utils.ClassInstanceProperty.__get__ = property.__get__
utils.ClassProperty.__get__ = property.__get__
