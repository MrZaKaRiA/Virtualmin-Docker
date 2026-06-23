#!/usr/bin/perl
# maintenance.cgi - disk usage and prune operations.

require './docker-lib.pl';
&ReadParse();

our (%config, %text, %in, %access);
%access = &get_module_acl();

&ui_print_header(undef, $text{'maint_title'}, "");

print &ui_alert_box(&html_escape($in{'msg'}), 'success') if ($in{'msg'});
print &ui_alert_box(&html_escape($in{'err'}), 'danger') if ($in{'err'});

# Disk usage.
print &ui_subheading($text{'maint_df'});
my ($dff, $df) = &system_df();
if ($dff) { print &ui_alert_box(&html_escape($df), 'danger'); }
elsif (!@$df) { print "<p>-</p>"; }
else {
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

if (&can('prune')) {
	print &ui_hr();
	print &ui_form_start("act.cgi", "post");
	print &ui_hidden("c", "system_prune");
	print &ui_table_start($text{'maint_system_prune'}, undef, 2);
	print &ui_table_row($text{'maint_prune_all'}, &ui_yesno_radio("all", 0));
	print &ui_table_row($text{'maint_prune_volumes'}, &ui_yesno_radio("volumes", 0));
	print &ui_table_end();
	print &ui_form_end([ [ undef, $text{'maint_system_prune'} ] ]);

	print &ui_form_start("act.cgi", "post");
	print &ui_hidden("c", "builder_prune");
	print &ui_table_start($text{'maint_builder_prune'}, undef, 2);
	print &ui_table_row($text{'maint_prune_all'}, &ui_yesno_radio("all", 0));
	print &ui_table_end();
	print &ui_form_end([ [ undef, $text{'maint_builder_prune'} ] ]);
	}
else {
	print &ui_alert_box($text{'err_noperm'}, 'warn');
	}

&ui_print_footer("index.cgi", $text{'index_return'});
