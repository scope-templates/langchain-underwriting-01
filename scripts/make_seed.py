"""Writes data/seed.json. The output is the same bytes on every run.

Run from the repo root: python scripts/make_seed.py
"""

import json
import random
from dataclasses import dataclass, field, replace
from datetime import date, timedelta
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "data" / "seed.json"
SEED = 222

HISTORY_START = date(2022, 6, 1)
BOOK_START = date(2022, 10, 3)
YEAR_START = date(2025, 10, 1)
SEED_END = date(2026, 9, 30)
AS_OF = date(2026, 10, 1)
LOG_BEGAN = date(2026, 4, 1)
FACT_EARLIEST = date(2025, 6, 2)
PREMIUM_AUTHORITY = 20_000
VALUE_AUTHORITY = 5_000_000
NEW_BUSINESS_RATE = {"before": 0.19, "year": 0.65}
RENEWAL_SUBMITTED = 0.5
MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September",
          "October", "November", "December"]
CARRIERS = ("Callander Indemnity Company", "Coteau Casualty Company")
CARRIER_SHORT = {CARRIERS[0]: "Callander", CARRIERS[1]: "Coteau"}

MARGIT, CALVIN, PRIYA, JONAH, LUCIA, TERRENCE, SABINE = 1, 2, 3, 4, 5, 6, 7
STAFF = [
    (MARGIT, "Margit Olafsen", "senior"),
    (CALVIN, "Calvin Ruehl", "senior"),
    (PRIYA, "Priya Ramaswamy", "underwriter"),
    (JONAH, "Jonah Feldkamp", "underwriter"),
    (LUCIA, "Lucia Brandvold", "underwriter"),
    (TERRENCE, "Terrence Okafor", "underwriter"),
    (SABINE, "Sabine Mulvaney", "underwriter"),
    (8, "Gretchen Hasselbring", "viewer"),
    (9, "Ruthann Bisbee", "viewer"),
    (10, "Omar Keddie", "viewer"),
    (11, "Lorna Fitzhugh", "viewer"),
]
SENIORS = (MARGIT, CALVIN)
UNDERWRITERS = (PRIYA, JONAH, LUCIA, TERRENCE, SABINE)
DESK_WEIGHTS = [(PRIYA, 3), (JONAH, 3), (LUCIA, 3), (TERRENCE, 3), (SABINE, 3), (MARGIT, 1), (CALVIN, 1)]
FIRST_NAMES = {sid: name.split()[0] for sid, name, _ in STAFF}

TOWNS = {
    "IA": [("Marquand Bluff", "52144"), ("Hesper Mills", "50628"), ("Dalby Center", "51035"),
           ("Coyle Junction", "50864")],
    "IL": [("Ardmoor", "61327"), ("Kasling", "62418"), ("Belcastle", "60973"), ("Orvis Prairie", "61742")],
    "WI": [("Pruden Falls", "54459"), ("Lake Ottilie", "53927"), ("Holmquist", "54836")],
    "MN": [("Eskelund", "56247"), ("Two Herons", "56583"), ("Saint Brannagh", "55388")],
    "MO": [("Corley Springs", "65439"), ("Tindall Ferry", "64688"), ("Bexley Ridge", "63559")],
    "NE": [("Varnell", "68852"), ("Sallow Creek", "69134")],
    "KS": [("Hadley Cross", "67446"), ("Pratter", "66958")],
    "SD": [("Dorrance Butte", "57367"), ("Kilcairn", "57631")],
}
STATE_WEIGHTS = [("IA", 26), ("IL", 16), ("WI", 15), ("MN", 13), ("MO", 12), ("NE", 7), ("KS", 6), ("SD", 5)]
STREETS = ["Elm", "Walnut", "Cedar", "Railroad", "Commerce", "Broadway", "Market", "Second", "Fourth", "Fifth",
           "Lincoln", "Grant", "Park", "Lake", "Bluff", "Prairie", "Center", "Washington", "Division", "State",
           "Oak", "Hickory", "Chestnut", "Pearl", "Spring", "River", "Bridge", "Church", "Highland", "Ridge"]
STREET_KINDS = ["St", "St", "Ave", "Ave", "Rd", "Blvd", "Dr", "Ln"]

LAST = ["Abernathy", "Aguirre", "Albrecht", "Amundsen", "Arceo", "Bakken", "Balogun", "Beaudry", "Bergstrom",
        "Blanchette", "Bohannon", "Bouchard", "Brekke", "Bucio", "Carrasco", "Cervantes", "Chao",
        "Clausen", "Contreras", "Dahlberg", "Danforth", "Delgado", "Demski", "Dorsch", "Dufresne",
        "Ebersole", "Eckhardt", "Engstrom", "Espinoza", "Fairbairn", "Feeney", "Figueroa", "Flaherty",
        "Fong", "Gaskell", "Giese", "Grajeda", "Gustafson", "Haugen", "Hedlund",
        "Hernandez", "Hjelm", "Holm", "Hruska", "Ibarra", "Iverson", "Janssen", "Jorgensen",
        "Kaminski", "Kasper", "Keane", "Kjelstad", "Klug", "Kozak", "Lam",
        "Larsen", "Leclair", "Lindahl", "Lozano", "Maas", "Magnuson", "Malecki", "Medina", "Mendel",
        "Mikkelsen", "Moua", "Nadler", "Nguyen", "Novak", "Nygaard", "Ochoa", "Olmstead", "Oyelaran",
        "Paquette", "Pedersen", "Pham", "Platt", "Pollard", "Quintero", "Rademacher", "Reinholt", "Rios",
        "Roemer", "Rosales", "Rudd", "Saelee", "Salgado", "Sandoval", "Schaefer", "Schmid", "Selvig", "Sheehan",
        "Skaar", "Sobczak", "Solberg", "Stoltz", "Sundquist", "Tellez", "Thao", "Tierney", "Trujillo",
        "Vang", "Velez", "Vogt", "Wendt", "Westergaard", "Wiebe", "Wojcik", "Xiong", "Yang",
        "Yeager", "Zamora", "Zielinski", "Zuniga"]
FIRST = ["Aaron", "Adriana", "Alicia", "Amos", "Andrea", "Angela", "Barb", "Beatriz", "Brent", "Brianna", "Bruce",
         "Caleb", "Carmen", "Cassie", "Chad", "Chue", "Clint", "Colleen", "Connor", "Dana", "Darnell", "Deb",
         "Diego", "Donna", "Dwayne", "Elena", "Erik", "Esperanza", "Evan", "Felipe", "Gina", "Glenn", "Greta",
         "Heidi", "Hodan", "Ian", "Jada", "Jamal", "Janelle", "Javier", "Jill", "Joaquin", "Jodi", "Josh", "Juana",
         "Karl", "Kayla", "Keith", "Khadra", "Kirk", "Kristin", "Lars", "Leticia", "Linh", "Lonnie", "Mai",
         "Marcy", "Mariah", "Maurice", "Mei", "Mitch", "Nell", "Nhia", "Nolan", "Norma", "Pa Houa", "Patrice",
         "Quinn", "Randall", "Renee", "Rocio", "Russ", "Sarah", "Shane", "Sherri", "Stacy", "Steve", "Tasha",
         "Terri", "Thanh", "Todd", "Tou", "Trent", "Vanessa", "Vern", "Whitney", "Xochitl", "Yer", "Zach"]
PLACES = ["Bluestem", "Sixmile", "Ninebark", "Turkey Run", "Gilt Edge", "Saltlick", "Prairie Rose", "Oxeye",
          "Whitetail", "Hackberry", "Driftwood", "Sandbar", "Cottonwood", "Bur Oak",
          "Switchgrass", "Meadowvale", "Plover", "Fox Hollow", "Sunfish", "Walleye",
          "Coneflower", "Barn Swallow", "Wild Plum", "Shelterbelt", "Cattail", "Ox Bow Bend"]
NOUNS = ["Tin Heron", "Crooked Ferrule", "Wicket", "Gilded Perch", "Copper Pail", "Lucky Drake", "Quiet Owl",
         "Saltgrass", "Rusted Plow", "Grain Elevator", "Brass Bell", "Long Furrow",
         "Sorghum", "Hay Loft", "Blue Gate", "Iron Gate"]
