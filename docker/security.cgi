#!/usr/bin/perl
# security.cgi - image vulnerability scanning (Docker Scout / Trivy).

require './docker-lib.pl';
&ReadParse();

our (%config, %text, %in);

&ui_print_header(undef, $text{'sec_title'}, "");

print &ui_alert_box(&html_escape($in{'msg'}), 'success') if ($in{'msg'});
print &ui_alert_box(&html_escape($in{'err'}), 'danger') if ($in{'err'});

my $scanner = &scanner_available();
if (!$scanner) {
	print &ui_alert_box($text{'sec_noscanner'}, 'warn');
	}
else {
	print &ui_alert_box(&text('sec_using', $scanner), 'info');
	print &ui_form_start("act.cgi", "post");
	print &ui_hidden("c", "scan");
	print &ui_table_start($text{'sec_heading'}, undef, 2);
	print &ui_table_row($text{'create_image'},
		&ui_textbox("image", &html_escape($in{'image'}), 50));
	print &ui_table_end();
	print &ui_form_end([ [ undef, $text{'sec_scan_button'} ] ]);
	}

&ui_print_footer("index.cgi", $text{'index_return'});
