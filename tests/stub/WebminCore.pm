# tests/stub/WebminCore.pm
# Minimal stand-in for Webmin's WebminCore, used only by the test-suite.
#
# Like the real one, `use WebminCore` injects the core API into the CALLER's
# package (docker-lib.pl does `use WebminCore` under whatever package it is
# compiled in: `main` for the CGIs, `docker` when a hook is pulled in through
# foreign_require()). Every function here is a benign no-op that returns
# something of the right shape so the module files can compile and the hook
# entry points can run without a real Webmin or Docker on the box.
#
# Keep it small: only add a function when a test actually needs it.
package WebminCore;

use strict;
use warnings;

sub import
{
my $pkg = caller;
no strict 'refs';

my %stub = (
	# init_config(): set up $module_name and make %config/%text exist.
	'init_config' => sub {
		${"${pkg}::module_name"} = 'docker';
		${"${pkg}::module_root_directory"} = '.';
		%{"${pkg}::config"}  = () if (!%{"${pkg}::config"});
		%{"${pkg}::text"}    = () if (!%{"${pkg}::text"});
		%{"${pkg}::gconfig"} = () if (!%{"${pkg}::gconfig"});
		return 1;
		},

	# No commands exist, nothing can be executed.
	'has_command'        => sub { 0 },
	'foreign_available'  => sub { 1 },
	'load_theme_library' => sub { 1 },
	'error_stderr'       => sub { },
	'error'              => sub { die(join("", @_)."\n") },
	'get_webprefix'      => sub { '' },

	# execute_command(cmd, stdin, \$out, \$err, ...): "fail", empty output.
	'execute_command' => sub {
		my ($cmd, $stdin, $out, $err) = @_;
		$$out = '' if (ref($out));
		$$err = '' if (ref($err));
		return 1;
		},

	# text(key, args...): the lang string (or the key) with $1.. substituted.
	'text' => sub {
		my ($k, @a) = @_;
		my $s = ${"${pkg}::text"}{$k};
		$s = $k if (!defined($s));
		$s =~ s/\$(\d+)/defined($a[$1-1]) ? $a[$1-1] : ''/ge;
		return $s;
		},

	'html_escape' => sub {
		my ($s) = @_;
		$s = '' if (!defined($s));
		$s =~ s/&/&amp;/g; $s =~ s/</&lt;/g; $s =~ s/>/&gt;/g; $s =~ s/"/&quot;/g;
		return $s;
		},

	# UI helpers: return plain strings, no markup needed.
	'ui_table_row'  => sub { join(" ", map { defined($_) ? $_ : '' } @_)."\n" },
	'ui_yesno_radio'=> sub { "yesno:".(defined($_[0]) ? $_[0] : '') },
	'ui_textbox'    => sub { "textbox:".(defined($_[0]) ? $_[0] : '') },
	'ui_text_color' => sub { defined($_[0]) ? $_[0] : '' },
	);

foreach my $name (keys %stub) {
	# Idempotent: a second `use WebminCore` in the same package (e.g. two
	# hooks loaded in one process) must not emit "Subroutine redefined".
	next if (defined(&{"${pkg}::${name}"}));
	*{"${pkg}::${name}"} = $stub{$name};
	}
}

1;
