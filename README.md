# FullStackIn – Django War Simulator (Hard)

Proiect CodeRun 7. Partea Hard: înregistrarea persoanelor de la API-ul challenge-ului
și „drafting” (recrutare) prin task-uri Celery în fundal, descărcate în paralel, cu retry la timeout.

**Împărțire:** backend (modele, task-uri Celery, view-uri, teste) + frontend
(template-uri în `army/templates/army/`, CSS/JS în `static/`).

## Ce face

1. **Peacetime** – task-ul `register_people` descarcă lista de la `/people` și o salvează în DB.
   Persoana „Hellstorm Fireburn” are `key = "draft-info"`, care duce la instrucțiunile de drafting.
2. **Drafting în paralel** – la „Start drafting” se lansează **simultan** câte un task `download_batch`
   pentru fiecare batch `/draft/0` … `/draft/9` (câte 10 persoane). Imediat ce un batch e descărcat,
   pornește task-ul lui separat de recrutare (`draft_batch`), care setează `rank` și `health`.
   Un batch lent sau picat nu le mai blochează pe celelalte.
3. **Retry** – la timeout sau eroare de rețea, fiecare batch reîncearcă singur cu backoff exponențial
   (1s, 2s, 4s … max 60s, până la 10 reîncercări). Batch-urile care tot eșuează sunt marcate `failed`.
   Dacă API-ul raportează un `next_batch` în plus față de cele 10, e descărcat și acela.
4. **Migrare DB** – `0001_register_people` creează persoanele fără rang;
   `0002_drafting` adaugă `rank`, `health`, `drafted_at` și modelul `DraftBatch` (progres pe batch).

API-ul challenge-ului: `https://coderun2026-csbwf4haa4d0gubu.westus3-01.azurewebsites.net`.
Uneori răspunde foarte greu sau deloc – de asta sunt retry-ul și timeout-ul configurabil.

## Instalare (o singură dată)

### Windows
```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env      # pune o SECRET_KEY generată
python manage.py migrate
```

### Fedora
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # pune o SECRET_KEY generată
python manage.py migrate
```

### Secret key
```bash
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```
Pune rezultatul în `.env` la `SECRET_KEY=`. Fără `.env` proiectul nu pornește (intenționat).

## Pornire

Aplicația are nevoie de **două terminale deschise în același timp**, ambele în folderul proiectului
și cu venv-ul activat.

### Terminal 1 – serverul web (Django)

| Windows | Fedora |
|---|---|
| `.\venv\Scripts\Activate.ps1` | `source venv/bin/activate` |
| `python manage.py runserver` | `python manage.py runserver` |

### Terminal 2 – worker-ul Celery (task-urile din fundal)

| Windows | Fedora |
|---|---|
| `.\venv\Scripts\Activate.ps1` | `source venv/bin/activate` |
| `celery -A config worker -P threads -c 10 -l info` | `celery -A config worker -P threads -c 10 -l info` |

- `-P threads` – worker-ul rulează task-urile pe thread-uri (merge identic pe Windows și Linux).
- `-c 10` – 10 task-uri simultan, adică toate cele 10 batch-uri se descarcă în paralel.
- `-l info` – vezi în terminal fiecare task, retry și eroare.
- După orice modificare în `army/tasks.py` sau `.env`, **repornește worker-ul** (`Ctrl+C` și din nou comanda).

### Apoi, în browser

1. http://127.0.0.1:8000/people/import/ – pornește importul persoanelor (`/people`)
2. http://127.0.0.1:8000/draft/ – apasă **Start drafting** și urmărești batch-urile live
3. http://127.0.0.1:8000/ – registrul cu toți soldații, filtrabil după rang

### Utile

```bash
python manage.py test army          # teste (API-ul e simulat, nu depind de server)
python manage.py createsuperuser    # apoi http://127.0.0.1:8000/admin/
```

Verifică dacă serverul challenge-ului răspunde (Windows: `curl.exe`):
```bash
curl -m 20 https://coderun2026-csbwf4haa4d0gubu.westus3-01.azurewebsites.net/people
```

## Configurare (`.env`)

| Variabilă | Implicit | Ce face |
|---|---|---|
| `SECRET_KEY` | – (obligatoriu) | cheia Django |
| `DEBUG` | `False` | `True` local |
| `ALLOWED_HOSTS` | gol | `localhost,127.0.0.1` local |
| `CHALLENGE_API_TIMEOUT` | `15` | câte secunde așteaptă o cerere spre API (recomandat `60`) |
| `CHALLENGE_BATCH_COUNT` | `10` | câte batch-uri se descarcă în paralel |
| `CHALLENGE_API_URL` | host-ul challenge-ului | alt API (ex. unul local pentru teste) |
| `CELERY_EAGER` | `False` | `True` = task-urile rulează direct, fără worker (doar teste rapide) |

Nu e nevoie de Redis: broker-ul Celery e un fișier SQLite în `.celery/` (ignorat de git).

## Pentru frontend

Template-urile sunt în `army/templates/army/` și extind `base.html`
(blocuri: `title`, `head`, `content`, `scripts`). CSS/JS în `static/css/` și `static/js/`.

| URL | Template / răspuns | Ce face |
|---|---|---|
| `/` sau `/people/` (`?rank=General`, `?page=2`) | `people_list.html` | registrul de persoane |
| `/people/<pk>/` | `person_detail.html` | detaliile unei persoane |
| `/people/import/` | `import.html` | panoul de import |
| `POST /people/import/start/` | 202 JSON / redirect | pornește înregistrarea |
| `GET /people/import/status/` | JSON | progresul importului + cheia lui Hellstorm |
| `/draft/` | `draft.html` | pagina de drafting |
| `POST /draft/` | 202 JSON / redirect | pornește drafting-ul (toate batch-urile în paralel) |
| `GET /draft/status/` | JSON | progres live: `registered`, `drafted`, `ranks`, `batches` |

- `Person`: `external_id`, `name`, `age`, `key`, `rank`, `health`, `registered_at`, `drafted_at`, `is_drafted`
- `batches` – listă de `{"number", "status", "attempts", "people_count", "error"}`
- statusuri batch: `downloading`, `retrying`, `downloaded`, `drafted`, `failed`
- POST-urile au nevoie de token CSRF (`{% csrf_token %}` sau header `X-CSRFToken`)

Exemplu `GET /draft/status/`:
```json
{
  "registered": 100,
  "drafted": 100,
  "ranks": [{"rank": "General", "count": 31}],
  "batches": [{"number": 0, "status": "drafted", "attempts": 1, "people_count": 10, "error": ""}]
}
```

## Structură

```
config/            setări Django, celery.py, urls
army/models.py     Person, DraftBatch
army/tasks.py      task-urile Celery (register, download paralel, draft, retry)
army/views.py      paginile + endpoint-urile JSON de status
army/templates/    template-urile (frontend)
static/            CSS + JS
army/tests.py      teste cu API simulat
```

## Lucru în echipă (git)

```bash
git pull                          # înainte să începi
git checkout -b frontend          # lucrează pe branch-ul tău
git add . && git commit -m "..."
git push -u origin frontend       # apoi faci Pull Request pe GitHub
```

Nu urca `.env`, `venv/`, `db.sqlite3` sau `.celery/` – sunt deja în `.gitignore`.
Pe Windows, nu adăuga linii în `.gitignore` cu `echo ... >>` din PowerShell (le scrie în UTF-16
și strică fișierul) – editează-l direct în editor.
