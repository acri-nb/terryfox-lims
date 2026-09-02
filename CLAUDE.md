# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

TerryFox LIMS — a Django 5 Laboratory Information Management System for ACRI tracking research
projects, cases, specimens, sequencing coverage and tier classification. Server-rendered Django
templates (Bootstrap 5 + crispy-forms), SQLite, deployed with Gunicorn over HTTPS behind systemd.

**The `origin` remote is public** (`github.com/acri-nb/terryfox-lims`), and two things are
already published in it. The database was tracked for 55 commits before being moved out of the
tree, so `git show <old-sha>:db.sqlite3` still returns a working SQLite file with ~1500 cases,
their Biobank IDs, the comments and the accounts — removing a file from HEAD does not remove its
blobs. And `.env` is tracked in HEAD with the production `SECRET_KEY` in it. Both were known and
accepted when the repo was kept open; neither is fixed by the rules below.

What the rules below *do* prevent is making it worse. Nothing new goes in: no live database, no
patient identifier, no real Biobank ID in a screenshot or a fixture.

## Commands

The application runs in the conda env named `django`
(`source ~/miniconda/etc/profile.d/conda.sh && conda activate django`). Use it for local work.

**`ops/` scripts do not all use it, and that is deliberate.** Only `deploy.sh` activates conda,
and only around its two `manage.py` calls. `backup_db.py`, `check_invariants.py`, `selftest.py`,
`lint_templates.py`, `restore_db.sh` and `install.sh` are stdlib-only and run under the system
`python3` — which is also what the hourly backup unit executes. Coupling the last line of defence
to the environment most likely to be broken would defeat its purpose. `status.sh` calls the env's
interpreter by absolute path instead.

```bash
# Development server (uses terryfox_lims/settings.py, DEBUG=True)
python manage.py runserver

# Migrations — locally only. On the server, see ops/deploy.sh below.
python manage.py makemigrations && python manage.py migrate

# Tests — 144: 137 methods across 19 classes in core/tests.py, plus 7 in
# core/test_e2e_livefilter.py that skip unless node + jsdom are present.
python manage.py test core
python manage.py test core.tests.TierCalculationTests       # one class
python3 ops/selftest.py                                     # the invariant gate itself

# Tier logic check — standalone script, NOT a Django test (calls django.setup() itself)
python test_tier_criteria.py

# Recompute tiers on all existing cases after changing tier thresholds
python update_tier_b_criteria.py

# Static files. Required after ANY change to static/ or to a {% static %} reference:
# production uses manifest storage, and a stale manifest 500s every page at render.
python manage.py collectstatic --noinput --settings=terryfox_lims.settings_prod

# Regenerate the README screenshots (needs playwright + chromium) — see Screenshots below
python ops/screenshots.py
```

Production. Four units are installed, not two: `terryfox-lims.service`,
`terryfox-lims-watchdog.timer`, `terryfox-lims-backup.timer`, and `terryfox-lims-v1.service`
(the frozen V1 archive — see below).

```bash
sudo ./ops/status.sh                       # the read-only "what is the state of production"
sudo systemctl {status,restart,stop} terryfox-lims.service
sudo journalctl -u terryfox-lims.service -f
tail -f /var/log/terryfox-lims/{access,error,watchdog}.log
```

The main service runs `gunicorn_start_robust.sh` → `gunicorn terryfox_lims.wsgi_prod:application`
bound to `0.0.0.0:443` with self-signed certs from `/root/ssl/`. Requires root (port 443). The
other `start_*.sh` scripts at the repository root are older launch paths kept around; prefer the
systemd service.

## Architecture

Single Django app `core` plus project package `terryfox_lims`.

- `core/models.py` (~830 lines) — ProjectLead → Project → Case → {Specimen, Accession, Comment},
  plus `IdentifierSequence`, `BatchOperation`, `SpecimenStatusChange`, `Favorite`
- `core/views.py` (~1365 lines) — all function-based views, no CBVs
- `core/forms.py` (~790 lines) — ModelForms + the batch/CSV/filter/user-management forms
- `core/statuses.py` — the status vocabulary and the V1 mapping
- `core/exports.py` — CSV and ZIP exports, stdlib only
- `core/urls.py` — flat URL table for the whole app
- `templates/core/` — roughly one template per view

### Three settings modules, layered

`terryfox_lims/settings_base.py` holds everything common. `settings.py` (dev) and
`settings_prod.py` (prod) import it with `from .settings_base import *` and override only what
genuinely differs. Module names are unchanged, so `wsgi`, `wsgi_prod`, the systemd units and the
start scripts keep working.

