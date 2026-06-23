#!/usr/bin/perl
# index.cgi - Docker overview dashboard + container management.
# This page is READ-ONLY: every state change is submitted by POST to act.cgi,
# which is covered by Webmin's trusted-referer check.

require './docker-lib.pl';
&ReadParse();

our (%config, %text, %in, %access);
%access = &get_module_acl();

&ui_print_header(undef, $text{'index_title'}, "", undef, 1, 1);

if (!&has_command('docker')) {
	&ui_print_endpage($text{'index_notinstalled'});
	}

# Feedback from act.cgi redirects.
print &ui_alert_box(&html_escape($in{'msg'}), 'success') if ($in{'msg'});
print &ui_alert_box(&html_escape($in{'err'}), 'danger') if ($in{'err'});
if ($config{'docker_context'}) {
	print &ui_alert_box(&text('index_context', &html_escape($config{'docker_context'})), 'info');
	}

# ---------------------------------------------------------------------------
# Dashboard summary
# ---------------------------------------------------------------------------
my $sum = &summary_counts();
if (!$sum->{'ok'}) {
	print &ui_alert_box(
		&text('index_daemondown', &html_escape($sum->{'error'} || '')), 'danger');
	}
else {
	my @cells;
	push(@cells, &dash_cell($text{'dash_running'}, $sum->{'running'}, 'success'));
	push(@cells, &dash_cell($text{'dash_paused'},  $sum->{'paused'},  'warn'));
	push(@cells, &dash_cell($text{'dash_stopped'}, $sum->{'stopped'}, 'danger'));
	push(@cells, &dash_cell($text{'dash_images'},  $sum->{'images'},  'info'));
	print &ui_grid_table(\@cells, 4, 100,
		[ map { "width=25% style='text-align:center'" } (1..4) ]);

	# Disk usage from "docker system df".
	my ($dffail, $df) = &system_df();
	if (!$dffail && @$df) {
		print &ui_columns_start([ $text{'dash_type'}, $text{'dash_total'},
			$text{'dash_active'}, $text{'dash_size'}, $text{'dash_reclaim'} ], 100);
		foreach my $r (@$df) {
			print &ui_columns_row([
				&html_escape($r->{'Type'}),
				&html_escape($r->{'TotalCount'}),
				&html_escape($r->{'Active'}),
				&html_escape($r->{'Size'}),
				&html_escape($r->{'Reclaimable'}),
				]);
			}
		print &ui_columns_end();
		}
	print "<p>".&text('dash_host',
		&html_escape($sum->{'name'} || '?'),
		&html_escape($sum->{'version'} || '?'))."</p>";
	}

# ---------------------------------------------------------------------------
# Navigation to the other sections
# ---------------------------------------------------------------------------
my @nav = (
	&ui_link("images.cgi", $text{'nav_images'}),
	&ui_link("compose.cgi", $text{'nav_compose'}),
	&ui_link("storage.cgi", $text{'nav_storage'}),
	&ui_link("maintenance.cgi", $text{'nav_maintenance'}),
	&ui_link("security.cgi", $text{'nav_security'}),
	&ui_link("registry.cgi", $text{'nav_registry'}),
	&ui_link("contexts.cgi", $text{'nav_contexts'}),
	);
print "<p>".join(" &nbsp;|&nbsp; ", @nav)."</p>";
print &ui_hr();

# ---------------------------------------------------------------------------
# Container list with bulk actions
# ---------------------------------------------------------------------------
print &ui_subheading($text{'cont_heading'});
my ($cfail, $containers) = &list_containers();
if ($cfail) {
	print &ui_alert_box(&html_escape($containers), 'danger');
	}
elsif (!@$containers) {
	print "<p>".$text{'cont_none'}."</p>";
	}
