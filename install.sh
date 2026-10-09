#!/bin/sh
#
# install.sh - install, upgrade or remove the Virtualmin Docker Webmin module.
#
# Usage (as root):
#   sh install.sh               install or upgrade to the latest release
#   sh install.sh v1.6.0        install or upgrade to a specific release tag
#   sh install.sh --uninstall   remove the module
#
# Upgrading is the same as installing: Webmin's install-module.pl replaces the
# module files in place and keeps /etc/webmin/docker (Module Config and the
# per-user ACLs). Nothing here is piped from the network into a shell; the
# package is downloaded to a temporary directory, checked, and then handed to
# Webmin's own installer.

set -eu

REPO="MrZaKaRiA/Virtualmin-Docker"
MODULE="docker"
PACKAGE="docker.wbm.gz"
MINISERV_CONF="/etc/webmin/miniserv.conf"

TMP_DIR=""

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

log() {
	printf '==> %s\n' "$*"
}

die() {
	printf 'install.sh: %s\n' "$*" >&2
	exit 1
}

usage() {
	sed -n '2,/^$/p' "$0" | sed 's/^# \{0,1\}//'
}

# Remove the temporary download directory. Wired to the EXIT trap below, so it
# also runs when the script dies early or is interrupted.
cleanup() {
	if [ -n "$TMP_DIR" ] && [ -d "$TMP_DIR" ]; then
		rm -rf "$TMP_DIR"
	fi
}
trap cleanup EXIT
trap 'exit 1' HUP INT TERM

# Locate the Webmin program directory. Try the usual package locations first,
# then fall back to the root= line Webmin itself writes into miniserv.conf.
find_webmin_root() {
	for dir in /usr/share/webmin /usr/libexec/webmin; do
		if [ -f "$dir/install-module.pl" ]; then
			printf '%s\n' "$dir"
			return 0
		fi
	done
	if [ -r "$MINISERV_CONF" ]; then
		dir=$(sed -n 's/^root=//p' "$MINISERV_CONF" | head -n 1)
		if [ -n "$dir" ] && [ -f "$dir/install-module.pl" ]; then
			printf '%s\n' "$dir"
			return 0
		fi
	fi
	return 1
}

# Download $1 to $2 with whichever of curl or wget is installed.
download() {
	url=$1
	out=$2
	if command -v curl >/dev/null 2>&1; then
		curl -fsSL --retry 3 -o "$out" "$url"
	elif command -v wget >/dev/null 2>&1; then
		wget -q -O "$out" "$url"
	else
		die "neither curl nor wget is installed; install one and try again"
	fi
}

# Sanity-check the downloaded package: it must be a gzip tarball and every
# entry must live under a top-level "docker/" directory, which is what Webmin
# expects for a .wbm.gz module archive.
verify_package() {
	pkg=$1
	gzip -t "$pkg" 2>/dev/null || die "$pkg is not a valid gzip file (download failed or wrong URL?)"
	listing=$(tar -tzf "$pkg") || die "$pkg is not a valid tar archive"
	[ -n "$listing" ] || die "$pkg is empty"
	bad=$(printf '%s\n' "$listing" | grep -v "^$MODULE/" | grep -v "^$MODULE\$" || true)
	if [ -n "$bad" ]; then
		die "unexpected archive layout: top-level entry must be '$MODULE/' (found: $(printf '%s' "$bad" | head -n 1))"
	fi
}

# Print the version= value from an installed module.info, if present.
installed_version() {
	info="$1/$MODULE/module.info"
	if [ -r "$info" ]; then
		sed -n 's/^version=//p' "$info" | head -n 1
	fi
}

