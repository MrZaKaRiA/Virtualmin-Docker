# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/) and the project uses
[Semantic Versioning](https://semver.org/).

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
