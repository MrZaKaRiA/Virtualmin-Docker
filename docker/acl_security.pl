# acl_security.pl
# Per-user access control for the Docker module. Admins can grant or deny each
# capability independently via Webmin Users -> (user) -> Docker.

# Loaded by Webmin's foreign_require() from OTHER modules' directories, so
# the lib must be found via @INC (which foreign_require primes with this
# module's directory). Never use a './' relative path here - see issues #1, #2.
require 'docker-lib.pl';

my @acl_keys = qw(view manage create delete exec prune backup proxy registry context);

# acl_security_form(&access) - render the ACL editing form.
sub acl_security_form
{
my ($access) = @_;
foreach my $k (@acl_keys) {
	my $val = defined($access->{$k}) ? $access->{$k} : 1;
	print &ui_table_row($text{'acl_'.$k},
		&ui_yesno_radio($k, $val));
	}
}

# acl_security_save(&access, &in) - persist the submitted ACL values.
sub acl_security_save
{
my ($access, $in) = @_;
foreach my $k (@acl_keys) {
	$access->{$k} = $in->{$k};
	}
}

1;
