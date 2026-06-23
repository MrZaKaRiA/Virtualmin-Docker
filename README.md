<div align="center">

# 🐳 Virtualmin Docker

### A clean, security-first Webmin & Virtualmin module for managing Docker from your browser

Containers · images · volumes · networks · Compose · backups · vulnerability scanning —
with a live dashboard widget and **Virtualmin reverse-proxy awareness**.

[![License: GPL v2](https://img.shields.io/badge/License-GPLv2-blue.svg)](LICENSE)
[![Webmin module](https://img.shields.io/badge/Webmin-module-FF6600.svg)](https://webmin.com)
[![Virtualmin](https://img.shields.io/badge/Virtualmin-integrated-2E7D32.svg)](https://virtualmin.com)
[![Version](https://img.shields.io/badge/version-1.2.0-success.svg)](CHANGELOG.md)
[![Hardened](https://img.shields.io/badge/shell--injection-hardened-brightgreen.svg)](#-security-model)

</div>

---

> **Why another Docker module?** Because a panel that runs **as root** has no business
> pasting your input into a shell. Every Docker command in this module is built from
> constant flags plus individually escaped values — proven, not promised
> (see [Security model](#-security-model)). On top of that it's fast, responsive, and
> it knows which of your Virtualmin sites proxy to which container.

If you want a full standalone Docker UI, look at [Portainer](https://www.portainer.io).
This module is for people who already live in **Webmin / Virtualmin** and want Docker
management that fits right in — under **Servers → Docker**.

## ✨ Highlights

- 🔒 **Injection-proof by construction** — no user input ever reaches `/bin/sh` unescaped.
- 🧭 **One-glance dashboard** — running/paused/stopped counts, disk usage, and a clickable home-screen widget.
- 🌐 **Virtualmin-aware** — see the domains/subdomains reverse-proxied to each container, right in the list.
- 🧰 **Everything you actually do** — full lifecycle, bulk actions, images, Compose, storage, backups, scanning.
- 👥 **Granular access control** — grant or deny each capability per Webmin user.
- 📝 **Audited** — every change is written to the Webmin Actions Log.

## 📸 Screenshots

> Drop your own PNGs into `docs/screenshots/` — they'll render here.

| Dashboard & containers | Home-screen widget |
| --- | --- |
| ![Dashboard](docs/screenshots/dashboard.png) | ![Widget](docs/screenshots/widget.png) |

## 🚀 Features

<table>
<tr><td valign="top" width="50%">

**Dashboard**
- Running / paused / stopped / image counts
- `docker system df` disk-usage breakdown
- Clickable **home-screen widget** on the Webmin dashboard

**Containers**
- List with live CPU / memory, **ports**, and **proxied domains**
- Start · stop · restart · pause · unpause · kill
- Remove · rename · update resources · clone
- **Bulk select-and-act** on many at once
- Per-container **logs** (timestamps, since, filter, auto-refresh, download),
  **inspect**, non-interactive **exec** with quick-command buttons, live **stats**

**Images**
- List · inspect · history · remove · pull · push · tag
- Build from an inline Dockerfile · run a new container
- **Docker Hub search** · prune

</td><td valign="top" width="50%">

**Compose**
- List projects + up / down / status / logs / validate (v2, with v1 fallback)

**Storage**
- Volumes & networks: list · inspect · create · remove · prune

**Backup & restore**
- Images: `save` / `load` to a host tar
- Containers: commit to an image · export the filesystem
- Volumes: back up & restore a local volume as `.tar.gz`

**Maintenance**
- `system prune` & `builder prune`, each with a confirmation

**Security**
- Image scanning via **Docker Scout** or **Trivy**

**Registry & contexts**
- Private-registry login · switch Docker context (rootless-friendly)

**Monitoring**
- "Docker Up" & "Container Up" monitor types for **System and Server Status**

</td></tr>
</table>

## 🌐 Virtualmin integration

Running Docker behind Virtualmin virtual servers? When a site has **Website Proxy
Settings → Proxying enabled** pointing at a local port (e.g. `http://localhost:3000`),
this module matches that port to the container publishing it and shows the
domain right in the container list:

| Name | Status | Image | Ports | Proxied to |
| --- | --- | --- | --- | --- |
| `server-1` | 🟢 Up (healthy) | `image/image` | `3000->3000/tcp` | [example.com](#) |

It reads Virtualmin's domain definitions read-only, links each domain through to
the live site, and **degrades silently to nothing on non-Virtualmin hosts**. Turn it
off any time in **Module Config**.

## 🔒 Security model

This is the whole reason the module exists.

| Guarantee | How |
| --- | --- |
| **No shell injection** | Every value from a form, config, or Docker output is wrapped with a single-quote escaper (`sq()`); constant flags stay literal. Verified by round-tripping `$()`, backticks, `;`, `\|`, `&&`, newlines and `-v /:/host` through a real `/bin/sh`. |
| **Allowlist validation** | Container/image/volume/network identifiers are checked against anchored regexes before use — rejecting control characters, leading dashes and path traversal. |
| **POST-only, referer-checked, audited** | All mutations go through one dispatcher (`act.cgi`) reached only by POST, gated by ACL, and logged with `webmin_log`. |
| **Secrets via stdin** | Registry passwords are fed to `docker login --password-stdin` over the child's STDIN — never on argv, never via `echo`, never stored. |
| **XSS-safe output** | All Docker output (names, statuses, error text) is HTML-escaped before display. |
| **Confirmations** | Destructive actions (remove / prune / restore) ask first. |

## 📦 Requirements

- A host running **Webmin** (or **Virtualmin**)
- The Docker engine + CLI (`docker`) available to the Webmin user
- Perl `JSON::PP` (ships with Perl 5.14+)
- Optional: `docker compose` (v2), and `docker scout` or `trivy` for scanning

## ⚙️ Installation

1. Download **`docker.wbm.gz`** from the [latest release](../../releases/latest).
2. In Webmin go to **Webmin Configuration → Webmin Modules → From uploaded file**,
   choose the package, and click **Install Module**.
3. Open it under **Servers → Docker**. The dashboard widget appears once the
   **System and Server Status** module is installed and enabled.

Build it yourself from a checkout:

```sh
tar -czf docker.wbm.gz docker     # top-level dir in the archive must be "docker"
```

## 🛠️ Configuration

**Module Config** (top-left cog) exposes:

- Show live CPU/memory stats in the list
- Show Virtualmin domains proxied to each container
- Default number of log lines · show the dashboard widget
- Confirm before destructive actions
- Preferred image scanner (auto / Docker Scout / Trivy)
- Default Compose file path · default backup directory · Docker context override

## 👥 Access control

Under **Webmin Users → _user_ → Docker**, grant or deny each capability
independently: **view · manage · create · delete · exec · prune · backup ·
registry · context**. The default grant is **full access** (you're the admin) —
tighten it per-user as needed.

## 🧩 Rootless Docker

Supported via [Docker contexts](https://docs.docker.com/engine/manage-resources/contexts/).
Create a context for the rootless socket, then `docker context use <name>` or set
the context override in the module's **Contexts** page.

## 🗂️ Module layout

| File | Purpose |
| --- | --- |
| `docker-lib.pl` | Secure core: shell quoting, validation, every Docker operation, Virtualmin proxy lookup |
| `index.cgi` | Overview dashboard + container management |
| `container.cgi` | Per-container logs / inspect / exec / stats / manage / backup |
| `images · compose · storage · maintenance · security · registry · contexts .cgi` | Section pages |
| `act.cgi` | The single POST action dispatcher (ACL-gated, audited) |
| `system_info.pl` | Home-screen dashboard widget |
| `status_monitor.pl` | Monitor types for System and Server Status |
| `acl_security.pl` · `defaultacl` | Per-user access control |
| `log_parser.pl` · `install_check.pl` | Audit-log rendering · Docker auto-detection |

## 🤝 Contributing

Issues and pull requests are welcome. Every `.cgi`/`.pl` file is validated with
`perl -c` in CI, and changes to command construction should keep the `sq()` +
allowlist discipline described above.

## 📜 License

Copyright © 2026 MrZaKaRiA.

This program is free software; you can redistribute it and/or modify it under the
terms of the [GNU General Public License version 2](LICENSE) as published by the
Free Software Foundation. It is distributed **without any warranty** — see the
license for details.

---

<div align="center">
<sub>Built for the Webmin & Virtualmin community. Not affiliated with Docker, Inc.</sub>
</div>
