#!/usr/bin/perl
# Regression tests for the host-bind-mount ACL, including Compose's resolved
# long and short volume forms.
use strict;
use warnings;
use Test::More;
use File::Spec;
use FindBin;

my $root = File::Spec->rel2abs(File::Spec->catdir($FindBin::Bin, '..'));
my $mdir = File::Spec->catdir($root, 'docker');
my $stub = File::Spec->catdir($FindBin::Bin, 'stub');
unshift @INC, $mdir, $stub;
require "$mdir/docker-lib.pl";

sub config_check
{
my ($json) = @_;
no warnings 'redefine';
local *main::run_docker = sub { return (0, $json, ''); };
return main::compose_config_uses_host_mount("--file '/safe/project.yml'");
}

my ($failed, $uses) = config_check('{"services":{"web":{"volumes":[{"type":"volume","source":"app-data","target":"/data"}]}}}');
is($failed, 0, 'resolved Compose config is read');
is($uses, 0, 'named Compose volume is allowed');

($failed, $uses) = config_check('{"services":{"web":{"volumes":[{"type":"bind","source":"/etc","target":"/host-etc"}]}}}');
is($failed, 0, 'resolved bind-mount config is read');
is($uses, 1, 'long-form Compose bind mount is detected');

($failed, $uses) = config_check('{"services":{"web":{"volumes":["./site:/usr/share/nginx/html"]}}}');
is($failed, 0, 'short-form Compose config is read');
is($uses, 1, 'short-form Compose host path is detected');

our %access = ( 'host_mount' => 0 );
my $err;
{
	no warnings 'redefine';
	local *main::run_docker = sub {
		return (0, '{"services":{"web":{"volumes":[{"type":"bind","source":"/etc"}]}}}', '');
	};
	($failed, $err) = main::compose_host_mount_allowed('up', "--file '/safe/project.yml'");
	}
is($failed, 1, 'untrusted user cannot launch a Compose project with a host bind');
like($err, qr/Host bind mounts require/, 'denial explains the required permission');

($failed, $err) = main::compose_host_mount_allowed('pull', "--file '/safe/project.yml'");
is($failed, 0, 'non-launching Compose actions do not require host-mount access');

done_testing();
