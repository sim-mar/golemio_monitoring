# Golemio Waste Monitoring

Automatický sběr a vizualizace dat o zaplněnosti nádob na tříděný odpad pro odběrné místo **Kašparovo náměstí 350/1, Praha 8** (stanice č. 0008/067, ID 5262).

## Co to dělá

- Každých ~6 hodin stáhne aktuální měření ze **[Golemio Open Data API v2](https://api.golemio.cz)**
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

## Soubory

| Soubor | Popis |
|---|---|
| `collect_data.py` | Stáhne aktuální měření z API, uloží do CSV |
| `build_html.py` | Přečte CSV a vygeneruje `index.html` s grafy |
| `kasparovo_namesti_odpady.csv` | Časová řada měření |
| `index.html` | Dashboard s grafy (generovaný automaticky) |
| `.github/workflows/collect.yml` | GitHub Actions workflow |

## Spuštění lokálně

```bash
pip install -r requirements.txt   # žádné externí závislosti, jen stdlib
python collect_data.py            # stáhne data a přegeneruje HTML
```

## Nastavení

API token je uložen jako GitHub secret `GOLEMIO_TOKEN`. Lokálně se používá token přímo v `collect_data.py` nebo přes environment proměnnou:

```bash
GOLEMIO_TOKEN=<tvůj_token> python collect_data.py
```

## Data

Senzory měří zaplnění 0–100 %. Škálování stavů:

| Hodnota | Stav |
|---|---|
| < 60 % | OK |
| 60–89 % | Pozor |
| ≥ 90 % | Kritické |

Zdroj dat: [Golemio Open Data API](https://golemio.cz) · Operátor ICT Praha
