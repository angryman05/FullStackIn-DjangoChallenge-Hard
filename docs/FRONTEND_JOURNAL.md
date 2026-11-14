# Frontend Journal & Backend Integration Contract
*Document for AI agent and backend developer collaboration on Django War Simulator (Hard Challenge).*

---

## 1. Intent
The frontend provides a tactical dark command center for General Deadlock's army during the Hard Challenge. It coordinates Phase 1 peacetime population ingestion from the deliberately slow external API, displays a sortable, searchable, and paginated registry with Hellstorm Fireburn highlighted (revealing his `<key>`), and orchestrates Phase 2 military drafting into combat ranks and health statistics.

### Core Design Decisions & Rationale
1. **Zero direct external API calls from browser:** The browser calls Django endpoints only. All external requests are managed via Celery tasks to handle Azure timeouts and retries safely.
2. **Short-polling over WebSockets:** Standard `fetch` polling (every 1.0s–1.5s) was chosen to avoid WebSocket/ASGI server overhead, enabling simple deployment on standard WSGI/Gunicorn with minimal moving parts.
3. **Generic model attribute inspection on Detail view:** The remote JSON shape and soldier attributes are subject to change. Iterating dynamically through `person._meta.fields` ensures future fields render without template rewrites.
4. **Vanilla JS with textContent only:** Strictly avoiding `innerHTML` with untrusted data prevents XSS from arbitrary names or keys returned by remote endpoints.
5. **Progressive enhancement on sorting:** Semantic HTML `<table>` with clickable header buttons, ARIA sort attributes, and DOM reordering without destroying existing elements or focus state.

---

## 2. LIVE CONTRACT

### 2.1 GET `/people/import/`
- **Caller:** Direct navigation via browser or navbar link.
- **Handler:** `army.views.people_import` [IMPLEMENTED BY BACKEND]
- **Request:** GET, standard headers.
- **Response:** 200 HTML (`army/import.html`).
- **Template Context:**
  - `key_person`: `Person | None` (Hellstorm Fireburn record if already downloaded)
  - `registered`: `int` (Total count of registered citizens)
  - `drafted`: `int` (Total count of drafted citizens)
  - `ranks`: `list[dict]` (`[{"rank": "General", "count": 1}, ...]`)
  - `batches`: `list[dict]` (`[{"number": 0, "status": "drafted", ...}, ...]`)

### 2.2 POST `/people/import/start/` (and `/people/register/`)
- **Caller:** `static/js/importer.js` (via `#start-import-btn`) and fallback `<form>` submit.
- **Handler:** `army.views.register_view` [IMPLEMENTED BY BACKEND]
- **Request:**
  - Headers: `X-CSRFToken: <csrftoken>`, `Accept: application/json`
  - Body: empty or form payload
- **Response:**
  - AJAX: 202 Accepted `{"job_id": "people-register", "status": "running"}`
  - Form submit: 302 Redirect to `/people/import/`

### 2.3 GET `/people/import/status/`
- **Caller:** `static/js/importer.js` (polled every 1.0s).
- **Handler:** `army.views.import_status` [IMPLEMENTED BY BACKEND]
- **Request:** GET, `Accept: application/json`.
- **Response:** 200 OK JSON:
  ```json
  {
    "status": "idle" | "running" | "done" | "error",
    "total": 120,          // int or null if total unknown (triggers indeterminate bar)
    "processed": 120,      // int
    "failed": 0,           // int
    "started_at": null,    // ISO string or null
    "finished_at": null,   // ISO string or null
    "error": null,         // string or null
    "key_found": true,     // boolean
    "key_value": "draft-0" // string
  }
  ```
- **Status Enum Values:** `idle`, `running`, `done`, `error`.

### 2.4 GET `/people/` (and `/`)
- **Caller:** Browser navigation.
- **Handler:** `army.views.people_list` [IMPLEMENTED BY BACKEND]
- **Request:** Query params: `?page=<int>&rank=<str>`
- **Response:** 200 HTML (`army/people_list.html`).
- **Template Context:**
  - `people`: `Page` (Iterable page object of `Person` instances: `pk`, `external_id`, `name`, `age`, `rank`, `health`, `key`, `is_drafted`)
  - `page_obj`: `Page` (Django Paginator page object for pagination controls)
  - `all_people_count`: `int` (Total unpaginated count)
  - `selected_rank`: `str | None`
  - `key_person`: `Person | None` (Hellstorm Fireburn record)
  - `registered`: `int`
  - `drafted`: `int`
  - `ranks`: `list[dict]` (`[{"rank": str, "count": int}]`)
  - `batches`: `list[dict]`

