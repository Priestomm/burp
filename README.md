# burp!

Trasforma post e reel Instagram in ricette strutturate, salvate in una libreria personale in cui puoi cercare per titolo, tag e ingrediente.

Si processa solo quello che condividi tu, un link alla volta: niente scraping. Se un link non si scarica, puoi sempre incollare la caption o mandare uno screenshot.

## Come funziona

La pipeline è divisa in stadi separati, ognuno testabile da solo:

```
link / caption incollata / screenshot
  1. ingestion      burp/ingest.py      normalizza il link, scarica caption e video (yt-dlp)
  2. estrazione     burp/extract.py     caption → trascrizione audio (Whisper) → frame letti da Claude
  3. strutturazione burp/structure.py   JSON validato con Pydantic, un retry se invalido
  4. libreria       burp/library.py     SQLite, ricerca, deduplica per link
```

- **Ingestion.** I link vengono ridotti a una forma canonica: senza `?igsh=…`, senza il nome dell'autore davanti e con `/reels/` riscritto in `/reel/`. Da yt-dlp si legge anche l'`author_handle`.
- **Estrazione a costo crescente.** Ogni fonte si usa solo se la precedente non basta. Una caption "basta" se ha almeno 25 parole, delle quantità o un elenco di ingredienti **e** un procedimento (un titolo come "Procedimento" o almeno due verbi di cucina diversi): se ci sono solo gli ingredienti, si cercano i passaggi nell'audio e poi nei frame. Se Whisper o PyAV non sono installati, si passa allo stadio successivo. Il log dice quale fonte è stata usata e perché, e fonte e motivo sono salvati con la ricetta.
- **Strutturazione.** Claude compila lo schema qui sotto, sempre in italiano (anche se il post è in inglese); solo `original_text` resta com'era. Poi alcune regole deterministiche controllano la risposta:
  - i nomi degli ingredienti vengono ricondotti al catalogo canonico (`data/ingredients.json`), così "pomodori", "tomato" e "pomodoro" diventano uno solo;
  - se manca una quantità (e non è q.b.) o mancano i passaggi, la ricetta è `partial`, anche se il modello l'aveva dichiarata completa;
  - la dieta non può essere più permissiva di quanto dicono gli ingredienti noti: una ricetta "vegetarian" con pecorino, che contiene caglio animale, diventa "neither".
- **Libreria.** Lo stesso post condiviso due volte viene salvato una volta sola, anche se una volta arriva come `/p/` e l'altra come `/reel/`. Il controllo avviene **prima** di scaricare o di chiamare il modello, quindi un duplicato non costa niente.

### Schema della ricetta (`burp/models.py`)

```jsonc
{
  "title": "Pasta zucchine e menta",
  "source_url": "https://www.instagram.com/reel/XXXX/",
  "author_handle": "cucina.di.anna",
  "servings": null,
  "time_minutes": null,
  "ingredients": [
    { "canonical_name": "pasta", "original_text": "pasta corta", "quantity": null, "unit": null },
    { "canonical_name": "zucchina", "original_text": "2 zucchine", "quantity": 2, "unit": null },
    { "canonical_name": "sale", "original_text": "sale e pepe", "quantity": null, "unit": "q.b." }
  ],
  "steps": ["Dora le zucchine in padella.", "…"],
  "tags": { "cuisine": "italiana", "course": "primo", "diet": "neither" },
  "completeness": { "status": "partial", "missing": ["quantità di pasta"] }
}
```

`course` è uno tra: antipasto, primo, secondo, contorno, piatto unico, dolce, colazione, snack, bevanda, salsa. `diet` è `vegan`, `vegetarian` o `neither`.

## Installazione