BUSINESS_SURNAMES = [
    "Aasen", "Abrego", "Ahlquist", "Alcala", "Almquist", "Amezcua", "Anfinson", "Arndt", "Arreola", "Aune",
    "Balderas", "Barajas", "Baumgart", "Beckwith", "Behrens", "Belmonte", "Bergland", "Bergum", "Bielski", "Biermann",
    "Blomquist", "Boehm", "Bonilla", "Borchert", "Bostwick", "Brandl", "Bratten", "Brekken", "Brody", "Bunde",
    "Burkholder", "Bystrom", "Cabrales", "Caceres", "Carrillo", "Casillas", "Castaneda", "Cepeda", "Christophersen",
    "Cisneros", "Coble", "Dahle", "Dahlquist", "Delacruz", "Deloria", "Dettmer", "Dieck", "Dobbins", "Dorn",
    "Dornfeld", "Dvorak", "Ebeling", "Eggers", "Egland", "Ehlert", "Eide", "Elgersma", "Ellefson", "Ellingboe",
    "Enriquez", "Erdahl", "Escamilla", "Espe", "Estrada", "Fenske", "Fiala", "Fiske", "Fjelstad", "Folkers",
    "Fritsche", "Fuentes", "Gaarder", "Galvan", "Gamez", "Garza", "Gerdes", "Gilbertson", "Gilje", "Gjerde",
    "Goetsch", "Grabowski", "Grimsrud", "Groth", "Guerrero", "Gunderson", "Haakenson", "Hanneman", "Harstad", "Haug",
    "Hauge", "Hedstrom", "Hegg", "Heggen", "Heinrich", "Helgeson", "Hemmer", "Henning", "Herrera", "Hilgers", "Hoeft",
    "Hofer", "Hoiland", "Holmgren", "Holtan", "Houska", "Hovland", "Huerta", "Huseby", "Ibsen", "Imhoff", "Iturbe",
    "Jahnke", "Jelinek", "Jernigan", "Juarez", "Kalina", "Kampa", "Kelderman", "Kingery", "Kjos", "Klemm", "Kloster",
    "Knutson", "Koerner", "Kolb", "Kopecky", "Kortum", "Kowal", "Krogstad", "Kubik", "Kvamme", "Lacy", "Lagos",
    "Langseth", "Lauer", "Ledesma", "Lien", "Lindblad", "Loera", "Lofgren", "Lucero", "Luedtke", "Lunde", "Lysne",
    "Madsen", "Maldonado", "Marek", "Mares", "Marquez", "Mattson", "Meza", "Mickelson", "Molinar", "Mork", "Mosqueda",
    "Mrozek", "Myhre", "Naegele", "Navarro", "Nelsen", "Nesheim", "Nordby", "Nowak", "Nyberg", "Ochs", "Odegaard",
    "Olivares", "Opsahl", "Orozco", "Ortiz", "Pacheco", "Pagel", "Paulsen", "Pena", "Petrik", "Pokorny", "Prado",
    "Quam", "Quinlan", "Quiroz", "Raasch", "Ramos", "Rasmussen", "Reinke", "Rendon", "Rieck", "Rindal", "Roiland",
    "Rojas", "Rosendahl", "Rubio", "Rustad", "Saari", "Salas", "Sanchez", "Sather", "Schoenfeld", "Schroeder", "Seim",
    "Serrano", "Sievers", "Skaug", "Skogen", "Slama", "Soto", "Stang", "Steffen", "Stenberg", "Strommen", "Suda",
    "Svoboda", "Tafoya", "Teig", "Thorson", "Tjaden", "Tollefson", "Tovar", "Trevino", "Tvedt", "Ueland",
    "Ulvestad", "Urbina", "Valdez", "Vasko", "Vigil", "Vik", "Villarreal", "Vollmer", "Waldron", "Westby", "Wickre",
    "Wiersma", "Wold", "Wollan", "Yanez", "Ybarra", "Zahn", "Zavala", "Zeman",
]
PLACES_MORE = ["Sable Ridge", "Otter Slough", "Coyote Flats", "Willowmere", "Mallard Slough", "Thistledown",
               "Juneberry", "Bluegill", "Chokecherry", "Bittern", "Kingbird", "Prairie Smoke", "Sweetgrass", "Foxtail",
               "Wolfberry", "Dickcissel", "Goldenrod", "Coralberry", "Yarrow", "Cordgrass", "Pasqueflower", "Wild Rye",
               "Turtle Creek", "Badger Hollow", "Plum Hollow", "Hickory Grove", "Rock Prairie", "Mud Lake",
               "Gopher Hill", "Owl Hollow"]
NOUNS_MORE = ["Hay Fork", "Corn Crib", "Butter Churn", "Sod House", "Bent Nail", "Hayrake", "Wagon Spoke",
              "Feed Sack", "Grain Bin", "Cast Net", "Rusty Anvil", "Fence Post", "Muskrat"]
CLASSES = [("full-service restaurant", "restaurant", 20), ("family restaurant", "restaurant", 14),
           ("pizzeria", "restaurant", 10), ("bar and grill", "bar", 14), ("tavern", "bar", 10),
           ("brewpub", "bar", 5), ("caterer", "caterer", 10), ("commercial bakery", "producer", 7),
           ("smoked meats producer", "producer", 4), ("salsa and sauce maker", "producer", 3),
           ("coffee roaster", "producer", 3)]
KIND_OF = {c: k for c, k, _ in CLASSES}
TRADE_NAMES = {
    "full-service restaurant": ["{s}'s Supper Club", "{s}'s Table", "Casa {s}", "{p} Chop House", "The {n} Room",
                                "{s} Bistro"],
    "family restaurant": ["{s}'s Family Restaurant", "{p} Diner", "{s}'s Kitchen", "{p} Cafe"],
    "pizzeria": ["{s}'s Pizza", "{p} Pizza Works", "{s} Pizzeria"],
    "bar and grill": ["{s}'s Bar & Grill", "{p} Grill & Tap", "The {n} Bar & Grill"],
    "tavern": ["{s}'s Tap", "{p} Tavern", "The {n}", "{s}'s Corner Bar"],
    "brewpub": ["{p} Brewing", "{s} Brewhouse", "{n} Brewing"],
    "caterer": ["{s} Catering", "{p} Events & Catering", "{s}'s Kitchen Catering"],
    "commercial bakery": ["{s} Bakery", "{p} Bread Co.", "{s}'s Bake House"],
    "smoked meats producer": ["{s}'s Smoked Meats", "{p} Jerky Co.", "{s} Meat Smokers"],
    "salsa and sauce maker": ["{s}'s Salsa", "{p} Sauce Co.", "{s} Pepper Works"],
    "coffee roaster": ["{p} Coffee Roasters", "{s} Roasting", "{n} Coffee"],
}
LEGAL_SUFFIXES = ["Hospitality LLC", "Restaurant Group LLC", "Foods Inc.", "Enterprises LLC", "Holdings LLC",
                  "Kitchens LLC"]
INITIALS = "ABCDEFGHJKLMNPRSTW"
COOKING = {
    "full-service restaurant": ["full line with fryers and a charbroiler", "woks and a fryer", "open grill, no fryers",
                                "wood-fired oven and a charbroiler"],
    "family restaurant": ["griddle, two fryers and a six-burner range", "flat top and two fryers",
                          "full line with fryers and a charbroiler"],
    "pizzeria": ["pizza deck ovens and one fryer", "conveyor pizza oven, no fryers"],
    "bar and grill": ["bar menu off two fryers", "fryers and a flat top", "smoker and two fryers"],
    "tavern": ["bar menu off two fryers", "frozen pizza oven only", "fryers and a flat top"],
    "brewpub": ["fryers and a flat top", "smoker and two fryers", "brick oven and one fryer"],
    "caterer": ["commissary kitchen with ovens and kettles", "commissary kitchen with a tilt skillet and fryer"],
    "commercial bakery": ["deck ovens and mixers, no fryers", "rack ovens, mixers and a donut fryer"],
    "smoked meats producer": ["smokehouse, slicer and vacuum packer", "two smokers and a vacuum packer"],
    "salsa and sauce maker": ["steam kettles and a bottling line", "kettles, a filler and a capper"],
    "coffee roaster": ["two drum roasters with an afterburner", "one drum roaster and a packing line"],
}
HOT_WORK = ("fryer", "smok", "oven", "roaster", "grill", "griddle", "flat top", "wok", "broiler")


def has_fryers(cooking: str) -> bool:
    return "fryer" in cooking and "no fryers" not in cooking
CONSTRUCTION = [("frame", 26), ("joisted masonry", 34), ("brick", 18), ("masonry noncombustible", 12),
                ("metal building", 10)]
MUSIC_NIGHTS = ["Friday and Saturday nights", "Saturday nights", "Thursday through Saturday", "every other Friday",
                "Sunday afternoons"]
FIRMS = {"Brule Inspection Services": ["Dwight Sobotka", "Marisa Quale"],
         "Kestner Risk Surveys": ["Len Ostby", "Tara Fuhrman"],
         "Ordway Loss Control": ["Nate Kulas"]}
BROKER_PATTERNS = ["{s} Insurance", "{s} & {s2} Insurance", "{t} Insurance Group", "{s} Insurance Services",
                   "{s} Risk Partners", "{s} Brothers Insurance", "{t} Insurance Center", "{s}-{s2} Insurance Brokers",
                   "{s} Insurance Associates", "First {t} Insurance"]
BROKER_SURNAMES = ["Allgood", "Ambler", "Ashby", "Bascom", "Birkeland", "Boyce", "Brandt", "Cady",
                   "Coffman", "Dempsey", "Denning", "Doolittle", "Eberly", "Ellingson", "Farnam", "Fosdick",
                   "Gerlach", "Gilliland", "Hagen", "Hammill", "Hartigan", "Hoefer", "Huebner", "Jessen",
                   "Kramer", "Lahey", "Langford", "Loftus", "Mabry", "Marsden", "McAuliffe", "McNary", "Meisner",
                   "Moberg", "Neidig", "Oberle", "Oakes", "Pettit", "Prescott", "Rasch", "Redfield",
                   "Rigby", "Ruhl", "Sadler", "Schutt", "Seaver", "Stroud", "Tolan", "Truax", "Unruh",
                   "Vickery", "Wardell", "Whalen", "Winslow", "Wurtz", "Yoakum", "Zook"]
EVENT_WEIGHTS = {
    "restaurant": [("owner", 12), ("opened", 10), ("closed", 5), ("bar_added", 9), ("bar_dropped", 3),
                   ("music_started", 5), ("music_stopped", 2), ("moved", 7), ("sprinklers", 5), ("renovated", 6),
                   ("headcount", 14), ("renamed", 5), ("parent", 4), ("delivery", 6), ("catering", 5)],
    "bar": [("owner", 13), ("opened", 6), ("closed", 4), ("bar_added", 6), ("bar_dropped", 3),
            ("music_started", 10), ("music_stopped", 4), ("moved", 6), ("sprinklers", 4), ("renovated", 6),
            ("headcount", 13), ("renamed", 5), ("parent", 3), ("delivery", 2)],
    "caterer": [("owner", 10), ("opened", 6), ("moved", 9), ("sprinklers", 4), ("renovated", 6), ("headcount", 18),
                ("renamed", 4), ("parent", 4), ("bar_added", 4)],
    "producer": [("owner", 10), ("opened", 6), ("moved", 10), ("sprinklers", 6), ("renovated", 7),
                 ("headcount", 18), ("renamed", 4), ("parent", 6), ("catering", 3)],
}
STAFFING = {"restaurant": (8, 45), "bar": (5, 25), "caterer": (4, 30), "producer": (4, 35)}
GROUP_NAMES = ["{p} Hospitality Group", "{s} Restaurant Partners", "{p} Food Group", "{s} Brands LLC"]


