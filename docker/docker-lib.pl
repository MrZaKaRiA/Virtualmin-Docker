# docker-lib.pl
# Core library for the Docker Webmin module.
#
# SECURITY MODEL
# --------------
# Webmin's command runners (execute_command / backquote_command) all execute
# through "/bin/sh -c", so every byte of a command string is shell-interpreted.
# This module therefore NEVER interpolates raw user input into a command. The
# rules, enforced throughout this file:
#
#   1. Every value that originates from CGI input, a config file, or Docker
#      output is wrapped with &sq() (single-quote shell escaping) before it is
#      placed in a command string. Constant flags/subcommands are literals.
#   2. Identifiers (container/image/volume/network names + ids) are additionally
#      validated against an allowlist regex before use, and a value may never be
#      smuggled into a token together with a flag.
#   3. Secrets (registry passwords) are fed to the child process via STDIN with
#      --password-stdin, never on argv and never via "echo |".
#   4. Read-only commands pass $safe=1; mutations pass $safe=0 so Webmin's
#      read-only-mode veto applies.
#
# All state changes, ACL gating and &webmin_log auditing live in the CGIs; the
# functions here are side-effect helpers that return ($failed, $data_or_error).

BEGIN { push(@INC, ".."); };

use strict;
use warnings;
use WebminCore;

init_config();

our (%config, %text, %gconfig);

# JSON::PP ships with core Perl (>= 5.14). Load lazily and degrade gracefully.
my $have_json = eval { require JSON::PP; JSON::PP->import(qw(decode_json)); 1; };

# ----------------------------------------------------------------------------
# Shell-quoting and validation
# ----------------------------------------------------------------------------

# sq(STRING) - single-quote-escape ONE shell token for /bin/sh.
# Inside single quotes the only special character is "'" itself, which is
# neutralised by closing the quote, adding an escaped literal quote, and
# reopening. This defeats $(), ``, ;, |, &, spaces, globs and newlines.
sub sq
{
my ($s) = @_;
$s = '' if (!defined($s));
$s =~ s/'/'\\''/g;
return "'".$s."'";
}

# sq_all(LIST) - quote and space-join a list of tokens.
sub sq_all
{
return join(" ", map { &sq($_) } @_);
}

# Allowlist validators. Each returns true/false; they do NOT call &error so they
# are safe to use from monitors and the dashboard widget too.
sub is_valid_name
{
my ($v) = @_;
return defined($v) && $v =~ /^[A-Za-z0-9][A-Za-z0-9_.\-]{0,127}$/;
}

sub is_valid_id
{
my ($v) = @_;
return defined($v) && $v =~ /^[0-9a-f]{12,64}$/;
}

# A container/volume/network reference may be a name OR an id.
sub is_valid_ref
{
my ($v) = @_;
return &is_valid_name($v) || &is_valid_id($v);
}

# Image references: registry[:port]/namespace/repo[:tag][@sha256:...]
sub is_valid_image
{
my ($v) = @_;
return 0 if (!defined($v) || $v eq '');
return 0 if ($v =~ /[\0\n\r\s]/);     # no whitespace/control
return 0 if ($v =~ /\.\./);           # no path traversal
return 0 if ($v =~ /^-/);             # no option injection
return $v =~ m!^[A-Za-z0-9][A-Za-z0-9_./:@\-]{0,255}$!;
}

# Reject control characters / leading dash in a free path token.
sub is_clean_token
{
my ($v) = @_;
return defined($v) && $v !~ /[\0\n\r]/ && $v ne '' && $v !~ /^-/;
}

# require_ref(REF) - validate a container reference or abort the request.
sub require_ref
{
my ($v) = @_;
&is_valid_ref($v) || &error($text{'err_badref'});
return $v;
}

# ----------------------------------------------------------------------------
# Low-level command execution
# ----------------------------------------------------------------------------

sub docker_bin
{
my $p = &has_command("docker");
return $p ? &sq($p) : "docker";
}

# Returns the "--context 'name'" fragment when an override context is configured.
sub context_flag
{
return $config{'docker_context'} ? " --context ".&sq($config{'docker_context'}) : "";
}

# run_docker(ARGSTRING, [STDIN_REF], [SAFE]) -> ($failed, $stdout, $stderr)
# ARGSTRING must already be built from literal flags and &sq()-quoted values.
# $failed is true when the command exits non-zero.
sub run_docker
{
my ($argstr, $stdin, $safe) = @_;
$safe = 0 if (!defined($safe));
my $cmd = &docker_bin().&context_flag()." ".$argstr;
my ($out, $err);
my $status = &execute_command($cmd, $stdin, \$out, \$err, 0, $safe);
my $failed = ($status != 0) ? 1 : 0;
return ($failed, defined($out) ? $out : '', defined($err) ? $err : '');
}

