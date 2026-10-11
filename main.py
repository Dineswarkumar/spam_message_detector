"""
Root entrypoint for Render and container deployments.
Forwards directly to backend.main:app so default start commands work out of the box.
"""
from backend.main import app  # noqa: F401

__all__ = ["app"]
