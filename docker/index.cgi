#!/usr/bin/perl
# index.cgi - Docker overview dashboard + container management.
# This page is READ-ONLY: every state change is submitted by POST to act.cgi,
# which is covered by Webmin's trusted-referer check.

require './docker-lib.pl';
&ReadParse();

our (%config, %text, %in, %access);
%access = &get_module_acl();

&ui_print_header(undef, $text{'index_title'}, "", undef, 1, 1);
print &dk_style();

# First-run page: distro-specific install command, snap PATH caveat, re-check link.
if (!&has_command('docker')) {
	&ui_print_endpage(&docker_install_hint());
	}

# Feedback from act.cgi redirects.
print &ui_alert_box(&html_escape($in{'msg'}), 'success') if ($in{'msg'});
print &ui_alert_box(&html_escape($in{'err'}), 'danger') if ($in{'err'});

# ---------------------------------------------------------------------------
# Dashboard summary
# ---------------------------------------------------------------------------
my $sum = &summary_counts();
if (!$sum->{'ok'}) {
	# Raw daemon error, plus a plain-language hint when the lib recognises it.
	my $msg = &text('index_daemondown', &html_escape($sum->{'error'} || ''));
	$msg .= "<br>".$sum->{'hint'} if ($sum->{'hint'});
	print &ui_alert_box($msg, 'danger');
	}
