# Virtualmin-Docker: fix plan for the reported issues + ease-of-use improvements

Date: 2026-10-09. Based on a fresh clone of `main` (f99411b, v1.5.2) and the
two open GitHub issues. Nothing in the repo has been changed yet; the fix was
verified on a scratch copy only.

---

## 1. The two issues are one bug

| Issue | Reporter sees | Where it happens |
| --- | --- | --- |
| #1 | `docker::list_system_info failed : Undefined subroutine &docker::foreign_available ... system_info.pl line 14` | Opening a Virtualmin Pro support ticket (and any page that builds the System Information dashboard) |
| #2 | `docker::load_theme_library failed : Undefined subroutine &docker::load_theme_library called at (eval 285) line 2` | Webmin Users -> user -> Docker ACL page |

**Root cause.** The five "hook" files that Webmin loads *from other modules*
all start with:

```perl
do './docker-lib.pl';
```

The `./` makes it a path relative to the **current working directory**. Webmin's
`foreign_require()` (web-lib-funcs.pl) does not change directory when called
from inside another module. It only puts the Docker module directory on `@INC`
and then evaluates `package docker; do '/usr/share/webmin/docker/<hook>'`.
So when the ACL editor runs from `/usr/share/webmin/acl`, or the dashboard runs
from the theme or `virtual-server` directory, `./docker-lib.pl` does not exist.
`do` fails **silently**, the hook file still returns true, and package
`docker::` ends up with no Webmin core functions at all. The first core
function touched then dies:

- `system_info.pl` calls `foreign_available` -> issue #1
- after loading `acl_security.pl`, Webmin itself evals `load_theme_library()`
  in package `docker` -> issue #2

The module's own pages never hit this because each `.cgi` uses
`require './docker-lib.pl'` and Webmin runs those with the module directory as
CWD.

Affected files (all identical one-line bug):

