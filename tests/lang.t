#!/usr/bin/perl
# tests/lang.t
# Every literal $text{'key'} / &text('key', ...) used by the module must be
# defined in docker/lang/en, otherwise the UI shows an empty string.
use strict;
use warnings;
use Test::More;
use File::Spec;
use FindBin;

my $root = File::Spec->rel2abs(File::Spec->catdir($FindBin::Bin, '..'));
my $mdir = File::Spec->catdir($root, 'docker');
my $lang = File::Spec->catfile($mdir, 'lang', 'en');

open(my $lh, '<', $lang) or BAIL_OUT("cannot read $lang: $!");
my %defined;
while (my $l = <$lh>) {
	$defined{$1} = 1 if ($l =~ /^([A-Za-z0-9_.\-]+)=/);
	}
close($lh);
ok(scalar(keys %defined) > 0, "lang/en defines some keys");

# key => { file => 1, ... }
my %used;
foreach my $f (sort(glob("$mdir/*.cgi"), glob("$mdir/*.pl"))) {
	my $rel = File::Spec->abs2rel($f, $root);
	open(my $fh, '<', $f) or BAIL_OUT("cannot read $f: $!");
	while (my $l = <$fh>) {
		while ($l =~ /\$text\{\s*['"]([A-Za-z0-9_.\-]+)['"]\s*\}/g) {
			$used{$1}{$rel} = 1;
			}
		while ($l =~ /\&?\btext\(\s*['"]([A-Za-z0-9_.\-]+)['"]/g) {
			$used{$1}{$rel} = 1;
			}
		}
	close($fh);
	}
ok(scalar(keys %used) > 0, "found text keys used by the module");

foreach my $k (sort keys %used) {
	ok($defined{$k}, "lang key '$k' is defined")
		or diag("used in: ".join(", ", sort keys %{$used{$k}}));
	}

done_testing();
