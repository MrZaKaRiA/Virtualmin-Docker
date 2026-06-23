#!/usr/bin/perl
# images.cgi - image listing, inspection, search, and image actions.

require './docker-lib.pl';
&ReadParse();

our (%config, %text, %in, %access);
%access = &get_module_acl();

&ui_print_header(undef, $text{'img_title'}, "", undef, 0, 0, 0, undef);

print &ui_alert_box(&html_escape($in{'msg'}), 'success') if ($in{'msg'});
print &ui_alert_box(&html_escape($in{'err'}), 'danger') if ($in{'err'});

# Read-only inspect / history (GET).
if (($in{'action'} || '') eq 'inspect' && $in{'image'}) {
	my ($f, $o) = &inspect_image($in{'image'});
	print &ui_subheading(&text('img_inspect_of', &html_escape($in{'image'})));
	print &ui_alert_box(&html_escape($o), 'danger') if ($f);
	print "<pre class='comment'>".&html_escape($o)."</pre>" if (!$f);
	print &ui_hr();
	}
elsif (($in{'action'} || '') eq 'history' && $in{'image'}) {
	my ($f, $o) = &image_history($in{'image'});
	print &ui_subheading(&text('img_history_of', &html_escape($in{'image'})));
	print &ui_alert_box(&html_escape($o), 'danger') if ($f);
	print "<pre class='comment'>".&html_escape($o)."</pre>" if (!$f);
	print &ui_hr();
	}

# Image list with bulk remove.
my ($lf, $images) = &list_images();
if ($lf) {
	print &ui_alert_box(&html_escape($images), 'danger');
	}
elsif (!@$images) {
	print "<p>".$text{'img_none'}."</p>";
	}
else {
	print &ui_form_start("act.cgi", "post", undef, "id='imgform'");
	print &ui_hidden("c", "image_remove");
	print &ui_hidden("force", 1);
	print &bulk_select_links('imgform', 'd')."<br>\n";
	print &ui_columns_start([ "", $text{'img_name'}, $text{'img_size'},
		$text{'img_created'}, $text{'cont_actions'} ], 100);
	foreach my $img (@$images) {
		my $ref = $img->{'name'};
		my $links = join(" | ",
			&ui_link("images.cgi?action=inspect&image=".&urlize($ref), $text{'cont_inspect'}),
			&ui_link("images.cgi?action=history&image=".&urlize($ref), $text{'img_history'}),
			&ui_link("security.cgi?image=".&urlize($ref), $text{'img_scan'}));
		print &ui_checked_columns_row([
			&html_escape($img->{'name'}),
			&html_escape($img->{'size'}),
			&html_escape($img->{'created'}),
			$links,
			], undef, "d", $ref);
		}
	print &ui_columns_end();
	my @b;
	push(@b, [ undef, $text{'img_remove'} ]) if (&can('delete'));
	print &ui_form_end(\@b);
	}

# Docker Hub search (read-only, GET).
print &ui_hr();
print &ui_form_start("images.cgi", "get");
print &ui_table_start($text{'img_search'}, undef, 2);
print &ui_table_row($text{'img_search_term'}, &ui_textbox("q", &html_escape($in{'q'} || ''), 30).
	" ".&ui_textbox("limit", ($in{'limit'} && $in{'limit'} =~ /^\d+$/) ? $in{'limit'} : 25, 4));
print &ui_table_end();
print &ui_form_end([ [ undef, $text{'img_search_button'} ] ]);

if (defined($in{'q'}) && $in{'q'} ne '') {
	my ($sf, $results) = &search_images($in{'q'}, $in{'limit'});
	if ($sf) {
		print &ui_alert_box(&html_escape($results), 'danger');
		}
	elsif (!@$results) {
		print "<p>".$text{'img_search_none'}."</p>";
		}
	else {
		print &ui_columns_start([ $text{'img_name'}, $text{'img_stars'},
			$text{'img_official'}, $text{'img_desc'}, "" ], 100);
		foreach my $r (@$results) {
			my $pull = "";
			if (&can('create')) {
				$pull = &ui_form_start("act.cgi", "post").
					&ui_hidden("c", "pull").
					&ui_hidden("image", $r->{'name'}).
					&ui_submit($text{'img_pull'}).
					&ui_form_end();
				}
			print &ui_columns_row([
				&html_escape($r->{'name'}),
				&html_escape($r->{'stars'}),
				$r->{'official'} ? $text{'yes'} : "",
				&html_escape($r->{'desc'}),
				$pull,
				]);
			}
		print &ui_columns_end();
		}
	}

# Action forms (create-capable users only).
if (&can('create')) {
	print &ui_hr();
	print &ui_form_start("act.cgi", "post");
	print &ui_hidden("c", "pull");
	print &ui_table_start($text{'img_pull'}, undef, 2);
	print &ui_table_row($text{'img_name'}, &ui_textbox("image", "", 50));
	print &ui_table_end();
	print &ui_form_end([ [ undef, $text{'img_pull'} ] ]);

	print &ui_form_start("act.cgi", "post");
	print &ui_hidden("c", "push");
	print &ui_table_start($text{'img_push'}, undef, 2);
	print &ui_table_row($text{'img_name'}, &ui_textbox("image", "", 50));
	print &ui_table_end();
	print &ui_form_end([ [ undef, $text{'img_push'} ] ]);

	print &ui_form_start("act.cgi", "post");
	print &ui_hidden("c", "tag");
	print &ui_table_start($text{'img_tag'}, undef, 2);
	print &ui_table_row($text{'img_from'}, &ui_textbox("source", "", 30));
	print &ui_table_row($text{'img_to'}, &ui_textbox("target", "", 30));
	print &ui_table_end();
	print &ui_form_end([ [ undef, $text{'img_tag'} ] ]);

	print &ui_form_start("act.cgi", "post");
	print &ui_hidden("c", "build");
	print &ui_table_start($text{'img_build'}, undef, 2);
	print &ui_table_row($text{'img_build_tag'}, &ui_textbox("tag", "", 30));
	print &ui_table_row($text{'img_dockerfile'}, &ui_textarea("dockerfile", "", 8, 70));
	print &ui_table_end();
	print &ui_form_end([ [ undef, $text{'img_build'} ] ]);

	print &ui_form_start("act.cgi", "post");
	print &ui_hidden("c", "run_image");
	print &ui_table_start($text{'img_run'}, undef, 2);
	print &ui_table_row($text{'create_image'}, &ui_textbox("image", "", 40));
	print &ui_table_row($text{'create_name'}, &ui_textbox("name", "", 30));
	print &ui_table_row($text{'create_ports'}, &ui_textarea("ports", "", 2, 40));
	print &ui_table_row($text{'create_volumes'}, &ui_textarea("volumes", "", 2, 40));
	print &ui_table_row($text{'create_restart'},
		&ui_select("restart", "", [ ["", $text{'create_default'}],
			"no", "on-failure", "always", "unless-stopped" ]));
	print &ui_table_end();
	print &ui_form_end([ [ undef, $text{'img_run'} ] ]);
	}

if (&can('prune')) {
	print &ui_hr();
	print &ui_form_start("act.cgi", "post");
	print &ui_hidden("c", "prune_images");
	print &ui_checkbox("all", 1, $text{'img_prune_all'}, 0)."<br>";
	print &ui_form_end([ [ undef, $text{'img_prune'} ] ]);
	}

&ui_print_footer("index.cgi", $text{'index_return'});
print "<script type='text/javascript'>if (window.viewer_init) { viewer_init() }</script>";
