"""Plugin architecture (Spec §35) — PLANNED, Phase 12.

A plugin will be a package exposing `register(registry)` that adds tools
(Spotify, Gmail, Discord, Calendar...). The BaseTool/ToolManager seam is the
integration point — plugins will get the same permissions/verification as
built-ins automatically.
"""
