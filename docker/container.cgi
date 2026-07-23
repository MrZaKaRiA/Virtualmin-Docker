#!/usr/bin/perl
# container.cgi - per-container detail (logs, inspect, exec, stats, manage).
# Read-only views; every mutation posts to act.cgi.

require './docker-lib.pl';
&ReadParse();

our (%config, %text, %in, %access);
%access = &get_module_acl();

my $id = $in{'id'};
&is_valid_ref($id) || do {
	&ui_print_header(undef, $text{'cont_title_unknown'}, "");
	print &ui_alert_box($text{'err_badref'}, 'danger');
	&ui_print_footer("index.cgi", $text{'index_return'});
	exit;
	};

# Resolve a friendly name (strips the leading slash docker adds).
my ($nf, $name, $nerr) = &run_docker('container inspect --format "{{.Name}}" '.&sq($id), undef, 1);
if ($nf) {
	&ui_print_header(undef, $text{'cont_title_unknown'}, "");
	print &ui_alert_box(&html_escape($nerr || $name || $text{'err_badref'}), 'danger');
	&ui_print_footer("index.cgi", $text{'index_return'});
	exit;
	}
$name =~ s/^\s*\/?//; $name =~ s/\s+$//;
my $disp = $name ne '' ? $name : $id;

# Plain-text log download.
if (($in{'tab'} || '') eq 'log' && $in{'download'}) {
	my ($f, $log) = &container_logs($id, { 'tail' => 5000, 'timestamps' => $in{'timestamps'} });
	print "Content-type: text/plain\n";
	print "Content-Disposition: attachment; filename=\"".$disp.".log\"\n\n";
	print $log;
	exit;
	}

&ui_print_header(undef, &text('cont_title', &html_escape($disp)), "");

print &ui_alert_box(&html_escape($in{'msg'}), 'success') if ($in{'msg'});
print &ui_alert_box(&html_escape($in{'err'}), 'danger') if ($in{'err'});

my $tab = $in{'tab'} || 'log';
my @tabs = ( [ 'log', $text{'tab_log'} ],
	     [ 'details', $text{'tab_details'} ],
	     [ 'inspect', $text{'tab_inspect'} ],
	     [ 'network', $text{'tab_network'} ],
	     [ 'top', $text{'tab_top'} ],
	     [ 'exec', $text{'tab_exec'} ],
	     [ 'stats', $text{'tab_stats'} ],
	     [ 'manage', $text{'tab_manage'} ] );
print &ui_tabs_start(\@tabs, 'tab', $tab, 1);

# ---- LOG -------------------------------------------------------------------
print &ui_tabs_start_tab('tab', 'log');
my $tail = ($in{'tail'} && $in{'tail'} =~ /^\d+$/) ? $in{'tail'} : ($config{'max_log_lines'} || 100);
my ($lf, $log) = &container_logs($id, {
	'tail'       => $tail,
	'timestamps' => $in{'timestamps'},
	'since'      => $in{'since'},
	'filter'     => $in{'filter'},
	'nocase'     => $in{'nocase'},
	});
print &ui_alert_box(&html_escape($log), 'danger') if ($lf);

print &ui_form_start("container.cgi", "get");
print &ui_hidden("id", $id);
print &ui_hidden("tab", "log");
print $text{'log_tail'}." ".&ui_textbox("tail", $tail, 5)." ";
print $text{'log_since'}." ".&ui_textbox("since", &html_escape($in{'since'} || ''), 12)." ";
print $text{'log_filter'}." ".&ui_textbox("filter", &html_escape($in{'filter'} || ''), 30)." ";
print &ui_checkbox("timestamps", 1, $text{'log_timestamps'}, $in{'timestamps'})." ";
print &ui_checkbox("nocase", 1, $text{'log_nocase'}, $in{'nocase'})." ";
print $text{'log_refresh'}." ".&ui_select("auto-refresh", $in{'auto-refresh'},
	[ ["", $text{'log_never'}], 3, 10, 30, 60 ]);
print &ui_form_end([ [ undef, $text{'act_refresh'} ] ]);

print "<p>".&ui_link("container.cgi?tab=log&download=1&id=".&urlize($id).
	($in{'timestamps'} ? "&timestamps=1" : ""), $text{'log_download'})."</p>";

print "<pre id='container-log'>".&html_escape($lf ? '' : $log)."</pre>";

