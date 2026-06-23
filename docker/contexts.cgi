#!/usr/bin/perl
# contexts.cgi - list and switch the Docker context the module talks to.

require './docker-lib.pl';
&ReadParse();

our (%config, %text, %in, %access);
%access = &get_module_acl();

&ui_print_header(undef, $text{'ctx_title'}, "");

print &ui_alert_box(&html_escape($in{'msg'}), 'success') if ($in{'msg'});
print &ui_alert_box(&html_escape($in{'err'}), 'danger') if ($in{'err'});

my ($cf, $contexts) = &list_contexts();
if ($cf) {
	print &ui_alert_box(&html_escape($contexts), 'danger');
	}
else {
	print "<p>".&text('ctx_current',
		"<tt>".&html_escape($config{'docker_context'} || 'default')."</tt>")."</p>";
	if (&can('context')) {
		print &ui_form_start("act.cgi", "post");
		print &ui_hidden("c", "set_context");
		print &ui_table_start($text{'ctx_heading'}, undef, 2);
		print &ui_table_row($text{'ctx_select'},
			&ui_select("context", $config{'docker_context'} || 'default',
				[ map { [ $_->{'name'},
					  $_->{'name'}.($_->{'current'} ? " ".$text{'ctx_active'} : "") ] }
				  @$contexts ]));
		print &ui_table_end();
		print &ui_form_end([ [ undef, $text{'ctx_switch_button'} ] ]);
		}
	else {
		print &ui_columns_start([ $text{'stor_name'}, $text{'ctx_desc'},
			$text{'ctx_endpoint'} ], 100);
		foreach my $c (@$contexts) {
			print &ui_columns_row([
				&html_escape($c->{'name'}).($c->{'current'} ? " ".$text{'ctx_active'} : ""),
				&html_escape($c->{'desc'}),
				&html_escape($c->{'endpoint'}),
				]);
			}
		print &ui_columns_end();
		}
	}

&ui_print_footer("index.cgi", $text{'index_return'});
