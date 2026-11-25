# Makefile for the Docker Webmin/Virtualmin module.
#
#   make test      run the whole test-suite (tests/*.t) with prove
#   make syntax    perl -c every docker/*.cgi and docker/*.pl
#   make package   build docker.wbm.gz (same command as the release workflow)
#   make clean     remove build artifacts
#
# Kept POSIX-make friendly: no GNU-only functions or pattern rules.

PERL    = perl
PROVE   = prove
MODULE  = docker
PACKAGE = $(MODULE).wbm.gz

all: test

test:
	$(PROVE) -v tests/

syntax:
	$(PROVE) -v tests/syntax.t

# The package's top-level directory must equal the module name.
package:
	tar --exclude='.DS_Store' --exclude='*.swp' -czf $(PACKAGE) $(MODULE)
	ls -l $(PACKAGE)

clean:
	rm -f $(PACKAGE)

.PHONY: all test syntax package clean