def us_holidays(year: int) -> list[date]:
    def nth(month: int, weekday: int, n: int) -> date:
        first = date(year, month, 1)
        return first + timedelta(days=(weekday - first.weekday()) % 7 + 7 * (n - 1))

    def observed(day: date) -> date:
        return day - timedelta(days=1) if day.weekday() == 5 else day + timedelta(days=1) if day.weekday() == 6 else day

    last_may = date(year, 5, 31) - timedelta(days=(date(year, 5, 31).weekday()) % 7)
    thanksgiving = nth(11, 3, 4)
    fixed = [date(year, 1, 1), date(year, 6, 19), date(year, 7, 4), date(year, 11, 11), date(year, 12, 25)]
    return [observed(d) for d in fixed] + [nth(1, 0, 3), nth(2, 0, 3), last_may, nth(9, 0, 1), nth(10, 0, 2),
                                           thanksgiving, thanksgiving + timedelta(days=1)]


HOLIDAYS = frozenset(d for year in range(2020, 2029) for d in us_holidays(year))


def is_workday(day: date) -> bool:
    return day.weekday() < 5 and day not in HOLIDAYS


def on_or_after(day: date) -> date:
    while not is_workday(day):
        day += timedelta(days=1)
    return day


def on_or_before(day: date) -> date:
    while not is_workday(day):
        day -= timedelta(days=1)
    return day


def add_workdays(day: date, n: int) -> date:
    for _ in range(n):
        day = on_or_after(day + timedelta(days=1))
    return day


def pick(rng: random.Random, pairs: list) -> object:
    return rng.choices([p for p, _ in pairs], weights=[w for _, w in pairs])[0]


def between(rng: random.Random, start: date, end: date) -> date:
    return start + timedelta(days=rng.randint(0, max(0, (end - start).days)))


def workday_between(rng: random.Random, start: date, end: date) -> date:
    day = on_or_after(between(rng, start, end))
    return day if day <= end else on_or_before(end)


def stamp(rng: random.Random, day: date) -> str:
    return f"{day.isoformat()}T{rng.randint(8, 16):02d}:{rng.choice([2, 9, 15, 21, 33, 40, 47, 56]):02d}:00"


def short(day: date) -> str:
    return f"{day.month}/{day.day}"


def a_year_on(day: date) -> date:
    try:
        return day.replace(year=day.year + 1)
    except ValueError:
        return day.replace(year=day.year + 1, day=28)


def person(rng: random.Random) -> str:
    return f"{rng.choice(FIRST)} {rng.choice(LAST)}"


def street(rng: random.Random) -> str:
    return f"{rng.randint(10, 2900)} {rng.choice(STREETS)} {rng.choice(STREET_KINDS)}"


def dollars(n: int) -> str:
    return f"${n:,}"


@dataclass(frozen=True)
class Building:
    year: int
    construction: str
    sprinklered: bool
    owned: bool


@dataclass(frozen=True)
class Ops:
    cooking: str
    liquor: int
    music: str | None
    delivery: bool
    offsite: bool


@dataclass(frozen=True)
class Snapshot:
    dba: str
    sites: tuple[str, ...]
    owner: str
    headcount: int
    ops: Ops
    building: Building
    parent: str | None
    change: tuple[date, str] | None = None


@dataclass(frozen=True)
class Event:
    day: date
    kind: str
    before: object
    after: object
    text: str


@dataclass
class Business:
    legal: str
    cls: str
    us_state: str
    town: str
    zip_code: str
    founded: int
    history: list[tuple[date, Snapshot]]
    events: list[Event] = field(default_factory=list)

    @property
    def kind(self) -> str:
        return KIND_OF[self.cls]

    def at(self, day: date) -> Snapshot:
        snap = self.history[0][1]
        for start, s in self.history:
            if start <= day:
                snap = s
        return snap

    def address(self, day: date) -> str:
        return f"{self.at(day).sites[0]}, {self.town}, {self.us_state} {self.zip_code}"

    def events_between(self, after: date, until: date) -> list[Event]:
        return [e for e in self.events if after < e.day <= until]


@dataclass
class Claim:
    loss: date
    reported: date
    kind: str
    paid: int
    reserve: int
    status: str


@dataclass
class Policy:
    biz: Business
    brokerage: int
    carrier: str
    effective: date
    premium: int
    limits: str
    prior: "Policy | None" = None
    submission: "Submission | None" = None
    let_go: bool = False
    cancelled_on: date | None = None
    claims: list[Claim] = field(default_factory=list)

    @property
    def expires(self) -> date:
        return a_year_on(self.effective)

    def chain(self) -> list["Policy"]:
        terms, p = [], self
        while p is not None:
            terms.append(p)
            p = p.prior
        return terms


@dataclass
class Submission:
    biz: Business
    received: date
    brokerage: int
    broker: str
    entered_by: int
    renewal_of: Policy | None
    tiv: int
    limits: str
    expiring_premium: int
    prior_claims: int
    contacts: list[tuple[str, str, date, int, str]] = field(default_factory=list)
    facts: list[tuple[str, str, date, int, str]] = field(default_factory=list)
    notes: list[tuple[str, int, str]] = field(default_factory=list)
    decisions: list[tuple[str, int, str, int | None, int | None, str | None]] = field(default_factory=list)


@dataclass
class Brokerage:
    name: str
    town: str
    us_state: str
    appointed: date
    active: bool
    weight: int
    producers: list[str]


class World:
    """Name pools and the book shared across the simulation."""

    def __init__(self, rng: random.Random):
        self.rng = rng
        self.roots = {"s": list(dict.fromkeys(LAST + BUSINESS_SURNAMES)), "p": PLACES + PLACES_MORE,
                      "n": NOUNS + NOUNS_MORE}
        for pool in self.roots.values():
            rng.shuffle(pool)
        self.initials: set[str] = set()
        self.used: dict[str, int] = {}
        self.groups = [self.name(GROUP_NAMES) for _ in range(18)]
        self.brokerages: list[Brokerage] = []
        self.policies: list[Policy] = []
        self.submissions: list[Submission] = []

    def phrase(self, make) -> str:
        """Calls make() until it gives a text used at most once before, so no body appears more than twice."""
        for _ in range(8):
            text = make()
            if self.used.get(text, 0) < 2:
                break
        self.used[text] = self.used.get(text, 0) + 1
        return text

    def name(self, patterns: list[str]) -> str:
        """A business name from one of `patterns`, built on a surname, place or noun no other business uses."""
        for pattern in self.rng.sample(patterns, len(patterns)):
            key = next(k for k in self.roots if "{" + k + "}" in pattern)
            if self.roots[key]:
                return pattern.format(**{key: self.roots[key].pop()})
        raise RuntimeError("the business name pools ran out")

    def legal_name(self) -> str:
        """An initials-based company name; no two businesses share the initials."""
        while True:
            initials = "".join(self.rng.choice(INITIALS) for _ in range(self.rng.choice([2, 2, 3])))
            if initials not in self.initials:
                self.initials.add(initials)
                return f"{initials} {self.rng.choice(LEGAL_SUFFIXES)}"


def make_brokerages(rng: random.Random, world: World) -> None:
    used: set[str] = set()
    states = [s for s, _ in STATE_WEIGHTS]
    while len(world.brokerages) < 120:
        us_state = pick(rng, STATE_WEIGHTS) if rng.random() < 0.8 else rng.choice(states)
        town, _ = rng.choice(TOWNS[us_state])
        s, s2 = rng.sample(BROKER_SURNAMES, 2)
        name = rng.choice(BROKER_PATTERNS).format(s=s, s2=s2, t=town)
        if name in used:
            continue
        used.add(name)
        early = rng.random() < 0.62
        appointed = (workday_between(rng, date(2022, 8, 1), BOOK_START) if early
                     else workday_between(rng, BOOK_START, date(2025, 8, 29)))
        world.brokerages.append(Brokerage(name, town, us_state, appointed, True,
                                          rng.choice([1, 1, 1, 1, 1, 2, 2, 3, 5, 8, 12]),
                                          [person(rng) for _ in range(rng.choice([1, 1, 2, 2, 3]))]))
    for b in rng.sample([b for b in world.brokerages if b.appointed < date(2023, 6, 1)], 8):
        b.active = False
    world.brokerages.sort(key=lambda b: (b.appointed, b.name))


def choose_brokerage(rng: random.Random, world: World, day: date) -> int:
    open_to = [(i, b) for i, b in enumerate(world.brokerages, start=1)
               if b.appointed <= day and (b.active or day < date(2024, 6, 1))]
    return rng.choices([i for i, _ in open_to], weights=[b.weight for _, b in open_to])[0]


def new_business(rng: random.Random, world: World, first_seen: date) -> Business:
    cls = pick(rng, [(c, w) for c, _, w in CLASSES])
    kind = KIND_OF[cls]
    us_state = pick(rng, STATE_WEIGHTS)
    town, zip_code = rng.choice(TOWNS[us_state])
    sites = rng.choice([1, 1, 1, 1, 1, 2, 2, 3]) if kind != "producer" else rng.choice([1, 1, 1, 2])
    liquor = {"restaurant": rng.choice([0, 0, 0, 8, 12, 15, 20, 25, 30]),
              "bar": rng.choice([30, 35, 40, 45, 50, 55, 60]),
              "caterer": rng.choice([0, 0, 5, 10])}.get(kind, 0)
    music = rng.choice(MUSIC_NIGHTS) if kind == "bar" and rng.random() < 0.35 else None
    year = rng.choice([rng.randint(1890, 1949), rng.randint(1950, 1989), rng.randint(1990, 2019)])
    construction = pick(rng, CONSTRUCTION)
    if construction in ("masonry noncombustible", "metal building") and year < 1955:
        year = rng.randint(1955, 2019)
    building = Building(year, construction, rng.random() < (0.55 if year >= 1990 else 0.2), rng.random() < 0.35)
    low, high = STAFFING[kind]
    pair = rng.sample(FIRST, 2)
    owner = rng.choice([person(rng), person(rng), f"{pair[0]} and {pair[1]} {rng.choice(LAST)}"])
    snap = Snapshot(
        dba=world.name(TRADE_NAMES[cls]),
        sites=tuple(street(rng) for _ in range(sites)),
        owner=owner,
        headcount=rng.randint(low, high) * sites if sites < 3 else rng.randint(low, high) * 2,
        ops=Ops(rng.choice(COOKING[cls]), liquor, music, kind == "restaurant" and rng.random() < 0.25,
                kind in ("restaurant", "caterer") and (kind == "caterer" or rng.random() < 0.15)),
        building=building,
        parent=rng.choice(world.groups) if rng.random() < 0.08 else None,
    )
    founded = rng.randint(1978, first_seen.year - 1)
    biz = Business(world.legal_name(), cls, us_state, town, zip_code, founded,
                   history=[(HISTORY_START, snap)])
    count = rng.choices([0, 1, 2, 3, 4, 5, 6], weights=[1, 4, 8, 12, 12, 9, 6])[0]
    for day in sorted(between(rng, HISTORY_START + timedelta(days=60), SEED_END) for _ in range(count)):
        apply_event(rng, world, biz, day, pick(rng, EVENT_WEIGHTS[kind]))
    return biz