The production database lives **outside the git tree** at `/var/lib/terryfox-lims/db.sqlite3`,
set through `DATABASE_PATH` in `.env`. `db.sqlite3` is no longer tracked, so no git command can
reach the **current** data — but the snapshots committed before the move are still in history
and still readable (see *Project* above).

`.env` is committed. `settings_prod.py` reads exactly eight of its keys through
`python-decouple`: `SECRET_KEY`, `DATABASE_PATH`, the five `EMAIL_*`, and `DEFAULT_FROM_EMAIL` —
which does not carry the `EMAIL_` prefix, so grepping for it finds five and looks short one. The other four
(`ALLOWED_HOSTS`, `SECURE_SSL_REDIRECT`, `SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE`) are
**hard-coded in `settings_prod.py` and ignored in `.env`** — editing them there changes nothing,
which is exactly the kind of silent no-op that costs an afternoon.

## Data model

### Tier is derived, never user-supplied

`Case.save()` unconditionally overwrites `self.tier` with `calculate_tier()` from the coverage
values (`dna_t_coverage`, `dna_n_coverage`, `rna_coverage`). Rules: FAIL if either DNA value is
missing or <30X; A if DNA(T)≥80 & DNA(N)≥30 & RNA≥80; B otherwise when DNA(N)≥30 and DNA(T)≥30.

Setting `tier` in a form or in the admin has no effect — both end in `Case.save()`, and
`CaseForm` does not even expose the field. **Writes that skip `save()` do not**: `loaddata`
(`DeserializedObject.save()` calls `save_base(raw=True)`, which bypasses any model-defined save),
`bulk_create` and `queryset.update()` store whatever value they carry. A case bulk-created with
DNA(T)=1 and DNA(N)=1 keeps the field default `A` instead of `FAIL`, and gets no ACC either.
`Project.soft_delete()` depends on that bypass on purpose: `self.cases.update(deleted_at=…)` must
archive without recomputing a single tier.

Changing a threshold does **not** retroactively update rows — existing cases must be re-saved
(see `update_tier_b_criteria.py`). Criteria history is in `docs/TIER_CRITERIA_UPDATED.md` and
`docs/CHANGELOG_TIER_UPDATE.md`.

### Identifiers, priority, project kind

`Case.acc_number` carries the LIMS-generated number and `Case.name` mirrors it as `ACC-%04d` for
display and exports — **but only for cases the LIMS numbered itself**. `save()` allocates only
when `acc_number` is NULL *and* `name` is empty, so a case created with a name of its own keeps
`acc_number = NULL` for good. That is the CSV path, which writes `CaseID` straight into `name`
and only back-parses a number when it matches `ACC-(\d+)`. Migration 0021 left the same holes on
purpose; SQLite treats NULLs as distinct in a unique index. The consequence to watch:
`resubmit()` on such a case builds the next attempt with no number and no name, so `save()` hands
it a brand-new ACC instead of keeping the old identifier.

`IdentifierSequence.allocate(n)` hands out numbers with UPDATE-then-SELECT (SQLite has no
`select_for_update`) and never reuses a freed one — a retired ACC may already be on a freezer
label. `save()` also strips `biobank_id` and turns a blank one into NULL, so `' N-BBN 42'` and
`'N-BBN 42'` cannot become two identifiers.

`other_id` is now `biobank_id`, indexed and searched alongside the ACC by both the project filter
and the global `/search/` view. ACC uniqueness is a DB constraint; biobank ID uniqueness is a
**soft** check in `Case.find_biobank_id_conflict()` that names the conflicting case and can be
overridden — two projects legitimately share a bare numbering space.

`Case.is_priority` leads `Case.Meta.ordering` and `project_detail` restates it, so priority cases
top **the project case list**. The pin does not survive an explicit `order_by` elsewhere:
`/search/` sorts by ACC alone, and the favorites page comes out in the order stars were added.
Both still show the flag without lifting the row.

`Project.kind` separates research projects from `Referred Cases`, but it is **not on
`ProjectForm`** (`fields = ['name', 'description', 'project_lead']`): a project's kind is set at
creation by the migration or from the shell, and no screen can change it afterwards.

### Specimens and the derived case status

`Specimen` holds the three independently-trackable entities inside a case — `normal_dna`,
`tumour_dna`, `tumour_rna` — which map 1:1 onto the old flat coverage columns (`dna_n`, `dna_t`,
`rna`). Those columns stay on `Case` as a **mirror**, so `calculate_tier()` is untouched and the
tier distribution is provably unchanged by the migration.

