from .server import mcp


def main():
    mcp.run(transport="stdio")


def main_http():
    mcp.run(transport="streamable-http")


__all__ = ["main", "main_http", "mcp"]
