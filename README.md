# Golemio Waste Monitoring

Automatický sběr a vizualizace dat o zaplněnosti nádob na tříděný odpad pro odběrné místo **Kašparovo náměstí 350/1, Praha 8** (stanice č. 0008/067, ID 5262).

## Co to dělá

- Každou hodinu (07:00–00:00 CEST) + jednou ve 04:00 CEST stáhne aktuální měření ze **[Golemio Open Data API v2](https://api.golemio.cz)**
- Uloží nová data do `kasparovo_namesti_odpady.csv`
- Vygeneruje `index.html` s interaktivními grafy
- Commituje změny zpět do repozitáře

Vše běží automaticky přes **GitHub Actions** — bez nutnosti mít zapnutý počítač.

## Monitorované nádoby

| Odpad | ID nádoby | Sensor | Frekvence svozu |
|---|---|---|---|
| Papír | 23270 | Sensoneo C01341 | Po, St, Pá |
| Multikomoditní sběr | 41581 | Sensoneo C01342 | Po, Pá |
| Kovy | 41580 | Sensoneo C01346 | Út |
| Barevné sklo | 42883 | Sensoneo C01343 | Čt |

Všechny nádoby jsou podzemního typu **3000 Podzemní SV**, vybavené senzory Sensoneo s adaptivní frekvencí měření (měří hustěji při vysokém zaplnění).

## Dashboard

Živý dashboard: **[sim-mar.github.io/golemio_monitoring](https://sim-mar.github.io/golemio_monitoring/)**

Aktualizuje se automaticky při každém novém měření.

## Soubory

| Soubor | Popis |
|---|---|
| `collect_data.py` | Stáhne aktuální měření z API, uloží do CSV |
| `build_html.py` | Přečte CSV a vygeneruje `index.html` s grafy |
| `kasparovo_namesti_odpady.csv` | Časová řada měření |
| `index.html` | Dashboard s grafy (generovaný automaticky) |
| `.github/workflows/collect.yml` | GitHub Actions workflow |



## Data

Senzory měří zaplnění 0–100 %. Škálování stavů:

| Hodnota | Stav |
|---|---|
| < 60 % | OK |
| 60–89 % | Pozor |
| ≥ 90 % | Kritické |

Zdroj dat: [Golemio Open Data API](https://golemio.cz) · Operátor ICT Praha
