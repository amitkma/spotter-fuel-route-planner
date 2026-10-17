"""Helpers to normalise place names and parse user supplied locations."""

# Standard library imports
import re
import unicodedata
from dataclasses import dataclass

# Spotter imports
from spotter.core.types import LatLng

US_STATES = {
    "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas", "CA": "California",
    "CO": "Colorado", "CT": "Connecticut", "DE": "Delaware", "DC": "District of Columbia",
    "FL": "Florida", "GA": "Georgia", "HI": "Hawaii", "ID": "Idaho", "IL": "Illinois",
    "IN": "Indiana", "IA": "Iowa", "KS": "Kansas", "KY": "Kentucky", "LA": "Louisiana",
    "ME": "Maine", "MD": "Maryland", "MA": "Massachusetts", "MI": "Michigan", "MN": "Minnesota",
    "MS": "Mississippi", "MO": "Missouri", "MT": "Montana", "NE": "Nebraska", "NV": "Nevada",
    "NH": "New Hampshire", "NJ": "New Jersey", "NM": "New Mexico", "NY": "New York",
    "NC": "North Carolina", "ND": "North Dakota", "OH": "Ohio", "OK": "Oklahoma",
    "OR": "Oregon", "PA": "Pennsylvania", "RI": "Rhode Island", "SC": "South Carolina",
    "SD": "South Dakota", "TN": "Tennessee", "TX": "Texas", "UT": "Utah", "VT": "Vermont",
    "VA": "Virginia", "WA": "Washington", "WV": "West Virginia", "WI": "Wisconsin",
    "WY": "Wyoming",
}  # fmt: skip
_STATE_BY_NAME = {name.lower(): code for code, name in US_STATES.items()}

# Not US. Catch these early so e.g. "Toronto, ON" doesn't go to Nominatim.
FOREIGN_REGIONS = {
    "ab", "alberta", "bc", "british columbia", "mb", "manitoba", "nb", "new brunswick",
    "nl", "newfoundland", "newfoundland and labrador", "ns", "nova scotia", "nt",
    "northwest territories", "nu", "nunavut", "on", "ontario", "pe", "pei",
    "prince edward island", "qc", "quebec", "sk", "saskatchewan", "yt", "yukon",
    "canada", "mexico", "mx",
}  # fmt: skip

# Common abbreviations, applied word by word.
_WORD_ALIASES = {
    "saint": "st",
    "sainte": "ste",
    "ft": "fort",
    "mt": "mount",
    "n": "north",
    "s": "south",
    "e": "east",
    "w": "west",
}

_COORDINATES = re.compile(r"^\s*(-?\d{1,2}(?:\.\d+)?)\s*[, ]\s*(-?\d{1,3}(?:\.\d+)?)\s*$")
_COUNTRY_SUFFIX = re.compile(r",?\s*(usa|us|united states( of america)?)\s*$", re.IGNORECASE)
_ZIP_SUFFIX = re.compile(r"\s+\d{5}(-\d{4})?\s*$")


def normalize_place_name(name: str) -> str:
    """Return a lookup key for a place name.

    "St. Louis", "Saint Louis" and "ST LOUIS " all become "stlouis".
    """
    ascii_name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    words = re.sub(r"[^a-z0-9]+", " ", ascii_name.lower()).split()
    return "".join(_WORD_ALIASES.get(word, word) for word in words)


def normalize_state(state: str) -> str | None:
    """Return the USPS code for a state given as code or full name, else None."""
    cleaned = " ".join(state.replace(".", "").split())
    if cleaned.upper() in US_STATES:
        return cleaned.upper()
    return _STATE_BY_NAME.get(cleaned.lower())


@dataclass(frozen=True, slots=True)
class ParsedLocation:
    """A user-supplied location, classified by how it can be resolved."""

    raw: str
    coordinates: LatLng | None = None
    city: str | None = None
    state: str | None = None
    #: e.g. a Canadian province
    foreign: bool = False


def parse_location(text: str) -> ParsedLocation:
    """Classify a location string as coordinates, "City, ST", or free text.

    Accepts "34.05,-118.24", "Austin, TX", "Austin, Texas", "Austin TX", "Austin, TX 78701"
    and "Austin, TX, USA". "Toronto, ON" is flagged as foreign. Anything else is returned as
    free text (for online geocoding).
    """
    raw = text.strip()
    if match := _COORDINATES.match(raw):
        return ParsedLocation(raw=raw, coordinates=LatLng(float(match[1]), float(match[2])))

    cleaned = _ZIP_SUFFIX.sub("", _COUNTRY_SUFFIX.sub("", raw)).strip(" ,")
    if "," in cleaned:
        city, _, state = cleaned.rpartition(",")
        if (code := normalize_state(state)) and city.strip():
            return ParsedLocation(raw=raw, city=city.strip(), state=code)
        if " ".join(state.replace(".", "").lower().split()) in FOREIGN_REGIONS:
            return ParsedLocation(raw=raw, foreign=True)
    else:
        # "Austin TX" / "Salt Lake City Utah" / "Kansas City New Mexico"
        words = cleaned.split()
        for n_state_words in (2, 1):
            if len(words) > n_state_words:
                state = " ".join(words[-n_state_words:])
                if code := normalize_state(state):
                    return ParsedLocation(
                        raw=raw, city=" ".join(words[:-n_state_words]), state=code
                    )
    return ParsedLocation(raw=raw)