else {
	# Live stats are optional (one extra docker call); enabled in module config.
	my $stats = {};
	if ($config{'show_stats'}) {
		my ($sfail, $s) = &container_stats();
		$stats = $s if (!$sfail);
		}

	print &ui_form_start("act.cgi", "post", undef, "id='contform'");
	print &ui_hidden("c", "container_bulk");
	print &bulk_select_links('contform', 'd')."<br>\n";
	print &ui_columns_start([
		"", $text{'cont_name'}, $text{'cont_status'}, $text{'cont_image'},
		$text{'cont_cpu'}, $text{'cont_mem'}, $text{'cont_actions'} ], 100);
	foreach my $c (@$containers) {
		my $st = $stats->{$c->{'id'}} || $stats->{$c->{'name'}} || {};
		my $links = join(" | ",
			&ui_link("container.cgi?tab=log&id=".&urlize($c->{'id'}), $text{'cont_logs'}),
			&ui_link("container.cgi?tab=inspect&id=".&urlize($c->{'id'}), $text{'cont_inspect'}),
			&ui_link("container.cgi?tab=exec&id=".&urlize($c->{'id'}), $text{'cont_exec'}));
		print &ui_checked_columns_row([
			&ui_link("container.cgi?id=".&urlize($c->{'id'}), &html_escape($c->{'name'})),
			&state_label($c->{'state'}, $c->{'status'}),
			&html_escape($c->{'image'}),
			&html_escape($st->{'cpu'} || ''),
			&html_escape(($st->{'memusage'} || '').($st->{'mem'} ? " (".$st->{'mem'}.")" : '')),
			$links,
			], undef, "d", $c->{'id'});
		}
	print &ui_columns_end();

	# Action buttons - gated by ACL.
	my @buttons;
	if (&can('manage')) {
		push(@buttons, [ "start",   $text{'act_start'} ]);
		push(@buttons, [ "stop",    $text{'act_stop'} ]);
		push(@buttons, [ "restart", $text{'act_restart'} ]);
		push(@buttons, [ "pause",   $text{'act_pause'} ]);
		push(@buttons, [ "unpause", $text{'act_unpause'} ]);
		push(@buttons, [ "kill",    $text{'act_kill'} ]);
		}
	if (&can('delete')) {
		push(@buttons, [ "remove", $text{'act_remove'} ]);
		}
	print &ui_form_end(\@buttons);
	}

# ---------------------------------------------------------------------------
# Create / clone container
# ---------------------------------------------------------------------------
if (&can('create')) {
	print &ui_hr();
	print &ui_form_start("act.cgi", "post");
	print &ui_hidden("c", "create");
	print &ui_table_start($text{'create_heading'}, undef, 2);
	print &ui_table_row($text{'create_name'}, &ui_textbox("name", "", 30));
	print &ui_table_row($text{'create_image'}, &ui_textbox("image", "", 40));
	print &ui_table_row($text{'create_command'}, &ui_textbox("command", "", 40));
	print &ui_table_row($text{'create_env'}, &ui_textarea("env", "", 3, 50));
	print &ui_table_row($text{'create_ports'}, &ui_textarea("ports", "", 3, 50));
	print &ui_table_row($text{'create_volumes'}, &ui_textarea("volumes", "", 3, 50));
	print &ui_table_row($text{'create_network'}, &ui_textbox("network", "", 30));
	print &ui_table_row($text{'create_restart'},
		&ui_select("restart", "", [ ["", $text{'create_default'}],
			"no", "on-failure", "always", "unless-stopped" ]));
	print &ui_table_row($text{'create_memory'}, &ui_textbox("memory", "", 12));
	print &ui_table_row($text{'create_cpus'}, &ui_textbox("cpus", "", 12));
	print &ui_table_row($text{'create_hardened'},
		&ui_yesno_radio("hardened", 0));
	print &ui_table_end();
	print &ui_form_end([ [ undef, $text{'create_button'} ] ]);

	if (!$cfail && @$containers) {
		print &ui_form_start("act.cgi", "post");
		print &ui_hidden("c", "clone");
		print &ui_table_start($text{'clone_heading'}, undef, 2);
		print &ui_table_row($text{'clone_source'},
			&ui_select("source", "",
				[ map { [ $_->{'name'}, $_->{'name'} ] } @$containers ]));
		print &ui_table_row($text{'clone_name'}, &ui_textbox("name", "", 30));
		print &ui_table_end();
		print &ui_form_end([ [ undef, $text{'clone_button'} ] ]);
		}
	}

&ui_print_footer("/", $text{'index_return_main'});

# Re-enable code highlighting if the theme supports it.
print "<script type='text/javascript'>if (window.viewer_init) { viewer_init() }</script>";

# dash_cell(LABEL, VALUE, LEVEL) - a big coloured number for the summary grid.
sub dash_cell
{
my ($label, $value, $level) = @_;
$value = 0 if (!defined($value));
return "<div style='font-size:200%'>".
	&ui_text_color(&html_escape($value), $level)."</div>".
	"<div>".&html_escape($label)."</div>";
}
