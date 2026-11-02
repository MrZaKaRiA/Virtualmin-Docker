#!/usr/bin/perl
# tests/syntax.t
# `perl -c` every CGI and library file with the WebminCore stub on @INC.
use strict;
use warnings;
use Test::More;
use File::Spec;
use FindBin;

my $root = File::Spec->rel2abs(File::Spec->catdir($FindBin::Bin, '..'));
my $mdir = File::Spec->catdir($root, 'docker');
my $stub = File::Spec->catdir($FindBin::Bin, 'stub');

my @files = sort(glob("$mdir/*.cgi"), glob("$mdir/*.pl"));
ok(scalar(@files) > 0, "found module files to check") or done_testing(), exit;

foreach my $f (@files) {
	my $rel = File::Spec->abs2rel($f, $root);
	my $out = qx{"$^X" -I"$mdir" -I"$stub" -c "$f" 2>&1};
	my $rc = $? >> 8;
	ok($rc == 0 && $out =~ /syntax OK/, "perl -c $rel")
		or diag($out);
	}

done_testing();
