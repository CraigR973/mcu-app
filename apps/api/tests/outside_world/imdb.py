"""IMDb's documented daily ratings format, with made-up scores for the fake catalogue."""

from __future__ import annotations

import gzip

import httpx

from .catalogue import everything
from .core import World

HOSTS = ("datasets.imdbws.com",)


def handle(request: httpx.Request, world: World) -> httpx.Response:
    if request.method != "GET" or request.url.path != "/title.ratings.tsv.gz":
        world.log(kind="unknown", host=request.url.host, path=request.url.path)
        return httpx.Response(404)
    scenario = world.scenario().get("imdb", {})
    status = int(scenario.get("status", 200))
    if status != 200:
        return httpx.Response(status, text="IMDb fake refusal")
    body = "tconst\taverageRating\tnumVotes\n" + "".join(
        f"{film.imdb_id or f'tt{film.tmdb_id:07d}'}\t8.2\t1234\n" for film in everything()
    )
    return httpx.Response(
        200, content=gzip.compress(body.encode()), headers={"Content-Type": "application/gzip"}
    )
