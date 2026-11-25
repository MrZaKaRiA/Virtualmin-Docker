#!/usr/bin/perl
# status_monitor.pl
# Monitor types for the "System and Server Status" module:
#   docker_up           - is the Docker daemon reachable?
#   docker_containerup  - is a named container running?

# Loaded by Webmin's foreign_require() from OTHER modules' directories, so
# the lib must be found via @INC (which foreign_require primes with this
# module's directory). Never use a './' relative path here - see issues #1, #2.
require 'docker-lib.pl';

# status_monitor_list() - supported monitor types.
sub status_monitor_list
{
return ( [ "docker_up", $text{'monitor_docker_up'} ],
	 [ "docker_containerup", $text{'monitor_container_up'} ] );
}

# status_monitor_status(type, &monitor, from-ui)
# Wrapped in eval so an internal error reports "unknown" (-1) to the status
# module instead of breaking its page.
sub status_monitor_status
{
my $rv = eval { &status_monitor_status_real(@_) };
if ($@) {
	my $e = $@; $e =~ s/\s+$//;
	&error_stderr("docker status_monitor: $e") if (defined(&error_stderr));
	return { 'up' => -1, 'desc' => $e };
	}
return $rv;
}

sub status_monitor_status_real
{
my ($type, $monitor, $fromui) = @_;

if ($type eq "docker_up") {
	my $sum = &summary_counts();
	return { 'up'   => $sum->{'ok'} ? 1 : 0,
		 'desc' => $sum->{'ok'} ? '' : ($sum->{'error'} || $text{'monitor_unreachable'}) };
	}
elsif ($type eq "docker_containerup") {
	my $c = $monitor->{'docker_container'};
	if (!&is_valid_ref($c)) {
		return { 'up' => -1, 'desc' => $text{'monitor_badcontainer'} };
		}
	my ($sf, $state, $serr) = &run_docker(
		'container inspect --format "{{.State.Status}}" '.&sq($c), undef, 1);
	$state =~ s/^\s+|\s+$//g;
	if ($sf) {
		# Distinguish "no such container" from "daemon unreachable" so an
		# outage does not raise false container-down alerts.
		my $sum = &summary_counts();
		if (!$sum->{'ok'}) {
			return { 'up' => -1, 'desc' => $text{'monitor_unreachable'} };
			}
		return { 'up' => 0, 'desc' => $text{'monitor_notfound'} };
		}
	my $up = ($state eq 'running') ? 1 : 0;
	return { 'up' => $up, 'desc' => ucfirst($state) };
	}
return { 'up' => -1, 'desc' => $text{'monitor_notype'} };
}

# status_monitor_dialog(type, &monitor)
sub status_monitor_dialog
{
my ($type, $mon) = @_;
if ($type eq "docker_containerup") {
	return &ui_table_row($text{'monitor_container'},
		&ui_textbox("docker_container", $mon->{'docker_container'}, 40));
	}
return undef;
}

# status_monitor_parse(type, &monitor, &in)
sub status_monitor_parse
{
my ($type, $mon, $in) = @_;
if ($type eq "docker_containerup") {
	$mon->{'docker_container'} = $in->{'docker_container'};
	}
}

1;
