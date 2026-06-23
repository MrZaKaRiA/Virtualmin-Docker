# log_parser.pl
# Renders this module's &webmin_log entries in the Webmin Actions Log module.

do './docker-lib.pl';

# parse_webmin_log(user, script, action, type, object, &params) -> HTML string
sub parse_webmin_log
{
my ($user, $script, $action, $type, $object, $p) = @_;
my $obj = &html_escape($object);
my %verb = (
	'start'   => 'Started', 'stop' => 'Stopped', 'restart' => 'Restarted',
	'pause'   => 'Paused', 'unpause' => 'Unpaused', 'kill' => 'Killed',
	'remove'  => 'Removed', 'create' => 'Created', 'clone' => 'Cloned',
	'rename'  => 'Renamed', 'update' => 'Updated', 'exec' => 'Ran command in',
	'copy'    => 'Copied files for', 'pull' => 'Pulled', 'push' => 'Pushed',
	'tag'     => 'Tagged', 'build' => 'Built', 'prune' => 'Pruned',
	'compose' => 'Ran compose on', 'scan' => 'Scanned',
	'login'   => 'Logged in to', 'context' => 'Switched context to',
	);
my $v = $verb{$action} || $action;
return "$v $type <tt>$obj</tt>";
}

1;