def apply_event(rng: random.Random, world: World, biz: Business, day: date, kind: str) -> None:
    snap = biz.history[-1][1]
    ops, building = snap.ops, snap.building
    if kind in ("renamed", "moved", "owner") and any(e.kind == kind and (day - e.day).days < 400 for e in biz.events):
        kind = "renovated"
    if kind == "closed" and len(snap.sites) < 2:
        kind = "headcount"
    if (kind == "bar_added" and ops.liquor >= 45) or (kind == "bar_dropped" and ops.liquor == 0):
        kind = "headcount"
    if (kind == "music_started" and ops.music) or (kind == "music_stopped" and not ops.music):
        kind = "renovated"
    if (kind == "sprinklers" and building.sprinklered) or (kind == "parent" and snap.parent):
        kind = "headcount"
    if (kind == "delivery" and ops.delivery) or (kind == "catering" and ops.offsite):
        kind = "renovated"
    before = after = None
    if kind == "owner":
        before, after = snap.owner, person(rng)
        snap, text = replace(snap, owner=after), f"{after} bought the business from {before}"
    elif kind == "opened":
        after = street(rng)
        snap = replace(snap, sites=snap.sites + (after,), headcount=snap.headcount + rng.randint(5, 18))
        noun = "production space" if biz.kind == "producer" else "location"
        text = f"Opened a second {noun} at {after}" if len(snap.sites) == 2 else f"Opened another {noun} at {after}"
    elif kind == "closed":
        after = snap.sites[-1]
        snap = replace(snap, sites=snap.sites[:-1], headcount=max(4, snap.headcount - rng.randint(4, 12)))
        text = f"Closed the {after} location"
    elif kind == "bar_added":
        before, after = ops.liquor, min(60, ops.liquor + rng.choice([15, 20, 25]))
        snap = replace(snap, ops=replace(ops, liquor=after))
        text = "Added a full bar" if before == 0 else f"Expanded the bar; liquor up to about {after}% of sales"
    elif kind == "bar_dropped":
        before, after = ops.liquor, 0 if biz.kind != "bar" else max(20, ops.liquor - 20)
        snap = replace(snap, ops=replace(ops, liquor=after))
        text = "Stopped serving liquor" if after == 0 else f"Cut the bar back; liquor down to about {after}% of sales"
    elif kind == "music_started":
        after = rng.choice(MUSIC_NIGHTS)
        snap, text = replace(snap, ops=replace(ops, music=after)), f"Started live music {after}"
    elif kind == "music_stopped":
        before = ops.music
        snap, text = replace(snap, ops=replace(ops, music=None)), "Stopped the live music"
    elif kind == "moved":
        before, after = snap.sites[0], street(rng)
        year = rng.randint(1955, 2021)
        new_building = Building(year, pick(rng, CONSTRUCTION), rng.random() < (0.6 if year >= 1990 else 0.25),
                                rng.random() < 0.3)
        snap = replace(snap, sites=(after,) + snap.sites[1:], building=new_building)
        text = f"Moved from {before} to {after}"
    elif kind == "sprinklers":
        snap = replace(snap, building=replace(building, sprinklered=True))
        text = "Put in a sprinkler system"
    elif kind == "headcount":
        before = snap.headcount
        ceiling = STAFFING[biz.kind][1] * len(snap.sites) + 10
        floor = STAFFING[biz.kind][0]
        after = min(ceiling, max(floor, round(before * rng.choice([0.6, 0.7, 0.8, 1.2, 1.3, 1.5]))))
        if after == before:
            after = before + 3
        snap = replace(snap, headcount=after)
        text = f"Cut back to about {after} staff" if after < before else f"Hired up to about {after} staff"
    elif kind == "renamed":
        before, after = snap.dba, world.name(TRADE_NAMES[biz.cls])
        snap, text = replace(snap, dba=after), f"Now trades as {after}"
    elif kind == "parent":
        after = rng.choice(world.groups)
        snap, text = replace(snap, parent=after), f"Bought by {after}"
    elif kind == "delivery":
        snap, text = replace(snap, ops=replace(ops, delivery=True)), "Started its own delivery"
    elif kind == "catering":
        snap, text = replace(snap, ops=replace(ops, offsite=True)), "Started catering off-site events"
    else:
        text = rng.choice(["Renovated the kitchen and replaced the hood", "Redid the dining room floor",
                           "Replaced the roof", "Added an outdoor patio", "Replaced the walk-in cooler",
                           "Rewired the kitchen"])
    biz.events.append(Event(day, kind, before, after, text))
    biz.history.append((day, replace(snap, change=(day, text))))


def total_insured_value(rng: random.Random, biz: Business, snap: Snapshot) -> int:
    value = sum(rng.randint(40, 260) * 1000 for _ in snap.sites)
    if snap.building.owned:
        value += rng.randint(800, 5600) * 1000 if biz.kind == "producer" else rng.randint(350, 1900) * 1000
    return round(value, -4)


def requested_limits(rng: random.Random, snap: Snapshot) -> str:
    gl = rng.choice(["$1M/$2M", "$1M/$2M", "$1M/$3M", "$500K/$1M"])
    forms = [f"GL {gl}", f"General liability {gl}"]
    text = rng.choice(forms)
    if snap.ops.liquor:
        text += rng.choice(["; liquor $1M", "; liquor liability $1M", "; liquor $500K"])
    if rng.random() < 0.3:
        text += "; hired and non-owned auto"
    return text


def premium_for(rng: random.Random, biz: Business, snap: Snapshot, tiv: int) -> int:
    base = {"restaurant": (2000, 5200), "bar": (3000, 7000), "caterer": (1800, 4500), "producer": (2200, 6500)}
    low, high = base[biz.kind]
    amount = rng.randint(low, high) * len(snap.sites) + snap.ops.liquor * rng.randint(60, 100)
    amount += tiv * rng.uniform(0.0028, 0.0048)
    if snap.ops.music:
        amount *= 1.15
    if snap.building.construction == "frame" and not snap.building.sprinklered:
        amount *= 1.2
    return int(round(amount, -1))


def fact_value(rng: random.Random, biz: Business, name: str, day: date) -> str:
    snap = biz.at(day)
    if name == "years_in_business":
        years = max(1, day.year - biz.founded)
        return rng.choice([f"{years} years", f"since {biz.founded}", f"opened in {biz.founded}"])
    if name == "owner":
        return snap.owner
    if name == "locations":
        n = len(snap.sites)
        if n == 1:
            return rng.choice(["1", f"One, {snap.sites[0]}", f"1, at {snap.sites[0]}"])
        return f"{n}: {', '.join(snap.sites)}"
    if name == "headcount":
        options = [f"about {snap.headcount}", str(snap.headcount)]
        if biz.kind in ("restaurant", "bar"):
            options.append(f"{snap.headcount}, about half part time")
        return rng.choice(options)
    if name == "operations":
        ops = snap.ops
        parts = [ops.cooking[0].upper() + ops.cooking[1:]]
        parts.append(f"liquor about {ops.liquor}% of sales" if ops.liquor else "no liquor")
        if ops.music:
            parts.append(f"live music {ops.music}")
        elif biz.kind == "bar":
            parts.append("no live entertainment")
        if ops.delivery:
            parts.append("own delivery")
        if ops.offsite:
            parts.append("off-site catering")
        return "; ".join(parts)
    if name == "building":
        b = snap.building
        spr = "sprinklered" if b.sprinklered else "not sprinklered"
        tenure = "owned" if b.owned else "leased"
        return rng.choice([f"{b.year}, {b.construction}, {spr}, {tenure}",
                           f"Built {b.year}; {b.construction}; {spr}",
                           f"{b.construction.capitalize()} from {b.year}, {spr}, {tenure}"])
    if name == "parent_company":
        return snap.parent or rng.choice(["None, independent", "None", "Independently owned"])
    if snap.change and (day - snap.change[0]).days <= 365:
        return snap.change[1]
    return rng.choice(["No changes in the last year", "None in the last year", "Nothing in the past year"])


# Each fact note: its text, the fields it fits, and what must exist by the day of the check.
FACT_NOTES = [
    ("on the application", ("years_in_business", "owner", "locations", "headcount", "operations", "building",
                            "parent_company"), "application"),
    ("inspection report, {month}", ("locations", "headcount", "operations", "building", "recent_change"),
     "inspection"),
    ("broker said on the call", ("owner", "locations", "headcount", "operations", "parent_company",
                                 "recent_change"), "call"),
    ("county assessor record", ("building",), None),
    ("their menu", ("operations",), "menu"),
    ("state liquor license record", ("owner",), "liquor"),
    ("Secretary of State filing", ("owner", "years_in_business", "parent_company"), None),
    ("fire marshal letter, {month}", ("building",), None),
    ("premium audit, {month}", ("headcount", "operations"), "audit"),
    ("from last year's file", ("years_in_business", "owner", "locations", "building", "parent_company"),
     "carried"),
    ("owner told me on the phone", ("owner", "locations", "headcount", "operations", "recent_change",
                                    "parent_company"), None),
    ("", ("years_in_business", "owner", "locations", "headcount", "operations", "building", "parent_company",
          "recent_change"), None),
]


