#!/usr/bin/perl
# storage.cgi - volumes and networks.

require './docker-lib.pl';
&ReadParse();

our (%config, %text, %in, %access);
%access = &get_module_acl();

&ui_print_header(undef, $text{'stor_title'}, "");

print &ui_alert_box(&html_escape($in{'msg'}), 'success') if ($in{'msg'});
print &ui_alert_box(&html_escape($in{'err'}), 'danger') if ($in{'err'});

# Inspect views (read-only).
if (($in{'action'} || '') eq 'inspect_volume' && $in{'name'}) {
	my ($f, $o) = &inspect_volume($in{'name'});
	print &ui_subheading(&html_escape($in{'name'}));
	print $f ? &ui_alert_box(&html_escape($o), 'danger')
		 : "<pre class='comment'>".&html_escape($o)."</pre>";
	print &ui_hr();
	}
elsif (($in{'action'} || '') eq 'inspect_network' && $in{'name'}) {
	my ($f, $o) = &inspect_network($in{'name'});
	print &ui_subheading(&html_escape($in{'name'}));
	print $f ? &ui_alert_box(&html_escape($o), 'danger')
		 : "<pre class='comment'>".&html_escape($o)."</pre>";
	print &ui_hr();
	}

# ---- Volumes ---------------------------------------------------------------
print &ui_subheading($text{'stor_volumes'});
my ($vf, $vols) = &list_volumes();
if ($vf) { print &ui_alert_box(&html_escape($vols), 'danger'); }
elsif (!@$vols) { print "<p>".$text{'stor_no_volumes'}."</p>"; }
else {
	print &ui_form_start("act.cgi", "post", undef, "id='volform'");
	print &ui_hidden("c", "volume_remove");
	print &bulk_select_links('volform', 'd')."<br>\n";
	print &ui_columns_start([ "", $text{'stor_name'}, $text{'stor_driver'},
		$text{'stor_mount'}, "" ], 100);
	foreach my $v (@$vols) {
		print &ui_checked_columns_row([
			&html_escape($v->{'name'}),
			&html_escape($v->{'driver'}),
			&html_escape($v->{'mountpoint'}),
			&ui_link("storage.cgi?action=inspect_volume&name=".&urlize($v->{'name'}), $text{'cont_inspect'}),
			], undef, "d", $v->{'name'});
		}
	print &ui_columns_end();
	my @b;
	push(@b, [ undef, $text{'stor_remove_volume'} ]) if (&can('delete'));
	print &ui_form_end(\@b);
	}

if (&can('create')) {
	print &ui_form_start("act.cgi", "post");
	print &ui_hidden("c", "volume_create");
	print &ui_table_start($text{'stor_create_volume'}, undef, 2);
	print &ui_table_row($text{'stor_name'}, &ui_textbox("name", "", 30));
	print &ui_table_row($text{'stor_driver'}, &ui_textbox("driver", "", 20));
	print &ui_table_end();
	print &ui_form_end([ [ undef, $text{'create_button'} ] ]);
	}
if (&can('prune')) {
	print &ui_form_start("act.cgi", "post");
	print &ui_hidden("c", "volume_prune");
	print &ui_form_end([ [ undef, $text{'stor_prune_volumes'} ] ]);
	}

# ---- Networks --------------------------------------------------------------
print &ui_hr();
print &ui_subheading($text{'stor_networks'});
my ($nf, $nets) = &list_networks();
if ($nf) { print &ui_alert_box(&html_escape($nets), 'danger'); }
elsif (!@$nets) { print "<p>".$text{'stor_no_networks'}."</p>"; }
else {
	print &ui_form_start("act.cgi", "post", undef, "id='netform'");
	print &ui_hidden("c", "network_remove");
	print &bulk_select_links('netform', 'n')."<br>\n";
	print &ui_columns_start([ "", $text{'stor_name'}, $text{'stor_driver'},
		$text{'dash_type'}, "" ], 100);
	foreach my $n (@$nets) {
		print &ui_checked_columns_row([
			&html_escape($n->{'name'}),
			&html_escape($n->{'driver'}),
			&html_escape($n->{'scope'}),
			&ui_link("storage.cgi?action=inspect_network&name=".&urlize($n->{'name'}), $text{'cont_inspect'}),
			], undef, "n", $n->{'name'});
		}
	print &ui_columns_end();
	my @b;
	push(@b, [ undef, $text{'stor_remove_network'} ]) if (&can('delete'));
	print &ui_form_end(\@b);
	}

if (&can('create')) {
	print &ui_form_start("act.cgi", "post");
	print &ui_hidden("c", "network_create");
	print &ui_table_start($text{'stor_create_network'}, undef, 2);
	print &ui_table_row($text{'stor_name'}, &ui_textbox("name", "", 30));
	print &ui_table_row($text{'stor_driver'}, &ui_textbox("driver", "", 20));
	print &ui_table_end();
	print &ui_form_end([ [ undef, $text{'create_button'} ] ]);
	}
if (&can('prune')) {
	print &ui_form_start("act.cgi", "post");
	print &ui_hidden("c", "network_prune");
	print &ui_form_end([ [ undef, $text{'stor_prune_networks'} ] ]);
	}

&ui_print_footer("index.cgi", $text{'index_return'});
print "<script type='text/javascript'>if (window.viewer_init) { viewer_init() }</script>";
