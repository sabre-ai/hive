"""hive — capture, enrich, store, and serve AI sessions."""

try:
    from importlib.metadata import version

    __version__ = version("hive-team")
except Exception:
    __version__ = "0.0.0"
