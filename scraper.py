"""
IKEA - scraper za primerjavo cen med Slovenijo, Avstrijo in Hrvaško.

Uporablja javni iskalni/kategorijski API podjetja IKEA
(sik.search.blue.cdtapps.com), ki ga uradna stran www.ikea.com v ozadju
kliče. API je odprt (CORS: *), ne zahteva prijave.

Namesto iskanja po ključnih besedah (ki je jezikovno odvisno in nikoli ne
zajame vsega) uporabimo endpoint "product-list-page?category=<koda>", ki
vrne VSE izdelke ene IKEA kategorije naenkrat (do 1000 na klic - IKEA-in
lastni maksimum). Kategorijske kode (npr. "st001", "fu004", "20649" ...) so
enake ne glede na jezik/državo - pridobljene z ročnim pregledom celotnega
menija "Izdelki" na ikea.com/si/sl/cat/izdelki-products/, zato scraper
zajame praktično celoten IKEA katalog (pohištvo, kuhinja, tekstil,
razsvetljava, dekoracija, vrt, rastline, elektronika, čiščenje, hišni
ljubljenčki, hrana ...), ne le pohištvo.

Zagon: python scraper.py
Izhod: data/products.json (polni podatki), data.js (za index.html)
"""

import json
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
PRODUCTS_FILE = DATA_DIR / "products.json"
DATA_JS_FILE = BASE_DIR / "data.js"

API_BASE = "https://sik.search.blue.cdtapps.com/{cc}/{lc}/product-list-page"
PAGE_SIZE = 1000  # IKEA-in maksimum na klic
REQUEST_DELAY_SECONDS = 0.3

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

# Vse kategorijske kode iz glavnega menija "Izdelki" na ikea.com/si/sl -
# tako nadrejene (npr. "st001") kot podrejene (npr. "19053"). Kode so
# jezikovno neodvisne (isti "fu004" vrne pisalne mize v SI, Schreibtische v
# AT, radne stolove u HR), zato zadostuje en sam seznam za vse tri države.
CATEGORY_CODES = [
    "fu004", "20649", "20652", "53249", "55002", "54173", "47068", "st001", "19053", "10475",
    "46052", "st003", "st002", "st004", "700440", "30454", "fu005", "46080", "21958", "10385",
    "700411", "10456", "18706", "st007", "10550", "10452", "10551", "34470", "10573", "15937",
    "16195", "46078", "st006", "10555", "16248", "bm001", "bm003", "24827", "bm002", "tl004",
    "24825", "20656", "19064", "57280", "19059", "54992", "700513", "24822", "700640", "fu003",
    "10663", "31786", "fu006", "57527", "20926", "57536", "10664", "31785", "ka001", "700292",
    "ka003", "700293", "24255", "ka002", "24264", "16200", "20676", "49117", "10471", "24263",
    "10482", "19121", "22957", "16282", "16298", "kt001", "18860", "kt003", "kt002", "16043",
    "16044", "18868", "20538", "18865", "15938", "20636", "15934", "18850", "31772", "42924",
    "18714", "20560", "fu002", "700675", "700676", "22659", "700417", "16244", "19141", "10705",
    "18768", "bc004", "45782", "700319", "59250", "20611", "bc001", "bc003", "bc002", "ba001",
    "700450", "20804", "20719", "20808", "16233", "20615", "20490", "20858", "20859", "tl003",
    "ba003", "10736", "40690", "20723", "20724", "30565", "tl001", "10653", "10659", "20528",
    "17893", "20542", "10655", "18730", "18690", "700528", "42925", "tl002", "10700", "10701",
    "18891", "700628", "14350", "li001", "li002", "16280", "14971", "36812", "17897", "20514",
    "de001", "10757", "10769", "24924", "20489", "pp003", "pp004", "10760", "10574", "10759",
    "42926", "25227", "od001", "od003", "700349", "31787", "17887", "34203", "21957", "34204",
    "pp001", "20494", "24887", "20493", "700778", "he001", "40842", "40843", "40845", "36814",
    "44531", "49081", "hs001", "56472", "46194", "lc001", "20601", "20609", "48925", "16213",
    "20608", "20602", "55004", "20826", "hi001", "16292", "sp001", "46077", "55984", "700718",
    "42948", "pt001", "39569", "39570", "fb001", "25215", "25217", "46192", "25216", "25214",
    "53254", "25213", "25212", "25211", "49147",
]