else {
	print &dk_cards([
		{ 'label' => $text{'dash_running'}, 'value' => $sum->{'running'}, 'level' => 'ok' },
		{ 'label' => $text{'dash_paused'},  'value' => $sum->{'paused'},  'level' => ($sum->{'paused'} ? 'warn' : '') },
		{ 'label' => $text{'dash_stopped'}, 'value' => $sum->{'stopped'}, 'level' => ($sum->{'stopped'} ? 'err' : '') },
		{ 'label' => $text{'dash_images'},  'value' => $sum->{'images'},  'level' => 'info' },
		]);

	# Disk usage from "docker system df".
	my ($dffail, $df) = &system_df();
	if (!$dffail && @$df) {
		print &dk_heading($text{'maint_df'}, "&#128190;");
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
		"<tt>".&html_escape($sum->{'name'} || '?')."</tt>",
		"<tt>".&html_escape($sum->{'version'} || '?')."</tt>")."</p>";
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
push(@nav, &ui_link("proxy.cgi", $text{'nav_proxy'})) if (&has_virtualmin());
print &ui_links_row(\@nav);

# Reverse-proxy health. Regressions (a domain whose own container moved ports)
# are actionable and shown prominently with a one-click fix. Not-yet-deployed
# services are shown quietly - they are not errors.
if (&has_virtualmin()) {
	my $h = &proxy_health();
	if (@{$h->{'regressed'}}) {
		foreach my $r (@{$h->{'regressed'}}) {
			my $msg = "<b>".$text{'proxy_health_heading'}."</b><br>".
				&text('proxy_health_regressed',
					"<b>".&html_escape($r->{'domain'})."</b>",
					&dk_badge("port ".$r->{'port'}, 'err'),
					&dk_badge("port ".$r->{'suggested'}, 'ok'),
					&html_escape($r->{'container'}));
			if (&can('proxy')) {
				$msg .= "<br>".&ui_form_start("act.cgi", "post").
					&ui_hidden("c", "set_proxy").
					&ui_hidden("domain", $r->{'domain'}).
					&ui_hidden("port", $r->{'suggested'}).
					&ui_submit($text{'proxy_fix_now'}).
					&ui_form_end();
			}
			print &ui_alert_box($msg, 'danger');
		}
	}
	if (@{$h->{'undeployed'}}) {
		my @d = map { &html_escape($_->{'domain'})." (".$_->{'port'}.")" }
			@{$h->{'undeployed'}};
		print &ui_alert_box(
			"<b>".&text('proxy_health_undeployed', scalar(@d))."</b><br>".
			join(" &middot; ", @d), 'info');
	}
}
print &ui_hr();

# ---------------------------------------------------------------------------
# Container list with bulk actions
# ---------------------------------------------------------------------------
print &ui_subheading($text{'cont_heading'});

# Warn when a standalone container looks like an old copy of a Compose app
# (the "Update created a second stack" trap).
my $duphtml = &stale_duplicates_html();
print &ui_alert_box($duphtml, 'warn') if ($duphtml ne '');

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

	# Map of host port -> Virtualmin domain(s) proxying to it (empty off Virtualmin).
	my $pmap = &proxy_map();

	# Compose projects known to this host, for per-container Update links.
	my %cproj;
	my ($plf, $plist) = &compose_ls();
	if (!$plf) { $cproj{$_->{'name'}} = 1 foreach (@$plist); }

	print &ui_form_start("act.cgi", "post", undef, "id='contform'");
	print &ui_hidden("c", "container_bulk");
	print &bulk_select_links('contform', 'd')."<br>\n";

	# Client-side text filter for the table below. The input has no name so
	# it is never POSTed with the bulk form; the counter format string is
	# carried in a data attribute so the script needs no interpolation.
	print "<p>".$text{'ux_filter'}." ".
		"<input type='text' id='ux_filter' size='30' autocomplete='off'> ".
		"<span id='ux_filter_count' data-fmt='".
		&html_escape($text{'ux_filter_count'})."'></span></p>\n";
	print "<div id='dk-contlist'>\n";
	print &ui_columns_start([
		"", $text{'cont_name'}, $text{'cont_status'}, $text{'cont_image'},
		$text{'cont_ports'}, $text{'cont_proxy'},
		$text{'cont_cpu'}, $text{'cont_mem'}, $text{'cont_actions'} ], 100);
	foreach my $c (@$containers) {
		my $st = $stats->{$c->{'id'}} || $stats->{$c->{'name'}} || {};
		my @doms = &container_proxied_domains($c->{'ports'}, $pmap);
		my $domhtml = @doms ? join("<br>", map {
			&ui_link("http://".$_, &html_escape($_), undef, "target=_blank") } @doms) : "";
		my @acts = (
			&ui_link("container.cgi?tab=log&id=".&urlize($c->{'id'}), $text{'cont_logs'}),
			&ui_link("container.cgi?tab=inspect&id=".&urlize($c->{'id'}), $text{'cont_inspect'}),
			&ui_link("container.cgi?tab=exec&id=".&urlize($c->{'id'}), $text{'cont_exec'}));
		# Offer Update for compose-managed containers - the way to actually
		# apply a new version from the compose/.env files.
		my $proj = &container_project($c->{'labels'});
		if ($proj && $cproj{$proj} && &can('manage')) {
			push(@acts, "<b>".&ui_link("update.cgi?project=".&urlize($proj),
				$text{'cont_update'})."</b>");
			}
		my $links = join(" | ", @acts);
		print &ui_checked_columns_row([
			&ui_link("container.cgi?id=".&urlize($c->{'id'}), &html_escape($c->{'name'})),
			&state_label($c->{'state'}, $c->{'status'}),
			&html_escape($c->{'image'}),
			&html_escape(&format_ports($c->{'ports'})),
			$domhtml,
			&html_escape($st->{'cpu'} || ''),
			&html_escape(($st->{'memusage'} || '').($st->{'mem'} ? " (".$st->{'mem'}.")" : '')),
			$links,
			], undef, "d", $c->{'id'});
		}
	print &ui_columns_end();
	print "</div>\n";

	# Filter rows on input, remember the last filter per browser, and
	# untick containers that are filtered out so a bulk action never hits
	# a row the user cannot see. Header rows (Webmin: tr.ui_columns_heads
	# with <td><b>; Authentic: <thead><tr><th>) are skipped.
	print <<'EOJS';
<script type="text/javascript">
(function() {
  var inp = document.getElementById('ux_filter');
  var cnt = document.getElementById('ux_filter_count');
  var box = document.getElementById('dk-contlist');
  if (!inp || !box) { return; }
  var KEY = 'docker_cont_filter';
  function rows() {
    var all = box.querySelectorAll('table tr'), out = [];
    for (var i = 0; i < all.length; i++) {
      var tr = all[i];
      if (tr.querySelector('th')) { continue; }
      if (tr.parentNode && tr.parentNode.tagName === 'THEAD') { continue; }
      if (/\bui_columns_head(s|ing)\b/.test(tr.className || '')) { continue; }
      out.push(tr);
    }
    return out;
  }
  function apply() {
    var q = (inp.value || '').toLowerCase(), rs = rows(), shown = 0;
    for (var i = 0; i < rs.length; i++) {
      var txt = (rs[i].textContent || '').toLowerCase();
      var hit = (q === '' || txt.indexOf(q) !== -1);
      rs[i].style.display = hit ? '' : 'none';
      if (hit) { shown++; }
      else {
        var cb = rs[i].querySelector("input[type='checkbox']");
        if (cb) { cb.checked = false; }
      }
    }
    if (cnt) {
      var fmt = cnt.getAttribute('data-fmt') || '';
      cnt.textContent = (q === '') ? '' :
        fmt.replace('$1', shown).replace('$2', rs.length);
    }
    try { if (q === '') { localStorage.removeItem(KEY); }
          else { localStorage.setItem(KEY, inp.value); } } catch (e) { }
  }
  inp.addEventListener('input', apply);
  inp.addEventListener('keydown', function(e) {
    if (e.key === 'Enter' || e.keyCode === 13) { e.preventDefault(); }
  });
  try { var saved = localStorage.getItem(KEY);
        if (saved) { inp.value = saved; } } catch (e) { }
  apply();
})();
</script>
EOJS

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
	print &help_note($text{'cont_help'});
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
