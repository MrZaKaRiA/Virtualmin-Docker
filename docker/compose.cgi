#!/usr/bin/perl
# compose.cgi - Docker Compose projects.

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
	}
else {
	# Project listing (Compose v2 only).
	my ($lf, $projects) = &compose_ls();
	if ($lf) {
		print &ui_alert_box(&html_escape($projects), 'warn');
		}
	elsif (@$projects) {
		print &ui_subheading($text{'compose_projects'});
		print &ui_columns_start([ $text{'compose_name'}, $text{'cont_status'},
			$text{'compose_files'} ], 100);
		foreach my $p (@$projects) {
			print &ui_columns_row([
				&html_escape($p->{'name'}),
				&html_escape($p->{'status'}),
				&html_escape($p->{'configfiles'}),
				]);
			}
		print &ui_columns_end();
		}

	# Run a compose action against a file.
	if (&can('manage')) {
		print &ui_form_start("act.cgi", "post");
		print &ui_hidden("c", "compose");
		print &ui_table_start($text{'compose_heading'}, undef, 2);
		print &ui_table_row($text{'compose_file'},
			&ui_textbox("compose_file", &html_escape($config{'compose_file'} || "docker-compose.yml"), 60));
		print &ui_table_row($text{'compose_action'},
			&ui_select("action", "", [
				[ "up", $text{'compose_up'} ],
				[ "down", $text{'compose_down'} ],
				[ "ps", $text{'compose_ps'} ],
				[ "logs", $text{'compose_logs'} ],
				[ "config", $text{'compose_validate'} ] ]));
		print &ui_table_row($text{'compose_down_volumes'}, &ui_yesno_radio("volumes", 0));
		print &ui_table_end();
		print &ui_form_end([ [ undef, $text{'compose_run_button'} ] ]);
		}
	else {
		print &ui_alert_box($text{'err_noperm'}, 'warn');
		}
	}

&ui_print_footer("index.cgi", $text{'index_return'});
print "<script type='text/javascript'>if (window.viewer_init) { viewer_init() }</script>";