# Auto-refresh: poll this page and swap in the fresh log block.
my $self = "container.cgi?tab=log&id=".&urlize($id)."&tail=".int($tail).
	($in{'timestamps'} ? "&timestamps=1" : "").
	($in{'nocase'} ? "&nocase=1" : "").
	((defined($in{'since'}) && $in{'since'} ne '') ? "&since=".&urlize($in{'since'}) : "").
	((defined($in{'filter'}) && $in{'filter'} ne '') ? "&filter=".&urlize($in{'filter'}) : "");
print <<"EOJS";
<script type="text/javascript">
(function() {
  var timer, sel = document.querySelector("select[name='auto-refresh']");
  function refresh() {
    if (!window.jQuery) { return; }
    jQuery.get("$self", function(resp) {
      var d = jQuery(jQuery.parseHTML(resp)).find("pre#container-log");
      jQuery("pre#container-log").text(d.text());
    });
  }
  function setup(p) { if (timer) { clearInterval(timer); timer = null; }
    if (p) { timer = setInterval(refresh, p * 1000); } }
  if (sel) { sel.addEventListener("change", function(e) {
    setup(e.target.value === "" ? null : e.target.value); }); }
})();
</script>
EOJS
print &ui_tabs_end_tab();

# ---- DETAILS (readable) ----------------------------------------------------
print &ui_tabs_start_tab('tab', 'details');
my ($df, $det) = &container_details($id);
if ($df) { print &ui_alert_box(&html_escape($det), 'danger'); }
else {
	print &ui_table_start($text{'tab_details'}, undef, 2);
	print &ui_table_row($text{'cont_name'}, &html_escape($det->{'name'}));
	print &ui_table_row($text{'cont_image'}, &html_escape($det->{'image'}));
	print &ui_table_row($text{'cont_status'},
		&state_label($det->{'state'}, $det->{'state'}).
		($det->{'health'} ? " (".&html_escape($det->{'health'}).")" : ""));
	print &ui_table_row($text{'det_created'}, &html_escape($det->{'created'}));
	print &ui_table_row($text{'det_started'}, &html_escape($det->{'started'}));
	print &ui_table_row($text{'create_restart'}, &html_escape($det->{'restart'}));
	print &ui_table_row($text{'det_project'}, &html_escape($det->{'project'} || "-"));
	print &ui_table_row($text{'det_entrypoint'}, "<tt>".&html_escape($det->{'entrypoint'} || "-")."</tt>");
	print &ui_table_row($text{'det_cmd'}, "<tt>".&html_escape($det->{'cmd'} || "-")."</tt>");
	print &ui_table_row($text{'det_ports'},
		@{$det->{'ports'}} ? join("<br>", map { &html_escape($_) } @{$det->{'ports'}}) : "-");
	print &ui_table_row($text{'det_mounts'},
		@{$det->{'mounts'}} ? join("<br>", map {
			&html_escape($_->{'src'})." &rarr; ".&html_escape($_->{'dst'}).
			" (".$_->{'mode'}.", ".&html_escape($_->{'type'}).")" } @{$det->{'mounts'}}) : "-");
	print &ui_table_row($text{'det_networks'},
		@{$det->{'networks'}} ? join("<br>", map {
			"<b>".&html_escape($_->{'name'})."</b> ".&html_escape($_->{'ip'} || "") } @{$det->{'networks'}}) : "-");
	print &ui_table_row($text{'det_env'},
		@{$det->{'env'}} ? "<pre class='comment' style='max-height:260px;overflow:auto'>".
			join("\n", map { &html_escape($_) } @{$det->{'env'}})."</pre>" : "-");
	print &ui_table_end();
	}
print &ui_tabs_end_tab();

# ---- INSPECT (raw JSON) ----------------------------------------------------
print &ui_tabs_start_tab('tab', 'inspect');
my ($inf, $insp) = &inspect_container($id);
if ($inf) { print &ui_alert_box(&html_escape($insp), 'danger'); }
else { print "<pre class='comment'>".&html_escape($insp)."</pre>"; }
print &ui_tabs_end_tab();

# ---- NETWORK (connect / disconnect) ----------------------------------------
print &ui_tabs_start_tab('tab', 'network');
my ($ndf, $ndet) = &container_details($id);
if (!$ndf && @{$ndet->{'networks'}}) {
	print &ui_columns_start([ $text{'stor_name'}, "IP", "" ], 100);
	foreach my $n (@{$ndet->{'networks'}}) {
		my $disc = "";
		if (&can('manage')) {
			$disc = &ui_form_start("act.cgi", "post").
				&ui_hidden("c", "net_disconnect").
				&ui_hidden("id", $id).
				&ui_hidden("network", $n->{'name'}).
				&ui_submit($text{'net_disconnect'}).
				&ui_form_end();
			}
		print &ui_columns_row([ "<b>".&html_escape($n->{'name'})."</b>",
			&html_escape($n->{'ip'} || ""), $disc ]);
		}
	print &ui_columns_end();
	}
