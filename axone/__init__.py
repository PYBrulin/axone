try:
    from ._version import version as __version__  # noqa
    from ._version import version_tuple  # noqa
except ImportError:
    __version__ = "unknown version"
    version_tuple = (0, 0, "unknown version")
