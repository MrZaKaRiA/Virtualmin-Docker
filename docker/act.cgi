#!/usr/bin/perl
# act.cgi - the single dispatcher for every state-changing Docker action.
#
# Security properties:
#   * Reached only by POST (Webmin's trusted-referer check gates it; we also
#     reject non-POST as defence in depth).
#   * Each action is individually ACL-gated via &require_acl.
#   * Every value comes from validated lib helpers; nothing is shell-built here.
#   * Destructive actions show a confirmation step (when enabled in config).
#   * Each success is recorded with &webmin_log for the Webmin action log.

require './docker-lib.pl';
&ReadParse();
&error_setup($text{'err_actionfailed'});

our (%config, %text, %in, %access);
%access = &get_module_acl();

# Refuse anything that is not a POST - all forms in this module use POST.
$ENV{'REQUEST_METHOD'} eq 'POST' || &error($text{'err_post'});

my $c = $in{'c'} || '';

# ---- helpers ---------------------------------------------------------------

sub redir
{
my ($dest, $msg, $err) = @_;
my @p;
push(@p, "msg=".&urlize($msg)) if (defined($msg) && $msg ne '');
push(@p, "err=".&urlize($err)) if (defined($err) && $err ne '');
$dest .= "?".join("&", @p) if (@p);
&redirect($dest);
exit;
}

# Render a command's textual output on its own page.
sub render
{
my ($title, $output) = @_;
&ui_print_header(undef, $title, "");
print "<pre class='comment'>".&html_escape($output)."</pre>";
&ui_print_footer("index.cgi", $text{'index_return'});
print "<script type='text/javascript'>if (window.viewer_init) { viewer_init() }</script>";
exit;
}

# Show a confirmation form that re-posts to act.cgi with confirmed=1.
sub confirm
{
my ($title, $prompt, $hidden, $button, $level) = @_;
return if ($in{'confirmed'} || !$config{'confirm_destructive'});
&ui_print_header(undef, $title, "");
print &ui_alert_box(&html_escape($prompt), $level || 'warn');
print &ui_form_start("act.cgi", "post");
# $hidden is a FLAT list of (name, value, name, value, ...) pairs.
for (my $i = 0; $i + 1 < scalar(@$hidden); $i += 2) {
	print &ui_hidden($hidden->[$i], $hidden->[$i + 1]);
	}
print &ui_hidden("confirmed", 1);
print &ui_form_end([ [ undef, $button ],
		     [ "cancel", $text{'confirm_cancel'} ] ]);
&ui_print_footer("index.cgi", $text{'index_return'});
exit;
}

# Selected checkbox values (null-joined), validated by the caller's lib helper.
sub selected
{
my ($field) = @_;
$field ||= "d";
return grep { defined($_) && $_ ne '' } split(/\0/, $in{$field});
}

if ($in{'cancel'}) {
	&redir("index.cgi");
	}

# ---- containers ------------------------------------------------------------

if ($c eq 'container_bulk') {
	my @ids = &selected("d");
	@ids || &redir("index.cgi", undef, $text{'err_noselection'});
	my ($action) = grep { $in{$_} }
		qw(start stop restart pause unpause kill remove);
	$action || &redir("index.cgi", undef, $text{'err_noaction'});

	if ($action eq 'remove') {
		&require_acl('delete');
		&confirm($text{'act_remove'},
			&text('confirm_remove', scalar(@ids)),
			[ ("c", "container_bulk"), ("remove", 1),
			  map { ("d", $_) } @ids ],
			$text{'act_remove'}, 'danger');
		my ($f, $o) = &remove_container(\@ids, 1, 0);
		&webmin_log("remove", "container", join(",", @ids)) if (!$f);
		&redir("index.cgi", $f ? undef : $text{'msg_removed'}, $f ? $o : undef);
		}
	else {
		&require_acl('manage');
		my ($f, $o) = &container_action($action, \@ids);
		&webmin_log($action, "container", join(",", @ids)) if (!$f);
		&redir("index.cgi", $f ? undef : &text('msg_action', $action),
			$f ? $o : undef);
		}
	}
