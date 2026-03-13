import asyncio

from . import server


def main():
    asyncio.run(server.main())


def main_http():
    asyncio.run(server.main_http())


__all__ = ["main", "main_http", "server"]
