#!/usr/bin/perl
# env.cgi - view and edit a Compose project's .env file (e.g. to change an image
# version), then run Update to apply it.

require './docker-lib.pl';
&ReadParse();

our (%config, %text, %in, %access);
%access = &get_module_acl();

my $project = $in{'project'};
&is_valid_name($project) || &error($text{'update_err_noproject'});

&ui_print_header(undef, &text('env_title', &html_escape($project)), "");
print &dk_style();

print &ui_alert_box(&html_escape($in{'msg'}), 'success') if ($in{'msg'});
print &ui_alert_box(&html_escape($in{'err'}), 'danger') if ($in{'err'});

my ($rf, $content, $path) = &read_project_env($project);
if ($rf) {
	print &ui_alert_box(&html_escape($content), 'danger');
	&ui_print_footer("compose.cgi", $text{'compose_title'});
	exit;
	}

print &help_note(&text('env_intro', "<tt>".&html_escape($path)."</tt>"));

if (&can('manage')) {
	print &ui_form_start("act.cgi", "post");
	print &ui_hidden("c", "env_save");
	print &ui_hidden("project", $project);
	print &ui_textarea("content", $content, 20, 90);
	print "<br>";
	print &ui_form_end([ [ undef, $text{'env_save_button'} ] ]);
	print &help_note($text{'env_after_note'});
	print "<p>".&ui_link("update.cgi?project=".&urlize($project),
		"<b>".$text{'env_goto_update'}."</b>")."</p>";
	}
else {
	print "<pre class='comment'>".&html_escape($content)."</pre>";
	print &ui_alert_box($text{'err_noperm'}, 'warn');
	}

&ui_print_footer("compose.cgi", $text{'compose_title'}, "index.cgi", $text{'index_return'});
