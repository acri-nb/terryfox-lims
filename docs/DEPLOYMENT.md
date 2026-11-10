# Deployment and migrations — operator runbook

This is the procedure for putting a change into production, whether or not it carries a
database migration. It is written for anyone holding `sudo` on `cair-tf-candig`. The
underlying tooling is described in [`ops/README.md`](../ops/README.md); this page is the
order of operations.

## The three rules

1. **`sudo ./ops/deploy.sh <label>` is the only way to deploy.** Never run
   `manage.py migrate` by hand on the server, and never restart the service onto new code
   without going through the script.
2. **A migration is deployed the day it reaches `main`.** The service runs straight from the
   checked-out tree, so the next reboot loads whatever code is there — and applies no
   migration. Code ahead of the database is an outage waiting for a reboot.
3. **Git on the server runs as `hadriengt`, never as root.** See
   [Updating the code on the server](#2-update-the-code-on-the-server).

## Where things are

| What | Where |
|---|---|
| Code the service runs | `/home/hadriengt/project/lims/terryfox-lims` (branch `main`) |
| Production database | `/var/lib/terryfox-lims/db.sqlite3` — outside the git tree |
| Backups | `/var/backups/terryfox-lims/{rotating,keep}/` |
| Invariant references | `/var/lib/terryfox-lims/deploy/` |
| Logs | `/var/log/terryfox-lims/{access,error,watchdog}.log` |
| Main service | `terryfox-lims.service` (gunicorn, port 443) |
| Other units | `terryfox-lims-watchdog.timer`, `terryfox-lims-backup.timer`, `terryfox-lims-v1.service` (frozen V1 archive, port 8443) |

## Procedure

### 1. Before you start: prepare the change locally

Do the development work in your own clone, not on the server.

```bash
python manage.py makemigrations          # if a model changed
python manage.py migrate
python manage.py test core
python3 ops/selftest.py
python manage.py collectstatic --noinput --settings=terryfox_lims.settings_prod   # if static/ changed
```

Commit, push to `origin/main`, and note whether the push contains a new file under
`core/migrations/`.

**If the migration adds, removes or recomputes rows**, find the expected deltas now. Doing it
during the deployment is too late. Rehearse on a copy of the latest backup:

```bash
COPY=$(mktemp -d)/rehearsal.sqlite3
sudo cp "$(sudo ls -t /var/backups/terryfox-lims/rotating/*.sqlite3 | head -1)" "$COPY"
sudo chown "$USER" "$COPY"

python3 ops/check_invariants.py --db "$COPY" --save "$COPY.before.json"
DATABASE_PATH="$COPY" python manage.py migrate
python3 ops/check_invariants.py --db "$COPY" --compare "$COPY.before.json"   # lists every delta

rm -f "$COPY" "$COPY.before.json"        # the copy holds live data: never keep it, never commit it
```

Each delta reported becomes one `--allow key=+N` (or `-N`) argument. The match is **exact**,
and every derived measure is a separate key. Adding three cases moves `core_case`,
`vivants:core_case`, `core_comment`, each `tier:*` and each `status:*` it touches. Declare
all of them, or the deployment will restore the database at step 6.

A migration that only adds a column or a table usually needs no `--allow` at all.

### 2. Update the code on the server

```bash
ssh cair-tf-candig
cd /home/hadriengt/project/lims/terryfox-lims

sudo ./ops/status.sh                                   # baseline: everything green?
sudo -u hadriengt git status --short                   # must be empty
sudo -u hadriengt git pull --ff-only origin main
sudo -u hadriengt git log --oneline -5                 # confirm you are where you think
```

Always use `sudo -u hadriengt git …`. From another account, plain `sudo git` is refused for
*dubious ownership*. From `hadriengt`'s own account it goes through and leaves root-owned
files in `.git/`, which break the next pull for everyone.
`--ff-only` refuses to create a merge on the server: if it fails, the server tree has
diverged, and that has to be understood before anything else.

From this point the tree is ahead of the database. Go straight to step 3.

### 3. Deploy

```bash
sudo ./ops/deploy.sh <label> [--allow key=+N ...]
```

The label names the backup that is kept forever. Use the migration name when there is one,
and a date plus a short SHA otherwise:

```bash
sudo ./ops/deploy.sh 0039_specimen_type_assay_labels
sudo ./ops/deploy.sh 0040_example --allow core_case=+12 --allow vivants:core_case=+12 ...
sudo ./ops/deploy.sh 2026-11-10-e5f243e          # code-only change, no migration
```

Code-only changes go through the same script: it runs `collectstatic`, restarts the service
and checks a real database read. A restart alone does none of that.

What the script does, in order:

| Step | Action | If it fails |
|---|---|---|
| — | checks that systemd answers | aborts, nothing touched |
| 1 | stops the watchdog timer and any run in flight | aborts, nothing touched |
| 2 | stops the service, refuses to continue while a `wsgi_prod` worker holds the database | aborts, service restarted |
| 3 | takes a labelled, verified backup with the database at rest | aborts, nothing migrated |
| 4 | freezes the invariants, replays your `--allow` as a dry run | aborts, nothing migrated: fix the arguments |
| 5 | `migrate`, then `collectstatic` | migrate fails → **database restored**; collectstatic fails → migrated database kept |
| 6 | compares the invariants against step 4 | undeclared drift → **database restored** |
| 7 | restarts, waits for an answer, proves an ORM read works | reported, **not** restored: the data is fine |

Expect a short outage of under a minute while the service is stopped. Whatever happens, the
script restarts the service and the watchdog on exit.

### 4. Verify

```bash
sudo ./ops/status.sh                      # no pending migration, units active, backups fresh
tail -20 /var/log/terryfox-lims/error.log
```

Then log in through the browser and open a project page. The login page never touches
`Case`, so it is the one page that keeps working when the schema is wrong. It proves
nothing.

## When it goes wrong

**Step 6 restored the database.** The data is back to its pre-migration state, but the tree
still holds the new code. Every authenticated page will now return 500 while `/` keeps
answering 302. Put the code back in line with the database before you leave:

```bash
sudo -u hadriengt git log --oneline -5
sudo -u hadriengt git checkout <last commit before the migration>
sudo systemctl restart terryfox-lims.service
sudo ./ops/status.sh                      # must report no pending migration
```

The tree is now on a detached `HEAD`. Fix the `--allow` arguments, or the migration itself,
then `git checkout main` and deploy again.

**Step 7: the application does not answer.** The database is migrated and verified, so do
not restore it. Read `systemctl status terryfox-lims.service` and
`/var/log/terryfox-lims/error.log`.

**A 500 with nothing in `error.log`.** With `DEBUG=False` and no `LOGGING` block, Django
sends tracebacks nowhere. To diagnose it, reproduce the error: copy a backup as in step 1,
bring it to the suspected migration level, and replay the request with
`DATABASE_PATH=<copy> python manage.py runserver 8001`.

**Going back to an earlier backup by hand:**

```bash
sudo ./ops/restore_db.sh                  # lists the 20 most recent backups and prompts
sudo ./ops/restore_db.sh <file>
```

The script verifies the backup before touching anything. The database it replaces is kept as
`<db>.remplacee-<stamp>` and never deleted. After a restore, check again that the code
matches the schema (`status.sh`).

## After a reboot

A reboot deploys whatever is checked out. Check that nothing is pending before you consider
the application healthy:

```bash
sudo ./ops/status.sh
```

If it lists a pending migration, run `sudo ./ops/deploy.sh <label>`. Do not just restart the
service: a restart applies no migration. The watchdog logs the same condition every five
minutes in `watchdog.log`, and it deliberately does not restart anything.

## Do not

- run `manage.py migrate`, `loaddata` or `flush` against `/var/lib/terryfox-lims/db.sqlite3`
  by hand;
- run `git` on the server as root, or commit from the server;
- leave a migration committed on `main` without deploying it the same day;
- copy the production database, or any backup of it, into the repository. The remote is
  public;
- widen the `wsgi_prod` process patterns in `ops/lib.sh`, `gunicorn_start_robust.sh` or
  `watchdog.sh`. A broader pattern catches the V1 archive, which makes `deploy.sh` refuse to
  migrate.
