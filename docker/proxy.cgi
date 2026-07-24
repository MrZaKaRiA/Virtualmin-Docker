#!/usr/bin/perl
# proxy.cgi - Virtualmin reverse-proxy management: see which domain proxies to
# which container, spot broken proxies (pointing at a dead port), and repoint a
# domain to a running container's port in one click.

require './docker-lib.pl';
&ReadParse();

our (%config, %text, %in, %access);
%access = &get_module_acl();

&ui_print_header(undef, $text{'proxy_title'}, "");
print &dk_style();

print &ui_alert_box(&html_escape($in{'msg'}), 'success') if ($in{'msg'});
print &ui_alert_box(&html_escape($in{'err'}), 'danger') if ($in{'err'});

if (!&has_virtualmin()) {
	print &ui_alert_box($text{'proxy_novm'}, 'warn');
	&ui_print_footer("index.cgi", $text{'index_return'});
	exit;
	}

print &help_note($text{'proxy_intro'});

# Read-only diagnostic: show exactly what Virtualmin reports for one domain.
if ($in{'diag'} && &is_valid_domain($in{'diag'})) {
	print &ui_subheading(&text('proxy_diag_for', &html_escape($in{'diag'})));
	my ($lf, $proxies) = &list_domain_proxies($in{'diag'});
	my $raw = "list-proxies --domain ".$in{'diag'}." --multiline:\n";
	if ($lf) { $raw .= "  ERROR: ".$proxies."\n"; }
	elsif (!@$proxies) { $raw .= "  (no proxy balancers found)\n"; }
	else {
		foreach my $p (@$proxies) {
			$raw .= "  path=".($p->{'path'}//'?')."  proxying=".($p->{'proxying'}//'?').
				"  url=".($p->{'url'}//'?')."\n";
			}
	}
	my ($d) = grep { $_->{'dom'} eq $in{'diag'} } @{&virtualmin_domains()};
	$raw .= "\ndomain config proxy_pass = ".($d && $d->{'proxy_pass'} ? $d->{'proxy_pass'} : "(unset)")."\n";
	# The web server determines which proxy mechanism applies.
	my $ws = "unknown";
	eval {
		&foreign_require("virtual-server");
		my $vd = &virtual_server::get_domain_by("dom", $in{'diag'});
		if ($vd) {
			my $w = &virtual_server::domain_has_website($vd);
			$ws = $w eq 'web' ? "Apache (proxy balancers)" : ($w || "none");
			}
		};
	$raw .= "web server = $ws\n";
	$raw .= "virtualmin binary = ".(&virtualmin_bin() || "(not found)")."\n";
	print "<pre class='comment'>".&html_escape($raw)."</pre>";
	print &ui_hr();
}

my $doms = &virtualmin_domains();
my @proxied = grep { $_->{'proxy_pass'} } @$doms;
my $pubs = &running_publishers();
my $dcm = &domain_container_map();   # domain -> { port, container }

# Options for the "reconnect to" selector: running containers and their ports.
my @portopts = map { [ $_->{'port'}, $_->{'name'}." (port ".$_->{'port'}.")" ] } @$pubs;

# Which host ports currently have a running container.
my %live;
$live{$_->{'port'}} ||= $_->{'name'} foreach (@$pubs);

if (!@proxied) {
	print "<p>".$text{'proxy_none'}."</p>";
	}
else {
	print &ui_columns_start([ $text{'proxy_domain'}, $text{'proxy_target'},
		$text{'proxy_state'}, $text{'proxy_reconnect'} ], 100);
	foreach my $d (@proxied) {
		my $port = &proxy_pass_port($d->{'proxy_pass'});
		my $local = ($d->{'proxy_pass'} =~ m!^https?://(localhost|127\.0\.0\.1)!i);
		my $own = $dcm->{$d->{'dom'}};       # this domain's own running container
		my ($state, $form) = ("", "");

		if (!$local) {
			$state = &dk_badge($text{'proxy_external'}, 'info');
			}
		elsif ($live{$port}) {
			$state = &dk_badge("&#10003; ".&text('proxy_ok', &html_escape($live{$port})), 'ok', 1);
			}
		elsif ($own) {
			# Regressed: its own container is on a different port. One-click fix.
			$state = &dk_badge("&#9888; ".&text('proxy_regressed',
				$own->{'port'}, &html_escape($own->{'container'})), 'err', 1);
			if (&can('proxy')) {
				$form = &ui_form_start("act.cgi", "post").
					&ui_hidden("c", "set_proxy").
					&ui_hidden("domain", $d->{'dom'}).
					&ui_hidden("port", $own->{'port'}).
					&ui_submit(&text('proxy_fix_to', $own->{'port'})).
					&ui_form_end();
				}
			}
		else {
			# No running container for this domain - not deployed.
			$state = &dk_badge("&#9679; ".&text('proxy_undeployed', $port), 'warn', 1);
			}

		# Fallback manual selector (any running container) for local rows that
		# have no exact suggestion, so nothing is a dead end.
		if (&can('proxy') && $local && !$live{$port} && !$own && @portopts) {
			$form = &ui_form_start("act.cgi", "post").
				&ui_hidden("c", "set_proxy").
				&ui_hidden("domain", $d->{'dom'}).
				&ui_select("port", $portopts[0]->[0], \@portopts).
				" ".&ui_submit($text{'proxy_apply'}).
				&ui_form_end();
			}

		print &ui_columns_row([
			&ui_link("https://".&urlize($d->{'dom'}), &html_escape($d->{'dom'}), undef,
				"target=_blank"),
			"<tt>".&html_escape($d->{'proxy_pass'})."</tt> ".
				&ui_link("proxy.cgi?diag=".&urlize($d->{'dom'}),
					"<small>[".$text{'proxy_diag'}."]</small>"),
			$state,
			$form,
			]);
		}
	print &ui_columns_end();
	print &help_note($text{'proxy_legend'});
	}

# Advanced: set an exact URL.
if (&can('proxy')) {
	print &ui_hr();
	print &ui_subheading($text{'proxy_advanced'});
	print &ui_form_start("act.cgi", "post");
	print &ui_hidden("c", "set_proxy");
	print &ui_table_start($text{'proxy_manual'}, undef, 2);
	print &ui_table_row($text{'proxy_domain'},
		&ui_select("domain", "", [ map { [ $_->{'dom'}, $_->{'dom'} ] } @$doms ]));
	print &ui_table_row($text{'proxy_url'},
		&ui_textbox("url", "http://localhost:3000/", 40));
	print &ui_table_end();
	print &ui_form_end([ [ undef, $text{'proxy_apply'} ] ]);
	print &help_note($text{'proxy_manual_note'});
	}

&ui_print_footer("index.cgi", $text{'index_return'});
