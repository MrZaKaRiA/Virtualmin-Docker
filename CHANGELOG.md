# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/) and the project uses
[Semantic Versioning](https://semver.org/).

## [1.3.0] - 2026-06-23

Made for non-technical users: every risky button now explains itself, and
destructive actions show exactly what will be deleted before acting.

### Added
- **Pinned project identity**: every project action passes an explicit
  `--project-name` taken from `docker compose ls`, so Docker always upgrades
  the *existing* stack in place — same containers, same volumes, same data —
  even if `name:`, `COMPOSE_PROJECT_NAME` or the directory changed since the
  stack was created. Without this, `up` silently builds a second stack with
  empty volumes. The advanced form accepts an optional project name too.
- **Old-copy detection**: warns on the dashboard and in red on the Update page
  when a standalone container runs the same application as a Compose project
  (old copy keeps the domain, port and data; the new project starts empty).
- **Update action** for Compose projects — pulls the image versions set in
  `docker-compose.yml` / `.env` and recreates the containers (a plain restart
  never applies a new version). Available as one-click buttons on the Compose
  page, a bold **Update** link on every compose-managed container, and a
  dedicated explanation page (`update.cgi`) describing what will happen.
- **One-click per-project Compose actions** (Update / Restart / Stop / Start /
  Logs / Status / Down) using each project's own recorded compose file — no
  path typing. Projects show the Virtualmin domain they belong to.
- **Deletion previews**: Maintenance now shows live, red-tagged lists of
  exactly what a prune would delete — stopped containers, unused volumes,
  leftover images — flagged **DATABASE** and **belongs to domain X** where
  detected. The same listing appears on every confirmation page.
- Plain-language help notes throughout: container actions, Compose button
  legend, prune descriptions, volume-removal warnings.

### Fixed
- **"Compose file not found"** when using the default relative
  `docker-compose.yml` path — relative paths were resolved against the module
  directory. The manual form now requires a full path with a clear message,
  and the per-project buttons remove the need to type paths at all.
- Manual Compose **Down** now asks for confirmation (red warning when
  volume removal is selected).

## [1.2.0] - 2026-06-23

### Added
- **Virtualmin integration**: the container list now shows the Virtualmin
  domains/subdomains whose Website Proxy Settings point at each container
  (matched by published host port), linked through to the site. Toggle in
  Module Config; silently empty on non-Virtualmin hosts.
- **Ports column** in the container list (de-duplicated host→container mapping).

### Fixed
- Rename (and copy / commit / export) reported "Invalid or unknown container
  reference" after succeeding: the redirect builder appended `?` to a URL that
  already had a query string, corrupting the `id` parameter. It now appends `&`
  when needed.

## [1.1.0] - 2026-06-23

### Added
- **Backup & restore**: save/load images (`docker save`/`load`), commit a
  container to an image, export a container's filesystem, and back up / restore
  local volumes as `.tar.gz` (via host `tar`). Gated by a new `backup` ACL and a
  configurable default backup directory.
- A clear **Remove container** action on the container Manage tab (in addition
  to the bulk Remove in the list).
- The **home-screen widget is now clickable** — its title, counts and an
  "Open Docker" link go straight into the module.

### Changed
- Default ACL is now **full access** (the installing admin), tightened per-user
  as needed — previously the least-privilege defaults hid delete/exec/prune even
  from the admin.
- Fixed the page footer showing "Return to Return to Docker" (the theme already
  prepends "Return to").

## [1.0.0] - 2026-06-23

Initial release. A clean, security-first Webmin module for managing Docker.

### Security
- All Docker commands are built from constant flags plus single-quote-escaped
  user values (`sq()`); no user input is ever interpolated raw into a shell.
- Identifiers (container/image/volume/network names and ids) are allowlist
  validated before use.
- Every state change is handled by a single POST-only dispatcher (`act.cgi`),
  covered by Webmin's trusted-referer check, ACL-gated, and recorded with
  `webmin_log`.
- Registry passwords are passed to `docker login --password-stdin` via the
  child process's standard input and are never stored or placed on a command
  line.
- Per-user ACL controls for view / manage / create / delete / exec / prune /
  registry / context, shipping least-privilege defaults.

### Added
- **Overview dashboard** with running/paused/stopped/image counts and
  `docker system df` disk usage.
- **Home-screen widget** (`system_info.pl`) showing Docker status on the
  Webmin dashboard.
- **Containers**: list, start, stop, restart, pause, unpause, kill, remove,
  rename, update resources, clone, and bulk select-and-act.
- **Per-container**: logs with timestamps / since / filter / auto-refresh and
  download, inspect, non-interactive exec with quick-command buttons, live
  stats, host<->container copy.
- **Images**: list, inspect, history, remove, pull, push, tag, build from an
  inline Dockerfile, run a new container, Docker Hub search, and prune.
- **Compose**: project listing plus up / down / status / logs / validate.
- **Storage**: volumes and networks - list, inspect, create, remove, prune.
- **Maintenance**: system prune and build-cache prune with confirmations.
- **Security**: image scanning via Docker Scout or Trivy (the removed
  `docker scan` is not used).
- **Registry** login and **Docker context** switching.
- **Monitors** for "System and Server Status": Docker Up and Container Up.
