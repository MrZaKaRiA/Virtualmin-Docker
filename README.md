# Webmin Docker

A clean, security-first [Webmin](https://webmin.com) module for managing Docker
from your browser — containers, images, volumes, networks, Compose projects,
and image scanning — with a status panel on the Webmin home dashboard.

It is written from scratch with a single guiding rule: **no user input ever
reaches a shell unescaped.** Webmin runs as root, so a Docker management module
is a high-value target; this one is built to be safe by construction.

> If you want a full standalone Docker UI, look at
> [Portainer](https://www.portainer.io). This module is for people who already
> run Webmin and want Docker management that fits naturally inside it.

## Features

**Dashboard**
- Running / paused / stopped container counts and image count
- `docker system df` disk-usage breakdown
- A **home-screen widget** that shows Docker status in the Webmin dashboard
  (the same area as "Servers Status")

**Containers**
- List with live CPU / memory, start, stop, restart, pause, unpause, kill,
  remove, rename, update resources (memory / cpus / pids / restart policy)
- **Bulk select-and-act** on many containers at once
- Create a container (env / ports / volumes / network / limits, optional
  hardened defaults) and clone an existing one
- Per-container **logs** (timestamps, since, text filter, auto-refresh,
  download), **inspect**, non-interactive **exec** with quick-command buttons,
  live **stats**, and host ↔ container file copy

**Images**
- List, inspect, history, remove, pull, push, tag
- Build from an inline Dockerfile, run a new container from an image
- **Docker Hub search** and prune (dangling or all unused)

**Compose**
- List projects (`docker compose ls`) and run up / down / status / logs /
  validate against any Compose file (v2 plugin, with legacy `docker-compose`
  fallback)

**Storage**
- Volumes and networks: list, inspect, create, remove, prune

**Maintenance**
- `system prune` and `builder prune` (build cache), each with a confirmation

**Security**
- Image vulnerability scanning via **Docker Scout** or **Trivy**
  (the removed `docker scan` is not used)

**Registry & contexts**
- Log in to a registry for private images, and switch the Docker context the
  module talks to (rootless Docker is supported via contexts)

**Monitors**
- "Docker Up" and "Docker Container Up" monitor types for the
  [System and Server Status](https://webmin.com/docs/modules/system-and-server-status/)
  module

## Security model

This is the reason the module exists, so it is worth stating plainly:

- **No shell injection.** Webmin's command runners all execute through
  `/bin/sh -c`. Every value originating from a form, a config file, or Docker
  output is wrapped with a single-quote shell escaper (`sq()`) before it is
  placed in a command. Constant flags are literals; user values are quoted
  tokens — they can never be read as extra flags or shell metacharacters.
- **Allowlist validation.** Container / image / volume / network identifiers
  are validated against anchored regexes before use, rejecting control
  characters, leading dashes, and path traversal.
- **POST-only, referer-checked, audited mutations.** Every state change goes
  through one dispatcher (`act.cgi`) that is reached only by POST (so Webmin's
  trusted-referer check applies), is gated by a per-action ACL, and is recorded
  with `webmin_log` for the Actions Log.
- **Secrets via stdin.** Registry passwords are passed to
  `docker login --password-stdin` through the child process's standard input —
  never on the command line, never via `echo`, and they are not stored by the
  module.
- **Least-privilege ACL.** Webmin users can be granted or denied each
  capability independently (view / manage / create / delete / exec / prune /
  registry / context). New grants default to view + basic lifecycle only.
- **Output escaping.** All Docker output (names, statuses, error text) is
  HTML-escaped before display to prevent stored XSS from container labels.
- **Destructive-action confirmations** for remove and prune (configurable).

## Requirements

- A host with Webmin installed
- The Docker engine and CLI (`docker`) available to the Webmin user
- Perl `JSON::PP` (ships with Perl 5.14+)
- Optional: `docker compose` (v2) for Compose, and `docker scout` or `trivy`
  for scanning

## Install

1. Download `docker.wbm.gz` from the
   [latest release](../../releases/latest).
2. In Webmin go to **Webmin → Webmin Configuration → Webmin Modules**, choose
   **From local file** (or **From uploaded file**), select the package, and
   install.
3. The module appears under **Servers → Docker**. The dashboard widget appears
   on the Webmin home page once the **System and Server Status** module is
   installed and enabled in your dashboard settings.

To build the package yourself from a checkout:

```sh
tar -czf docker.wbm.gz docker
```

(The top-level directory in the archive must be `docker`.)

## Rootless Docker

Rootless Docker is supported through
[Docker contexts](https://docs.docker.com/engine/manage-resources/contexts/).
Create a context for the rootless socket, then either run
`docker context use <name>` or set the context override under
**Contexts** in the module (or in **Module Config**).

## Configuration

**Module Config** (top-left cog) exposes:

- Show live CPU / memory stats in the list
- Default number of log lines
- Show the dashboard widget
- Confirm before destructive actions
- Preferred image scanner (auto / Docker Scout / Trivy)
- Default Compose file path
- Docker context override

## Module layout

| File | Purpose |
|------|---------|
| `docker-lib.pl` | Secure core: shell quoting, validation, and all Docker operations |
| `index.cgi` | Overview dashboard + container management |
| `container.cgi` | Per-container logs / inspect / exec / stats / manage |
| `images.cgi`, `compose.cgi`, `storage.cgi`, `maintenance.cgi`, `security.cgi`, `registry.cgi`, `contexts.cgi` | Section pages |
| `act.cgi` | The single POST action dispatcher (ACL-gated, audited) |
| `system_info.pl` | Home-screen dashboard widget |
| `status_monitor.pl` | Monitor types for System and Server Status |
| `acl_security.pl`, `defaultacl` | Per-user access control |
| `log_parser.pl` | Renders audit-log entries |
| `install_check.pl` | Auto-detection of Docker |

## License

[MIT](LICENSE)