# Parse newline-delimited JSON output (one object per line) from --format "{{json .}}".
sub docker_json_lines
{
my ($argstr) = @_;
my ($failed, $out, $err) = &run_docker($argstr, undef, 1);
return (1, $err || $out) if ($failed);
return (1, "JSON support unavailable (install perl JSON::PP)") if (!$have_json);
my @rows;
foreach my $line (split(/\r?\n/, $out)) {
	next if ($line !~ /\S/);
	my $obj = eval { decode_json($line) };
	push(@rows, $obj) if ($obj && ref($obj) eq 'HASH');
	}
return (0, \@rows);
}

# Parse a JSON array (docker inspect / history) into an arrayref.
sub docker_json_array
{
my ($argstr) = @_;
my ($failed, $out, $err) = &run_docker($argstr, undef, 1);
return (1, $err || $out) if ($failed);
return (1, "JSON support unavailable (install perl JSON::PP)") if (!$have_json);
my $data = eval { decode_json($out) };
return (1, "Could not parse Docker JSON output") if (!$data);
return (0, $data);
}

# ----------------------------------------------------------------------------
# Daemon / system information
# ----------------------------------------------------------------------------

# get_info() -> ($failed, \%info) from "docker info". Used by the dashboard,
# the monitors and the home-screen widget. A non-zero exit means the daemon
# is unreachable.
sub get_info
{
my ($failed, $info) = &docker_json_array('info --format "{{json .}}"');
return ($failed, $info) if ($failed);
return (0, $info);
}

# get_info_text() -> ($failed, $text) raw human-readable "docker info".
sub get_info_text
{
my ($failed, $out, $err) = &run_docker('info', undef, 1);
return ($failed, $failed ? ($err || $out) : $out);
}

# summary_counts() -> hashref of headline numbers for the dashboard / widget.
# Returns { 'ok' => 0/1, 'error' => ..., running/paused/stopped/containers/images/version }.
sub summary_counts
{
my ($failed, $info) = &get_info();
if ($failed || ref($info) ne 'HASH') {
	return { 'ok' => 0, 'error' => (ref($info) ? '' : $info) };
	}
# docker info also reports ServerErrors when the client is up but the daemon is not.
if ($info->{'ServerErrors'} && ref($info->{'ServerErrors'}) eq 'ARRAY' &&
    @{$info->{'ServerErrors'}}) {
	return { 'ok' => 0, 'error' => join("; ", @{$info->{'ServerErrors'}}) };
	}
return {
	'ok'         => 1,
	'containers' => $info->{'Containers'},
	'running'    => $info->{'ContainersRunning'},
	'paused'     => $info->{'ContainersPaused'},
	'stopped'    => $info->{'ContainersStopped'},
	'images'     => $info->{'Images'},
	'version'    => $info->{'ServerVersion'},
	'name'       => $info->{'Name'},
	'os'         => $info->{'OperatingSystem'},
	'ncpu'       => $info->{'NCPU'},
	'memtotal'   => $info->{'MemTotal'},
	};
}

# system_df() -> ($failed, \@rows) each { Type, TotalCount, Active, Size, Reclaimable }.
sub system_df
{
my ($failed, $rows) = &docker_json_lines('system df --format "{{json .}}"');
return ($failed, $rows);
}

# ----------------------------------------------------------------------------
# Containers
# ----------------------------------------------------------------------------

sub list_containers
{
my ($failed, $rows) = &docker_json_lines(
	'container ls --all --no-trunc --format "{{json .}}"');
return ($failed, $rows) if ($failed);
my @out;
foreach my $r (@$rows) {
	push(@out, {
		'id'     => $r->{'ID'},
		'name'   => $r->{'Names'},
		'image'  => $r->{'Image'},
		'state'  => $r->{'State'},
		'status' => $r->{'Status'},
		'ports'  => $r->{'Ports'},
		'labels' => $r->{'Labels'},
		});
	}
return (0, \@out);
}

# container_stats() -> ($failed, \%by_id) keyed by container ID and Name.
sub container_stats
{
my ($failed, $rows) = &docker_json_lines(
	'stats --no-stream --all --no-trunc --format "{{json .}}"');
return ($failed, $rows) if ($failed);
my %by;
foreach my $r (@$rows) {
	my $rec = {
		'cpu'      => $r->{'CPUPerc'},
		'mem'      => $r->{'MemPerc'},
		'memusage' => $r->{'MemUsage'},
		'netio'    => $r->{'NetIO'},
		'blockio'  => $r->{'BlockIO'},
		'pids'     => $r->{'PIDs'},
		};
	$by{$r->{'ID'}} = $rec if ($r->{'ID'});
	$by{$r->{'Name'}} = $rec if ($r->{'Name'});
	}
return (0, \%by);
}

# inspect_container(REF) -> ($failed, $pretty_json_text)
sub inspect_container
{
my ($ref) = @_;
return (1, "Invalid reference") if (!&is_valid_ref($ref));
my ($failed, $out, $err) = &run_docker(
	'container inspect '.&sq($ref), undef, 1);
return ($failed, $failed ? ($err || $out) : $out);
}

