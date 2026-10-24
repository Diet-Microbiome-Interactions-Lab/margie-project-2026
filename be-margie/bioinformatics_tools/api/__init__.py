"""
FastAPI application for bioinformatics tools (bioinformatics_tools.api.main: app, serve).

The package loads the app only when app or serve is asked for: the short helpers the API runs
on the cluster (services.job_history, for each job list) import from it, and loading the whole
app first took them 2 s and its secret keys.
"""

__all__ = ['app', 'serve']


def __getattr__(name: str):
    if name in __all__:
        from bioinformatics_tools.api import main
        return getattr(main, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