# IKEA-in interni "homeFurnishingBusinessName" je (skoraj vedno) v angleščini
# ne glede na jezik strani - tu ga prevedemo v slovenske nazive sklopov za
# prikaz. Nov, nepričakovan naziv se izpiše tak, kot ga vrne API.
BUSINESS_NAME_LABELS = {
    "Living room seating": "Sedežno pohištvo (dnevna soba)",
    "Living room storage": "Shranjevanje za dnevno sobo",
    "Bedroom furniture": "Spalniško pohištvo",
    "Beds & Mattresses": "Postelje in žimnice",
    "Dining": "Jedilnica",
    "Workspaces": "Domača pisarna",
    "Kitchen & appliances": "Kuhinja",
    "Bathroom": "Kopalnica",
    "Children's IKEA": "Otroško pohištvo in oprema",
    "Outdoor": "Vrtno pohištvo",
    "Home organisation": "Ureditev in shranjevanje",
    "Decoration": "Ogledala in dekoracija",
    "Cooking": "Kuhanje in pribor",
    "Lighting & Home electronics": "Razsvetljava in elektronika",
    "Home textiles": "Tekstil za dom",
    "Bed and bath textiles": "Tekstil za posteljo in kopalnico",
    "Textiles": "Tekstil",
    "Curtains & blinds": "Zavese in senčila",
    "Plants & Flowers": "Rastline in rože",
    "Plant pots": "Cvetlični lonci",
    "Home smart": "Pametni dom",
    "Home electronics": "Domača elektronika",
    "Cleaning & laundry": "Čiščenje in pranje perila",
    "Home improvement": "Izboljšave doma",
    "Pets": "Izdelki za hišne ljubljenčke",
    "Food & beverages": "Hrana in pijača",
    "Tableware & cookware": "Namizna in kuhinjska posoda",
    "Eating": "Jedilni pribor in posoda",
    "Rugs": "Preproge",
    "Consumer packaged food goods": "Švedska hrana in pijača",
    "Other business opportunities": "Drugo",
}


def fetch_category(cc: str, lc: str, category: str) -> list:
    url = API_BASE.format(cc=cc, lc=lc)
    params = {"category": category, "size": PAGE_SIZE}
    try:
        resp = requests.get(url, params=params, headers=HEADERS, timeout=30)
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:  # noqa: BLE001 - scraper must keep going on a bad category
        print(f"    ! napaka pri kategoriji '{category}' ({cc}): {exc}")
        return []

    return data.get("productListPage", {}).get("productWindow", []) or []


def extract_product(p: dict) -> dict | None:
    price = p.get("salesPrice", {})
    business = p.get("businessStructure", {})
    business_name = business.get("homeFurnishingBusinessName")

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
        "businessLabel": BUSINESS_NAME_LABELS.get(business_name, business_name or "Drugo"),
        "categoryPath": [c.get("name") for c in (p.get("categoryPath") or [])],
    }


def scrape_country(cc_key: str) -> dict:
    country = COUNTRIES[cc_key]
    cc, lc = country["cc"], country["lc"]
    print(f"== {country['label']} ({cc}/{lc}) ==")

    by_item_no: dict[str, dict] = {}
    for i, category in enumerate(CATEGORY_CODES, 1):
        products = fetch_category(cc, lc, category)
        found = 0
        for p in products:
            product = extract_product(p)
            if not product or not product["itemNo"]:
                continue
            if product["itemNo"] not in by_item_no:
                by_item_no[product["itemNo"]] = product
                found += 1
        if i % 20 == 0 or i == len(CATEGORY_CODES):
            print(f"  [{i}/{len(CATEGORY_CODES)}] '{category}': +{found} (skupaj {len(by_item_no)})")
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
