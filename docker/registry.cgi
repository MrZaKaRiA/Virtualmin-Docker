#!/usr/bin/perl
# registry.cgi - log in to a registry for private pulls/pushes.
# The password is fed to "docker login --password-stdin" via STDIN and is never
# stored in the module config (Docker persists its own credential reference).

require './docker-lib.pl';
&ReadParse();

our (%config, %text, %in, %access);
%access = &get_module_acl();

&ui_print_header(undef, $text{'reg_title'}, "");

print &ui_alert_box(&html_escape($in{'msg'}), 'success') if ($in{'msg'});
print &ui_alert_box(&html_escape($in{'err'}), 'danger') if ($in{'err'});

if (&can('registry')) {
	print &ui_alert_box($text{'reg_note'}, 'info');
	print &ui_form_start("act.cgi", "post");
	print &ui_hidden("c", "registry_login");
	print &ui_table_start($text{'reg_heading'}, undef, 2);
	print &ui_table_row($text{'reg_server'},
		&ui_textbox("server", "", 40)." ".$text{'reg_server_hint'});
	print &ui_table_row($text{'reg_user'}, &ui_textbox("username", "", 30));
	print &ui_table_row($text{'reg_pass'}, &ui_password("password", "", 30));
	print &ui_table_end();
	print &ui_form_end([ [ undef, $text{'reg_login_button'} ] ]);
	}
else {
	print &ui_alert_box($text{'err_noperm'}, 'warn');
	}

&ui_print_footer("index.cgi", $text{'index_return'});
