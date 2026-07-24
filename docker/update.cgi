#!/usr/bin/perl
# update.cgi - explains and performs a Compose project update (pull the image
# versions set in the compose/.env files, then recreate the containers).
# This page IS the confirmation: its button posts confirmed=1 to act.cgi.

require './docker-lib.pl';
&ReadParse();

our (%config, %text, %in, %access);
%access = &get_module_acl();

my $project = $in{'project'};
&is_valid_name($project) || &error($text{'update_err_noproject'});
my ($pf, $p) = &find_compose_project($project);
$pf && &error(&html_escape($p));

&ui_print_header(undef, &text('update_title2', &html_escape($project)), "");
print &dk_style();

# What will happen, in plain words.
print &ui_subheading($text{'update_what'});
print "<ul>";
print "<li>".$text{'update_point1'}."</li>";
print "<li>".$text{'update_point2'}."</li>";
print "<li><b>".$text{'update_point3'}."</b></li>";
print "<li>".&ui_text_color($text{'update_point4'}, 'warn')."</li>";
print "<li>".&text('update_pinned', "<tt>".&html_escape($project)."</tt>")."</li>";
print "</ul>";
print &help_note($text{'update_note_restart'});

# The compose files that define the project.
print &ui_table_start($text{'update_files'}, undef, 2);
foreach my $cf (split(/\s*,\s*/, $p->{'configfiles'} || '')) {
	print &ui_table_row(undef, "<tt>".&html_escape($cf)."</tt>", 2);
	}
my $dmap = &compose_domain_map();
if ($dmap->{$project}) {
	print &ui_table_row($text{'compose_domain'},
		&html_escape($dmap->{$project}));
	}
print &ui_table_end();

# The containers that will be recreated.
my ($cf2, $containers) = &list_containers();
if (!$cf2) {
	my @mine = grep { (&container_project($_->{'labels'}) || '') eq $project }
			@$containers;
	if (@mine) {
		print &ui_subheading($text{'update_containers'});
		print &ui_columns_start([ $text{'cont_name'}, $text{'cont_image'},
			$text{'cont_status'} ], 100);
		foreach my $c (@mine) {
			print &ui_columns_row([
				&html_escape($c->{'name'}),
				&html_escape($c->{'image'}),
				&state_label($c->{'state'}, $c->{'status'}),
				]);
			}
		print &ui_columns_end();
		}
	}

# Red flag if an old standalone copy of this application is running - updating
# the project will NOT touch it, and it may still own the domain and the data.
my $duphtml = &stale_duplicates_html($project);
print &ui_alert_box($duphtml, 'danger') if ($duphtml ne '');

if (&can('manage')) {
	print &ui_form_start("act.cgi", "post");
	print &ui_hidden("c", "compose_project");
	print &ui_hidden("project", $project);
	print &ui_hidden("paction", "update");
	print &ui_hidden("confirmed", 1);
	print &ui_form_end([ [ undef, $text{'update_button'} ] ]);
	}
else {
	print &ui_alert_box($text{'err_noperm'}, 'warn');
	}

&ui_print_footer("index.cgi", $text{'index_return'});