# Best-effort Webmin URL from miniserv.conf (port= and ssl=), for the hint
# printed at the end. Falls back to a generic hint if anything is missing.
webmin_url_hint() {
	port=""
	ssl=""
	if [ -r "$MINISERV_CONF" ]; then
		port=$(sed -n 's/^port=//p' "$MINISERV_CONF" | head -n 1)
		ssl=$(sed -n 's/^ssl=//p' "$MINISERV_CONF" | head -n 1)
	fi
	if [ -n "$port" ]; then
		scheme="http"
		[ "$ssl" = "1" ] && scheme="https"
		printf '%s://%s:%s/%s/\n' "$scheme" "$(hostname 2>/dev/null || echo localhost)" "$port" "$MODULE"
	fi
}

# ---------------------------------------------------------------------------
# Argument handling
# ---------------------------------------------------------------------------

ACTION="install"
VERSION=""

case "${1:-}" in
	"")
		;;
	-h|--help)
		usage
		exit 0
		;;
	--uninstall|--remove)
		ACTION="uninstall"
		;;
	-*)
		die "unknown option '$1' (try --help)"
		;;
	*)
		VERSION=$1
		# Accept "1.6.0" as well as the release tag form "v1.6.0".
		case "$VERSION" in
			[0-9]*) VERSION="v$VERSION" ;;
		esac
		;;
esac

[ "$(id -u)" -eq 0 ] || die "this script must run as root (try: sudo sh install.sh)"

WEBMIN_ROOT=$(find_webmin_root) || die "cannot find the Webmin program directory (is Webmin installed?)"
log "Webmin found in $WEBMIN_ROOT"

# ---------------------------------------------------------------------------
# Uninstall
# ---------------------------------------------------------------------------

if [ "$ACTION" = "uninstall" ]; then
	if [ ! -d "$WEBMIN_ROOT/$MODULE" ]; then
		die "the $MODULE module is not installed in $WEBMIN_ROOT"
	fi
	if [ -f "$WEBMIN_ROOT/delete-module.pl" ]; then
		log "Removing the $MODULE module with delete-module.pl"
		perl "$WEBMIN_ROOT/delete-module.pl" "$MODULE"
		log "Done. The module and its configuration in /etc/webmin/$MODULE have been removed."
	else
		cat <<MSG
This Webmin version has no delete-module.pl. Remove the module from the UI:

    Webmin Configuration -> Webmin Modules -> Delete Modules -> tick "Docker" -> Delete

Webmin removes $WEBMIN_ROOT/$MODULE and /etc/webmin/$MODULE for you.
MSG
	fi
	exit 0
fi

# ---------------------------------------------------------------------------
# Install / upgrade
# ---------------------------------------------------------------------------

if [ -n "$VERSION" ]; then
	URL="https://github.com/$REPO/releases/download/$VERSION/$PACKAGE"
else
	URL="https://github.com/$REPO/releases/latest/download/$PACKAGE"
fi

PREVIOUS=$(installed_version "$WEBMIN_ROOT")
if [ -n "$PREVIOUS" ]; then
	log "Currently installed: $MODULE $PREVIOUS (will be upgraded in place; config and ACLs are kept)"
fi

TMP_DIR=$(mktemp -d "${TMPDIR:-/tmp}/virtualmin-docker.XXXXXX")
PKG="$TMP_DIR/$PACKAGE"

log "Downloading $URL"
download "$URL" "$PKG"

log "Checking the package"
verify_package "$PKG"

log "Installing with $WEBMIN_ROOT/install-module.pl"
perl "$WEBMIN_ROOT/install-module.pl" "$PKG"

NEW=$(installed_version "$WEBMIN_ROOT")
[ -n "$NEW" ] || die "install-module.pl finished but $WEBMIN_ROOT/$MODULE/module.info was not found"

echo
log "Installed Virtualmin Docker module version $NEW"
HINT=$(webmin_url_hint)
if [ -n "$HINT" ]; then
	echo "    Open Webmin -> Servers -> Docker, or go to $HINT"
else
	echo "    Open Webmin -> Servers -> Docker"
fi
echo "    (Reload the Webmin page if the menu entry does not show up yet.)"