**The mirror does not maintain itself.** `Specimen.save()` calls `case.sync_from_specimens()`, so
the mirror, the derived status and the tier stay in phase for every write that goes through
`save()` — `update_fields` included. Anything that bypasses `save()` must re-sync by hand:
`ensure_specimens()` creates through `bulk_create` and therefore calls `sync_from_specimens()`
right after, and the same obligation falls on any future `bulk_update` or `queryset.update()`.
`sync_from_specimens()` returns immediately when the case has no specimen — overwriting the
coverages of a V1 case not yet split into specimens with NULL would be data loss, not a refresh.

`Case.status` is derived too (`editable=False`): it is the least advanced specimen status **among
those whose state is known**, so a case whose DNA is analysed and whose RNA is still
`unknown_legacy` keeps reading "Analysis complete" instead of regressing. The pending specimen is
surfaced by the `to_classify` annotation and its filter, not by dragging the badge down.

The vocabulary lives in `core/statuses.py`: 10 statuses in 3 stages, plus `unknown_legacy` for
rows inherited from V1. `statuses.from_any()` accepts v1 slugs and v1 labels so existing CSVs
still import. A case is never forced to three specimens — `ensure_specimens(types)` takes the
list, and P10_Prostate has no RNA specimen at all. `ensure_specimens()` only ever *adds*: it
never deletes or converts an existing specimen, which is why unchecking a type on an existing
case cannot silently destroy its coverage.

### Intake: who, and how it was preserved

`Case.created_by` is `SET_NULL` on a `User` FK — a departure must not delete the cases someone
entered — and nullable, because the 1329 pre-V2 cases have no known author. The page says
*intake not recorded* and the export leaves the column empty rather than inventing an audit
trail. There are **four** creation paths (single, batch, CSV, resubmit) and all four record the
author; a resubmit records whoever relaunched it, not the original author, since that is a
distinct act. A CSV import that *updates* a pre-existing case leaves its author alone —
`created_by` is only set inside the `if created:` branch.

`Specimen.preservation` (FF / FFPE / Other / Not recorded) lives on the **specimen**, not the
case: the normal is usually blood while the tumour may be FFPE, so one value per case would
record something false for one of them. Intake still asks only once and applies it to all — the
same split already used for status — and the per-specimen panel corrects the odd one.
`Not recorded` is never offered at entry: it is the state of the 3955 pre-existing specimens, not
an answer. A `carry_forward` specimen keeps its preservation through a resubmit; it is physically
the same sample.

Preservation is the one field the CSV import does not carry: its header is a contract with files
already in circulation, so imported cases get `Not recorded`.

### Resubmit

`Case.resubmit()` archives the current attempt and opens the next one under the **same ACC**. It
archives *before* creating: the ACC uniqueness constraint is conditioned on
`deleted_at IS NULL AND is_archived = False`, so creating first would briefly leave two active
cases sharing a number and trip it. Nothing is copied — comments, coverage and statuses stay
physically on the archived row, which is what "the old case's history is archived" asks for.
`carry_forward` reuses the specimens that are still good. `Case.objects` hides archived attempts;
`all_objects` and `previous_attempts()` reach them, and their pages render read-only.

### Soft delete

`Project` and `Case` inherit `SoftDeleteModel`: the delete views set `deleted_at` instead of
issuing a `DELETE`. `objects` hides removed rows, `all_objects` sees everything, and
`base_manager_name = 'all_objects'` keeps FK traversal working. Deleting a project used to
cascade — measured at 256 cases plus their comments on P06.

There is **no restore view, and no admin path either**. `deleted_at` is `editable=False`, so it
is on no admin form; and neither `CaseAdmin` nor `ProjectAdmin` overrides `get_queryset`, so the
admin reads `_default_manager` — the alive-only one, not the `all_objects` that
`base_manager_name` sets. A removed row is neither listed nor openable there.

Restore from the shell, through the model methods, never by editing the field:
`Case.all_objects.get(pk=…).restore()`. For a project use `Project.restore()` and nothing else —
`soft_delete()` stamped the project *and* its live cases with one shared timestamp, so clearing
the project's own `deleted_at` gives back a project whose cases are all still invisible.

### Favorites

`Favorite(user, case)` with a `UniqueConstraint` — a double submit must be a no-op, and the view
uses `get_or_create` so the constraint never surfaces as an error. `favorite_toggle` is
`@require_POST`: a GET link would be followed by browser prefetch or a crawler and would silently
change someone's list. It honours a `next` field and falls back to the case page, so pruning the
list from `/favorites/` does not bounce you elsewhere on every removal. No edit permission is
required — a favorite is a bookmark, not lab data, and a viewer needs it as much as an editor.
Soft-deleted and archived cases **stay** in the list, labelled; dropping them silently would read
as a lost favorite.