def fact_note(rng: random.Random, sub: Submission, name: str, day: date) -> str:
    biz = sub.biz
    snap = biz.at(day)
    inspections = [c for c in sub.contacts if c[0] == "inspection" and c[2] <= day and biz.at(c[2]) is snap]
    calls = [c for c in sub.contacts if c[0] == "broker_call" and c[2] <= day and biz.at(c[2]) is snap]
    expiring = sub.renewal_of

    def available(needs: str | None) -> bool:
        if needs == "application":
            return sub.received <= day <= sub.received + timedelta(days=45) and biz.at(sub.received) is snap
        if needs == "inspection":
            return bool(inspections)
        if needs == "call":
            return bool(calls)
        if needs == "menu":
            return biz.kind in ("restaurant", "bar") and day >= sub.received
        if needs == "liquor":
            return snap.ops.liquor > 0
        if needs in ("audit", "carried"):
            return expiring is not None and expiring.effective + timedelta(days=60) <= day < sub.received
        return True

    text = rng.choice([t for t, fields, needs in FACT_NOTES if name in fields and available(needs)])
    if "{month}" not in text:
        return text
    if text.startswith("inspection"):
        when = inspections[-1][2]
    elif text.startswith("premium audit"):
        when = between(rng, expiring.effective + timedelta(days=30), day)
    else:
        when = between(rng, day - timedelta(days=150), day)
    return text.format(month=MONTHS[when.month - 1])


def remark(rng: random.Random, sub: Submission, day: date, voice: str, said: set) -> str | None:
    """One sentence about the business as it stands on `day`, in a broker's, an inspector's or the desk's words."""
    biz = sub.biz
    snap = biz.at(day)
    recent = [e for e in biz.events if timedelta(0) <= day - e.day <= timedelta(days=300)]
    text = None
    told = None
    if recent and rng.random() < 0.85:
        e = recent[-1] if rng.random() < 0.6 else rng.choice(recent)
        if e not in said:
            told, text = e, event_sentence(rng, biz, snap, e, voice)
    if text is None:
        text = state_sentence(rng, biz, snap, voice)
    if text is None or text in said:
        return None
    said.update(x for x in (text, told) if x is not None)
    return text


def event_sentence(rng: random.Random, biz: Business, snap: Snapshot, e: Event, voice: str) -> str | None:
    month = MONTHS[e.day.month - 1]
    who = {"broker": "Broker says", "inspector": "Per the manager,", "desk": "Endorsement request:"}[voice]
    if e.kind == "owner":
        return rng.choice([f"{who} {e.after} bought the place from {e.before} in {month}.",
                           f"New owner since {month}: {e.after}.",
                           f"{e.after} owns it now; {e.before} sold in {month}."])
    if e.kind == "opened":
        return rng.choice([f"{who} they opened {e.after} in {month}, {len(snap.sites)} locations now.",
                           f"They added {e.after} in {month}."])
    if e.kind == "closed":
        return rng.choice([f"{who} they closed {e.after} in {month}.",
                           f"The {e.after} location closed in {month}; down to {len(snap.sites)}."])
    if e.kind == "bar_added":
        return rng.choice([f"{who} they put in a bar in {month}; liquor runs about {e.after}% of sales.",
                           f"Liquor is about {e.after}% of sales since the bar went in ({month})."])
    if e.kind == "bar_dropped":
        if e.after == 0:
            return rng.choice([f"{who} they stopped serving liquor in {month}.", f"No liquor since {month}."])
        return f"Liquor is down to about {e.after}% of sales since {month}."
    if e.kind == "music_started":
        return rng.choice([f"{who} they have live music {e.after} since {month}.",
                           f"Bands {e.after}, started in {month}; small stage by the back wall."])
    if e.kind == "music_stopped":
        return rng.choice([f"{who} the live music ended in {month}.", f"No more bands since {month}."])
    if e.kind == "moved":
        b = snap.building
        spr = "sprinklered" if b.sprinklered else "no sprinklers"
        if voice == "inspector":
            return f"They moved to {e.after} in {month}: {b.construction}, built {b.year}, {spr}."
        return rng.choice([f"{who} they moved to {e.after} in {month}.",
                           f"New address since {month}: {e.after}, a {b.construction} building from {b.year}."])
    if e.kind == "sprinklers":
        return rng.choice([f"Sprinkler system went in during {month}.", f"{who} sprinklers were installed in {month}."])
    if e.kind == "headcount":
        return rng.choice([f"{who} they're at about {e.after} employees.", f"Payroll is about {e.after} people now."])
    if e.kind == "renamed":
        return rng.choice([f"{who} they trade as {e.after} since {month}.",
                           f"They go by {e.after} now, since {month}."])
    if e.kind == "parent":
        return rng.choice([f"{who} {e.after} bought them in {month}.",
                           f"Owned by {e.after} since {month}."])
    if e.kind == "delivery":
        return f"They started their own delivery in {month}, {rng.choice(['two', 'three'])} drivers."
    if e.kind == "catering":
        how_many = rng.choice(["a few", "two or three", "four or five"])
        return f"Off-site catering since {month}, {how_many} events a month."
    return f"{e.text} in {month}."


def state_sentence(rng: random.Random, biz: Business, snap: Snapshot, voice: str) -> str | None:
    topic = rng.choice(["owner", "sites", "headcount", "liquor", "building"])
    if topic == "owner":
        couple = " and " in snap.owner
        return rng.choice([f"{snap.owner} {'run' if couple else 'runs'} it day to day.",
                           f"Spoke with {snap.owner}, the {'owners' if couple else 'owner'}."])
    if topic == "sites":
        if len(snap.sites) == 1:
            return f"One location, {snap.sites[0]}."
        return f"{len(snap.sites)} locations: {', '.join(snap.sites)}."
    if topic == "headcount":
        return f"About {snap.headcount} on payroll."
    if topic == "liquor" and biz.kind in ("restaurant", "bar"):
        if snap.ops.liquor:
            return f"Liquor about {snap.ops.liquor}% of sales."
        return "No liquor served."
    if topic == "building" and voice != "broker":
        b = snap.building
        return f"{b.construction.capitalize()}, built {b.year}, {'sprinklered' if b.sprinklered else 'no sprinklers'}."
    return None


HAZARDS = [
    ("Back stairs to the basement have no handrail.", "handrail on the basement stairs"),
    ("Grease buildup on the wall behind the fryers.", "clean the wall and hood plenum behind the fryers"),
    ("Extension cord feeding the reach-in cooler.", "hard-wire the reach-in cooler"),
    ("Exit sign out by the restrooms.", "repair the exit sign by the restrooms"),
    ("Floor mats at the dish station are worn through.", "replace the dish station mats"),
    ("Walk-in cooler door gasket torn.", None),
    ("Pothole in the parking lot by the front door.", "patch the lot by the entrance"),
    ("Portable extinguisher by the line last tagged over a year ago.", "service the portable extinguishers"),
    ("Ice machine dripping onto the floor.", "fix the ice machine drain"),
    ("Storage stacked against the rear exit.", "keep the rear exit clear"),
    ("Patio pavers uneven near the gate.", "level the patio pavers"),
    ("Propane cylinders stored inside by the back door.", "move propane cylinders outside to a cage"),
    ("No K-class extinguisher at the fryers.", "add a K-class extinguisher at the fryers"),
]
CLAIM_REPLIES = ["it was a one-off", "the owner made changes after it", "it is still with the adjuster",
                 "nothing like it before or since"]
TIDY = ["Kitchen was clean and well kept.", "Good housekeeping throughout.", "Floors dry, aisles clear.",
        "Housekeeping fair.", "Neat operation."]


def inspection_findings(rng: random.Random, biz: Business, day: date, sub: Submission, said: set) -> str:
    snap = biz.at(day)
    b, ops = snap.building, snap.ops
    contact = rng.choice([snap.owner.split(" and ")[0], person(rng)])
    role = "owner" if contact in snap.owner else rng.choice(["GM", "kitchen manager", "manager"])
    parts = [rng.choice([f"Walked it with {contact}, the {role}.", f"Met {contact} ({role}) at {snap.sites[0]}.",
                         f"{contact}, the {role}, showed us around.", "", "", ""])]
    spr = rng.choice(["fully sprinklered", "sprinklered throughout", "wet system throughout"]) if b.sprinklered \
        else rng.choice(["no sprinklers", "not sprinklered", "no sprinkler system"])
    parts.append(rng.choice([f"{b.construction.capitalize()}, built {b.year}, {spr}.",
                             f"Building is {b.construction} from {b.year}; {spr}.",
                             f"{rng.choice(['One', 'Two'])}-story {b.construction} ({b.year}), {spr}."]))
    parts.append(f"Cooking: {ops.cooking}.")
    if biz.kind != "producer" and rng.random() < 0.6:
        hood_month = MONTHS[(day - timedelta(days=rng.randint(20, 200))).month - 1]
        parts.append(rng.choice([f"Hood and duct cleaned in {hood_month} per the tag.",
                                 f"Wet chemical system tagged {hood_month}.",
                                 f"Hood cleaning sticker from {hood_month}."]))
    if ops.liquor:
        parts.append(rng.choice([f"Bar seats {rng.randint(8, 30)}; liquor about {ops.liquor}% of sales per the {role}.",
                                 f"Liquor near {ops.liquor}% of sales.",
                                 f"Full bar, about {ops.liquor}% of sales."]))
    elif biz.kind in ("restaurant", "bar"):
        parts.append(rng.choice(["No alcohol.", "No liquor served.", ""]))
    if ops.music:
        parts.append(rng.choice([f"Live music {ops.music}.",
                                 f"Bands {ops.music}; capacity sign says {rng.randint(60, 220)}."]))
    if ops.offsite:
        parts.append("Does off-site catering.")
    if len(snap.sites) > 1:
        others = ", ".join(snap.sites[1:])
        parts.append(rng.choice([f"Saw {snap.sites[0]} only; did not visit {others}.",
                                 f"Visited {snap.sites[0]}; {others} not seen."]))
    if rng.random() < 0.4:
        extra = remark(rng, sub, day, "inspector", said)
        if extra:
            parts.append(extra)
    hazards = HAZARDS if has_fryers(ops.cooking) else [h for h in HAZARDS if "fryer" not in h[0]]
    found = rng.sample(hazards, rng.choice([0, 1, 1, 2]))
    parts.extend(h for h, _ in found)
    recs = [r for _, r in found if r]
    if not found:
        parts.append(rng.choice(TIDY))
    if recs:
        parts.append(f"Recs: {'; '.join(recs)}.")
    return " ".join(p for p in parts if p)