elsif ($c eq 'create' || $c eq 'run_image') {
	&require_acl('create');
	my %opts = (
		'name'     => $in{'name'},
		'image'    => $in{'image'},
		'command'  => $in{'command'},
		'restart'  => $in{'restart'},
		'network'  => $in{'network'},
		'memory'   => $in{'memory'},
		'cpus'     => $in{'cpus'},
		'hardened' => $in{'hardened'},
		'env'      => [ &parse_lines($in{'env'}) ],
		'ports'    => [ &parse_lines($in{'ports'}) ],
		'volumes'  => [ &parse_lines($in{'volumes'}) ],
		);
	my ($f, $o) = &create_container(\%opts);
	&webmin_log("create", "container", $in{'name'} || $in{'image'},
		{ 'image' => $in{'image'} }) if (!$f);
	&redir($c eq 'run_image' ? "images.cgi" : "index.cgi",
		$f ? undef : $text{'msg_created'}, $f ? $o : undef);
	}
elsif ($c eq 'clone') {
	&require_acl('create');
	my ($f, $o) = &clone_container($in{'source'}, $in{'name'});
	&webmin_log("clone", "container", $in{'source'}) if (!$f);
	&redir("index.cgi", $f ? undef : $text{'msg_cloned'}, $f ? $o : undef);
	}
elsif ($c eq 'rename') {
	&require_acl('manage');
	my ($f, $o) = &rename_container($in{'id'}, $in{'newname'});
	&webmin_log("rename", "container", $in{'id'},
		{ 'to' => $in{'newname'} }) if (!$f);
	&redir("container.cgi?id=".&urlize($f ? $in{'id'} : $in{'newname'}),
		$f ? undef : $text{'msg_renamed'}, $f ? $o : undef);
	}
elsif ($c eq 'update') {
	&require_acl('manage');
	my ($f, $o) = &update_container($in{'id'}, {
		'memory'  => $in{'memory'},
		'cpus'    => $in{'cpus'},
		'pids'    => $in{'pids'},
		'restart' => $in{'restart'},
		});
	&webmin_log("update", "container", $in{'id'}) if (!$f);
	&redir("container.cgi?id=".&urlize($in{'id'}),
		$f ? undef : $text{'msg_updated'}, $f ? $o : undef);
	}
elsif ($c eq 'exec') {
	&require_acl('exec');
	my ($f, $o) = &exec_in_container($in{'id'}, $in{'cmd'});
	&webmin_log("exec", "container", $in{'id'}, { 'cmd' => $in{'cmd'} }) if (!$f);
	&render($text{'cont_exec'}, $f ? $o : ($o eq '' ? $text{'exec_nooutput'} : $o));
	}
elsif ($c eq 'copy_to') {
	&require_acl('exec');
	my ($f, $o) = &copy_to_container($in{'host_path'}, $in{'id'}, $in{'target_path'});
	&webmin_log("copy", "container", $in{'id'}) if (!$f);
	&redir("container.cgi?tab=exec&id=".&urlize($in{'id'}),
		$f ? undef : $text{'msg_copied'}, $f ? $o : undef);
	}
elsif ($c eq 'copy_from') {
	&require_acl('exec');
	my ($f, $o) = &copy_from_container($in{'id'}, $in{'source_path'}, $in{'host_dest'});
	&webmin_log("copy", "container", $in{'id'}) if (!$f);
	&redir("container.cgi?tab=exec&id=".&urlize($in{'id'}),
		$f ? undef : $text{'msg_copied'}, $f ? $o : undef);
	}

# ---- images ----------------------------------------------------------------

elsif ($c eq 'image_remove') {
	&require_acl('delete');
	my @ids = &selected("d");
	@ids || &redir("images.cgi", undef, $text{'err_noselection'});
	&confirm($text{'img_remove'}, &text('confirm_image_remove', scalar(@ids)),
		[ ("c", "image_remove"), ("force", $in{'force'}), map { ("d", $_) } @ids ],
		$text{'img_remove'}, 'danger');
	my ($f, $o) = &remove_image(\@ids, $in{'force'});
	&webmin_log("remove", "image", join(",", @ids)) if (!$f);
	&redir("images.cgi", $f ? undef : $text{'msg_image_removed'}, $f ? $o : undef);
	}
elsif ($c eq 'pull') {
	&require_acl('create');
	my ($f, $o) = &pull_image($in{'image'});
	&webmin_log("pull", "image", $in{'image'}) if (!$f);
	&render($text{'img_pull'}, $o);
	}
elsif ($c eq 'push') {
	&require_acl('create');
	my ($f, $o) = &push_image($in{'image'});
	&webmin_log("push", "image", $in{'image'}) if (!$f);
	&render($text{'img_push'}, $o);
	}
elsif ($c eq 'tag') {
	&require_acl('create');
	my ($f, $o) = &tag_image($in{'source'}, $in{'target'});
	&webmin_log("tag", "image", $in{'source'}) if (!$f);
	&redir("images.cgi", $f ? undef : $text{'msg_tagged'}, $f ? $o : undef);
	}