## Permissions

Two different mechanisms, and a third thing that is not a mechanism at all.

- **Model permissions** guard Project (create / update / delete), ProjectLead (all four views),
  case **creation** (`case_create`, `batch_case_create`, `csv_case_import`, `case_resubmit` →
  `core.add_case`), case **deletion** (`core.delete_case`), and bulk status
  (`bulk_status_update`, `bulk_status_undo` → `core.change_case`, its only two consumers in the
  whole repo). The `viewer` / `editor` groups are auto-created by a `post_migrate` signal at the
  bottom of `core/models.py`, but their *permission assignments* are not code-managed — they are
  set in the admin / DB, which is why the suite has a `make_editor()` helper that grants them
  explicitly rather than a permissions test class.
- **Editing an existing case has no model permission at all.** There is no `case_update` view and
  no such URL: the case fields, the specimens and coverages, the status, the accessions and the
  comments are all POST branches of `case_detail`, which carries only `@login_required` and
  guards on an inline **group-name** test —
  `can_edit = request.user.groups.filter(name='editor').exists() or request.user.is_superuser`,
  then `and not case.is_archived`. Granting `core.change_case` to a group therefore does **not**
  open editing, and revoking model permissions does **not** close it; only literal membership of
  the group named `editor` counts.
- **Read views** (`home`, `project_detail`, `case_detail`, `case_search`, `favorite_list`, plus
  `csv_case_export` and `project_export_bundle`) carry `@login_required` and nothing else. Any
  authenticated account sees — and exports — every project of every group. There is no
  per-project access control; do not assume one exists.
- **User-management views** (`user_list`, `user_create`, `batch_user_create`, `user_update`,
  `user_delete`) and the consortium export bypass both and check `request.user.is_superuser`
  inline. Role is inferred from group membership; passwords are auto-generated by
  `_generate_password()` and shown once.

Templates decide whether to show edit controls from a `can_edit` flag the view computes, not from
`perms.*`. Changing a decorator without changing that flag leaves buttons on screen that lead to
a 403.

## Operations tooling (`ops/`)

**Never run `manage.py migrate` by hand on the server.** `sudo ./ops/deploy.sh <label>` is the
only path, and the `sudo` is not optional. The five **shell** scripts (`deploy.sh`,
`restore_db.sh`, `install.sh`, `install_v1_archive.sh`, `status.sh`) test `$EUID` and abort
without it — `status.sh` included, read-only though it is, because the database and the logs
belong to root. The Python ones test nothing: `python3 ops/selftest.py` runs fine as your own
user, which is why the Commands block above shows it without `sudo`.

`deploy.sh` runs **seven** steps: it stops the watchdog (which otherwise restarts the service
mid-migration), takes a verified labelled backup, freezes invariants, **stops the service** and
refuses to continue while any `wsgi_prod` worker still holds the database, runs `migrate` *and*
`collectstatic`, re-compares invariants, then restarts and verifies that the app answers. A
deployment is a short outage, not a hot swap.

The restore is not a blanket. A failed `migrate` restores; undeclared drift restores; a failed
`collectstatic` leaves the migrated database in place; and an app that does not answer within
three minutes is reported *without* restoring, because the data is fine and throwing it away
would be the worse error.

**Declaring an expected drift is exact, not a ceiling.** `check_invariants.py` accepts a delta
only when `--allow key=+N` matches it precisely, and every derived measure is its own key —
sanctioning three new cases in the selftest takes seven flags (`core_case`, `vivants:core_case`,
`core_comment`, `tier:A`, `tier:B`, `tier:FAIL`, `status:completed`). Declaring only the obvious
one means the deployment reaches step 6, finds undeclared deltas, and auto-restores.

The fourteen scripts (plus `README.md`, and the `systemd/` and `v1/` subdirectories):