### 2.5 GET `/people/<pk>/`
- **Caller:** Links from registry table.
- **Handler:** `army.views.person_detail` [IMPLEMENTED BY BACKEND]
- **Request:** GET, pk in URL path.
- **Response:** 200 HTML (`army/person_detail.html`).
- **Template Context:**
  - `person`: `Person` model instance
  - `fields`: `list[dict]` (`[{"name": "external_id", "verbose_name": "External Id", "value": 1, "is_key": false}, ...]`)

### 2.6 GET `/draft/`
- **Caller:** Browser navigation.
- **Handler:** `army.views.draft_view` [IMPLEMENTED BY BACKEND]
- **Request:** GET.
- **Response:** 200 HTML (`army/draft.html`).
- **Template Context:**
  - `key_person`: `Person | None`
  - `registered`: `int`
  - `drafted`: `int`
  - `ranks`: `list[dict]`
  - `batches`: `list[dict]` (`[{"number": int, "status": str, "attempts": int, "people_count": int, "error": str}]`)

### 2.7 POST `/draft/` (and `/draft/start/`)
- **Caller:** `static/js/draft.js` (`#start-draft-btn`) or form POST.
- **Handler:** `army.views.draft_view` [IMPLEMENTED BY BACKEND]
- **Request:** Headers: `X-CSRFToken: <csrftoken>`, `Accept: application/json`.
- **Response:** 202 Accepted `{"status": "running", "message": "Drafting started"}` or 302 Redirect.

### 2.8 GET `/draft/status/`
- **Caller:** `static/js/draft.js` (polled every 1.5s).
- **Handler:** `army.views.draft_status` [IMPLEMENTED BY BACKEND]
- **Request:** GET, `Accept: application/json`.
- **Response:** 200 OK JSON:
  ```json
  {
    "registered": 120,
    "drafted": 45,
    "ranks": [
      { "rank": "General", "count": 1 },
      { "rank": "Lieutenant", "count": 4 }
    ],
    "batches": [
      {
        "number": 0,
        "status": "drafted",
        "attempts": 1,
        "people_count": 10,
        "error": ""
      }
    ]
  }
  ```
- **Batch Status Enum:** `downloading`, `retrying`, `downloaded`, `drafted`, `failed`.

---

## 3. DOM & File Map

### Files Created / Maintained
- `static/css/styles.css`: Single unified command center stylesheet. Responsive, dark theme (`#090d16`), accessible focus rings, `<progress>` bar styling, table sort icons, toast positioning.
- `static/js/main.js`: Global toast notification engine (`Toast.show`), CSRF extraction, copy-to-clipboard chip interactions.
- `static/js/importer.js`: Controls `/people/import/`, manages 1s polling, timer stopwatch, indeterminate/determinate progress, error panel.
- `static/js/people.js`: Client-side search and accessible column sorting (`aria-sort`, `Intl.Collator`, DOM row reordering).
- `static/js/draft.js`: Phase 2 live batch telemetry polling, batch cards rendering, and soldier mobilization trigger.
- `templates/army/base.html`: Common layout with command center header, DEFCON status badge, message-to-toast bridge, navigation, and toast container.
- `templates/army/import.html`: Page 1 Ingestion control panel.
- `templates/army/people_list.html`: Page 2 Population registry, search, filters, table, pagination, Hellstorm row callout.
- `templates/army/person_detail.html`: Page 3 Generic personnel dossier inspecting all model fields dynamically.
- `templates/army/draft.html`: Page 4 Phase 2 war room with key display, instructions, batch telemetry cards, and rank distribution.
- `templates/404.html`: Custom 404 Radar Lost page.

