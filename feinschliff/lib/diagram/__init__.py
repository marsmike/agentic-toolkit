"""DSL → themed Excalidraw → PNG pipeline.

Lifted from feinschliff/brands/*/renderers/pptx/diagram_pipeline.py in PR-2 to
remove a 6× duplication. The brand-binding (which Excalidraw theme to apply)
is now a parameter rather than a hard-coded import.
"""
from .pipeline import render_diagram, strip_theme_pragma
from .validator import check

__all__ = ["render_diagram", "strip_theme_pragma", "check"]
