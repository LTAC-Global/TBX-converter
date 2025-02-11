use strict;
use warnings;

use XML::Twig;

sub main
{
    my ($file, $ext) = @_;
	
	$ext = $ext || '';
	#THIS LINE DOES NOT WORK ON THE SERVER    
    #exit "File does not have a '.tbx' extension.\n" if $_[0] !~ /\.tbx$/;
    
    ## ordered by severity
    my %messages = (
		not_xml => "This file does not appear to be an XML or TBX file.",
		bad_ext => "This file does not appear to have the correct file extension.",
        malformed_xml => "File does not appear to be well-formed XML.",
        malformed_tbx => "File appears to be well-formed XML, but does not appear to be TBX.",
        invalid_tbx => "File claims to be TBX, but does not appear valid.",
        v2 => "File appears to be a 2008 TBX (v2) file.",
        bad_v3 => "File appears to be a 2019 TBX (v3) file, but has no valid dialect.",
        v3 => "File appears to be a 2019 TBX (v3) file with dialect:",
    );
    
    
    my $twig = XML::Twig->new(
        twig_handlers =>
        {
            ## TBX-Min originally had a mandatory upper-case <TBX> root element, but this is not legal in any other case
            TBX => sub {
                if ($_->att('dialect') eq "TBX-Min") { print $messages{'v2'}."\n" }
                else { print $messages{'invalid_tbx'}."\n" }
            },
            ## 2008 TBX has <martif> lower-case.
            martif => sub {
                print $messages{'v2'}."\n";
            },
            ## 2018 TBX files have a mandator lower-case <tbx> root element
            tbx => sub {
                if ($_->att('type') =~ /^TBX-.+?/)
                {
                    printf $messages{'v3'}." '%s'\n", $_->att('type');    
                }
                else {
                    print $messages{'bad_v3'}."\n";
                }
            },
            'MARTIF' => sub {
                print $messages{'invalid_tbx'}."\n";
            }
        }
    );
    
	exit $messages{'bad_ext'}."\n" unless $file =~ /\.(xml|tbxm?)$/i || $ext =~ /(xml|tbxm?)$/i;
    
	open(my $fh, '<', $file);
	my $firstline;
	
	while (<$fh>)
	{
		if ($_ =~ /\w/g)
		{
			die $messages{'not_xml'}."\n" unless $_ =~ /<\?xml/i;
			last;
		}
	}
	
	exit $messages{'malformed_xml'}."\n" unless $twig->safe_parsefile($file);
}

exit "Missing target file.\n" if (@ARGV < 1);

#if on the server, extension will be fed to $ARGV[1]
main(@ARGV);