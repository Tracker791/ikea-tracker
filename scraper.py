"""
IKEA pohištvo - scraper za primerjavo cen med Slovenijo, Avstrijo in Hrvaško.

Uporablja javni iskalni API podjetja IKEA (sik.search.blue.cdtapps.com), ki ga
uradna stran www.ikea.com/<cc>/<lc>/search/ v ozadju kliče za vsak iskalni niz.
API je odprt (CORS: *), ne zahteva prijave in vrača strukturirane podatke o
izdelku: ime, ceno, kategorijo (IKEA-ina lastna klasifikacija), oceno kupcev
in povezavo do strani izdelka.

Ker API omogoča samo iskanje po nizu (ni "prebrskaj po kategoriji"), pohištvo
zajamemo tako, da vsako IKEA kategorijo pohištva predstavimo z eno ali dvema
iskalnima frazama v jeziku posamezne države (glej CATEGORY_QUERIES). Rezultati
se združijo in razdvojijo po "homeFurnishingBusinessName" - IKEA-inem internem
imenu poslovnega področja, ki je (nenavadno koristno) enako ne glede na jezik
strani, zato lahko izdelke iz vseh treh držav zanesljivo razvrstimo v enake
sklope.

Zagon: python scraper.py
Izhod: data/products.json (polni podatki), data.js (za index.html)
"""

import json
import time
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

import requests

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
PRODUCTS_FILE = DATA_DIR / "products.json"
DATA_JS_FILE = BASE_DIR / "data.js"

API_BASE = "https://sik.search.blue.cdtapps.com/{cc}/{lc}/search-result-page"
PAGE_SIZE = 100
REQUEST_DELAY_SECONDS = 0.4

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
}

COUNTRIES = {
    "si": {"cc": "si", "lc": "sl", "label": "IKEA Slovenija", "domain": "https://www.ikea.com/si/sl"},
    "at": {"cc": "at", "lc": "de", "label": "IKEA Avstrija", "domain": "https://www.ikea.com/at/de"},
    "hr": {"cc": "hr", "lc": "hr", "label": "IKEA Hrvaška", "domain": "https://www.ikea.com/hr/hr"},
}