def call_findings(rng: random.Random, sub: Submission, day: date, first: bool, said: set) -> str:
    biz, snap = sub.biz, sub.biz.at(day)
    renewal = sub.renewal_of
    parts = [rng.choice(["", "", f"{sub.broker.split()[0]} called back.", "Left a message; returned that afternoon.",
                         "Short call."])]
    pool = []
    if renewal is None:
        pool += [f"Expiring premium is {dollars(sub.expiring_premium)} with another market.",
                 f"Wants a quote by {short(add_workdays(day, rng.randint(5, 15)))}.",
                 f"Prior carrier shows {['no claims', 'one claim', 'two claims'][sub.prior_claims]} in three years.",
                 f"Owner would take a {dollars(rng.choice([1000, 2500, 5000]))} deductible to keep the price down.",
                 "Broker is showing it to two other markets.",
                 "Asked for the menu and the last hood cleaning invoice.",
                 f"They have been with the same carrier since {rng.randint(2015, 2023)}."]
    else:
        pool += [f"Renewal is due {short(renewal.expires)}; same limits.",
                 "Broker asked if we can hold the premium flat.",
                 "Insured wants to lower the deductible.",
                 "Broker will send updated sales and payroll figures."]
        reported = [c for c in renewal.claims if c.reported <= day]
        if reported:
            pool.append(f"Asked about the {reported[-1].kind.replace('_', ' ')} claim from "
                        f"{MONTHS[reported[-1].loss.month - 1]}; broker says {rng.choice(CLAIM_REPLIES)}.")
        if not biz.events_between(renewal.effective, day):
            pool.append("Broker says nothing has changed since last year.")
    if snap.ops.liquor:
        pool.append(rng.choice(["Owner will sign the liquor supplement.", "Needs liquor at $1M for the license."]))
    if biz.kind in ("restaurant", "caterer"):
        pool.append(f"Off-site catering: {'yes, a few events a month' if snap.ops.offsite else 'none'}.")
    parts += rng.sample(pool, rng.choice([1, 1, 2]))
    if rng.random() < (0.6 if first else 0.75):
        extra = remark(rng, sub, day, "broker", said)
        if extra:
            parts.append(extra)
    return " ".join(p for p in parts if p)


MENU_NOTES = ["heavy on fried items", "mostly grill and sandwiches", "short bar menu", "family style",
              "lots of smoked meats", "pizza and wings", "small plates", "breakfast all day", "a fish fry on Fridays"]


def working_note(rng: random.Random, sub: Submission, day: date) -> str:
    snap, broker = sub.biz.at(day), sub.broker.split()[0]
    options = [f"Waiting on the property schedule from {broker}.",
               f"App is missing the year built; asked {broker}.",
               f"Sales figures in: about {dollars(rng.randint(4, 30) * 100_000 * len(snap.sites))} last year."]
    if sub.biz.kind != "producer":
        options += [f"Photos of the kitchen came in from {broker}.",
                    f"Hood cleaning invoice dated {short(day - timedelta(days=rng.randint(15, 120)))} came in."]
    if sub.renewal_of is None:
        claims = sub.prior_claims
        options.append("Loss runs came in: no claims in three years." if not claims else
                       f"Loss runs came in: {claims} claim(s) in three years, "
                       f"{dollars(rng.randint(8, 400) * 100)} paid.")
    if snap.ops.liquor:
        options.append(f"Asked {broker} for the signed liquor supplement.")
    if sub.biz.kind in ("restaurant", "bar"):
        options.append(f"Menu came in: {', '.join(rng.sample(MENU_NOTES, 2))}.")
    ahead = [c for c in sub.contacts if c[0] == "inspection" and c[2] > day]
    if ahead:
        options.append(f"Ordered an inspection from {ahead[0][1].split(', ', 1)[1]} for {short(ahead[0][2])}.")
    return rng.choice(options)


def bound_note(rng: random.Random, sub: Submission, day: date) -> str:
    broker, dba = sub.broker.split()[0], sub.biz.at(day).dba
    landlord = f"{rng.choice(LAST)} Properties LLC"
    return rng.choice([f"Certificate of insurance sent to the landlord, {landlord}.",
                       f"Added {landlord} as additional insured at {broker}'s request.",
                       f"Sent the premium audit form to {broker}; due back {short(add_workdays(day, 15))}.",
                       f"{broker} asked for a copy of the declarations page for {dba}.",
                       f"{broker} sent a mailing address change for {dba}."])


def not_taken_note(rng: random.Random, sub: Submission, premium: int, quoted_on: date) -> str:
    broker = sub.broker.split()[0]
    owner = sub.biz.at(quoted_on).owner.split()[0]
    lower = dollars(int(round(premium * rng.uniform(0.75, 0.95), -1)))
    return rng.choice([f"{broker} says they went with another market at {lower}.",
                       f"No word from {broker} since the quote on {short(quoted_on)}; marking it not taken.",
                       f"{broker} says {owner} stayed with the expiring carrier at {lower}.",
                       f"{broker} says {owner} decided not to move it this year.",
                       f"{broker} says {dollars(premium)} was too high; they wanted something near {lower}."])


def senior_decline_note(rng: random.Random, sub: Submission, snap: Snapshot, premium: int) -> str:
    options = [f"Declined after review. Not comfortable writing {dollars(sub.tiv)} of value for {dollars(premium)}."]
    if snap.ops.liquor:
        options.append(f"Not at {dollars(premium)} with liquor near {snap.ops.liquor}% of sales. Declined.")
    if not snap.building.sprinklered:
        options.append(f"Too much value ({dollars(sub.tiv)}) in a {snap.building.construction} building without "
                       "sprinklers. Declined.")
    return rng.choice(options)


def claims_known(sub: Submission, day: date) -> list[Claim]:
    return [c for p in sub.renewal_of.chain() for c in p.claims if c.reported <= day] if sub.renewal_of else []


def decline_reason(rng: random.Random, sub: Submission, day: date) -> str | None:
    biz, snap = sub.biz, sub.biz.at(day)
    reasons = []
    bands = snap.ops.music and snap.ops.liquor >= 35 and rng.random() < 0.6
    if snap.ops.liquor >= 50:
        reasons.append(f"Liquor is about {snap.ops.liquor}% of sales{' with live music' if bands else ''}.")
    elif bands:
        reasons.append(f"Live music with liquor near {snap.ops.liquor}% of sales.")
    b = snap.building
    if b.construction == "frame" and not b.sprinklered and b.year < 1950:
        reasons.append(f"Frame building from {b.year} with no sprinklers.")
    known = claims_known(sub, day)
    incurred = sum(c.paid + c.reserve for c in known)
    if len(known) >= 2 or any(c.kind == "liquor_liability" for c in known):
        reasons.append(f"{len(known)} claim(s) across the terms we wrote, {dollars(incurred)} incurred.")
    if biz.kind == "bar" and biz.founded >= day.year - 1:
        reasons.append("Bar open less than two years.")
    if not reasons and rng.random() < 0.09:
        reasons.append(rng.choice(["Broker could not get loss runs from the prior carrier.",
                                   f"Hood and duct cleaning records only go back to {MONTHS[day.month - 1]}.",
                                   "Owner would not sign the liquor supplement."
                                   if snap.ops.liquor else "Could not get a signed application."]))
    if not reasons or (len(reasons) == 1 and "Live music" in reasons[0] and rng.random() < 0.5):
        return None
    return " ".join(reasons)


def quote_terms(rng: random.Random, snap: Snapshot, sub: Submission) -> str | None:
    options = []
    if snap.ops.liquor:
        options.append(rng.choice(["Liquor liability $1M sublimit", "Assault and battery sublimit $100,000"]))
    if snap.building.sprinklered:
        options.append("Protective safeguards endorsement (sprinklers)")
    if any(c[0] == "inspection" for c in sub.contacts):
        options.append("Inspection recommendations complete within 60 days")
    if sub.biz.kind != "producer":
        options.append("Hood and duct cleaning every six months")
    if snap.ops.offsite:
        options.append("Off-site catering limited to $250,000 in annual sales")
    if not options or rng.random() < 0.2:
        return None
    return "; ".join(rng.sample(options, rng.randint(1, min(3, len(options)))))