Serve [uv](https://docs.astral.sh/uv/) (Python ≥ 3.13).

```sh
uv sync                    # basta per caption incollata e screenshot
uv sync --extra media      # in più: scarico dei link (yt-dlp), trascrizione (faster-whisper), frame (PyAV)
uv sync --extra media --extra cutout   # in più: scontorno locale con rembg, per il tema Zine
cp .env.example .env       # poi compila ANTHROPIC_API_KEY (e i token Telegram se usi il bot)
```

Chiavi e token si leggono dalle variabili d'ambiente o da `.env`, che git ignora. Le variabili disponibili:

| Variabile | A cosa serve |
| --- | --- |
| `ANTHROPIC_API_KEY` | obbligatoria per importare |
| `BURP_MODEL` | modello usato (default `claude-sonnet-5-5`) |
| `BURP_FAST_MODEL` | modello per i lavori piccoli: dividere i titoli, scegliere il fotogramma, «Completa con l'AI» (default `claude-haiku-5-5`) |
| `BURP_DB_PATH` | dove sta la libreria (default `data/burp.db`) |
| `BURP_MEDIA_DIR` | dove stanno le foto dei piatti (default `data/media`) |
| `TELEGRAM_BOT_TOKEN`, `TELEGRAM_ALLOWED_USER_IDS` | bot Telegram |
| `WHISPER_MODEL` | modello Whisper locale (`tiny`, `base`, `small`…) |
| `INSTAGRAM_COOKIES_FILE` | cookie per i link che richiedono il login |
| `BURP_PHOTO_FROM_REEL` | foto del piatto anche dal video del reel (spenta; solo uso personale) |
| `PEXELS_API_KEY` | tema Zine: foto degli ingredienti freschi da Pexels (gratuita su pexels.com/api) |
| `BURP_CONTACT_EMAIL` | contatto nello User-Agent verso Open Food Facts, che lo chiede alle app |
| `BURP_CUTOUT_MODEL` | modello di rembg per lo scontorno (default `silueta`, 44 MB al primo uso) |

## CLI

```sh
# importare
uv run burp import --url https://www.instagram.com/reel/XXXX/
uv run burp import --caption-file caption.txt --url https://www.instagram.com/p/XXXX/
uv run burp import --caption "testo incollato…"
uv run burp import --screenshot a.png b.png
uv run burp import --url … --dry-run          # mostra il risultato senza salvare

# cercare (i filtri si combinano; senza filtri elenca tutto)
uv run burp search carbonara
uv run burp search --tag primo --tag vegana
uv run burp search --ingredient ceci --ingredient pasta

# leggere e togliere
uv run burp show 3
uv run burp show 3 --json
uv run burp delete 3

# ricette salvate prima della divisione del titolo (nome in due righe + descrittore)
uv run burp backfill-titles --dry-run
uv run burp backfill-titles
```

Il **fallback manuale funziona sempre**: `--caption`, `--caption-file` e `--screenshot` non scaricano nulla. Se un link non si scarica (Instagram spesso chiede il login per i reel), imposta `INSTAGRAM_COOKIES_FILE` con un file di cookie in formato Netscape, oppure incolla la caption o usa uno screenshot. Con `--url` insieme a una caption o a uno screenshot, il link resta come fonte e serve per la deduplica.

Come funziona la ricerca:
- per titolo, ignorando maiuscole e accenti;
- per tag, che confronta cucina, portata o dieta (anche in italiano: "vegana", "vegetariana");
- per ingrediente, sul nome canonico: "chickpeas" trova "ceci", "pecorino" trova "pecorino romano".

## Bot Telegram

1. Crea un bot con [@BotFather](https://t.me/BotFather) e metti il token in `TELEGRAM_BOT_TOKEN`.
2. Metti il tuo id numerico in `TELEGRAM_ALLOWED_USER_IDS` (lo trovi con @userinfobot). Separa più id con una virgola.
3. Avvia il bot:

```sh
uv run burp bot
```

Inoltra al bot un link, incolla una caption o mandagli uno screenshot. Risponde con titolo, tag, completezza, fonte usata e numero nella libreria. Se il link è già in libreria te lo dice e non rifà niente. Il bot risponde solo agli id in `TELEGRAM_ALLOWED_USER_IDS`.

Per consultare la libreria dal telefono (i comandi compaiono anche nel menu di Telegram):

| Comando | Cosa fa |
| --- | --- |
| `/cerca vegana ceci` | ricette in cui **ogni parola** compare nel titolo, nei tag (cucina, portata, dieta) o negli ingredienti; senza parole mostra le ultime salvate |
| `/ricetta 3` | la ricetta completa: ingredienti con le righe originali, procedimento, cosa manca |
| `/aiuto` | cosa sa fare il bot |

## Foto del piatto

Dopo l'import, un job in background prepara la foto senza far aspettare la ricetta:

1. prende quello che mandi tu: screenshot, o un video (registrazione dello schermo, clip). Il video del reel scaricato dal link si usa **solo se accendi `BURP_PHOTO_FROM_REEL=true`** (vedi sotto);
2. dai video estrae 10 fotogrammi, 7 dall'ultimo terzo, dove di solito c'è il piatto finito;
3. un modello veloce (`BURP_FAST_MODEL`) sceglie l'immagine dove il piatto finito si vede meglio, con una confidenza e un testo alternativo. Sotto 0,5 non usa niente;
4. salva l'originale e una stampa a retino a due inchiostri (rosso a 15°, nero a 45°), con creator e link del post per l'attribuzione.

Senza una foto buona la pagina mostra solo carta e adesivi: **nessuna immagine generata**.

```sh
uv run burp import --caption-file caption.txt --video registrazione.mov
uv run burp photo 3 screenshot.jpg            # foto per una ricetta già salvata
uv run burp worker                            # esegue i job (il bot li esegue già da sé)
```

Dal bot: manda uno screenshot o un video insieme alla ricetta, oppure un'immagine con didascalia `/foto 3`. I bot Telegram non possono scaricare file oltre i 20 MB.

### Foto dal video del reel (opzionale, solo uso personale)

Con `BURP_PHOTO_FROM_REEL=true` nel `.env`, per gli import da link la foto si prende anche dal video del reel, già scaricato per la trascrizione, e la pagina la attribuisce al creator. È spenta di default per due motivi: estende uno scaricamento che i termini d'uso di Instagram vietano (raccolta automatica di contenuti), e il fotogramma è un'immagine del creator, quindi va bene in una libreria privata ma non in un'app pubblica, nemmeno con l'attribuzione. Se metti burp! online, lasciala spenta.

```sh
uv run burp photos-from-reels --dry-run   # quali ricette salvate non hanno ancora la foto
uv run burp photos-from-reels             # riscarica i loro reel una volta e mette le foto in coda
```

Dopo ogni foto i file di partenza (video e screenshot copiati) vengono cancellati: restano solo il fotogramma scelto e la sua stampa.

## Tema Zine

In `/impostazioni` scegli tra due temi: **Adesivi** e **Zine**. Dati e funzioni sono gli stessi; cambiano la pagina e una parte delle immagini.

Lo Zine è una pagina di fanzine su carta gialla: il fotogramma del piatto fotocopiato (dithering a 1 bit, macchioline di toner, ombra del coperchio, bordo strappato) con il ritaglio del piatto che ne esce, gli ingredienti come ritagli fotocopiati a forbice, la tabella delle dosi per 1, 2, 3… persone, e le note a pennarello blu generate dai dati: «io!» sulla colonna dell'1, un anello con «quanti?» attorno alle quantità mancanti, un'ondulata sotto tempi e temperature. «L'ho cucinata» scrive da sé «burp!» con la data.

Il **pennarello** (pulsante in cima alla ricetta Zine) disegna a mano libera sulla pagina, con il mouse, il dito o la penna. Ogni tratto si aggancia all'elemento che ha sotto il suo centro (la foto, il titolo, un ingrediente, un passaggio, la tabella) e si salva in millesimi della larghezza di quell'elemento: sul telefono, dove il testo va a capo in un altro modo, il cerchio attorno al tofu resta attorno al tofu. Il disegno si salva intero dopo ogni tratto (`PUT /api/recipes/{id}/drawing`), così «annulla» è solo un tratto in meno; Esc o «fatto» per uscire.

Le immagini dello Zine si preparano in background, come la foto:

- **Piatto**: la fotocopia e il ritaglio partono dal fotogramma già scelto per gli Adesivi. Il ritaglio usa rembg, in locale (extra `cutout`).
- **Ingredienti**: il modello veloce scrive le ricerche (una chiamata per ricetta), i prodotti confezionati si cercano su **Open Food Facts** (foto CC BY-SA 3.0: le nostre fotocopie ne sono derivate e restano CC BY-SA), gli altri su **Pexels** (serve `PEXELS_API_KEY`). Il modello sceglie la foto migliore tra 3-5, che viene scontornata, ritagliata a forbice e fotocopiata. Unsplash non si usa: la sua API obbliga a mostrare le immagini dai suoi indirizzi, senza modificarle.
- Ogni ingrediente si cerca **una volta sola** e si riusa in tutte le ricette. Se non c'è una foto buona resta un biglietto di carta con il nome: mai immagini generate.
- Le attribuzioni (fotografo e Pexels, prodotto e licenza Open Food Facts) sono in fondo alla pagina.

```sh
uv run burp zine-images          # stampe Zine delle foto esistenti e ingredienti di tutte le ricette
uv run burp worker --once        # le prepara (il bot lo fa da solo)
uv run burp backfill-words       # la parola nella lingua della cucina, per le ricette già salvate
```

La **parola in verticale** (per esempio もちもち, «consistenza gommosa») la scrive il modello durante l'import, solo se la cucina d'origine usa un alfabeto non latino e se è sicuro della parola.

## Web app

La dashboard è in `web/` (Next.js 16, React 19, TypeScript): vedi [web/README.md](web/README.md).

```sh
uv run burp dev            # API, bot e dashboard insieme; Ctrl+C li ferma tutti
uv run burp dev --no-bot   # solo API e dashboard (--no-web: solo la parte Python)
```

I log arrivano nello stesso terminale con il prefisso `[api]`, `[bot]` o `[web]`; se uno dei tre si ferma, `burp dev` chiude anche gli altri e dice quale. Il bot parte solo se nel `.env` ci sono `TELEGRAM_BOT_TOKEN` e `TELEGRAM_ALLOWED_USER_IDS`. Per avviarli a mano, uno per terminale:

```sh
uv run burp serve          # API su 127.0.0.1:8000
uv run burp bot            # bot Telegram (fa girare anche il worker)
cd web && pnpm dev         # http://localhost:3000
```

- **Libreria** (`/`): un foglio di adesivi, uno per ricetta, con forma e colore fissati dal suo numero e quanti dati restano da chiarire; ricerca a parole libere.
- **Ricetta** (`/ricette/3`): nome in due righe enormi, aggettivi nel fumetto con la mascotte, foto a retino con gli adesivi della dieta e delle porzioni, avviso per le quantità mancanti ("Li scrivo io" / "Sì, a occhio"), selettore da 1 a 4 persone con le dosi ricalcolate, procedimento e "L'ho cucinata".
- **Completa con l'AI**: il pulsante in cima alla ricetta (o «Stimale con l'AI» nell'avviso) chiede al modello veloce (`BURP_FAST_MODEL`, Haiku 5.5) di stimare le quantità che il reel non dice, porzioni e tempo se mancano, e di riscrivere i passaggi in modo più chiaro, dicendo cosa ha aggiunto. Le stime restano separate: compaiono con l'adesivo «stima», le tue correzioni vincono sempre, «Togli le stime» torna al reel e «Come nel reel» mostra i passaggi originali. Circa 0,1¢ a clic.
- **Adesivi** (`/adesivi`): tutti i componenti SVG su un foglio.

Per ora gira solo in locale e senza login: prima di metterla online servono autenticazione e un hosting per API e foto.

## Test

```sh
uv run ruff check . && uv run ruff format --check .
uv run pytest                                        # offline, nessuna chiamata a pagamento
ANTHROPIC_API_KEY=… uv run pytest -m live            # contro l'API vera (costa)
```

`tests/fixtures/captions/` contiene quattro caption di riferimento:

| Fixture | Caso |
| --- | --- |
| `completa.txt` | ricetta completa: deve risultare `complete` |
| `quantita_mancanti.txt` | quantità non dette: `partial`, nessuna quantità inventata |
| `vuota.txt` | caption vuota: serve il fallback su trascrizione o frame |
| `inglese.txt` | caption in inglese: la ricetta va salvata in italiano |

`tests/test_fixtures.py` le fa passare per tutta la pipeline con un modello finto e verifica le garanzie del codice: fonte scelta, completezza forzata, nomi canonici. `tests/test_structure_live.py` verifica che il modello vero si comporti come previsto, per esempio che traduca davvero la caption inglese.

## Fuori scope, per ora

UI dell'app, share sheet mobile, lista della spesa, porzioni scalabili.
