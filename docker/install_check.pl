# install_check.pl
# Lets Webmin auto-detect whether this module is usable on the host.

# Loaded by Webmin's foreign_require() from OTHER modules' directories, so
# the lib must be found via @INC (which foreign_require primes with this
# module's directory). Never use a './' relative path here - see issues #1, #2.
require 'docker-lib.pl';

# is_installed(mode) - return 2 if Docker is present (installed & ready),
# 0 otherwise. Webmin uses this when refreshing/auto-adding modules.
sub is_installed
{
my ($mode) = @_;
return &has_command("docker") ? 2 : 0;
}

1;