elsif ($c eq 'build') {
	&require_acl('create');
	my ($f, $o) = &build_image($in{'tag'}, $in{'dockerfile'});
	&webmin_log("build", "image", $in{'tag'}) if (!$f);
	&render($text{'img_build'}, $o);
	}
elsif ($c eq 'prune_images') {
	&require_acl('prune');
	&confirm($text{'img_prune'}, $text{'confirm_prune_images'},
		[ ("c", "prune_images"), ("all", $in{'all'}) ], $text{'img_prune'}, 'danger');
	my ($f, $o) = &prune_images($in{'all'});
	&webmin_log("prune", "image", "*") if (!$f);
	&render($text{'img_prune'}, $o);
	}

# ---- backup & restore ------------------------------------------------------

elsif ($c eq 'image_save') {
	&require_acl('backup');
	my ($f, $o) = &save_image($in{'image'}, $in{'path'});
	&webmin_log("save", "image", $in{'image'}, { 'path' => $in{'path'} }) if (!$f);
	&redir("images.cgi", $f ? undef : $text{'msg_saved'}, $f ? $o : undef);
	}
elsif ($c eq 'image_load') {
	&require_acl('backup');
	my ($f, $o) = &load_image($in{'path'});
	&webmin_log("load", "image", $in{'path'}) if (!$f);
	&render($text{'backup_load'}, $o eq '' ? $text{'exec_nooutput'} : $o);
	}
elsif ($c eq 'container_commit') {
	&require_acl('backup');
	my ($f, $o) = &commit_container($in{'id'}, $in{'image'});
	&webmin_log("commit", "container", $in{'id'}, { 'image' => $in{'image'} }) if (!$f);
	&redir("container.cgi?tab=manage&id=".&urlize($in{'id'}),
		$f ? undef : $text{'msg_committed'}, $f ? $o : undef);
	}
elsif ($c eq 'container_export') {
	&require_acl('backup');
	my ($f, $o) = &export_container($in{'id'}, $in{'path'});
	&webmin_log("export", "container", $in{'id'}, { 'path' => $in{'path'} }) if (!$f);
	&redir("container.cgi?tab=manage&id=".&urlize($in{'id'}),
		$f ? undef : $text{'msg_exported'}, $f ? $o : undef);
	}
elsif ($c eq 'volume_backup') {
	&require_acl('backup');
	my ($f, $o) = &backup_volume($in{'name'}, $in{'path'});
	&webmin_log("backup", "volume", $in{'name'}, { 'path' => $in{'path'} }) if (!$f);
	&redir("storage.cgi", $f ? undef : $text{'msg_backed_up'}, $f ? $o : undef);
	}
elsif ($c eq 'volume_restore') {
	&require_acl('backup');
	&confirm($text{'stor_restore_volume'}, $text{'confirm_restore'},
		[ ("c", "volume_restore"), ("name", $in{'name'}), ("path", $in{'path'}) ],
		$text{'stor_restore_volume'}, 'warn');
	my ($f, $o) = &restore_volume($in{'name'}, $in{'path'});
	&webmin_log("restore", "volume", $in{'name'}, { 'path' => $in{'path'} }) if (!$f);
	&redir("storage.cgi", $f ? undef : $text{'msg_restored'}, $f ? $o : undef);
	}

# ---- storage (volumes & networks) -----------------------------------------

elsif ($c eq 'volume_create') {
	&require_acl('create');
	my ($f, $o) = &create_volume($in{'name'}, $in{'driver'});
	&webmin_log("create", "volume", $in{'name'}) if (!$f);
	&redir("storage.cgi", $f ? undef : $text{'msg_volume_created'}, $f ? $o : undef);
	}
elsif ($c eq 'volume_remove') {
	&require_acl('delete');
	my @n = &selected("d");
	@n || &redir("storage.cgi", undef, $text{'err_noselection'});
	&confirm($text{'stor_remove_volume'}, &text('confirm_volume_remove', scalar(@n)),
		[ ("c", "volume_remove"), map { ("d", $_) } @n ],
		$text{'stor_remove_volume'}, 'danger');
	my ($f, $o) = &remove_volume(\@n);
	&webmin_log("remove", "volume", join(",", @n)) if (!$f);
	&redir("storage.cgi", $f ? undef : $text{'msg_removed'}, $f ? $o : undef);
	}
