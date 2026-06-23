# acl_security.pl
# Per-user access control for the Docker module. Admins can grant or deny each
# capability independently via Webmin Users -> (user) -> Docker.

do './docker-lib.pl';

my @acl_keys = qw(view manage create delete exec prune registry context);

# acl_security_form(&access) - render the ACL editing form.
sub acl_security_form
{
my ($access) = @_;
foreach my $k (@acl_keys) {
	my $def = ($k eq 'view' || $k eq 'manage') ? 1 : 0;
	my $val = defined($access->{$k}) ? $access->{$k} : $def;
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
