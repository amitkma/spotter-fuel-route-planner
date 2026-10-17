"""Build `data/us_places.csv.gz` from the US Census Bureau Gazetteer files.

Output is (name, state, lat, lng) rows, used to geocode stations and start/finish offline.

Source (public domain):
    https://www.census.gov/geographies/reference-files/time-series/geo/gazetteer-files.html
    - Places (incorporated + CDPs)
    - County subdivisions (towns/townships, needed for New England, PA, NY, Midwest)

Usage:
    python scripts/build_places_dataset.py [--year 2024] [--output data/us_places.csv.gz]
"""

import argparse
import csv
import gzip
import io
import re
import unicodedata
import zipfile
from pathlib import Path

import requests

BASE_URL = "https://www2.census.gov/geo/docs/maps-data/data/gazetteer/{year}_Gazetteer/{file}.zip"
SOURCES = [
    # (file stem, kind). On duplicate (name, state) the earlier source wins.
    ("{year}_Gaz_place_national", "place"),
    ("{year}_Gaz_cousubs_national", "cousub"),
]

# Suffixes Census adds to names, e.g. "Austin city".
LSAD_SUFFIX = re.compile(
    r"\s+(city and borough|consolidated government|unified government|metropolitan government|"
    r"metro government|urban county|county|charter township|city|town|village|borough|township|"
    r"CDP|municipality|plantation|CCD|UT|gore|grant|location|purchase|precinct|district|"
    r"comunidad|zona urbana)$",
    re.IGNORECASE,
)


def clean_name(raw: str) -> list[str]:
    """Return the display name(s) a Census entry should be searchable by."""
    name = unicodedata.normalize("NFKD", raw).encode("ascii", "ignore").decode()
    name = re.sub(r"\(balance\)", "", name).strip()
    name = LSAD_SUFFIX.sub("", name).strip()
    names = [name]
    # Consolidated city-counties: "Nashville-Davidson", "Louisville/Jefferson County".
    for sep in ("-", "/"):
        if sep in name:
            names.append(name.split(sep)[0].strip())
    return [n for n in names if n]


def read_source(year: int, stem: str) -> list[dict[str, str]]:
    """Download one gazetteer zip and return its rows."""
    file = stem.format(year=year)
    response = requests.get(BASE_URL.format(year=year, file=file), timeout=120)
    response.raise_for_status()
    with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
        text = archive.read(f"{file}.txt").decode("utf-8")
    reader = csv.DictReader(io.StringIO(text), delimiter="\t")
    return [{k.strip(): (v or "").strip() for k, v in row.items()} for row in reader]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--year", type=int, default=2024)
    parser.add_argument("--output", type=Path, default=Path("data/us_places.csv.gz"))
    args = parser.parse_args()

    seen: set[tuple[str, str]] = set()
    rows: list[tuple[str, str, str, str, str]] = []
    for stem, kind in SOURCES:
        source_rows = read_source(args.year, stem)
        # Biggest first, so a duplicated name in a state maps to the main place.
        source_rows.sort(key=lambda r: -int(r.get("ALAND") or 0))
        for row in source_rows:
            for name in clean_name(row["NAME"]):
                key = (name.lower(), row["USPS"])
                if key in seen:
                    continue
                seen.add(key)
                lat = f"{float(row['INTPTLAT']):.5f}"
                lng = f"{float(row['INTPTLONG']):.5f}"
                rows.append((name, row["USPS"], lat, lng, kind))

    rows.sort(key=lambda r: (r[1], r[0]))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(args.output, "wt", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(["name", "state", "lat", "lng", "kind"])
        writer.writerows(rows)
    print(f"Wrote {len(rows)} places to {args.output}")


if __name__ == "__main__":
    main()
