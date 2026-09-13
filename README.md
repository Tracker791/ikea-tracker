# IKEA tracker – SI / AT / HR

Primerja cene IKEA pohištva med Slovenijo, Avstrijo in Hrvaško. Podatki se
dnevno osvežujejo prek uradnega iskalnega API-ja ikea.com
(`sik.search.blue.cdtapps.com`), izdelki pa so razvrščeni v sklope po
IKEA-ini lastni klasifikaciji (`homeFurnishingBusinessName`).

Ni uradna stran podjetja IKEA.

## Razvoj

```bash
pip install requests
python scraper.py   # osveži data/products.json in data.js
python -m http.server 8765   # lokalni predogled na http://localhost:8765
```

## Samodejna osvežitev

`.github/workflows/scrape.yml` vsak dan ob 4:00 UTC požene `scraper.py` in
samodejno objavi (commit + push) posodobljene podatke.