def work_submission(rng: random.Random, world: World, sub: Submission) -> Policy | None:
    """Plays one submission from receipt to its outcome or to the end of the seed year; returns a bound policy."""
    biz, u = sub.biz, sub.entered_by
    said: set = set()
    renewal = sub.renewal_of
    deadline = on_or_before(renewal.expires - timedelta(days=1)) if renewal else None

    def desk_day(after: date, low: int, high: int) -> date:
        day = add_workdays(after, rng.randint(low, high))
        return min(day, deadline) if deadline and deadline > after else day

    planned: list[tuple[str, date]] = []
    day = sub.received
    for _ in range(rng.choice([1, 1, 1, 2])):
        day = desk_day(day, 1, 4 if renewal else 6)
        planned.append(("broker_call", day))
    if rng.random() < (0.35 if renewal else 0.6):
        planned.append(("inspection", desk_day(sub.received, 4, 12 if renewal else 20)))
    planned.sort(key=lambda p: p[1])
    for kind, when in planned:
        if when > SEED_END:
            continue
        by = u if rng.random() < 0.9 else rng.choice(UNDERWRITERS)
        if kind == "inspection":
            firm = rng.choice(list(FIRMS))
            text = world.phrase(lambda: inspection_findings(rng, biz, when, sub, said))
            sub.contacts.append((kind, f"{rng.choice(FIRMS[firm])}, {firm}", when, by, text))
        else:
            first = not any(c[0] == "broker_call" for c in sub.contacts)
            sub.contacts.append((kind, f"{sub.broker}, {world.brokerages[sub.brokerage - 1].name}", when, by,
                                 world.phrase(lambda: call_findings(rng, sub, when, first, said))))
    decided = desk_day(max(w for _, w in planned), 1, 5)
    review_end = min(SEED_END, decided - timedelta(days=1))

    fields = ["years_in_business", "owner", "locations", "headcount", "operations", "building", "parent_company",
              "recent_change"]
    carried_from = max(FACT_EARLIEST, renewal.effective + timedelta(days=60)) if renewal else None
    carried_to = sub.received - timedelta(days=10)
    for name in sorted(rng.sample(fields, rng.randint(2, 5)), key=fields.index):
        if carried_from and carried_from < carried_to and rng.random() < 0.7:
            checked = workday_between(rng, carried_from, carried_to)
        elif rng.random() < 0.55 or review_end <= sub.received:
            checked = min(add_workdays(sub.received, rng.choice([0, 0, 1, 2])), SEED_END)
        else:
            checked = workday_between(rng, sub.received, review_end)
        sub.facts.append((name, fact_value(rng, biz, name, checked), checked, u, fact_note(rng, sub, name, checked)))
    first = sub.facts[0]
    if rng.random() < 0.08 and len(sub.facts) < 5 and first[2] + timedelta(days=30) < SEED_END:
        later = workday_between(rng, first[2] + timedelta(days=30), min(SEED_END, first[2] + timedelta(days=200)))
        sub.facts.append((first[0], fact_value(rng, biz, first[0], later), later, u,
                          fact_note(rng, sub, first[0], later)))

    for _ in range(rng.choice([0, 0, 1])):
        when = workday_between(rng, sub.received, max(sub.received, review_end))
        if when <= SEED_END:
            sub.notes.append((stamp(rng, when), u, world.phrase(lambda: working_note(rng, sub, when))))

    if decided > SEED_END:
        return None
    snap = biz.at(decided)
    reason = decline_reason(rng, sub, decided)
    if reason:
        sub.decisions.append((stamp(rng, decided), u, "decline", None, None, None))
        sub.notes.append((sub.decisions[-1][0], u, world.phrase(
            lambda: rng.choice(["Declined. ", "Declining. ", "Passing on this one. ", "Decline: ", ""]) + reason)))
        return None
    if renewal:
        premium = int(round(renewal.premium * rng.uniform(0.97, 1.12) * (1.1 if claims_known(sub, decided) else 1), -1))
    else:
        premium = premium_for(rng, biz, snap, sub.tiv)
    deductible = rng.choice([1000, 1000, 2500, 2500, 5000] if sub.tiv < 2_000_000 else [5000, 10000])
    if renewal and rng.random() < 0.3:
        deductible = rng.choice([500, 1000])
    terms = quote_terms(rng, snap, sub)
    at = stamp(rng, decided)
    sub.decisions.append((at, u, "quote", premium, deductible, terms))
    quoted_on = decided
    if premium > PREMIUM_AUTHORITY or sub.tiv > VALUE_AUTHORITY:
        senior = rng.choice([s for s in SENIORS if s != u])
        why = (f"premium over {dollars(PREMIUM_AUTHORITY)}" if premium > PREMIUM_AUTHORITY
               else f"TIV is {dollars(sub.tiv)}")
        sub.notes.append((at, u, world.phrase(lambda: rng.choice([
            f"Quoted {dollars(premium)} with a {dollars(deductible)} deductible; {why}, referred to "
            f"{FIRST_NAMES[senior]}.",
            f"Referring to {FIRST_NAMES[senior]}: {why}. Quote is {dollars(premium)}, {dollars(deductible)} "
            "deductible."]))))
        quoted_on = desk_day(decided, 1, 7)
        if quoted_on > SEED_END:
            return None
        at = stamp(rng, quoted_on)
        if rng.random() < 0.15:
            sub.decisions.append((at, senior, "decline", None, None, None))
            sub.notes.append((at, senior, world.phrase(
                lambda: senior_decline_note(rng, sub, biz.at(quoted_on), premium))))
            return None
        sub.decisions.append((at, senior, "confirm", premium, deductible, terms))
        sub.notes.append((at, senior, world.phrase(lambda: rng.choice([
            f"Confirmed at {dollars(premium)}.", f"OK to release the quote at {dollars(premium)}.",
            f"Read the file; fine at {dollars(premium)} with the {dollars(deductible)} deductible. Confirmed."]))))
    else:
        reason_bits = ["", "", " Good operator."]
        if any(c[0] == "inspection" for c in sub.contacts):
            reason_bits.append(" Inspection was fine apart from the recs.")
        if has_fryers(snap.ops.cooking):
            reason_bits.append(" Priced up for the fryers.")
        if (not claims_known(sub, decided)) if renewal else sub.prior_claims == 0:
            reason_bits.append(" Loss free three years.")
        sub.notes.append((at, u, world.phrase(lambda: rng.choice([
            f"Quoted {dollars(premium)}, {dollars(deductible)} deductible.",
            f"Quote out at {dollars(premium)} with a {dollars(deductible)} deductible.",
            f"Sent the quote: {dollars(premium)}, {dollars(deductible)} ded."]) + rng.choice(reason_bits))))
    answer = desk_day(quoted_on, 3, 12 if renewal else 25)
    if answer > SEED_END:
        return None
    recorder = u if rng.random() < 0.8 else rng.choice(UNDERWRITERS)
    at = stamp(rng, answer)
    if rng.random() >= (0.84 if renewal else 0.42) or (renewal and answer >= renewal.expires):
        sub.decisions.append((at, recorder, "not_taken", None, None, None))
        sub.notes.append((at, recorder, world.phrase(lambda: not_taken_note(rng, sub, premium, quoted_on))))
        if renewal:
            renewal.let_go = True
        return None
    if renewal:
        effective, carrier = renewal.expires, renewal.carrier if rng.random() < 0.9 else rng.choice(CARRIERS)
    else:
        effective, carrier = answer + timedelta(days=rng.randint(0, 20)), rng.choice(CARRIERS)
    sub.decisions.append((at, recorder, "bind", premium, deductible, terms))
    sub.notes.append((at, recorder, f"Bound effective {short(effective)} on {CARRIER_SHORT[carrier]} paper at "
                                    f"{dollars(premium)}."))
    policy = Policy(biz, sub.brokerage, carrier, effective, premium, sub.limits, prior=renewal, submission=sub)
    for e in biz.events_between(effective, SEED_END):
        when = add_workdays(e.day, rng.randint(3, 30))
        if when <= SEED_END and rng.random() < 0.7 and e not in said:
            said.add(e)
            sub.notes.append((stamp(rng, when), u, event_sentence(rng, biz, biz.at(when), e, "desk")))
    later_start = max(answer, effective) + timedelta(days=20)
    for _ in range(rng.choice([0, 0, 1])):
        if later_start < SEED_END:
            when = workday_between(rng, later_start, SEED_END)
            sub.notes.append((stamp(rng, when), u, world.phrase(lambda: bound_note(rng, sub, when))))
    return policy


def open_submission(rng: random.Random, world: World, biz: Business, received: date, brokerage: int,
                    renewal: Policy | None) -> Submission:
    snap = biz.at(received)
    tiv = total_insured_value(rng, biz, snap)
    sub = Submission(biz, received, brokerage, rng.choice(world.brokerages[brokerage - 1].producers),
                     pick(rng, DESK_WEIGHTS), renewal, tiv,
                     renewal.limits if renewal and rng.random() < 0.8 else requested_limits(rng, snap),
                     int(round(premium_for(rng, biz, snap, tiv) * rng.uniform(0.8, 1.15), -2)),
                     rng.choice([0, 0, 0, 1, 1, 2]))
    world.submissions.append(sub)
    return sub


def write_policy(rng: random.Random, world: World, biz: Business, brokerage: int, effective: date,
                 prior: Policy | None) -> Policy:
    snap = biz.at(effective)
    premium = premium_for(rng, biz, snap, total_insured_value(rng, biz, snap))
    if prior:
        premium = int(round(prior.premium * rng.uniform(0.96, 1.1), -1))
    carrier = prior.carrier if prior and rng.random() < 0.9 else rng.choice(CARRIERS)
    limits = prior.limits if prior else requested_limits(rng, snap)
    return Policy(biz, brokerage, carrier, effective, premium, limits, prior=prior)


def settle_term(rng: random.Random, policy: Policy) -> Policy:
    """Decides whether the term is cancelled and draws its claims."""
    if rng.random() < 0.035:
        cancel = between(rng, policy.effective + timedelta(days=30), policy.expires - timedelta(days=10))
        if cancel <= SEED_END:
            policy.cancelled_on = cancel
    add_claims(rng, policy)
    return policy