# container_logs(REF, \%opts) -> ($failed, $text)
# opts: tail (int), timestamps (0/1), since (string), filter (string), nocase (0/1)
# Filtering is done in Perl (no shell pipe) for safety.
sub container_logs
{
my ($ref, $opts) = @_;
$opts ||= {};
return (1, "Invalid reference") if (!&is_valid_ref($ref));
my $tail = $opts->{'tail'};
$tail = 100 if (!defined($tail) || $tail !~ /^\d+$/);
$tail = 5000 if ($tail > 5000);
my $arg = 'container logs --tail '.int($tail);
if ($opts->{'timestamps'}) {
	$arg .= ' --timestamps';
	}
if (defined($opts->{'since'}) && $opts->{'since'} ne '') {
	# since is a duration (10m) or RFC3339/epoch - allow a conservative charset
	my $since = $opts->{'since'};
	if ($since =~ /^[A-Za-z0-9:\.\+\-]{1,40}$/) {
		$arg .= ' --since '.&sq($since);
		}
	}
$arg .= ' '.&sq($ref);
my ($failed, $out, $err) = &run_docker($arg, undef, 1);
return ($failed, $err || $out) if ($failed);
my $log = $out;
$log .= $err if (defined($err) && $err ne '');   # docker writes logs to stderr too
my $filter = $opts->{'filter'};
if (defined($filter) && $filter ne '') {
	my @keep;
	foreach my $line (split(/\r?\n/, $log)) {
		if ($opts->{'nocase'}) {
			push(@keep, $line) if (index(lc($line), lc($filter)) >= 0);
			}
		else {
			push(@keep, $line) if (index($line, $filter) >= 0);
			}
		}
	$log = @keep ? join("\n", @keep) : "";
	}
return (0, $log);
}

# container_action(ACTION, [opts], REFS...) -> ($failed, $output)
# ACTION is one of the lifecycle verbs in the whitelist below.
my %LIFECYCLE = map { $_ => 1 } qw(start stop restart pause unpause kill);
sub container_action
{
my ($action, $refs, $opts) = @_;
$opts ||= {};
return (1, "Action not allowed") if (!$LIFECYCLE{$action});
my @refs = grep { &is_valid_ref($_) } @$refs;
return (1, "No valid containers selected") if (!@refs);
my $arg = 'container '.$action;
if (($action eq 'stop' || $action eq 'restart') &&
    defined($opts->{'time'}) && $opts->{'time'} =~ /^\d+$/) {
	$arg .= ' --time '.int($opts->{'time'});
	}
if ($action eq 'kill' && $opts->{'signal'} &&
    $opts->{'signal'} =~ /^[A-Z0-9]{1,20}$/) {
	$arg .= ' --signal '.&sq($opts->{'signal'});
	}
$arg .= ' '.join(" ", map { &sq($_) } @refs);
my ($failed, $out, $err) = &run_docker($arg, undef, 0);
return ($failed, $failed ? ($err || $out) : ($out || ''));
}

sub remove_container
{
my ($refs, $force, $volumes) = @_;
my @refs = grep { &is_valid_ref($_) } @$refs;
return (1, "No valid containers selected") if (!@refs);
my $arg = 'container rm';
$arg .= ' --force' if ($force);
$arg .= ' --volumes' if ($volumes);
$arg .= ' '.join(" ", map { &sq($_) } @refs);
my ($failed, $out, $err) = &run_docker($arg, undef, 0);
return ($failed, $failed ? ($err || $out) : ($out || ''));
}

sub rename_container
{
my ($ref, $newname) = @_;
return (1, "Invalid container reference") if (!&is_valid_ref($ref));
return (1, "Invalid new name") if (!&is_valid_name($newname));
my ($failed, $out, $err) = &run_docker(
	'container rename '.&sq($ref).' '.&sq($newname), undef, 0);
return ($failed, $failed ? ($err || $out) : '');
}

# update_container(REF, \%opts) opts: memory, cpus, restart, pids
sub update_container
{
my ($ref, $opts) = @_;
return (1, "Invalid container reference") if (!&is_valid_ref($ref));
my $arg = 'container update';
if (defined($opts->{'memory'}) && $opts->{'memory'} ne '') {
	$opts->{'memory'} =~ /^\d+[bkmgBKMG]?$/
		|| return (1, "Invalid memory value");
	$arg .= ' --memory '.&sq($opts->{'memory'});
	}
if (defined($opts->{'cpus'}) && $opts->{'cpus'} ne '') {
	$opts->{'cpus'} =~ /^\d+(\.\d+)?$/
		|| return (1, "Invalid cpus value");
	$arg .= ' --cpus '.&sq($opts->{'cpus'});
	}
if (defined($opts->{'pids'}) && $opts->{'pids'} ne '') {
	$opts->{'pids'} =~ /^-?\d+$/
		|| return (1, "Invalid pids limit");
	$arg .= ' --pids-limit '.&sq($opts->{'pids'});
	}
if (defined($opts->{'restart'}) && $opts->{'restart'} ne '') {
	my %ok = map { $_ => 1 } ('no', 'on-failure', 'always', 'unless-stopped');
	$ok{$opts->{'restart'}} || return (1, "Invalid restart policy");
	$arg .= ' --restart '.&sq($opts->{'restart'});
	}
$arg .= ' '.&sq($ref);
my ($failed, $out, $err) = &run_docker($arg, undef, 0);
return ($failed, $failed ? ($err || $out) : ($out || ''));
}