if (&can('manage')) {
	my ($nlf, $nets) = &list_networks();
	if (!$nlf) {
		print &ui_form_start("act.cgi", "post");
		print &ui_hidden("c", "net_connect");
		print &ui_hidden("id", $id);
		print &ui_table_start($text{'net_connect_to'}, undef, 2);
		print &ui_table_row($text{'tab_network'},
			&ui_select("network", "", [ map { [ $_->{'name'}, $_->{'name'} ] } @$nets ]));
		print &ui_table_end();
		print &ui_form_end([ [ undef, $text{'net_connect'} ] ]);
		}
	}
print &ui_tabs_end_tab();

# ---- TOP (processes) -------------------------------------------------------
print &ui_tabs_start_tab('tab', 'top');
my ($tf, $topout) = &docker_top($id);
if ($tf) { print &ui_alert_box(&html_escape($topout), 'warn'); }
else { print "<pre class='comment'>".&html_escape($topout)."</pre>"; }
print &ui_tabs_end_tab();

# ---- EXEC ------------------------------------------------------------------
print &ui_tabs_start_tab('tab', 'exec');
if (&can('exec')) {
	# Quick-shell buttons.
	print &ui_subheading($text{'exec_quick'});
	my @quick = ('ls -la', 'ps aux', 'env', 'df -h', 'cat /etc/os-release', 'uname -a');
	foreach my $q (@quick) {
		print &ui_form_start("act.cgi", "post");
		print &ui_hidden("c", "exec");
		print &ui_hidden("id", $id);
		print &ui_hidden("cmd", $q);
		print &ui_submit($q);
		print &ui_form_end();
		}

	print &ui_hr();
	print &ui_form_start("act.cgi", "post");
	print &ui_hidden("c", "exec");
	print &ui_hidden("id", $id);
	print &ui_table_start($text{'exec_custom'}, undef, 2);
	print &ui_table_row($text{'exec_command'}, &ui_textbox("cmd", "", 50));
	print &ui_table_end();
	print &ui_form_end([ [ undef, $text{'exec_run'} ] ]);

	print &ui_hr();
	print &ui_form_start("act.cgi", "post");
	print &ui_hidden("c", "copy_to");
	print &ui_hidden("id", $id);
	print &ui_table_start($text{'copy_to'}, undef, 2);
	print &ui_table_row($text{'copy_host_path'}, &ui_textbox("host_path", "", 40));
	print &ui_table_row($text{'copy_target_path'}, &ui_textbox("target_path", "/tmp", 30));
	print &ui_table_end();
	print &ui_form_end([ [ undef, $text{'copy_button'} ] ]);

	print &ui_form_start("act.cgi", "post");
	print &ui_hidden("c", "copy_from");
	print &ui_hidden("id", $id);
	print &ui_table_start($text{'copy_from'}, undef, 2);
	print &ui_table_row($text{'copy_source_path'}, &ui_textbox("source_path", "/", 30));
	print &ui_table_row($text{'copy_host_dest'}, &ui_textbox("host_dest", "/tmp", 30));
	print &ui_table_end();
	print &ui_form_end([ [ undef, $text{'copy_button'} ] ]);
	}
else {
	print &ui_alert_box($text{'err_noperm'}, 'warn');
	}
print &ui_tabs_end_tab();

# ---- STATS -----------------------------------------------------------------
print &ui_tabs_start_tab('tab', 'stats');
my ($stf, $stats) = &container_stats();
my $st = (!$stf && ($stats->{$id} || $stats->{$name})) || {};
print &ui_table_start($text{'tab_stats'}, undef, 2);
print &ui_table_row($text{'cont_cpu'}, &html_escape($st->{'cpu'} || '-'));
print &ui_table_row($text{'stats_mem'}, &html_escape(($st->{'memusage'} || '-')." (".($st->{'mem'} || '-').")"));
print &ui_table_row($text{'stats_net'}, &html_escape($st->{'netio'} || '-'));
print &ui_table_row($text{'stats_block'}, &html_escape($st->{'blockio'} || '-'));
print &ui_table_row($text{'stats_pids'}, &html_escape($st->{'pids'} || '-'));
print &ui_table_end();
print &ui_tabs_end_tab();

