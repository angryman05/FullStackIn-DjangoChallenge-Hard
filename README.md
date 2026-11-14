# FullStackIn – Django War Simulator (Hard)

Proiect CodeRun 7. Partea Hard: înregistrarea persoanelor de la API-ul challenge-ului
și „drafting” (recrutare) prin task-uri Celery în fundal, cu retry la timeout.

**Împărțire:** backend-ul e gata (modele, task-uri Celery, view-uri, teste).
Frontend-ul (template-urile din `army/templates/army/`) e doar un schelet funcțional – de stilizat.

## Ce face

1. **Peacetime** – task-ul `register_people` descarcă lista de la `/people` și o salvează în DB.
   Persoana „Hellstorm Fireburn” are `key = "draft-info"`, care duce la instrucțiunile de drafting.
2. **Drafting** – fiecare batch `/draft/<n>` (0–9, câte 10 persoane) e descărcat de un task separat
   (`download_batch`). Imediat ce un batch e descărcat, pornește task-ul lui de recrutare (`draft_batch`),
   care setează `rank` și `health`, iar în paralel se descarcă batch-ul următor (`next_batch`).
3. **Retry** – la timeout sau eroare de rețea, task-urile reîncearcă cu backoff exponențial
   (1s, 2s, 4s … max 60s, până la 10 reîncercări). Batch-urile care tot eșuează sunt marcate `failed`.
4. **Migrare DB** – `0001_register_people` creează persoanele fără rang;
   `0002_drafting` adaugă `rank`, `health`, `drafted_at` și modelul `DraftBatch` (progres pe batch).

API-ul challenge-ului: `https://coderun2026-csbwf4haa4d0gubu.westus3-01.azurewebsites.net`
(configurabil cu `CHALLENGE_API_URL` în `.env`). Uneori răspunde greu sau deloc – de asta e retry-ul.

## Instalare

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

## Pornire (două terminale, ambele cu venv activat)

```bash
python manage.py runserver
celery -A config worker -l info -P solo     # -P solo e obligatoriu pe Windows, merge și pe Linux
```

Deschide http://127.0.0.1:8000/ și apasă **Start drafting**. Progresul se actualizează singur.

- Nu e nevoie de Redis: broker-ul Celery e un fișier SQLite în `.celery/` (ignorat de git).
- Fără worker? Pune `CELERY_EAGER=True` în `.env` și task-urile rulează direct în request (doar pentru teste rapide).
- Admin: `python manage.py createsuperuser`, apoi http://127.0.0.1:8000/admin/
- Teste (API-ul e simulat, nu depind de server): `python manage.py test army`

## Pentru frontend

Toate template-urile sunt în `army/templates/army/` și extind `base.html`
(blocuri: `title`, `head`, `content`, `scripts`). Poți schimba HTML-ul/CSS-ul liber,
doar păstrează numele variabilelor din context și URL-urile.

| URL | Template / răspuns | Ce primești în context |
|---|---|---|
| `/` (filtru: `?rank=General`) | `people_list.html` | `people`, `selected_rank`, `registered`, `drafted`, `ranks`, `batches` |
| `/people/<pk>/` | `person_detail.html` | `person` |
| `POST /people/register/` | redirect la `/` | pornește doar înregistrarea |
| `POST /draft/` | redirect la `/` | pornește înregistrarea + drafting-ul complet |
| `GET /draft/status/` | JSON | la fel ca `/`, fără `people` – pentru progres live (polling) |

- `people` – listă de `Person`: `external_id`, `name`, `age`, `key`, `rank`, `health`,
  `registered_at`, `drafted_at`, `is_drafted`
- `ranks` – listă de `{"rank", "count"}` (ranguri văzute: Private, Sergeant, Lieutenant, General)
- `batches` – listă de `{"number", "status", "attempts", "people_count", "error"}`
- statusuri batch: `downloading`, `retrying`, `downloaded`, `drafted`, `failed`
- formularele POST au nevoie de `{% csrf_token %}`
- link spre o persoană: `{% url 'army:person_detail' p.pk %}`

Exemplu `GET /draft/status/`:
```json
{
  "registered": 100,
  "drafted": 100,
  "ranks": [{"rank": "General", "count": 31}],
  "batches": [{"number": 0, "status": "drafted", "attempts": 1, "people_count": 10, "error": ""}]
}
```

Fișiere CSS/JS/imagini: pune-le în `army/static/army/` și folosește `{% load static %}`.

## Structură

```
config/            setări Django, celery.py, urls
army/models.py     Person, DraftBatch
army/tasks.py      task-urile Celery (register, download, draft, retry)
army/views.py      paginile + /draft/status/
army/templates/    template-urile (frontend)
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
