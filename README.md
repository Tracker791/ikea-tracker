# IKEA tracker – SI / AT / HR

Primerja cene celotnega IKEA kataloga med Slovenijo, Avstrijo in Hrvaško.
Podatki se dnevno osvežujejo prek uradnega API-ja ikea.com
(`sik.search.blue.cdtapps.com`, endpoint `product-list-page`), ki vrne vse
izdelke ene IKEA kategorije naenkrat. Scraper obišče ~215 kategorijskih kod
(pohištvo, kuhinja, tekstil, razsvetljava, dekoracija, vrt, rastline,
elektronika, čiščenje, hišni ljubljenčki, hrana ...) - te kode so enake ne
glede na jezik strani, zato en sam seznam pokrije vse tri države. Izdelki so
razvrščeni v sklope po IKEA-ini lastni klasifikaciji
(`homeFurnishingBusinessName`).

Ni uradna stran podjetja IKEA.

## Razvoj

```bash
pip install requests
python scraper.py   # osveži data/products.json in data.js (traja nekaj minut)
python -m http.server 8765   # lokalni predogled na http://localhost:8765
```

## Samodejna osvežitev

`.github/workflows/daily-scrape.yml` vsak dan ob 4:00 UTC požene
`scraper.py` in v istem koraku objavi (commit + push + GitHub Pages deploy)
posodobljene podatke.