elsif ($c eq 'volume_prune') {
	&require_acl('prune');
	&confirm($text{'stor_prune_volumes'}, $text{'confirm_prune_volumes'},
		[ ("c", "volume_prune") ], $text{'stor_prune_volumes'}, 'danger');
	my ($f, $o) = &prune_volumes();
	&webmin_log("prune", "volume", "*") if (!$f);
	&render($text{'stor_prune_volumes'}, $o);
	}
elsif ($c eq 'network_create') {
	&require_acl('create');
	my ($f, $o) = &create_network($in{'name'}, $in{'driver'});
	&webmin_log("create", "network", $in{'name'}) if (!$f);
	&redir("storage.cgi", $f ? undef : $text{'msg_network_created'}, $f ? $o : undef);
	}
elsif ($c eq 'network_remove') {
	&require_acl('delete');
	my @n = &selected("n");
	@n || &redir("storage.cgi", undef, $text{'err_noselection'});
	&confirm($text{'stor_remove_network'}, &text('confirm_network_remove', scalar(@n)),
		[ ("c", "network_remove"), map { ("n", $_) } @n ],
		$text{'stor_remove_network'}, 'danger');
	my ($f, $o) = &remove_network(\@n);
	&webmin_log("remove", "network", join(",", @n)) if (!$f);
	&redir("storage.cgi", $f ? undef : $text{'msg_removed'}, $f ? $o : undef);
	}
elsif ($c eq 'network_prune') {
	&require_acl('prune');
	&confirm($text{'stor_prune_networks'}, $text{'confirm_prune_networks'},
		[ ("c", "network_prune") ], $text{'stor_prune_networks'}, 'danger');
	my ($f, $o) = &prune_networks();
	&webmin_log("prune", "network", "*") if (!$f);
	&render($text{'stor_prune_networks'}, $o);
	}

# ---- maintenance -----------------------------------------------------------

elsif ($c eq 'system_prune') {
	&require_acl('prune');
	&confirm($text{'maint_system_prune'},
		$in{'all'} ? $text{'confirm_system_prune_all'} : $text{'confirm_system_prune'},
		[ ("c", "system_prune"), ("all", $in{'all'}), ("volumes", $in{'volumes'}) ],
		$text{'maint_system_prune'}, 'danger');
	my ($f, $o) = &system_prune($in{'all'}, $in{'volumes'});
	&webmin_log("prune", "system", "*",
		{ 'all' => $in{'all'}, 'volumes' => $in{'volumes'} }) if (!$f);
	&render($text{'maint_system_prune'}, $o);
	}
elsif ($c eq 'builder_prune') {
	&require_acl('prune');
	&confirm($text{'maint_builder_prune'}, $text{'confirm_builder_prune'},
		[ ("c", "builder_prune"), ("all", $in{'all'}) ],
		$text{'maint_builder_prune'}, 'danger');
	my ($f, $o) = &builder_prune($in{'all'});
	&webmin_log("prune", "buildcache", "*") if (!$f);
	&render($text{'maint_builder_prune'}, $o);
	}

# ---- compose ---------------------------------------------------------------

elsif ($c eq 'compose') {
	&require_acl('manage');
	$config{'compose_file'} = $in{'compose_file'};
	&save_module_config();
	my ($f, $o) = &compose_run($in{'compose_file'}, $in{'action'},
		{ 'volumes' => $in{'volumes'} });
	&webmin_log("compose", "project", $in{'compose_file'},
		{ 'action' => $in{'action'} }) if (!$f);
	&render($text{'compose_heading'}, $o eq '' ? $text{'exec_nooutput'} : $o);
	}

# ---- security --------------------------------------------------------------

elsif ($c eq 'scan') {
	&require_acl('view');
	my ($f, $o) = &scan_image($in{'image'});
	&webmin_log("scan", "image", $in{'image'}) if (!$f);
	&render($text{'sec_heading'}, $o eq '' ? $text{'exec_nooutput'} : $o);
	}

# ---- registry --------------------------------------------------------------

elsif ($c eq 'registry_login') {
	&require_acl('registry');
	my ($f, $o) = &registry_login($in{'server'}, $in{'username'}, $in{'password'});
	# Never log the password or its params.
	&webmin_log("login", "registry", $in{'server'}) if (!$f);
	&redir("registry.cgi", $f ? undef : $text{'msg_registry'}, $f ? $o : undef);
	}

# ---- contexts --------------------------------------------------------------

elsif ($c eq 'set_context') {
	&require_acl('context');
	my ($f, $o) = &set_context($in{'context'});
	&webmin_log("context", "docker", $in{'context'}) if (!$f);
	&redir("index.cgi", $f ? undef : $text{'msg_context'}, $f ? $o : undef);
	}

else {
	&error($text{'err_unknown'});
	}