# Sklopi pohištva: en logični sklop = ena ali več iskalnih fraz na državo.
# "label" je prikazni naslov sklopa na strani (slovensko, saj je občinstvo SI).
# Dejansko razvrščanje izdelkov v sklope na strani temelji na
# businessStructure.homeFurnishingBusinessName iz odgovora API-ja (glej
# BUSINESS_NAME_LABELS spodaj) - iskalne fraze tu služijo samo temu, da
# izdelke sploh najdemo.
CATEGORY_QUERIES = {
    "sofas": {
        "label": "Sedežne garniture in fotelji",
        "si": ["sedežna garnitura", "fotelj", "trosed", "dvosed"],
        "at": ["sofa", "sessel", "ecksofa"],
        "hr": ["kauč", "fotelja", "trosjed", "dvosjed"],
    },
    "beds": {
        "label": "Postelje in žimnice",
        "si": ["posteljni okvir", "žimnica", "otroška postelja"],
        "at": ["bettgestell", "matratze", "kinderbett"],
        "hr": ["okvir kreveta", "madrac", "dječji krevet"],
    },
    "wardrobes": {
        "label": "Garderobne omare in shranjevanje",
        "si": ["garderobna omara", "drsna vrata omara"],
        "at": ["kleiderschrank", "schiebetürenschrank"],
        "hr": ["ormar za odjeću", "ormar s kliznim vratima"],
    },
    "drawers": {
        "label": "Predalniki in komode",
        "si": ["predalnik", "komoda", "nočna omarica"],
        "at": ["kommode", "nachttisch"],
        "hr": ["komoda", "noćni ormarić"],
    },
    "bookcases": {
        "label": "Knjižne omare in regali",
        "si": ["knjižna omara", "regal", "kockaste police"],
        "at": ["bücherregal", "regal"],
        "hr": ["biblioteka", "polica", "regal"],
    },
    "dining": {
        "label": "Jedilne mize in stoli",
        "si": ["jedilna miza", "jedilni stol", "barski stol"],
        "at": ["esstisch", "esszimmerstuhl", "barhocker"],
        "hr": ["blagovaonski stol", "blagovaonska stolica", "barska stolica"],
    },
    "living_tables": {
        "label": "Mize za dnevno sobo",
        "si": ["klubska mizica", "stranska mizica"],
        "at": ["couchtisch", "beistelltisch"],
        "hr": ["stolić za kavu", "pomoćni stolić"],
    },
    "office": {
        "label": "Pisalne mize in pisarniški stoli",
        "si": ["pisalna miza", "pisarniški stol"],
        "at": ["schreibtisch", "bürostuhl"],
        "hr": ["radni stol", "uredska stolica"],
    },
    "tv_media": {
        "label": "TV omarice in pohištvo za medije",
        "si": ["tv omarica", "polica za medije"],
        "at": ["tv-möbel", "mediamöbel"],
        "hr": ["tv ormarić", "polica za medije"],
    },
    "kitchen": {
        "label": "Kuhinjski elementi",
        "si": ["kuhinjski element", "kuhinjska omarica"],
        "at": ["küchenschrank", "küchenhängeschrank"],
        "hr": ["kuhinjski element", "kuhinjski ormarić"],
    },
    "bathroom": {
        "label": "Kopalniško pohištvo",
        "si": ["kopalniška omarica", "umivalniška omara"],
        "at": ["badezimmermöbel", "waschbeckenschrank"],
        "hr": ["kupaonski ormarić", "ormarić s umivaonikom"],
    },
    "kids": {
        "label": "Otroško in dojenčkovo pohištvo",
        "si": ["otroška omara", "previjalna miza", "visok stolček"],
        "at": ["kinderschrank", "wickeltisch", "kinderhochstuhl"],
        "hr": ["dječji ormar", "previjaonik", "dječja visoka stolica"],
    },
    "outdoor": {
        "label": "Vrtno pohištvo",
        "si": ["vrtna miza", "vrtni stol", "ležalnik"],
        "at": ["gartentisch", "gartenstuhl", "sonnenliege"],
        "hr": ["vrtni stol", "vrtna stolica", "ležaljka"],
    },
    "hallway": {
        "label": "Predsobno pohištvo",
        "si": ["obešalnik", "klop za čevlje", "omarica za čevlje"],
        "at": ["garderobenständer", "schuhschrank"],
        "hr": ["vješalica za odjeću", "ormarić za cipele"],
    },
    "mirrors": {
        "label": "Ogledala",
        "si": ["stensko ogledalo", "stoječe ogledalo"],
        "at": ["wandspiegel", "standspiegel"],
        "hr": ["zidno zrcalo", "stojeće zrcalo"],
    },
    "storage_boxes": {
        "label": "Škatle in organizatorji za shranjevanje",
        "si": ["škatla za shranjevanje", "organizator za predal", "obešalnik za oblačila"],
        "at": ["aufbewahrungsbox", "schubladen-organizer", "kleiderbügel"],
        "hr": ["kutija za pohranu", "organizator za ladicu", "vješalica za odjeću"],
    },
}

# IKEA-in interni "homeFurnishingBusinessName" je (skoraj vedno) v angleščini
# ne glede na jezik strani - tu ga prevedemo v slovenske nazive sklopov za
# prikaz. Seznam ključev je izčrpen glede na to, kar dejansko vrne API za
# si/at/hr (preverjeno ročno); nov, nepričakovan naziv se izpiše kot je.
BUSINESS_NAME_LABELS = {
    "Living room seating": "Sedežno pohištvo (dnevna soba)",
    "Living room storage": "Shranjevanje za dnevno sobo",
    "Bedroom furniture": "Spalniško pohištvo",
    "Beds & Mattresses": "Postelje in žimnice",
    "Dining": "Jedilnica",
    "Workspaces": "Domača pisarna",
    "Kitchen & appliances": "Kuhinja",
    "Bathroom": "Kopalnica",
    "Children's IKEA": "Otroško pohištvo",
    "Outdoor": "Vrtno pohištvo",
    "Home organisation": "Ureditev in shranjevanje",
    "Decoration": "Ogledala in dekoracija",
}

# Ti nazivi pomenijo, da je izdelek pricurljal v rezultate zaradi širokega
# iskalnega niza (npr. "regal" najde tudi kakšno svetilko), ni pa dejansko
# pohištvo - take izdelke izločimo, da stran ostane pri temi "pohištvo".
DROP_BUSINESS_NAMES = {
    "Cooking",
    "Lighting & Home electronics",
    "Home textiles",
    "Bed and bath textiles",
}


def slugify(value: str) -> str:
    value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    return "".join(c if c.isalnum() else "-" for c in value.lower()).strip("-")


def fetch_query(cc: str, lc: str, query: str) -> list:
    url = API_BASE.format(cc=cc, lc=lc)
    params = {"q": query, "size": PAGE_SIZE, "c": "sr"}
    try:
        resp = requests.get(url, params=params, headers=HEADERS, timeout=20)
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:  # noqa: BLE001 - scraper must keep going on a bad query
        print(f"    ! napaka pri '{query}' ({cc}): {exc}")
        return []

    main = data.get("searchResultPage", {}).get("products", {}).get("main", {})
    return main.get("items", []) or []