def add_claims(rng: random.Random, policy: Policy) -> None:
    snap = policy.biz.at(policy.effective)
    rate = 0.17 + (0.07 if policy.biz.kind == "bar" else 0) + snap.ops.liquor / 1000 + (0.04 if snap.ops.music else 0)
    end = min(policy.expires, policy.cancelled_on or policy.expires, SEED_END)
    kinds = [("slip_and_fall", 45), ("spoilage", 15), ("theft", 13)]
    if any(word in snap.ops.cooking for word in HOT_WORK):
        kinds.append(("kitchen_fire", 14))
    if snap.ops.liquor:
        kinds.append(("liquor_liability", 6 + snap.ops.liquor // 5))
    ranges = {"slip_and_fall": (1500, 60000), "spoilage": (800, 14000), "theft": (900, 18000),
              "kitchen_fire": (4000, 160000), "liquor_liability": (12000, 210000)}
    while rng.random() < rate and len(policy.claims) < 3 and end > policy.effective:
        kind = pick(rng, kinds)
        loss = between(rng, policy.effective, end - timedelta(days=1))
        lag = rng.randint(0, 6) if kind in ("spoilage", "theft", "kitchen_fire") else rng.randint(1, 90)
        reported = on_or_after(loss + timedelta(days=lag))
        if reported > SEED_END:
            continue
        low, high = ranges[kind]
        incurred = int(round(rng.uniform(low, high), -1))
        age = (SEED_END - reported).days
        settled = age > (90 if kind in ("spoilage", "theft") else 300) and rng.random() < 0.9
        if settled:
            paid = 0 if rng.random() < 0.1 else incurred
            policy.claims.append(Claim(loss, reported, kind, paid, 0, "closed"))
        else:
            paid = int(round(incurred * rng.uniform(0, 0.5), -1)) if age > 30 else 0
            policy.claims.append(Claim(loss, reported, kind, paid, incurred - paid, "open"))
        rate *= 0.5
    policy.claims.sort(key=lambda c: (c.loss, c.kind))


def simulate(rng: random.Random) -> World:
    world = World(rng)
    make_brokerages(rng, world)
    day = BOOK_START
    while day <= SEED_END:
        if is_workday(day):
            pre = day < YEAR_START
            if rng.random() < NEW_BUSINESS_RATE["before" if pre else "year"]:
                biz = new_business(rng, world, day)
                brokerage = choose_brokerage(rng, world, day)
                if pre:
                    effective = day + timedelta(days=rng.randint(0, 20))
                    world.policies.append(settle_term(rng, write_policy(rng, world, biz, brokerage, effective, None)))
                else:
                    bound = work_submission(rng, world, open_submission(rng, world, biz, day, brokerage, None))
                    if bound:
                        world.policies.append(settle_term(rng, bound))
        day += timedelta(days=1)
    renew_book(rng, world)
    return world


def renew_book(rng: random.Random, world: World) -> None:
    """Walks every policy to its expiry in date order, writing renewal terms and renewal submissions."""
    queue = sorted(world.policies, key=lambda p: (p.expires, p.biz.legal))
    while queue:
        policy = queue.pop(0)
        if policy.cancelled_on:
            continue
        received = on_or_before(policy.expires - timedelta(days=rng.randint(40, 75)))
        brokerage = world.brokerages[policy.brokerage - 1]
        renewed = None
        if received < YEAR_START:
            outcome = pick(rng, [("renew", 66), ("expired", 27), ("non_renewed", 7)])
            if not brokerage.active and policy.expires >= date(2024, 6, 1):
                outcome = "expired"
            if outcome == "renew":
                renewed = write_policy(rng, world, policy.biz, policy.brokerage, policy.expires, policy)
            policy.let_go = outcome == "non_renewed"
        elif received <= SEED_END and brokerage.active and rng.random() < RENEWAL_SUBMITTED:
            sub = open_submission(rng, world, policy.biz, received, policy.brokerage, policy)
            renewed = work_submission(rng, world, sub)
            if sub.decisions and sub.decisions[-1][2] == "decline":
                policy.let_go = True
        if renewed:
            world.policies.append(settle_term(rng, renewed))
            queue.append(renewed)
            queue.sort(key=lambda p: (p.expires, p.biz.legal))


def build() -> str:
    rng = random.Random(SEED)
    world = simulate(rng)
    policies = sorted(world.policies, key=lambda p: (p.effective, p.biz.legal))
    submissions = sorted(world.submissions, key=lambda s: (s.received, s.biz.legal))
    policy_ids = {id(p): i for i, p in enumerate(policies, start=1)}
    renewed = {id(p.prior) for p in policies if p.prior}
    sub_ids = {id(s): i for i, s in enumerate(submissions, start=1)}

    rows = {k: [] for k in ("inspections_and_calls", "facts", "notes", "decisions", "claims")}
    for sid, sub in enumerate(submissions, start=1):
        for kind, whom, when, by, text in sub.contacts:
            rows["inspections_and_calls"].append({"submission_id": sid, "kind": kind, "with_whom": whom,
                                                  "held_on": when.isoformat(), "recorded_by": by, "findings": text})
        for name, value, when, by, note in sub.facts:
            rows["facts"].append({"submission_id": sid, "field": name, "value": value, "checked_on": when.isoformat(),
                                  "checked_by": by, "note": note})
        for at, author, body in sub.notes:
            rows["notes"].append({"submission_id": sid, "author": author, "written_at": at, "body": body})
        for at, actor, action, premium, deductible, terms in sub.decisions:
            rows["decisions"].append({"actor": actor, "submission_id": sid, "action": action, "premium": premium,
                                      "deductible": deductible, "terms": terms, "at": at})
    for pid, policy in enumerate(policies, start=1):
        for c in policy.claims:
            rows["claims"].append({"policy_id": pid, "date_of_loss": c.loss.isoformat(),
                                   "reported_on": c.reported.isoformat(), "kind": c.kind, "paid": c.paid,
                                   "reserve": c.reserve, "status": c.status})

    def numbered(table: list[dict], key) -> list[dict]:
        return [{"id": i, **row} for i, row in enumerate(sorted(table, key=key), start=1)]

    data = {
        "staff": [{"id": i, "name": n, "email": f"{n.lower().replace(' ', '.')}@ketterlyuw.com", "role": r}
                  for i, n, r in STAFF],
        "brokerages": [{"id": i, "name": b.name, "city": b.town, "state": b.us_state,
                        "appointed_on": b.appointed.isoformat(), "status": "active" if b.active else "inactive"}
                       for i, b in enumerate(world.brokerages, start=1)],
        "policies": [{"id": i, "insured": p.biz.legal, "state": p.biz.us_state, "carrier": p.carrier,
                      "brokerage_id": p.brokerage, "effective": p.effective.isoformat(),
                      "expires": p.expires.isoformat(), "annual_premium": p.premium, "limits": p.limits,
                      "status": status_on(p, AS_OF, renewed),
                      "cancelled_on": p.cancelled_on.isoformat() if p.cancelled_on else None,
                      "prior_policy_id": policy_ids[id(p.prior)] if p.prior else None,
                      "submission_id": sub_ids[id(p.submission)] if p.submission else None}
                     for i, p in enumerate(policies, start=1)],
        "submissions": [{"id": i, "business": s.biz.legal, "dba": s.biz.at(s.received).dba, "state": s.biz.us_state,
                         "address": s.biz.address(s.received), "class_of_business": s.biz.cls,
                         "requested_limits": s.limits, "total_insured_value": s.tiv, "brokerage_id": s.brokerage,
                         "broker_contact": s.broker, "received_on": s.received.isoformat(), "entered_by": s.entered_by,
                         "renewal_of": policy_ids[id(s.renewal_of)] if s.renewal_of else None}
                        for i, s in enumerate(submissions, start=1)],
        "inspections_and_calls": numbered(rows["inspections_and_calls"],
                                          lambda r: (r["submission_id"], r["held_on"], r["kind"])),
        "facts": numbered(rows["facts"], lambda r: (r["submission_id"], r["checked_on"], r["field"])),
        "notes": numbered(rows["notes"], lambda r: (r["submission_id"], r["written_at"])),
        "decisions": sorted(rows["decisions"], key=lambda d: (d["at"], d["submission_id"])),
        "claims": numbered(rows["claims"], lambda r: (r["date_of_loss"], r["policy_id"], r["kind"])),
    }
    data["activity"] = numbered(book_entries(rng, data, policies, renewed), lambda r: (r["at"], r["action"]))
    return dump(data)


def status_on(p: Policy, day: date, renewed: set[int]) -> str:
    """The policy's status at the start of `day`: pending until it takes effect, in force until its term ends,
    then non-renewed (its renewal declined or let go, with no renewal term) or expired."""
    if p.cancelled_on:
        return "cancelled"
    if p.effective > day:
        return "pending"
    if p.expires > day:
        return "in_force"
    return "non_renewed" if p.let_go and id(p) not in renewed else "expired"


CANCEL_REASONS = ["Insured closed the business.", "Nonpayment of premium.", "Insured sold the business; the buyer "
                  "placed its own coverage.", "Broker's request; the insured moved the account."]


def book_entries(rng: random.Random, data: dict, policies: list[Policy], renewed: set[int]) -> list[dict]:
    """The activity entries the desk's own steps have left on the book since the log began: terms starting and
    ending on their dates, cancellations and claim closings."""
    entries = []

    def entry(actor: int, action: str, at: str, detail: str, **subject: int) -> None:
        row = {"actor": actor, "action": action, "submission_id": None, "policy_id": None, "claim_id": None,
               "brokerage_id": None, "detail": detail, "at": at}
        entries.append({**row, **subject})

    def first_read(day: date) -> str:
        return f"{on_or_after(day).isoformat()}T08:{rng.choice([3, 6, 11, 14, 22, 27]):02d}:00"

    everyone = [sid for sid, _, _ in STAFF]
    for pid, p in enumerate(policies, start=1):
        bound_on = date.fromisoformat(p.submission.decisions[-1][0][:10]) if p.submission else p.effective
        if LOG_BEGAN <= p.effective <= AS_OF and bound_on < p.effective:
            entry(rng.choice(everyone), "policy_started", first_read(p.effective),
                  f"term began {p.effective.isoformat()}", policy_id=pid)
        if status_on(p, AS_OF, renewed) in ("expired", "non_renewed") and p.expires >= LOG_BEGAN:
            entry(rng.choice(everyone), "policy_ended", first_read(p.expires),
                  f"term ended {p.expires.isoformat()}", policy_id=pid)
        if p.cancelled_on and p.cancelled_on >= LOG_BEGAN:
            entry(rng.choice(SENIORS), "policy_cancelled", stamp(rng, on_or_after(p.cancelled_on)),
                  f"cancelled as of {p.cancelled_on.isoformat()}: {rng.choice(CANCEL_REASONS)}", policy_id=pid)
    for claim in data["claims"]:
        if claim["status"] == "closed":
            closed_on = workday_between(rng, date.fromisoformat(claim["reported_on"]) + timedelta(days=20), SEED_END)
            if closed_on >= LOG_BEGAN:
                entry(rng.choice(SENIORS), "claim_closed", stamp(rng, closed_on),
                      f"closed with ${claim['paid']:,} paid", claim_id=claim["id"])
    return entries


def dump(data: dict) -> str:
    """One object per table, {"columns": [...], "rows": [[...], ...]}, one row per line."""
    tables = []
    for name, rows in data.items():
        columns = list(rows[0])
        lines = ",\n".join(json.dumps([row[c] for c in columns], ensure_ascii=False) for row in rows)
        tables.append(f' "{name}": {{"columns": {json.dumps(columns)}, "rows": [\n{lines}\n ]}}')
    return "{\n" + ",\n".join(tables) + "\n}\n"


if __name__ == "__main__":
    OUT.write_bytes(build().encode("utf-8"))
    print(f"wrote {OUT}")