| File | What it is for |
|---|---|
| `deploy.sh` | the only sanctioned migration path (above) |
| `check_invariants.py` | the gate: counts, tiers, statuses, orphans, duplicates. Pure SQL, no Django |
| `selftest.py` | proves the gate still catches what it claims to |
| `backup_db.py` | online SQLite backup, re-read and recounted after writing. 48 hourly / 30 daily / 12 monthly; `--label` keeps forever under `keep/` |
| `restore_db.sh` | the whole way back. With no argument it lists the twenty most recent backups and prompts; verifies before touching anything; never deletes the database it replaces (set aside as `<db>.remplacee-<stamp>`). `deploy.sh` calls it with `--force`, so a change here changes both paths |
| `status.sh` | the read-only "what is production doing": units, HTTP, pending migrations, backups, free space, invariants. Calls the conda interpreter by absolute path — a hand-typed `manage.py showmigrations` picks the base python and dies on `No module named 'decouple'`, which reads exactly like an outage when nothing is wrong |
| `lib.sh` | shared shell helpers, home of the `wsgi_prod` pgrep pattern and the deliberately generous `wait_for_app` budget |
| `install.sh` | one-shot: moved the database out of the git tree, installed the backup timer. Already run here |
| `install_v1_archive.sh` | one-shot: installed the frozen V1 archive. Already run here |
| `lint_templates.py` | template width lint, run from inside `StaticAssetTests` |
| `render_report.py` | Markdown → PDF with the app's own tokens and vendored Plex fonts. Needs `markdown` + `weasyprint`, which are **not** in `requirements.txt` |
| `seed_demo.py` | synthetic demo database for screenshots (below) |
| `screenshots.py` | regenerates `docs/screenshots/` via Playwright (below) |
| `live_filter_harness.js` | the jsdom harness `core/test_e2e_livefilter.py` drives |

Hourly verified backups run from `terryfox-lims-backup.timer`. Full details in `ops/README.md`.

### The frozen V1 archive

A **second instance runs on the same machine**: `/opt/terryfox-lims-v1`, unit
`terryfox-lims-v1.service`, port 8443, serving the V1 code against a read-only snapshot at
`/var/lib/terryfox-lims/v1-frozen.sqlite3`. It exists so the consortium can still consult
pre-migration data. `ops/v1/` holds its settings, wsgi module, read-only middleware, banner and
unit file.

Two things make it work, and both look like accidents to someone tidying up:

- **Three separate patterns name the production workers, in three files, and only one of them
  kills.** `ops/lib.sh` merely *observes* (`lims_writer_pids` → `assert_no_writers`, which is how
  `deploy.sh` refuses to migrate under a live writer). The killer is the `pkill` in
  `gunicorn_start_robust.sh`, and `watchdog.sh` carries a third. All three are narrowed to
  `wsgi_prod` on purpose: a broader pattern matched `wsgi_archive` too, so starting the main
  service killed the archive *and* `deploy.sh` mistook the archive for a writer and refused to
  migrate. Widening any of them "to catch stray workers" brings both faults back, and widening
  the `lib.sh` one alone brings back only the second — they are not interchangeable.
- **Two different files make login possible on a read-only database**, and the second looks like
  dead code. `settings_archive.py` opens SQLite with `mode=ro` and switches `SESSION_ENGINE` to
  signed cookies, because logging in writes to `django_session`. That is not enough:
  `update_last_login` writes to `auth_user`, and it is disconnected in `ops/v1/wsgi_archive.py`,
  *after* `get_wsgi_application()` and with the `dispatch_uid` Django registered it under —
  without that uid the disconnect silently does nothing.

### Screenshots

`docs/screenshots/` is regenerated by `ops/screenshots.py`, which drives Playwright against a
throwaway database seeded by `ops/seed_demo.py` with a fixed seed. **The repository is public: a
real Biobank ID in a PNG is a published identifier.** `seed_demo.py` refuses outright to run
against a non-empty database rather than trust its caller. Pointing the script at the live
database is the obvious shortcut and there is no test that would stop you.

## Front end

### Design layer

`static/css/lims.css` replaced the ~265 lines of inline Flat-UI-style CSS that V1 (2025) carried
in `base.html`. Borders rather than resting shadows; one hue per status **stage** (four colours, not ten); tier
semantics fixed (A green, B amber, FAIL red) with the letter always present — amber and red are
indistinguishable under deuteranopia, so colour never carries identity alone.

The no-shadow rule is the intent, not the current state: lims.css sets `box-shadow: none` on
`.card`, but 18 cards across 13 templates still carry Bootstrap's `.shadow-sm`, which the
vendored stylesheet declares `!important` — no lims.css rule can beat it from any position in the
cascade. Removing the utility from the template is the only fix. IBM
Plex Sans/Mono, Bootstrap and FontAwesome are all **vendored under `static/`**: no CDN at runtime.

**`lims.css` is linked after Bootstrap and redeclares `.form-control` / `.form-select` at equal
specificity.** For a long time that silently neutralised every Bootstrap modifier that only
refines those base classes: `.form-control-sm` and `.form-select-sm` were inert everywhere they
were used, including the bulk-status bar. There is now an explicit `.form-control-sm,
.form-select-sm` rule after the base one. Before adding a Bootstrap utility that tunes a control,
check that lims.css does not override the property later in the cascade.

