"""api.themoviedb.org/3 — answered from the small catalogue in ``catalogue.py``."""

from __future__ import annotations

import re

import httpx

from . import catalogue
from .catalogue import Film

HOSTS = ("api.themoviedb.org",)

_PROVIDERS = {
    "GB": {
        "link": "https://www.themoviedb.org/movie/watch?locale=GB",
        "flatrate": [
            {"provider_id": 8, "provider_name": "Fake Stream", "logo_path": "/fake-stream.jpg"}
        ],
    }
}


#: TMDB's real genre ids, so the app's genre names come out as they do in production.
_GENRE_IDS = {
    "Adventure": 12,
    "Comedy": 35,
    "Crime": 80,
    "Drama": 18,
    "Horror": 27,
    "Music": 10402,
    "Mystery": 9648,
    "Science Fiction": 878,
    "Thriller": 53,
    "Western": 37,
    "Film Noir": 80,
}


def _norm(text: str) -> str:
    return re.sub(r"[^a-z0-9 ]+", " ", text.lower()).strip()


def _movie_json(film: Film, appended: set[str]) -> dict[str, object]:
    body: dict[str, object] = {
        "id": film.tmdb_id,
        "title": film.title,
        "original_title": film.title,
        "overview": f"{film.title} is a made-up film for the end-to-end suite.",
        "release_date": film.release_date,
        "runtime": film.runtime,
        "tagline": "",
        "status": "Released",
        "budget": 0,
        "revenue": 0,
        "vote_average": 7.1,
        "vote_count": 1200,
        "popularity": 20.0,
        "adult": False,
        "video": False,
        "imdb_id": film.imdb_id or f"tt{film.tmdb_id:07d}",
        "original_language": "en",
        "homepage": "",
        "poster_path": f"/poster-{film.tmdb_id}.jpg",
        "backdrop_path": f"/backdrop-{film.tmdb_id}.jpg",
        "belongs_to_collection": None,
        "genres": [{"id": _GENRE_IDS.get(name, 18), "name": name} for name in film.genres],
        "production_companies": [],
        "production_countries": [{"iso_3166_1": "GB", "name": "United Kingdom"}],
        "spoken_languages": [{"iso_639_1": "en", "name": "English", "english_name": "English"}],
    }
    if "credits" in appended:
        body["credits"] = {
            "cast": [
                {
                    "id": film.tmdb_id * 10 + i,
                    "name": name,
                    "character": f"Role {i + 1}",
                    "order": i,
                    "profile_path": None,
                    "credit_id": f"c{film.tmdb_id}{i}",
                }
                for i, name in enumerate(film.cast)
            ],
            "crew": [
                {
                    "id": film.tmdb_id * 10 + 9,
                    "name": film.director,
                    "job": "Director",
                    "department": "Directing",
                    "profile_path": None,
                    "credit_id": f"d{film.tmdb_id}",
                }
            ],
        }
    if "videos" in appended:
        body["videos"] = {"results": []}
    if "watch/providers" in appended:
        body["watch/providers"] = {"results": _PROVIDERS}
    if "keywords" in appended:
        body["keywords"] = {
            "keywords": [{"id": 9000 + i, "name": word} for i, word in enumerate(film.keywords)]
        }
    return body


def _search(query: str, year: int | None) -> dict[str, object]:
    wanted = _norm(query)
    exact: list[Film] = []
    partial: list[Film] = []
    for film in catalogue.everything():
        title = _norm(film.title)
        if year is not None and film.year != year:
            continue
        if title == wanted:
            exact.append(film)
        elif wanted and wanted in title:
            partial.append(film)
    found = (exact + partial)[:20]
    results = [
        {
            "id": film.tmdb_id,
            "title": film.title,
            "original_title": film.title,
            "overview": f"{film.title} is a made-up film for the end-to-end suite.",
            "release_date": film.release_date,
            "popularity": 20.0 - index,
            "vote_average": 7.1,
            "vote_count": 1200,
            "poster_path": f"/poster-{film.tmdb_id}.jpg",
            "backdrop_path": None,
            "adult": False,
            "video": False,
            "genre_ids": [],
            "original_language": "en",
        }
        for index, film in enumerate(found)
    ]
    return {"page": 1, "results": results, "total_pages": 1, "total_results": len(results)}


def handle(request: httpx.Request, world: object) -> httpx.Response:
    path = request.url.path.removeprefix("/3")
    params = request.url.params

    if path == "/search/movie":
        year_text = params.get("year")
        year = int(year_text) if year_text and year_text.isdigit() else None
        return httpx.Response(200, json=_search(params.get("query", ""), year))
    if path in ("/search/tv", "/search/person"):
        return httpx.Response(
            200, json={"page": 1, "results": [], "total_pages": 0, "total_results": 0}
        )

    movie = re.fullmatch(r"/movie/(\d+)(/.*)?", path)
    if movie:
        film = catalogue.by_id(int(movie.group(1)))
        if film is None:
            return httpx.Response(404, json={"status_code": 34, "status_message": "Not found"})
        tail = movie.group(2) or ""
        if tail == "":
            appended = set(params.get("append_to_response", "").split(","))
            return httpx.Response(200, json=_movie_json(film, appended))
        if tail == "/keywords":
            return httpx.Response(
                200,
                json={"id": film.tmdb_id, "keywords": [{"id": 1, "name": w} for w in film.keywords]},
            )
        if tail == "/watch/providers":
            return httpx.Response(200, json={"id": film.tmdb_id, "results": _PROVIDERS})
        if tail == "/release_dates":
            return httpx.Response(200, json={"id": film.tmdb_id, "results": []})
        if tail in ("/recommendations", "/similar"):
            return httpx.Response(
                200, json={"page": 1, "results": [], "total_pages": 0, "total_results": 0}
            )
        if tail == "/alternative_titles":
            return httpx.Response(200, json={"id": film.tmdb_id, "titles": []})

    if path in ("/movie/upcoming", "/discover/movie", "/movie/now_playing", "/trending/movie/week"):
        return httpx.Response(
            200, json={"page": 1, "results": [], "total_pages": 0, "total_results": 0}
        )
    if re.fullmatch(r"/person/\d+/movie_credits", path):
        return httpx.Response(200, json={"id": 0, "cast": [], "crew": []})
    if path == "/configuration":
        return httpx.Response(200, json={"images": {}})

    world.log(kind="unknown", host=request.url.host, path=request.url.path)  # type: ignore[attr-defined]
    return httpx.Response(404, json={"status_code": 34, "status_message": "Not faked"})