# ---- MANAGE ----------------------------------------------------------------
print &ui_tabs_start_tab('tab', 'manage');
if (&can('manage')) {
	print &ui_form_start("act.cgi", "post");
	print &ui_hidden("c", "rename");
	print &ui_hidden("id", $id);
	print &ui_table_start($text{'manage_rename'}, undef, 2);
	print &ui_table_row($text{'manage_newname'}, &ui_textbox("newname", "", 30));
	print &ui_table_end();
	print &ui_form_end([ [ undef, $text{'manage_rename_button'} ] ]);

	print &ui_form_start("act.cgi", "post");
	print &ui_hidden("c", "update");
	print &ui_hidden("id", $id);
	print &ui_table_start($text{'manage_update'}, undef, 2);
	print &ui_table_row($text{'create_memory'}, &ui_textbox("memory", "", 12));
	print &ui_table_row($text{'create_cpus'}, &ui_textbox("cpus", "", 12));
	print &ui_table_row($text{'manage_pids'}, &ui_textbox("pids", "", 12));
	print &ui_table_row($text{'create_restart'},
		&ui_select("restart", "", [ ["", $text{'create_default'}],
			"no", "on-failure", "always", "unless-stopped" ]));
	print &ui_table_end();
	print &ui_form_end([ [ undef, $text{'manage_update_button'} ] ]);
	}

# Backup: commit to an image / export the filesystem to a host tar.
if (&can('backup')) {
	my $bdir = $config{'backup_dir'} || "/var/backups/docker";
	print &ui_hr();
	print &ui_form_start("act.cgi", "post");
	print &ui_hidden("c", "container_commit");
	print &ui_hidden("id", $id);
	print &ui_table_start($text{'container_commit'}, undef, 2);
	print &ui_table_row($text{'container_commit_image'}, &ui_textbox("image", "", 30));
	print &ui_table_end();
	print &ui_form_end([ [ undef, $text{'container_commit_button'} ] ]);

	print &ui_form_start("act.cgi", "post");
	print &ui_hidden("c", "container_export");
	print &ui_hidden("id", $id);
	print &ui_table_start($text{'container_export'}, undef, 2);
	print &ui_table_row($text{'backup_path'}, &ui_textbox("path", "$bdir/$disp.tar", 50));
	print &ui_table_end();
	print &ui_form_end([ [ undef, $text{'container_export_button'} ] ]);
	}

# Connect a Virtualmin domain to this container's published port.
if (&can('proxy') && &has_virtualmin()) {
	my ($clf, $clist) = &list_containers();
	my ($me) = !$clf ? grep { $_->{'id'} eq $id || $_->{'name'} eq $name } @$clist : ();
	my @cports = $me ? &container_host_ports($me->{'ports'}) : ();
	if (@cports) {
		my $doms = &virtualmin_domains();
		print &ui_hr();
		print &ui_form_start("act.cgi", "post");
		print &ui_hidden("c", "connect_domain");
		print &ui_hidden("id", $id);
		print &ui_table_start($text{'cont_connect_domain'}, undef, 2);
		print &ui_table_row($text{'proxy_domain'},
			&ui_select("domain", "", [ map { [ $_->{'dom'}, $_->{'dom'} ] } @$doms ]));
		print &ui_table_row($text{'det_ports'},
			&ui_select("port", $cports[0], [ map { [ $_, "port ".$_ ] } @cports ]));
		print &ui_table_end();
		print &ui_form_end([ [ undef, $text{'cont_connect_button'} ] ]);
		print &help_note($text{'cont_connect_note'});
		}
	}

# Remove this container.
if (&can('delete')) {
	print &ui_hr();
	print &ui_form_start("act.cgi", "post");
	print &ui_hidden("c", "container_bulk");
	print &ui_hidden("d", $id);
	print &ui_hidden("remove", 1);
	print &ui_table_start($text{'manage_remove'}, undef, 2);
	print &ui_table_row($text{'manage_remove_hint'}, "&nbsp;");
	print &ui_table_end();
	print &ui_form_end([ [ undef, $text{'manage_remove_button'} ] ]);
	}

if (!&can('manage') && !&can('backup') && !&can('delete')) {
	print &ui_alert_box($text{'err_noperm'}, 'warn');
	}
print &ui_tabs_end_tab();

print &ui_tabs_end(1);
&ui_print_footer("index.cgi", $text{'index_return'});
print "<script type='text/javascript'>if (window.viewer_init) { viewer_init() }</script>";