`base.html` starts with `{% load static %}` — without it every page, login included, raises
`TemplateSyntaxError`. `settings_prod` configures whitenoise through `STORAGES`:
`STATICFILES_STORAGE` was **removed in Django 5.1** and had been silently inert. The manifest
storage means a missing `{% static %}` path 500s at render, so `StaticAssetTests` renders pages
with that storage active — run it before touching templates or assets, and run `collectstatic`
first or it will fail on a stale manifest. It walks a hand-maintained list, not every URL:
`user_update`, `user_delete` and `project_lead_confirm_delete` are rendered by nothing under
manifest storage, so a bad `{% static %}` in one of those three reaches production unnoticed.
Add the page to `_pages()` when you add a template.

Django's `{# … #}` is **single-line only**. A multi-line one is served verbatim into the HTML;
use `{% comment %}` for anything longer, and `StaticAssetTests` asserts no template syntax leaks
into a rendered page.

### Narrow screens

`static/css/lims.css` had **no width breakpoints at all** until the mobile pass; every flex row
was a chain of atoms with `min-width: auto` that pushed the page instead of wrapping — the
project header alone asked for ~1050px in a 360px viewport. There are now three breakpoints, all
Bootstrap's (991.98 / 767.98 / 575.98), plus four unconditional guards: `overflow-wrap` on `body`
and text blocks, `.nav-search-input` (replacing an inline `min-width` no media query could
reach), and `.alert-dismissible { padding-right: 3rem }` which restores the Bootstrap rule
`.alert` was clobbering.

`.form-control`, `.form-select` and their `-sm` variants are forced to **16px below 768px**:
anything smaller makes iOS Safari auto-zoom on focus. That is what makes `-sm` safe on a dense
panel. The rule has specificity (0,1,0) and does **not** reach the navbar search field, held at
13px by `.navbar .form-control` (0,2,0) — the 991.98 block only touches its width. That one field
still auto-zooms on an iPhone.

`ops/lint_templates.py` estimates the width each unwrapped flex row demands and fails above
336px; it runs inside `StaticAssetTests`, so the regression cannot come back quietly. It is a
static estimate over the template text, not a layout engine: it cannot see a width a stylesheet
imposes, and it will not catch a Bootstrap grid row that overflows.

### Forms: two traps that fail silently

**Never replace `field.widget`.** Assigning a fresh `forms.Select()` to style a field loses the
choices the field bound to the old widget, and the menu renders with **zero options** — no error,
no message, just a control nobody can use. That is exactly what happened to
`Specimen.preservation`; `status` survived only because its `.choices` were reassigned a few
lines later. Set the class on the widget the field already owns:
`self.fields['x'].widget.attrs['class'] = 'form-select'`.

**A Bootstrap grid row must total 12 columns.** The specimen edit panel went to 13 when
preservation was added and Bootstrap wrapped the last field onto its own line, under the label.
Nothing breaks, so no test failed — `SpecimenPanelTests` now parses the template and asserts the
sum. The current split is 2+3+3+2+2, arrived at by measuring the rendered widths in a real
browser: the longest option of each menu has to fit, and the coverage input has to leave room for
its value.

`Specimen.unit_short` ('X' / 'M') exists for that last point: `M reads` appended to a narrow
input takes most of its width, and a coverage of 90.9 displayed as `9`. The full unit stays in
the read-only table, the exports and the form labels — only the inline suffix is abbreviated.

`CaseForm.Meta.fields` is `['biobank_id', 'is_priority']` only; status and coverage are excluded
because the `Case` columns are a mirror recomputed on every write, so a form writing to them
would be overwritten. The form behaves differently on an existing instance: `specimen_types` and
`preservation` are both popped in `__init__`, because the per-specimen panel is authoritative
there and a required field would make the edit form invalid.

### Live filtering

`static/js/live-filter.js` makes the filter forms on `home`, `project_detail` and `case_search`
apply as you type (250 ms debounce) or pick, instead of requiring a click on *Filter* and then on
*Clear*. It replays the same GET request and swaps only the elements marked `data-live-region`,
matched **by id** between the current page and the parsed response. The server stays the sole
authority on what matches: nothing is hidden client-side, which would be wrong the moment a list
is paginated.

The script equips only `form[data-live-filter]`, and hides whatever carries `data-live-submit`
inside it — that is how the *Filter* button disappears once JS is running, and why the button
must keep the attribute rather than be deleted from the template. A form without
`data-live-filter` stays a plain GET form no matter how many regions surround it — and a page may carry **several** regions (the
project page swaps both `#cases-heading` and `#cases-region`, so the result count follows the
filter).

