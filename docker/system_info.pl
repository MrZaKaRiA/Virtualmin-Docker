# system_info.pl
# Contributes a panel to the Webmin home-page System Information dashboard
# (the same area that renders the "Servers Status" panel). The core function
# list_combined_system_info() discovers this file in every module and calls
# list_system_info(). Requires the "System and Server Status" (system-status)
# module to be installed and enabled in the user's dashboard settings.

do './docker-lib.pl';

# list_system_info(&data, &in, &modskip) -> list of panel hashrefs.
sub list_system_info
{
my ($data, $in, $modskip) = @_;
return () if (!&foreign_available($module_name));
return () if (defined($config{'widget_enabled'}) && !$config{'widget_enabled'});
return () if (!&has_command('docker'));

my $sum = &summary_counts();

# Daemon unreachable -> a single red warning panel.
if (!$sum->{'ok'}) {
	return ( {
		'type'    => 'warning',
		'level'   => 'danger',
		'id'      => $module_name.'_down',
		'desc'    => $text{'widget_title'},
		'warning' => &text('widget_down',
			"<a href='".&get_webprefix()."/$module_name/'>".
			&html_escape($text{'widget_open'})."</a>"),
		} );
	}

# Link the panel straight into the module.
my $url = &get_webprefix()."/$module_name/";
my $link = sub { my ($v) = @_; return "<a href='$url'>$v</a>"; };

my @table;
push(@table, { 'desc'  => $text{'dash_running'},
	       'value' => &$link(&ui_text_color($sum->{'running'} || 0, 'success')),
	       'chart' => [ $sum->{'containers'} || 0, $sum->{'running'} || 0 ] });
push(@table, { 'desc'  => $text{'dash_paused'},
	       'value' => &$link(&ui_text_color($sum->{'paused'} || 0, $sum->{'paused'} ? 'warn' : 'success')) });
push(@table, { 'desc'  => $text{'dash_stopped'},
	       'value' => &$link(&ui_text_color($sum->{'stopped'} || 0, $sum->{'stopped'} ? 'danger' : 'success')) });
push(@table, { 'desc'  => $text{'dash_images'},
	       'value' => &$link($sum->{'images'} || 0) });
push(@table, { 'desc'  => $text{'widget_version'},
	       'value' => &html_escape($sum->{'version'} || '?') });
push(@table, { 'desc'  => '',
	       'value' => "<a href='$url'>".&html_escape($text{'widget_open'})." &raquo;</a>",
	       'wide'  => 1 });

return ( {
	'type'     => 'table',
	'id'       => $module_name.'_summary',
	'desc'     => "<a href='$url'>".&html_escape($text{'widget_title'})."</a>",
	'open'     => 1,
	'priority' => 6,
	'table'    => \@table,
	} );
}

1;
