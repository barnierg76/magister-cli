"""MCP server module for Magister CLI.

This module provides an MCP (Model Context Protocol) server that exposes
Magister operations as tools for Claude and other AI agents.
"""

from magister_cli.mcp.server import mcp, main

__all__ = ["mcp", "main"]