Rules the templates must respect, all covered by `LiveFilterTests`:

- the region wraps the table **and** its empty state, so its id is in the response for every
  outcome. A region rendered only when there are results vanishes on the first fruitless search
  and the previous list stays on screen, reading as a filter with no effect;
- the form stays **outside** every region, which is what keeps the caret alive while typing;
- `Clear` is always rendered with `data-live-clear` and a plain `hidden` attribute rather than
  behind `{% if request.GET %}` — the form is never re-rendered, so a conditional link would
  never come back. `form.reset()` is not used for it either: reset restores the HTML's *initial*
  values, which on a filtered page are the filter itself.

After a swap the script fires `lims:filtre` on `document`. The bulk-selection script listens for
it and rebinds; without that, checkboxes keep ticking but nothing counts them.

`LiveFilterTests` never executes a line of JavaScript — it would pass against an empty script.
`core/test_e2e_livefilter.py` closes that gap: it loads the real file into jsdom against a live
server, focuses the field and types. It skips unless `LIMS_JSDOM` is set, `node` is on the PATH
and the harness file exists — the variable is the switch, so the module stays skipped even on a
machine where jsdom is installed until you point at it:

```bash
npm install jsdom@24          # jsdom 25+ needs Node 20; 24 works on Node 18
LIMS_JSDOM=$PWD/node_modules/jsdom python manage.py test core.test_e2e_livefilter
```

### Bulk status change

`bulk_status_update` (checkboxes on the project table) applies one status to every selected case
inside a transaction, writing a `BatchOperation` plus one `SpecimenStatusChange` per touched
specimen. An `apply_to` menu says *which* specimens — "move 40 cases to Sequencing Complete" is
ambiguous once status lives on the specimen.

`BatchOperation.undo()` restores each specimen **only if it is still at the value the batch set**
— a specimen edited afterwards is left alone, so undo never overwrites later work. It is reached
from a banner on the project page that shows only the most recent batch: there is no history
view, so an undo not taken immediately is effectively gone.

Selection is ~60 lines of plain JS: select-all, shift-click range, and the sticky action bar.
The bar is rendered `hidden` and only the script reveals it, and both menus and the Apply button
live inside it — so **without JavaScript the checkboxes render but nothing can be submitted**.
The graceful-degradation claim that was here before was wrong; treat bulk status as a
JS-dependent feature.

## Exports

`core/exports.py`, stdlib only. `cases.csv` is **wide** — one row per case with a fixed block of
columns per specimen — because a PI cross-references it with a clinical sheet on `Biobank_ID`; a
long file would triple their cohort count unnoticed. The ZIP bundle adds `specimens.csv`,
`comments.csv` and `cases_archived.csv`. Archived attempts live in their own file, never behind a
state column in `cases.csv`, so a filter mistake cannot inflate a count. Every child file carries
`(ACC, Attempt)`: joining on ACC alone fans attempt-1 rows onto attempt 2 after a resubmit, and
the README says so.

Consortium-wide export is superuser-only and logged at WARNING. A PI keeps the export of their
own project, which is not gated on group membership — any authenticated user can export any
project they can open, and they can open all of them.

`_cases_queryset()` carries the `select_related` / `prefetch_related` the row builders need.
Adding a column that reaches a new relation without adding it there reopens an N+1;
`ExportTests` measures the query count against case count and will catch it. Three other tests
hold the same line — `ProjectListingTests` on the home page, `ExportTests` on the bundle, and
`FavoriteTests` on the favorites list — so a new relation touched from any of those templates has
a guard already waiting.

## CSV import

`csv_case_import` requires headers `CaseID,Status,DNAT,DNAN,RNA` plus a biobank column spelled
either `Biobank_ID` (current) or `Other_ID` (V1, still accepted because teams have files in that
shape). A template CSV lives in `static/csv/`.

It upserts **by `Case.name` within the project** — not by ACC and not by Biobank ID. `CaseID` is
taken verbatim as the name, and only back-parsed into `acc_number` when it matches `ACC-(\d+)`,
without touching `IdentifierSequence`. A file with names of its own therefore creates cases with
no ACC at all (see *Identifiers* above).

The import never writes coverage or status onto `Case`: it calls `ensure_specimens()` — creating
the three specimens on a pre-V2 case that has none — and writes to the specimens, because the
`Case` columns are a mirror that any later save would recompute.