def extract_product(item: dict, category_key: str) -> dict | None:
    p = item.get("product")
    if not p or item.get("type") != "PRODUCT":
        return None

    price = p.get("salesPrice", {})
    business = p.get("businessStructure", {})
    business_name = business.get("homeFurnishingBusinessName")
    if business_name in DROP_BUSINESS_NAMES:
        return None

    previous_price = None
    prev = price.get("previous")
    if prev and prev.get("wholeNumber"):
        try:
            previous_price = float(f"{prev['wholeNumber']}.{prev.get('decimals') or '0'}")
        except ValueError:
            previous_price = None

    return {
        "itemNo": p.get("itemNoGlobal") or p.get("itemNo") or p.get("id"),
        "name": p.get("name"),
        "typeName": p.get("typeName"),
        "measure": p.get("itemMeasureReferenceText"),
        "validDesign": p.get("validDesignText"),
        "price": price.get("numeral"),
        "currency": price.get("currencyCode"),
        "previousPrice": previous_price,
        "priceTag": price.get("tag"),
        "priceTagText": price.get("tagText"),
        "advertisement": (price.get("advertisement") or {}).get("text"),
        "validTo": (price.get("advertisement") or {}).get("validTo"),
        "lastChance": p.get("lastChance", False),
        "onlineSellable": p.get("onlineSellable", True),
        "ratingValue": p.get("ratingValue"),
        "ratingCount": p.get("ratingCount"),
        "image": p.get("mainImageUrl"),
        "url": p.get("pipUrl"),
        "businessName": business_name,
        "businessLabel": BUSINESS_NAME_LABELS.get(business_name, business_name or "Drugo pohištvo"),
        "categoryPath": [c.get("name") for c in (p.get("categoryPath") or [])],
        "matchedCategoryKey": category_key,
    }


def scrape_country(cc_key: str) -> dict:
    country = COUNTRIES[cc_key]
    cc, lc = country["cc"], country["lc"]
    print(f"== {country['label']} ({cc}/{lc}) ==")

    by_item_no: dict[str, dict] = {}
    for category_key, cat in CATEGORY_QUERIES.items():
        queries = cat.get(cc_key, [])
        for query in queries:
            items = fetch_query(cc, lc, query)
            found = 0
            for item in items:
                product = extract_product(item, category_key)
                if not product or not product["itemNo"]:
                    continue
                if product["itemNo"] not in by_item_no:
                    by_item_no[product["itemNo"]] = product
                    found += 1
            print(f"  '{query}': +{found} novih (skupaj {len(by_item_no)})")
            time.sleep(REQUEST_DELAY_SECONDS)

    return {
        "label": country["label"],
        "domain": country["domain"],
        "error": None,
        "products": list(by_item_no.values()),
    }


def load_previous() -> dict:
    if not PRODUCTS_FILE.exists():
        return {}
    try:
        with open(PRODUCTS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}
    prev = {}
    for cc_key, country_data in data.get("countries", {}).items():
        prev[cc_key] = {p["itemNo"]: p for p in country_data.get("products", []) if p.get("itemNo")}
    return prev


def apply_change_tracking(countries: dict, previous: dict) -> None:
    for cc_key, country_data in countries.items():
        prev_products = previous.get(cc_key, {})
        for product in country_data["products"]:
            prev = prev_products.get(product["itemNo"])
            if prev is None:
                product["status"] = "new"
            elif prev.get("price") != product.get("price"):
                product["status"] = "changed"
                product["previousRunPrice"] = prev.get("price")
            else:
                product["status"] = "same"


def main() -> None:
    previous = load_previous()

    countries = {}
    for cc_key in COUNTRIES:
        countries[cc_key] = scrape_country(cc_key)

    apply_change_tracking(countries, previous)

    output = {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "countries": countries,
    }

    DATA_DIR.mkdir(exist_ok=True)
    with open(PRODUCTS_FILE, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    with open(DATA_JS_FILE, "w", encoding="utf-8") as f:
        f.write("window.IKEA_DATA = ")
        json.dump(output, f, ensure_ascii=False)
        f.write(";\n")

    total = sum(len(c["products"]) for c in countries.values())
    print(f"\nSkupaj {total} izdelkov, shranjeno v {PRODUCTS_FILE} in {DATA_JS_FILE}")


if __name__ == "__main__":
    main()
