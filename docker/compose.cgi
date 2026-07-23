#!/usr/bin/perl
# compose.cgi - Docker Compose projects, with per-project one-click actions.

require './docker-lib.pl';
&ReadParse();

our (%config, %text, %in, %access);
%access = &get_module_acl();

&ui_print_header(undef, $text{'compose_title'}, "");

print &ui_alert_box(&html_escape($in{'msg'}), 'success') if ($in{'msg'});
print &ui_alert_box(&html_escape($in{'err'}), 'danger') if ($in{'err'});

my ($kind) = &compose_prefix();
if (!$kind) {
	print &ui_alert_box($text{'compose_notinstalled'}, 'warn');
	&ui_print_footer("index.cgi", $text{'index_return'});
	exit;
	}

print &help_note($text{'compose_intro'});

# ---------------------------------------------------------------------------
# Projects with one-click actions
# ---------------------------------------------------------------------------
my ($lf, $projects) = &compose_ls();
my $dmap = &compose_domain_map();
if ($lf) {
	print &ui_alert_box(&html_escape($projects), 'warn');
	}
elsif (!@$projects) {
	print "<p>".$text{'compose_noproject'}."</p>";
	}
else {
	print &ui_subheading($text{'compose_projects'});
	print &ui_columns_start([ $text{'compose_name'}, $text{'compose_domain'},
		$text{'cont_status'}, $text{'compose_files'},
		$text{'cont_actions'} ], 100);
	foreach my $p (@$projects) {
		my $name = $p->{'name'};
		my $dom = $dmap->{$name};
		my $actions = '';
		if (&can('manage')) {
			foreach my $a ( [ 'update',  $text{'compose_update'} ],
					[ 'restart', $text{'compose_restart'} ],
					[ 'stop',    $text{'compose_stop'} ],
					[ 'start',   $text{'compose_start'} ],
					[ 'logs',    $text{'compose_logs2'} ],
					[ 'ps',      $text{'compose_ps2'} ],
					[ 'down',    $text{'compose_down2'} ] ) {
				$actions .= "<span style='display:inline-block;margin:1px'>".
					&ui_form_start("act.cgi", "post").
					&ui_hidden("c", "compose_project").
					&ui_hidden("project", $name).
					&ui_hidden("paction", $a->[0]).
					&ui_submit($a->[1]).
					&ui_form_end().
					"</span>";
				}
			}
		print &ui_columns_row([
			&html_escape($name),
			$dom ? &ui_link("https://".&urlize($dom), &html_escape($dom), undef,
				"target=_blank") : "",
			&html_escape($p->{'status'}),
			&html_escape($p->{'configfiles'}),
			$actions,
			]);
		}
	print &ui_columns_end();

	# Plain-language legend for non-technical users.
	print &ui_subheading($text{'compose_legend'});
	print "<ul>";
	print "<li><b>".$text{'compose_update'}."</b> &mdash; ".$text{'compose_update_desc'}."</li>";
	print "<li><b>".$text{'compose_restart'}."</b> &mdash; ".$text{'compose_restart_desc'}."</li>";
	print "<li><b>".$text{'compose_stop'}."</b> &mdash; ".$text{'compose_stop_desc'}."</li>";
	print "<li><b>".$text{'compose_start'}."</b> &mdash; ".$text{'compose_start_desc'}."</li>";
	print "<li><b>".$text{'compose_logs2'}."</b> / <b>".$text{'compose_ps2'}."</b> &mdash; ".$text{'compose_readonly_desc'}."</li>";
	print "<li><b>".$text{'compose_down2'}."</b> &mdash; ".&ui_text_color($text{'compose_down_desc'}, 'danger')."</li>";
	print "</ul>";
	print &help_note($text{'compose_update_note'});
	}

# ---------------------------------------------------------------------------
# Advanced: run an action against an arbitrary compose file
# ---------------------------------------------------------------------------
if (&can('manage')) {
	print &ui_hr();
	print &ui_subheading($text{'compose_advanced'});
	print &help_note($text{'compose_abs_hint'});
	print &ui_form_start("act.cgi", "post");
	print &ui_hidden("c", "compose");
	print &ui_table_start($text{'compose_heading'}, undef, 2);
	print &ui_table_row($text{'compose_file'},
		&ui_textbox("compose_file",
			&html_escape($config{'compose_file'} || ""), 70));
	print &ui_table_row($text{'compose_action'},
		&ui_select("action", "", [
			[ "update", $text{'compose_update'} ],
			[ "up", $text{'compose_up'} ],
			[ "restart", $text{'compose_restart'} ],
			[ "stop", $text{'compose_stop'} ],
			[ "start", $text{'compose_start'} ],
			[ "pull", $text{'compose_pull'} ],
			[ "ps", $text{'compose_ps2'} ],
			[ "logs", $text{'compose_logs2'} ],
			[ "config", $text{'compose_validate'} ],
			[ "down", $text{'compose_down2'} ] ]));
	print &ui_table_row($text{'compose_down_volumes'},
		&ui_yesno_radio("volumes", 0)." ".
		&ui_text_color($text{'compose_down_volumes_warn'}, 'danger'));
	print &ui_table_end();
	print &ui_form_end([ [ undef, $text{'compose_run_button'} ] ]);
	}
else {
	print &ui_alert_box($text{'err_noperm'}, 'warn');
	}

&ui_print_footer("index.cgi", $text{'index_return'});
print "<script type='text/javascript'>if (window.viewer_init) { viewer_init() }</script>";
