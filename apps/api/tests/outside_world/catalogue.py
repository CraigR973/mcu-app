"""The films the fake TMDB knows: a few named ones, and numbered fillers.

Test data, not a record of real films: every field a screen shows is made up here.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Film:
    tmdb_id: int
    title: str
    year: int
    director: str = "Dana Director"
    runtime: int = 110
    genres: tuple[str, ...] = ("Drama",)
    cast: tuple[str, ...] = ("Alex Actor", "Sam Star")
    imdb_id: str | None = None
    keywords: tuple[str, ...] = field(default_factory=tuple)

    @property
    def release_date(self) -> str:
        return f"{self.year}-06-15"


#: Imported from the fixture sheet, and the ones the flows name.
NAMED: tuple[Film, ...] = (
    Film(1001, "The Lighthouse Keeper", 1994, "Maria Marsh", 118, ("Drama", "Thriller")),
    Film(1002, "Night Train to Lisbon Docks", 1987, "Omar Reyes", 104, ("Thriller",)),
    Film(1003, "Copper Canyon", 1972, "Ida Lund", 131, ("Western",)),
    Film(1004, "Paper Moons Over Leeds", 2003, "Ben Okafor", 96, ("Comedy",)),
    Film(1005, "The Quiet Engine", 2011, "Priya Nair", 124, ("Science Fiction", "Drama")),
    Film(1006, "Harbour Lights", 1958, "Leo Brandt", 99, ("Film Noir", "Crime")),
    Film(1007, "A Winter Of Wolves", 2016, "Sofia Kell", 142, ("Adventure",)),
    Film(1008, "Glass Orchard", 1999, "Tom Vale", 108, ("Horror",)),
    # Imported by the import case itself, after the seed.
    Film(1301, "Lantern Street", 1976, "Hana Cole", 97, ("Drama",)),
    Film(1302, "Velvet Frontier", 2019, "Rui Costa", 115, ("Western", "Drama")),
    # Wanted, not owned: the shop-price and alert cases.
    Film(1401, "Ember Coast", 2012, "Lena Fox", 103, ("Drama",)),
    Film(1402, "Salt And Static", 2005, "Joss Hale", 99, ("Science Fiction",)),
    # In the catalogue (wanted) but not owned: the offline replay adds a copy of it.
    Film(1403, "Paper Lantern", 2007, "Yuki Aoki", 94, ("Drama",)),
    # Unknown to the catalogue: the offline replay adds it by its TMDB id alone (Batch Z1).
    Film(1404, "Paper Kite", 2010, "Ines Moreau", 101, ("Drama",)),
    # Not owned at the start: the add-by-scan flow adds this one.
    Film(1101, "Midnight Ferry", 2009, "Nora Quill", 101, ("Mystery",)),
    # AA5 owns this fixture; the barcode case keeps 1202 to itself.
    Film(1501, "Velvet Observatory", 2018, "Mina Shore", 107, ("Drama",)),
    # AA6 owns a unique year-bounded draw fixture.
    Film(1601, "The Copper Lantern", 1931, "Lina Reed", 84, ("Drama",)),
    # The movie-night shortlist and match.
    Film(1201, "Rooftop Opera", 2014, "Yan Zhou", 112, ("Comedy", "Music")),
    Film(1202, "The Salt Road", 1991, "Kit Marlowe", 127, ("Adventure",)),
)

FILLER_FIRST = 900001
FILLER_COUNT = 62


def fillers() -> tuple[Film, ...]:
    return tuple(
        Film(FILLER_FIRST + n, f"Filler Feature {n + 1:03d}", 2001 + (n % 20))
        for n in range(FILLER_COUNT)
    )


def everything() -> tuple[Film, ...]:
    return NAMED + fillers()


def by_id(tmdb_id: int) -> Film | None:
    return next((film for film in everything() if film.tmdb_id == tmdb_id), None)
