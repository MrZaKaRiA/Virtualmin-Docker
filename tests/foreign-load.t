#!/usr/bin/perl
# tests/foreign-load.t
# Regression test for the hook-loading bug: Webmin's foreign_require() loads
# docker/<hook>.pl from OTHER modules' directories, as
#     package docker; do '/abs/path/docker/<hook>';
# with the module dir on @INC and some other CWD. A hook that pulled in the
# lib with `do './docker-lib.pl'` silently loaded nothing. This test
# reproduces that environment for every hook, each in a fresh perl process
# (require caches in %INC, so one process could mask a failure).
use strict;
use warnings;
use Test::More;
use File::Temp qw(tempdir);
use File::Spec;
use FindBin;
use IPC::Open3;
use Symbol qw(gensym);

my $root   = File::Spec->rel2abs(File::Spec->catdir($FindBin::Bin, '..'));
my $mdir   = File::Spec->catdir($root, 'docker');
my $stub   = File::Spec->catdir($FindBin::Bin, 'stub');
my $tmpdir = tempdir(CLEANUP => 1);

# hook file => its own entry point that must exist after loading
my %hooks = (
	'acl_security.pl'   => 'acl_security_form',
	'system_info.pl'    => 'list_system_info',
	'status_monitor.pl' => 'status_monitor_list',
	'log_parser.pl'     => 'parse_webmin_log',
	'install_check.pl'  => 'is_installed',
	);

# run_child(code, @args) -> (exit status, stdout, stderr)
# Runs CODE in a fresh perl with the module dir and the stub on @INC and the
# CWD moved to a scratch directory that is NOT the module dir.
sub run_child
{
my ($code, @args) = @_;
my $pre = "chdir(q{$tmpdir}) || die \"chdir: \$!\";\n";
my $err = gensym;
my $pid = open3(my $in, my $out, $err,
	$^X, '-w', "-I$mdir", "-I$stub", '-e', $pre.$code, @args);
close($in);
local $/;
my $stdout = <$out>;
my $stderr = <$err>;
waitpid($pid, 0);
return ($? >> 8, defined($stdout) ? $stdout : '', defined($stderr) ? $stderr : '');
}

# Child program that loads one hook exactly like foreign_require() does and
# prints what it found.
my $load_one = <<'CODE';
my ($mdir, $hook, $entry) = @ARGV;
my $ok = eval "package docker; do '$mdir/$hook' || die(\$@ || \$! || 'do returned false'); 1";
print "LOAD=", ($ok ? 1 : 0), "\n";
print "ERR=", ($@ =~ s/\n/ /gr), "\n" if (!$ok);
print "SQ=", (defined(&docker::sq) ? 1 : 0), "\n";
no strict 'refs';
print "ENTRY=", (defined(&{"docker::$entry"}) ? 1 : 0), "\n";
CODE

foreach my $hook (sort keys %hooks) {
	my $entry = $hooks{$hook};
	subtest "$hook loads via foreign_require() from another directory" => sub {
		my ($rc, $out, $err) = run_child($load_one, $mdir, $hook, $entry);
		my %r = map { /^(\w+)=(.*)$/ ? ($1 => $2) : () } split(/\n/, $out);
		is($rc, 0, "child perl exited 0") or diag($err);
		is($r{'LOAD'}, 1, "do '$hook' succeeded")
			or diag("error: ".($r{'ERR'} || '?'));
		is($r{'SQ'}, 1, "docker-lib.pl was loaded (defined &docker::sq)");
		is($r{'ENTRY'}, 1, "entry point docker::$entry is defined");
		};
	}

subtest "two hooks in one process emit no 'redefined' warnings" => sub {
	my $code = <<'CODE';
my ($mdir) = @ARGV;
foreach my $hook ('system_info.pl', 'status_monitor.pl') {
	eval "package docker; do '$mdir/$hook' || die(\$@ || \$! || 'do returned false'); 1"
		or die "$hook: $@";
	}
print "SQ=", (defined(&docker::sq) ? 1 : 0), "\n";
CODE
	my ($rc, $out, $err) = run_child($code, $mdir);
	is($rc, 0, "child perl exited 0") or diag($err);
	like($out, qr/^SQ=1$/m, "lib loaded");
	my @redef = grep { /redefined/ } split(/\n/, $err);
	is(scalar(@redef), 0, "no 'Subroutine redefined' warnings under -w")
		or diag(join("\n", @redef[0..($#redef < 9 ? $#redef : 9)]));
	};

subtest "hook entry points run in the stub environment" => sub {
	my $code = <<'CODE';
my ($mdir) = @ARGV;
foreach my $hook ('system_info.pl', 'status_monitor.pl') {
	eval "package docker; do '$mdir/$hook' || die(\$@ || \$! || 'do returned false'); 1"
		or die "$hook: $@";
	}
# The public wrappers swallow errors; call the inner functions too so a die
# inside them is not hidden.
my @panels = docker::list_system_info({}, {}, {});
print "PANELS=", scalar(@panels), "\n";
my @inner = eval { docker::list_system_info_panels({}, {}, {}) };
print "PANELS_ERR=", ($@ =~ s/\n/ /gr), "\n";
my $st = docker::status_monitor_status('docker_up', {}, 0);
print "ST_REF=", ref($st), "\n";
print "ST_UP=", (ref($st) eq 'HASH' && exists($st->{'up'}) ? $st->{'up'} : 'missing'), "\n";
my $real = eval { docker::status_monitor_status_real('docker_up', {}, 0) };
print "ST_ERR=", ($@ =~ s/\n/ /gr), "\n";
my @types = docker::status_monitor_list();
print "TYPES=", scalar(@types), "\n";
CODE
	my ($rc, $out, $err) = run_child($code, $mdir);
	my %r = map { /^(\w+)=(.*)$/ ? ($1 => $2) : () } split(/\n/, $out);
	is($rc, 0, "child perl exited 0") or diag($err);
	is($r{'PANELS'}, 0, "list_system_info() returns no panels (no docker command)");
	is($r{'PANELS_ERR'}, '', "list_system_info_panels() did not die");
	is($r{'ST_REF'}, 'HASH', "status_monitor_status() returns a hashref");
	is($r{'ST_UP'}, 0, "status_monitor_status('docker_up') reports down (up => 0)");
	is($r{'ST_ERR'}, '', "status_monitor_status_real() did not die");
	is($r{'TYPES'}, 2, "status_monitor_list() returns two monitor types");
	};

done_testing();
