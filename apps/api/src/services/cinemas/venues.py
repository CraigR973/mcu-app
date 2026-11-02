"""The owner-approved nine venues and their observed source entry points."""

from dataclasses import dataclass
from uuid import NAMESPACE_URL, UUID, uuid5


@dataclass(frozen=True)
class Venue:
    slug: str
    name: str
    source: str
    source_id: str
    programme_url: str
    official_url: str

    @property
    def id(self) -> UUID:
        return uuid5(NAMESPACE_URL, "mcu:cinema:" + self.slug)


_CT = "https://cinematimes.com/uk/glasgow/cinemas/"
VENUES = (
    Venue(
        "odeon-kilmarnock",
        "ODEON Kilmarnock",
        "cinematimes",
        "odeon-kilmarnock",
        _CT + "odeon-kilmarnock/",
        "https://www.odeon.co.uk/cinemas/kilmarnock/",
    ),
    Venue(
        "odeon-glasgow-quay",
        "ODEON Glasgow Quay",
        "cinematimes",
        "odeon-glasgow-springfield-quay",
        _CT + "odeon-glasgow-springfield-quay/",
        "https://www.odeon.co.uk/cinemas/glasgow-quay/",
    ),
    Venue(
        "odeon-braehead",
        "ODEON Braehead",
        "cinematimes",
        "odeon-braehead-renfrew",
        _CT + "odeon-braehead-renfrew/",
        "https://www.odeon.co.uk/cinemas/braehead/",
    ),
    Venue(
        "odeon-east-kilbride",
        "ODEON East Kilbride",
        "cinematimes",
        "odeon-east-kilbride-glasgow",
        _CT + "odeon-east-kilbride-glasgow/",
        "https://www.odeon.co.uk/cinemas/east-kilbride/",
    ),
    Venue(
        "cineworld-silverburn",
        "Cineworld Glasgow Silverburn",
        "cineworld",
        "X0VQ1",
        "https://www.cineworld.co.uk/cinemas/x0vq1-cineworld-cinema-glasgow-silverburn/",
        "https://www.cineworld.co.uk/cinemas/glasgow-silverburn",
    ),
    Venue(
        "vue-st-enoch",
        "Vue Glasgow St Enoch",
        "vue",
        "10097",
        "https://www.myvue.com/cinema/glasgow-st-enoch/whats-on",
        "https://www.myvue.com/cinema/glasgow-st-enoch/whats-on",
    ),
    Venue(
        "everyman-glasgow",
        "Everyman Glasgow, Princes Square",
        "everyman",
        "X11DQ",
        "https://www.everymancinema.com/venues-list/x11dq-everyman-glasgow/",
        "https://www.everymancinema.com/venues-list/x11dq-everyman-glasgow/",
    ),
    Venue(
        "gft",
        "Glasgow Film Theatre",
        "gft",
        "gft",
        "https://www.glasgowfilm.org/all-listings/",
        "https://www.glasgowfilm.org/all-listings/",
    ),
    Venue(
        "science-centre-imax",
        "Glasgow Science Centre IMAX",
        "science",
        "gscimax",
        "https://www.glasgowsciencecentre.org/imax",
        "https://www.glasgowsciencecentre.org/imax",
    ),
)
BY_ID = {v.id: v for v in VENUES}
BY_SLUG = {v.slug: v for v in VENUES}