# parse_lines(TEXT) -> trimmed, non-empty lines (for env/ports/volumes textareas).
sub parse_lines
{
my ($v) = @_;
return grep { $_ ne '' } map { my $x = $_; $x =~ s/^\s+|\s+$//g; $x } split(/\r?\n/, defined($v) ? $v : "");
}

# create_container(\%opts) -> ($failed, $output)
# opts: name, image (required), command, env[], ports[], volumes[], restart,
#       memory, cpus, network, hardened (0/1)
sub create_container
{
my ($opts) = @_;
return (1, "Image is required") if (!$opts->{'image'});
return (1, "Invalid image reference") if (!&is_valid_image($opts->{'image'}));
my @cmd = ('container', 'run', '--detach');

if (defined($opts->{'name'}) && $opts->{'name'} ne '') {
	&is_valid_name($opts->{'name'}) || return (1, "Invalid container name");
	push(@cmd, '--name', &sq($opts->{'name'}));
	}
if (defined($opts->{'restart'}) && $opts->{'restart'} ne '') {
	my %ok = map { $_ => 1 } ('no', 'on-failure', 'always', 'unless-stopped');
	$ok{$opts->{'restart'}} || return (1, "Invalid restart policy");
	push(@cmd, '--restart', &sq($opts->{'restart'}));
	}
if (defined($opts->{'network'}) && $opts->{'network'} ne '') {
	&is_valid_ref($opts->{'network'}) || return (1, "Invalid network");
	push(@cmd, '--network', &sq($opts->{'network'}));
	}
if (defined($opts->{'memory'}) && $opts->{'memory'} ne '') {
	$opts->{'memory'} =~ /^\d+[bkmgBKMG]?$/ || return (1, "Invalid memory value");
	push(@cmd, '--memory', &sq($opts->{'memory'}));
	}
if (defined($opts->{'cpus'}) && $opts->{'cpus'} ne '') {
	$opts->{'cpus'} =~ /^\d+(\.\d+)?$/ || return (1, "Invalid cpus value");
	push(@cmd, '--cpus', &sq($opts->{'cpus'}));
	}
foreach my $e (@{$opts->{'env'} || []}) {
	$e =~ /^[A-Za-z_][A-Za-z0-9_]*=/ || return (1, "Invalid environment line: $e");
	push(@cmd, '--env', &sq($e));
	}
foreach my $p (@{$opts->{'ports'} || []}) {
	# host-ip? host-port(range)? : container-port(range) [/proto]
	$p =~ m!^(\d{1,3}(\.\d{1,3}){3}:)?(\d{1,5}(-\d{1,5})?:)?\d{1,5}(-\d{1,5})?(/(tcp|udp))?$!
		|| return (1, "Invalid port mapping: $p");
	push(@cmd, '--publish', &sq($p));
	}
foreach my $v (@{$opts->{'volumes'} || []}) {
	&is_clean_token($v) || return (1, "Invalid volume: $v");
	push(@cmd, '--volume', &sq($v));
	}
if ($opts->{'hardened'}) {
	push(@cmd, '--cap-drop=ALL', '--security-opt', 'no-new-privileges');
	}
push(@cmd, &sq($opts->{'image'}));

# Optional command: split into words, each its own quoted token.
if (defined($opts->{'command'}) && $opts->{'command'} ne '') {
	foreach my $w (split(/\s+/, $opts->{'command'})) {
		next if ($w eq '');
		push(@cmd, &sq($w));
		}
	}
my ($failed, $out, $err) = &run_docker(join(" ", @cmd), undef, 0);
return ($failed, $failed ? ($err || $out) : ($out || ''));
}

# clone_container(SOURCE, NEWNAME) - replicate a container's key settings.
sub clone_container
{
my ($source, $newname) = @_;
return (1, "Invalid source container") if (!&is_valid_ref($source));
my ($failed, $data) = &docker_json_array(
	'container inspect '.&sq($source).' --format "{{json .}}"');
return ($failed, $data) if ($failed);
my $d = ref($data) eq 'ARRAY' ? $data->[0] : $data;
return (1, "Could not read source container") if (ref($d) ne 'HASH');

my @ports;
my $pb = $d->{'HostConfig'}{'PortBindings'} || {};
foreach my $k (keys %$pb) {
	foreach my $b (@{$pb->{$k} || []}) {
		my $hp = $b->{'HostPort'} || '';
		push(@ports, ($hp ne '' ? $hp.':' : '').$k) if ($k);
		}
	}
my %opts = (
	'name'    => $newname,
	'image'   => $d->{'Config'}{'Image'},
	'env'     => $d->{'Config'}{'Env'} || [],
	'ports'   => \@ports,
	'volumes' => $d->{'HostConfig'}{'Binds'} || [],
	'restart' => $d->{'HostConfig'}{'RestartPolicy'}{'Name'} || '',
	);
return &create_container(\%opts);
}

# ----------------------------------------------------------------------------
# Images
# ----------------------------------------------------------------------------

sub list_images
{
my ($failed, $rows) = &docker_json_lines('image ls --format "{{json .}}"');
return ($failed, $rows) if ($failed);
my @out;
foreach my $r (@$rows) {
	my $repo = $r->{'Repository'};
	my $tag = $r->{'Tag'};
	my $name = ($repo && $repo ne '<none>') ?
		$repo.($tag && $tag ne '<none>' ? ':'.$tag : '') : ($r->{'ID'} || '<none>');
	push(@out, {
		'id'      => $r->{'ID'},
		'name'    => $name,
		'repo'    => $repo,
		'tag'     => $tag,
		'size'    => $r->{'Size'},
		'created' => $r->{'CreatedSince'},
		});
	}
return (0, \@out);
}

sub inspect_image
{
my ($ref) = @_;
return (1, "Invalid image reference") if (!&is_valid_image($ref) && !&is_valid_id($ref));
my ($failed, $out, $err) = &run_docker('image inspect '.&sq($ref), undef, 1);
return ($failed, $failed ? ($err || $out) : $out);
}

sub image_history
{
my ($ref) = @_;
return (1, "Invalid image reference") if (!&is_valid_image($ref) && !&is_valid_id($ref));
my ($failed, $out, $err) = &run_docker(
	'image history --no-trunc '.&sq($ref), undef, 1);
return ($failed, $failed ? ($err || $out) : $out);
}

sub pull_image
{
my ($ref) = @_;
return (1, "Invalid image reference") if (!&is_valid_image($ref));
my ($failed, $out, $err) = &run_docker('image pull '.&sq($ref), undef, 0);
return ($failed, $failed ? ($err || $out) : ($out || ''));
}

sub push_image
{
my ($ref) = @_;
return (1, "Invalid image reference") if (!&is_valid_image($ref));
my ($failed, $out, $err) = &run_docker('image push '.&sq($ref), undef, 0);
return ($failed, $failed ? ($err || $out) : ($out || ''));
}

sub tag_image
{
my ($src, $dst) = @_;
return (1, "Invalid source image") if (!&is_valid_image($src) && !&is_valid_id($src));
return (1, "Invalid target image") if (!&is_valid_image($dst));
my ($failed, $out, $err) = &run_docker(
	'image tag '.&sq($src).' '.&sq($dst), undef, 0);
return ($failed, $failed ? ($err || $out) : '');
}

sub remove_image
{
my ($refs, $force) = @_;
my @refs = grep { &is_valid_image($_) || &is_valid_id($_) } @$refs;
return (1, "No valid images selected") if (!@refs);
my $arg = 'image rm';
$arg .= ' --force' if ($force);
$arg .= ' '.join(" ", map { &sq($_) } @refs);
my ($failed, $out, $err) = &run_docker($arg, undef, 0);
return ($failed, $failed ? ($err || $out) : ($out || ''));
}

sub prune_images
{
my ($all) = @_;
my $arg = 'image prune --force';
$arg .= ' --all' if ($all);
my ($failed, $out, $err) = &run_docker($arg, undef, 0);
return ($failed, $failed ? ($err || $out) : ($out || ''));
}

# search_images(TERM, LIMIT) -> ($failed, \@rows)
sub search_images
{
my ($term, $limit) = @_;
return (1, "Invalid search term") if (!defined($term) || $term !~ /^[\w][\w.\/\-]{0,127}$/);
$limit = 25 if (!defined($limit) || $limit !~ /^\d+$/ || $limit < 1 || $limit > 100);
my ($failed, $rows) = &docker_json_lines(
	'search --limit '.int($limit).' --format "{{json .}}" '.&sq($term));
return ($failed, $rows) if ($failed);
my @out;
foreach my $r (@$rows) {
	push(@out, {
		'name'     => $r->{'Name'},
		'desc'     => $r->{'Description'},
		'stars'    => $r->{'StarCount'},
		'official' => $r->{'IsOfficial'},
		});
	}
return (0, \@out);
}

# build_image(TAG, DOCKERFILE_TEXT) - build from inline Dockerfile content.
sub build_image
{
my ($tag, $dockerfile) = @_;
return (1, "Invalid build tag") if (!&is_valid_image($tag));
return (1, "Dockerfile content is required") if (!defined($dockerfile) || $dockerfile !~ /\S/);
my $dir = &transname();
mkdir($dir, 0700) || return (1, "Could not create build directory");
my $file = "$dir/Dockerfile";
open(my $fh, ">", $file) || do { rmdir($dir); return (1, "Could not write Dockerfile"); };
print $fh $dockerfile;
close($fh);
my ($failed, $out, $err) = &run_docker(
	'build --tag '.&sq($tag).' '.&sq($dir), undef, 0);
unlink($file);
rmdir($dir);
return ($failed, ($out || '').($err || ''));
}

# ----------------------------------------------------------------------------
# Volumes & networks
# ----------------------------------------------------------------------------

sub list_volumes
{
my ($failed, $rows) = &docker_json_lines('volume ls --format "{{json .}}"');
return ($failed, $rows) if ($failed);
my @out;
foreach my $r (@$rows) {
	push(@out, {
		'name'       => $r->{'Name'},
		'driver'     => $r->{'Driver'},
		'mountpoint' => $r->{'Mountpoint'},
		'scope'      => $r->{'Scope'},
		});
	}
return (0, \@out);
}

sub inspect_volume
{
my ($name) = @_;
return (1, "Invalid volume name") if (!&is_valid_ref($name));
my ($failed, $out, $err) = &run_docker('volume inspect '.&sq($name), undef, 1);
return ($failed, $failed ? ($err || $out) : $out);
}

sub create_volume
{
my ($name, $driver) = @_;
return (1, "Invalid volume name") if (!&is_valid_name($name));
my $arg = 'volume create';
if (defined($driver) && $driver ne '') {
	&is_valid_name($driver) || return (1, "Invalid driver");
	$arg .= ' --driver '.&sq($driver);
	}
$arg .= ' '.&sq($name);
my ($failed, $out, $err) = &run_docker($arg, undef, 0);
return ($failed, $failed ? ($err || $out) : ($out || ''));
}

sub remove_volume
{
my ($names) = @_;
my @names = grep { &is_valid_ref($_) } @$names;
return (1, "No valid volumes selected") if (!@names);
my ($failed, $out, $err) = &run_docker(
	'volume rm '.join(" ", map { &sq($_) } @names), undef, 0);
return ($failed, $failed ? ($err || $out) : ($out || ''));
}

sub prune_volumes
{
my ($failed, $out, $err) = &run_docker('volume prune --force', undef, 0);
return ($failed, $failed ? ($err || $out) : ($out || ''));
}

sub list_networks
{
my ($failed, $rows) = &docker_json_lines('network ls --format "{{json .}}"');
return ($failed, $rows) if ($failed);
my @out;
foreach my $r (@$rows) {
	push(@out, {
		'id'     => $r->{'ID'},
		'name'   => $r->{'Name'},
		'driver' => $r->{'Driver'},
		'scope'  => $r->{'Scope'},
		});
	}
return (0, \@out);
}

sub inspect_network
{
my ($name) = @_;
return (1, "Invalid network name") if (!&is_valid_ref($name));
my ($failed, $out, $err) = &run_docker('network inspect '.&sq($name), undef, 1);
return ($failed, $failed ? ($err || $out) : $out);
}

sub create_network
{
my ($name, $driver) = @_;
return (1, "Invalid network name") if (!&is_valid_name($name));
my $arg = 'network create';
if (defined($driver) && $driver ne '') {
	&is_valid_name($driver) || return (1, "Invalid driver");
	$arg .= ' --driver '.&sq($driver);
	}
$arg .= ' '.&sq($name);
my ($failed, $out, $err) = &run_docker($arg, undef, 0);
return ($failed, $failed ? ($err || $out) : ($out || ''));
}

sub remove_network
{
my ($names) = @_;
my @names = grep { &is_valid_ref($_) } @$names;
return (1, "No valid networks selected") if (!@names);
my ($failed, $out, $err) = &run_docker(
	'network rm '.join(" ", map { &sq($_) } @names), undef, 0);
return ($failed, $failed ? ($err || $out) : ($out || ''));
}

sub prune_networks
{
my ($failed, $out, $err) = &run_docker('network prune --force', undef, 0);
return ($failed, $failed ? ($err || $out) : ($out || ''));
}

sub connect_network
{
my ($network, $container) = @_;
return (1, "Invalid network") if (!&is_valid_ref($network));
return (1, "Invalid container") if (!&is_valid_ref($container));
my ($failed, $out, $err) = &run_docker(
	'network connect '.&sq($network).' '.&sq($container), undef, 0);
return ($failed, $failed ? ($err || $out) : '');
}

sub disconnect_network
{
my ($network, $container) = @_;
return (1, "Invalid network") if (!&is_valid_ref($network));
return (1, "Invalid container") if (!&is_valid_ref($container));
my ($failed, $out, $err) = &run_docker(
	'network disconnect '.&sq($network).' '.&sq($container), undef, 0);
return ($failed, $failed ? ($err || $out) : '');
}

# ----------------------------------------------------------------------------
# Maintenance / prune
# ----------------------------------------------------------------------------

sub system_prune
{
my ($all, $volumes) = @_;
my $arg = 'system prune --force';
$arg .= ' --all' if ($all);
$arg .= ' --volumes' if ($volumes);
my ($failed, $out, $err) = &run_docker($arg, undef, 0);
return ($failed, $failed ? ($err || $out) : ($out || ''));
}

sub builder_prune
{
my ($all) = @_;
my $arg = 'builder prune --force';
$arg .= ' --all' if ($all);
my ($failed, $out, $err) = &run_docker($arg, undef, 0);
return ($failed, $failed ? ($err || $out) : ($out || ''));
}

# ----------------------------------------------------------------------------
# Exec & copy
# ----------------------------------------------------------------------------

# exec_in_container(REF, CMD) - run CMD inside the container via its own shell.
# The whole CMD is passed as ONE single-quoted token to "sh -c" INSIDE the
# container, so there is no shell injection on the host. Never interactive.
sub exec_in_container
{
my ($ref, $cmd) = @_;
return (1, "Invalid container reference") if (!&is_valid_ref($ref));
return (1, "No command given") if (!defined($cmd) || $cmd !~ /\S/);
return (1, "Command contains illegal characters") if ($cmd =~ /[\0]/);
my ($failed, $out, $err) = &run_docker(
	'container exec '.&sq($ref).' /bin/sh -c '.&sq($cmd), undef, 0);
return ($failed, ($out || '').($err || ''));
}

sub copy_to_container
{
my ($host_path, $ref, $target) = @_;
return (1, "Invalid container reference") if (!&is_valid_ref($ref));
return (1, "Invalid host path") if (!&is_clean_token($host_path));
return (1, "Invalid target path") if (!&is_clean_token($target));
my ($failed, $out, $err) = &run_docker(
	'cp '.&sq($host_path).' '.&sq($ref.':'.$target), undef, 0);
return ($failed, $failed ? ($err || $out) : '');
}

sub copy_from_container
{
my ($ref, $source, $host_dest) = @_;
return (1, "Invalid container reference") if (!&is_valid_ref($ref));
return (1, "Invalid source path") if (!&is_clean_token($source));
return (1, "Invalid host destination") if (!&is_clean_token($host_dest));
my ($failed, $out, $err) = &run_docker(
	'cp '.&sq($ref.':'.$source).' '.&sq($host_dest), undef, 0);
return ($failed, $failed ? ($err || $out) : '');
}

# ----------------------------------------------------------------------------
# Compose
# ----------------------------------------------------------------------------

# compose_prefix() -> the compose invocation as an arg fragment, or undef.
# Prefers the v2 plugin ("docker compose"); falls back to legacy docker-compose.
sub compose_prefix
{
# Probe the v2 plugin.
my ($f) = &run_docker('compose version', undef, 1);
return ('plugin', 'compose') if (!$f);
return ('legacy', undef) if (&has_command('docker-compose'));
return (undef, undef);
}

my %COMPOSE_ACTIONS = map { $_ => 1 } qw(up down ps logs config);
sub compose_run
{
my ($file, $action, $opts) = @_;
$opts ||= {};
return (1, "Action not allowed") if (!$COMPOSE_ACTIONS{$action});
return (1, "Compose file is required") if (!&is_clean_token($file));
return (1, "Compose file not found") if (!-r $file);
my ($kind, $sub) = &compose_prefix();
return (1, "Docker Compose is not installed") if (!$kind);

my $tail = '';
$tail = ' up --detach' if ($action eq 'up');
$tail = ' down' if ($action eq 'down');
$tail .= ' --volumes' if ($action eq 'down' && $opts->{'volumes'});
$tail = ' ps' if ($action eq 'ps');
$tail = ' logs --no-color --tail 200' if ($action eq 'logs');
$tail = ' config --quiet' if ($action eq 'config');

if ($kind eq 'plugin') {
	my ($failed, $out, $err) = &run_docker(
		'compose --file '.&sq($file).$tail, undef, 0);
	return ($failed, ($out || '').($err || ''));
	}
else {
	# Legacy docker-compose binary (does not honour the module context flag).
	my $bin = &has_command('docker-compose');
	my $cmd = &sq($bin).' --file '.&sq($file).$tail;
	my ($out, $err);
	my $status = &execute_command($cmd, undef, \$out, \$err, 0, 0);
	return (($status != 0 ? 1 : 0), ($out || '').($err || ''));
	}
}

# compose_ls() -> ($failed, \@projects) each { name, status, configfiles }
sub compose_ls
{
my ($kind, $sub) = &compose_prefix();
return (1, "Docker Compose v2 is required for project listing") if ($kind ne 'plugin');
my ($failed, $out, $err) = &run_docker('compose ls --all --format json', undef, 1);
return (1, $err || $out) if ($failed);
return (1, "JSON support unavailable") if (!$have_json);
my $data = eval { decode_json($out) };
return (0, []) if (!$data || ref($data) ne 'ARRAY');
my @out;
foreach my $p (@$data) {
	push(@out, {
		'name'        => $p->{'Name'},
		'status'      => $p->{'Status'},
		'configfiles' => $p->{'ConfigFiles'},
		});
	}
return (0, \@out);
}

# ----------------------------------------------------------------------------
# Security scanning
# ----------------------------------------------------------------------------

# scanner_available() -> 'scout' | 'trivy' | undef (honours configured preference)
sub scanner_available
{
my $pref = $config{'scanner'} || 'auto';
my $have_scout = sub {
	my ($f) = &run_docker('scout version', undef, 1);
	return !$f;
	};
my $have_trivy = &has_command('trivy') ? 1 : 0;
if ($pref eq 'trivy') { return $have_trivy ? 'trivy' : undef; }
if ($pref eq 'scout') { return &$have_scout() ? 'scout' : undef; }
# auto
return 'scout' if (&$have_scout());
return 'trivy' if ($have_trivy);
return undef;
}

sub scan_image
{
my ($ref) = @_;
return (1, "Invalid image reference") if (!&is_valid_image($ref) && !&is_valid_id($ref));
my $scanner = &scanner_available();
return (1, "No scanner available (install Docker Scout or Trivy)") if (!$scanner);
if ($scanner eq 'scout') {
	my ($failed, $out, $err) = &run_docker(
		'scout cves '.&sq($ref), undef, 1);
	return (0, ($out || '').($err || ''));
	}
else {
	my $bin = &has_command('trivy');
	my $cmd = &sq($bin).' image '.&sq($ref);
	my ($out, $err);
	&execute_command($cmd, undef, \$out, \$err, 0, 1);
	return (0, ($out || '').($err || ''));
	}
}

# ----------------------------------------------------------------------------
# Registry
# ----------------------------------------------------------------------------

# registry_login(SERVER, USER, PASS) - feeds the password via STDIN, never argv.
sub registry_login
{
my ($server, $user, $pass) = @_;
return (1, "Username is required") if (!defined($user) || $user eq '');
return (1, "Invalid username") if ($user =~ /[\0\n\r]/);
return (1, "Password is required") if (!defined($pass) || $pass eq '');
my $arg = 'login --username '.&sq($user).' --password-stdin';
if (defined($server) && $server ne '') {
	&is_valid_image($server) || return (1, "Invalid registry server");
	$arg .= ' '.&sq($server);
	}
# Pass the password as a SCALAR REF so Webmin writes it to the child's STDIN
# pipe (verified behaviour) instead of placing it on the command line.
my ($failed, $out, $err) = &run_docker($arg, \$pass, 0);
return ($failed, $failed ? ($err || $out) : ($out || ''));
}

# ----------------------------------------------------------------------------
# Contexts
# ----------------------------------------------------------------------------

sub list_contexts
{
my ($failed, $rows) = &docker_json_lines('context ls --format "{{json .}}"');
return ($failed, $rows) if ($failed);
my @out;
foreach my $r (@$rows) {
	push(@out, {
		'name'     => $r->{'Name'},
		'current'  => $r->{'Current'},
		'desc'     => $r->{'Description'},
		'endpoint' => $r->{'DockerEndpoint'},
		});
	}
return (0, \@out);
}

sub set_context
{
my ($name) = @_;
$name = '' if (!defined($name) || $name eq 'default');
return (1, "Invalid context name") if ($name ne '' && !&is_valid_name($name));
$config{'docker_context'} = $name;
&save_module_config();
return (0, "Context updated");
}

# ----------------------------------------------------------------------------
# Shared UI helpers
# ----------------------------------------------------------------------------

# state_dot(STATE) - a coloured status indicator matching the dashboard style.
sub state_dot
{
my ($state) = @_;
my $running = (defined($state) && $state eq 'running');
my $paused  = (defined($state) && $state eq 'paused');
my $level = $running ? 'success' : ($paused ? 'warn' : 'danger');
return &ui_text_color("&#9679;", $level);
}

# state_label(STATE, STATUS) - coloured "running (Up 3 hours)" style text.
sub state_label
{
my ($state, $status) = @_;
return &state_dot($state)." ".&html_escape(defined($status) ? $status : ($state || ''));
}

# bulk_select_links(FORMID, FIELD) - "select all / invert" links scoped to a
# specific form by id. Both arguments are constants supplied by this module, so
# there is no untrusted data in the emitted JavaScript. Using the form id avoids
# any dependence on form ordering (which varies with ACL-gated forms).
sub bulk_select_links
{
my ($formid, $field) = @_;
my $loop = "var f=document.getElementById('$formid');if(f){for(var i=0;i<f.elements.length;i++){if(f.elements[i].name=='$field')";
return "<a href='#' onclick=\"".$loop."f.elements[i].checked=true;}}return false;\">".
		$text{'select_all'}."</a> | ".
	"<a href='#' onclick=\"".$loop."f.elements[i].checked=!f.elements[i].checked;}}return false;\">".
		$text{'select_invert'}."</a>";
}

# can(KEY) - read the current user's module ACL flag (default allow for 'view').
sub can
{
my ($key) = @_;
our %access;
%access = &get_module_acl() if (!%access);
return $access{$key} ? 1 : 0;
}

# require_acl(KEY) - abort unless the current user holds the named permission.
sub require_acl
{
my ($key) = @_;
&can($key) || &error($text{'err_noperm'} || "You are not permitted to perform this action");
}

1;