**An empty cell means *unchanged*, not *erase*.** It used to overwrite with NULL, and since the
tier recomputes on every save, affected cases dropped silently to FAIL.

**The import is not atomic.** There is no `transaction.atomic` around the row loop: a row with an
unknown status or an unparseable number is appended to `error_rows` and skipped with `continue`,
and every row before it stays written. The page reports the counts plus an
*Import completed with some errors* warning listing the offending row numbers. A half-applied
file is the normal outcome of a bad row, not an exception.

Re-uploading is **not** idempotent. The upsert covers the case, its coverages and its statuses,
but the optional `source_other_comments` column — present in the shipped
`static/csv/template_csv.csv` — creates a `Comment` on every pass with no existence check. Import
the same file twice and every commented case carries the comment twice.

## Tests

144 tests in 19 classes plus the jsdom module. Two module-level helpers hold the suite together
and are worth knowing before adding a class:

- `make_editor(username)` creates a user in the `editor` group with its permissions granted
  explicitly — group permission assignments are not code-managed, so a test cannot rely on them;
- `envoi_creation(**champs)` builds a valid POST for `case_create` / `batch_case_create` and
  takes overrides as keyword arguments. Tests used to write that dict by hand, so every new
  required field broke all of them at once for a reason unrelated to what they check.

### Template fields must actually be rendered

`specimen_types` became required on `BatchCaseForm` during the specimens increment and was never
added to `batch_case_form.html`. The browser could therefore not submit anything valid and batch
creation was dead — while the tests passed, because they posted the field directly. They
validated the view and never the page.

`FormRenderingTests` covers **both** creation pages: it reads the required fields off the form
the view actually built, asserts the template renders each one, then posts what the page offers
and checks that cases appear. Note that it filters on `champ.required`, so a field that is
optional in the form but needed in practice still slips through. Apply the same check to any form
where a required field is added.

## Repo conventions

- The live database is **not** in the repo. Use `ops/backup_db.py` before anything that writes.
- The remote is **public**. No live data, no patient identifier, no real Biobank ID — in a
  commit, a fixture, or a screenshot.
- `.env` is committed; only eight of its keys are read (see *Three settings modules*).
- `/staticfiles/` is gitignored, but 133 files are **tracked in HEAD right now**: `.gitignore`
  never applies to an already-tracked path, so the rule was added after they went in and has no
  effect on them. `git status` stays quiet while they drift out of date. Do not add more; run
  `collectstatic` locally instead.
- `requirements.txt` pins nothing — it is a bare list of package names. `markdown`, `weasyprint`,
  `playwright` and `jsdom` are used by `ops/` tooling and are absent from it on purpose: they are
  not needed to run the application.
- Model verbose names and user-facing strings use `gettext_lazy as _`; there are no translation
  catalogs — it is convention only.
- Comments and script output are a mix of English and French. New code follows the file it lives
  in.
- The repository root holds V1 leftovers next to live tooling. Live: `manage.py`,
  `gunicorn_start_robust.sh` (what the unit runs), `watchdog.sh`, `check_production.py`,
  `test_tier_criteria.py`, `update_tier_b_criteria.py`. Superseded, kept for reference and not
  wired to anything: `gunicorn_start.sh`, `start_production.sh`, `start_production_debug.sh`,
  `start_lims_backend.sh`, `setup_nginx_production.sh`, `setup_letsencrypt.sh`,
  `setup_https_ip.sh`, `debug_network.sh`, `create_viewer_users.py`. Check `ops/` and the systemd
  units before following any of the second group.
- Never add a `Co-Authored-By` or `Claude-Session` trailer to a commit in this repository.

## Documentation

- `README.md` — user-facing overview, with the screenshots from `docs/screenshots/`
- `docs/RAPPORT_V2_SYNTHESE.md` (+ `.pdf`) — what changed in V2 and why, five pages, for the
  consortium
- `docs/RAPPORT_V2.md` (+ `.pdf`) — the same in full, eleven pages, with the measurements
- `ops/README.md` — backups, invariants, deployment, restore
- `docs/PRODUCTION.md`, `docs/NGINX_DEPLOYMENT.md`, `docs/HTTPS.md` — deployment guides written
  for earlier setups; `NGINX_DEPLOYMENT.md` in particular describes a path not in use (the
  service binds 443 directly). Verify against `ops/` and the systemd units before following them.
- `.documentation_dev.md` (mirrored as the Cursor rule `.cursor/rules/documentation_dev.mdc` —
  the two have drifted) predates most of V2. Verify against source.

Both PDFs are produced by `python3 ops/render_report.py <file.md>`.