### Critical DOM Identifiers (Do NOT rename or change in backend)
- `#toast-container`: Root container for floating toast notifications.
- `#start-import-btn`: Button triggering peacetime registration.
- `#retry-import-btn`: Retry button in the error panel.
- `#import-status-badge`: Badge reflecting `IDLE`, `RUNNING`, `DONE`, `ERROR`.
- `#import-progress-bar`: Native `<progress>` element.
- `#progress-percent`: Text element reflecting progress percentage.
- `#counter-downloaded`: Downloaded citizen counter.
- `#counter-saved`: Saved citizen counter.
- `#counter-failed`: Failed batch counter.
- `#elapsed-time`: Active timer display (`MM:SS`).
- `#error-panel`: Container for import errors (`.visible` class toggled).
- `#error-message-text`: Text content container for error description.
- `#secret-key-banner`: Panel surfacing Hellstorm Fireburn's key.
- `#secret-key-chip`: Click-to-copy button containing key value.
- `#people-search-input`: Client-side search input filter.
- `#people-table`: Table element containing citizens roster.
- `[data-type="number|text"]`: Attribute on `<th>` determining sort algorithm.
- `tr.key-person-row`: Row highlighting Hellstorm Fireburn.
- `[data-person-id]`: Attribute on `<tr>` with database PK.
- `[data-copy]`: Attribute containing exact string copied to clipboard.
- `#start-draft-btn`: Button triggering Phase 2 batch drafting.
- `#draft-status-badge`: Phase 2 status badge.
- `#batch-cards-container`: Container receiving dynamically rendered batch status cards.
- `#rank-breakdown-container`: Container receiving rank distribution badges.

---

## 4. Open Questions for Backend
1. **Total Count during Peacetime Registration:** Does the remote `/people` endpoint return a total count header or envelope metadata before the full list completes downloading?
   - *Current assumption:* The total is unknown during active downloading (frontend displays indeterminate sliding animation), then sets to total records once saved.
   - *Impact if wrong:* Determinate percentage can be rendered sooner if `total` is supplied.
2. **Phase 2 Secret Key Scheme:** Is `<key>` strictly the relative URL path to the first batch (e.g. `draft/0`) or an authentication token?
   - *Current assumption:* The backend task uses `payload.get("key")` or starts at batch 0 (`download_batch.si(0)`).
   - *Impact if wrong:* If `<key>` defines an arbitrary endpoint path, the task entrypoint should accept the key dynamically.

---

## 5. Change Log

### Entry 1: 2026-11-14 11:35
- **What was built:** Complete Hard Challenge frontend architecture.
- **Files touched:**
  - `config/settings.py` (added `STATICFILES_DIRS`, updated `TEMPLATES['DIRS']`)
  - `config/urls.py` (added `handler404`)
  - `army/urls.py` (added routes for `/people/import/`, `/people/import/status/`, `/draft/`, `/people/`)
  - `army/views.py` (added `people_import`, `import_status`, updated `people_list` with pagination, updated `person_detail` with dynamic fields, updated `draft_view` for GET/POST, added `custom_404`)
  - `static/css/styles.css` (custom dark theme, progress bar, tables, badges, toasts)
  - `static/js/main.js` (toast system, copy chips, CSRF)
  - `static/js/importer.js` (control panel polling, progress tracking, stopwatch)
  - `static/js/people.js` (instant client search, accessible sorting)
  - `static/js/draft.js` (live batch telemetry, rank distribution)
  - `templates/army/base.html`, `templates/base.html`, `templates/army/import.html`, `templates/army/people_list.html`, `templates/army/person_detail.html`, `templates/army/draft.html`, `templates/404.html`
  - `army/tests.py` (added `test_frontend_pages_and_contracts` verifying all endpoints and templates)
- **Contract Change:** CONTRACT CHANGE: Added `GET /people/import/` and `GET /people/import/status/` alongside existing `draft/status/` to support the dedicated control panel. Made `GET /draft/` return the HTML war room view.
- **Manual Verification:** Tested via `python manage.py test` (5/5 tests passing in 0.36s).

---

## 6. Integration Checklist
- [x] `TEMPLATES['DIRS']` configured in `config/settings.py`
- [x] `STATICFILES_DIRS` configured in `config/settings.py`
- [x] `GET /people/import/` rendered with status and start controls
- [x] `POST /people/import/start/` connected to `register_people.delay()`
- [x] `GET /people/import/status/` returns status and counts JSON
- [x] `GET /people/` renders table with pagination (`page_obj`) and search/sort
- [x] `GET /people/<id>/` generic field iteration over `person._meta.fields`
- [x] `GET /draft/` renders Phase 2 instructions and live batch cards
- [x] `POST /draft/` triggers `start_drafting.delay()`
- [x] `GET /draft/status/` polled for live batch progress
- [x] Custom 404 page configured and verified
- [x] All 5 Django backend & frontend unit tests passing