- `docker/acl_security.pl` (issue #2)
- `docker/system_info.pl` (issue #1)
- `docker/status_monitor.pl` (System and Server Status monitors will fail the same way)
- `docker/log_parser.pl` (Webmin Actions Log rendering will fail the same way)
- `docker/install_check.pl` (Webmin "refresh modules" auto-detect)

**Why CI did not catch it.** The release workflow only runs `perl -c` with a
stub `WebminCore`, which never executes the `do` line.

**Reproduced locally.** A stub Webmin core that mirrors `foreign_require`
(module dir on `@INC`, CWD = another directory) shows all five hooks load but
the library does not:

```
acl_security.pl    do=ok   LIB NOT LOADED
system_info.pl     do=ok   LIB NOT LOADED
status_monitor.pl  do=ok   LIB NOT LOADED
log_parser.pl      do=ok   LIB NOT LOADED
install_check.pl   do=ok   LIB NOT LOADED
```

## 2. The fix (release as v1.5.3)

Replace the loader line in all five hook files with the form core Webmin
modules use (compare `apache/acl_security.pl`, `system-status/system_info.pl`):

```perl
require 'docker-lib.pl';
```

Why `require` rather than `do 'docker-lib.pl'`:

- No `./` so Perl searches `@INC`, which `foreign_require` always primes with
  the module directory. Works from any CWD.
- `require` is idempotent. The Authentic dashboard loads `system_info.pl` and
  the status module may load `status_monitor.pl` in the same process; `do`
  would re-run the 2,000-line lib and emit 122 "Subroutine redefined" warnings
  into the Webmin error log. Verified: `require` gives zero warnings.
- `require` dies with a clear "Can't locate docker-lib.pl" if the lib is ever
  missing, instead of the silent failure that produced these two confusing
  reports.

Verified on a scratch copy: all five hooks load the lib from a foreign CWD,
two hooks in one process load cleanly, and `perl -c` passes on every file.

Steps:

1. Apply the one-line change to the five files.
2. Make the widget defensive so it can **never** break other people's pages
   again: wrap the body of `list_system_info` in `eval { }` and `return ()`
   on any error. Issue #1 shows the real cost of a crashing widget is that it
   takes the whole Virtualmin support page down with it. Do the same for
   `status_monitor_status` (return `up => -1` on an internal error).
3. Bump `docker/module.info` to `version=1.5.3`, add a CHANGELOG `[1.5.3]`
   "Fixed" entry describing the hook-loading bug.
4. Tag `v1.5.3`; the existing workflow builds and publishes `docker.wbm.gz`.
5. Reply on both issues: cause, fix version, and "re-install from the
   latest-release URL (settings and ACLs are kept)". Close after confirmation.

## 3. Add a real regression test to CI

Add `tests/foreign-load.t` (plain Perl, no CPAN deps) plus a slightly richer
`tests/stub/WebminCore.pm` that injects no-op `init_config`, `has_command`,
`foreign_available`, `load_theme_library` into the caller package, the way the
real `WebminCore` does. The test, for each hook file:

- `chdir` to a temp directory that is *not* the module dir,
- put `docker/` on `@INC`,
- `eval "package docker; do '<abs>/docker/<hook>' || die"`,
- assert `defined &docker::sq` and that the hook's own entry point
  (`acl_security_form`, `list_system_info`, `status_monitor_list`,
  `parse_webmin_log`, `is_installed`) exists,
- load two hooks in one process under `-w` and assert no warnings.

Wire it into `release.yml` next to the `perl -c` step, and run the whole check
job on `push` and `pull_request` too, not only on tags. Today nothing is
tested until the moment a release is cut.

## 4. Make the module easier to install, upgrade, and use

Ordered by value for effort. Items 4.1 to 4.4 can ship with 1.5.3 or right
after; the rest is a 1.6.0 batch.

### 4.1 One-command install / upgrade (`install.sh` in the repo)

A documented script that downloads the latest `docker.wbm.gz` from GitHub
releases, runs `/usr/share/webmin/install-module.pl`, and prints the URL of
the module page. Same script upgrades in place. README gets an "Option 0"
with the one-liner and a note that the GitHub-URL install inside Webmin still
works. Also add an **Uninstall** section (Webmin Configuration -> Webmin
Modules -> Delete) which is missing today.

### 4.2 README fixes

- The Screenshots table points at `docs/screenshots/dashboard.png` and
  `widget.png` which do not exist, so the README shows two broken images.
  Either add real screenshots or remove the table until they exist.
- Add a **Troubleshooting** section listing the two error strings from the
  issues with "upgrade to 1.5.3 or later", and the common Docker-side causes
  (socket permissions, snap Docker path, rootless socket needing a context).
- Add a short "Requirements check" table: Webmin version tested, Docker
  Engine version tested, Compose v2.

### 4.3 First-run experience in the module

Today, if Docker is not installed, the index page prints one sentence and
stops. If the daemon is unreachable it prints Docker's raw error. Improve:

- Not installed: show the official install command for the detected distro
  (apt / dnf) in a code block, plus a "Re-check" link.
- Daemon unreachable: map the three common raw errors to plain-language hints:
  "permission denied on /var/run/docker.sock" -> socket group / rootless
  context; "Cannot connect to the Docker daemon" -> `systemctl start docker`;
  "context not found" -> fix the override in Module Config / Contexts.

### 4.4 Repo hygiene

- `.claude/settings.local.json` is committed; remove it and add `.claude/` to
  `.gitignore`.
- Add a tiny `Makefile` (or `tools/build.sh`) with `make test` (perl -c +
  foreign-load test) and `make package` (the tar command from the README), so
  contributors and CI run the same thing.

### 4.5 Widget and monitor robustness (beyond the eval in step 2)

- The dashboard widget runs `docker info` on every Webmin home-page load. Cache
  the summary for ~30 seconds in `$module_var_directory` so a slow daemon does
  not slow every dashboard render.
- Honour `widget_enabled=0` before touching Docker at all (already done) and
  skip the widget entirely for users without the `view` ACL.

### 4.6 Guided Compose deploy (largest usability win, 1.6.0)

The Compose page already has per-project buttons. Add a "New project" form:
project name, directory (default under the Virtualmin domain's home), paste
`docker-compose.yml`, optional `.env`, then **Deploy** = `compose up -d`.
Pair it with the existing proxy "Fix now" so a non-technical user can go
from pasted compose file to a live domain without the shell.

### 4.7 Smaller UX items

- "Pull & recreate" (Update) button directly in the container row is already
  there; add a confirm-and-show-diff of image digests before/after.
- Container list: remember the last sort/filter per user (Webmin
  `$userconfig`), add a text filter box.
- Logs page: "tail -f" style auto-refresh already exists; add a "copy to
  clipboard" button.

## 5. Suggested replies to the issues

**#1 (rushowr):** "Thanks, and sorry for the breakage. Root cause: the
dashboard widget file loaded the module library with a path relative to the
current directory, which is wrong when Webmin loads it from another module
(the Virtualmin support page builds the System Information dashboard). Fixed
in v1.5.3; re-install from the latest-release URL and the error disappears.
Your settings and ACLs are preserved."

**#2 (imsergiobernal):** "Great report. Not a Webmin 2.670 incompatibility:
`acl_security.pl` used `do './docker-lib.pl'`, which fails silently when the
ACL editor loads the file from `/usr/share/webmin/acl`, so Webmin's own
`load_theme_library()` call found an empty `docker::` package. Fixed in
v1.5.3 (now `require 'docker-lib.pl'`, resolved via @INC like core modules).
Re-install from the latest-release URL."

## 6. Effort

| Item | Effort |
| --- | --- |
| Section 2 fix + defensive eval + version bump + changelog + release | about 1 hour |
| Section 3 regression test + CI on push/PR | about 1 hour |
| 4.1 to 4.4 | 2 to 3 hours |
| 4.5 to 4.7 | 1 to 2 days, can be split |
