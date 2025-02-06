#!usr/bin/perl

use strict;
use warnings;
use XML::Twig;
use LWP::Simple;
use Data::Dumper;
use JSON;
use open ':encoding(utf-8)', ':std'; #this ensures output file is UTF-8

# The purpose of this app is to convert TBX-Basic, TBX-Min, and TBX-Default files into the newest standard of TBX
# using the XML parser XML Twig. 
#
# The App may be run silently with no commands or with prompts
#
# The order for command line input is perl <perlscript> <filename> <option1> <option2>
# Usable options: -s == Run silently


my $input_filehandle;
my $check = 0;
my $elt;


if (@ARGV > 1) {
	
	if ($ARGV[1] eq "-s") 
	{
		my $input_filehandle = get_filehandle($ARGV[0]);
		mode2($input_filehandle);
	}
	else 
	{
		print_instructions();
	}
}
elsif (@ARGV == 1)
{
	my $input_filehandle = get_filehandle($ARGV[0]);
	mode1($input_filehandle);	
	
	print "The conversion is complete!\n"
}
else 
{
	print_instructions();
}

sub get_schemas
{
	my ($dialect) = @_;
	
	return if !$dialect;
	
	$dialect = 'TBX-Basic' if ($dialect eq "TBX");
	
	my $url = "http://validate.tbxinfo.net/dialects/$dialect";
	my $response_str = get($url);
	my $json_obj = JSON->new;
	my $data = $json_obj->decode($response_str);
	
	my %schemas = (
		dca_rng =>	${@$data[0]}{'dca_rng'},
		dca_sch =>	${@$data[0]}{'dca_sch'},
		dct_nvdl =>	${@$data[0]}{'dct_nvdl'}
	) if @$data[0];
	
	return \%schemas;
}

sub get_filehandle
{
	my ($input) = @_;
    my $fh;
	
	open $fh, '<', $input;

    return $fh;
}

sub print_instructions
{
	print "Usage: $0 <input file name> <options> \n";
	print "\tOPTIONS:\n";
	print "\t\t-s\tRun Silently with no User Interface prompts\n\n";
	exit();
}
# Run with prompts
sub mode1 
{
	my ($fh) = @_;
	
	while(1) {

		print "Press (y) to continue.\n";
		my $Continue = <STDIN>;
		chomp($Continue); 
		$Continue=~tr/A-Z/a-z/;

		unless($Continue eq 'y') {next}

		last
	}
	
	
	program_bulk($fh);
}

# Run Silently
sub mode2  
{
	my ($fh) = @_;
	program_bulk($fh);
}

# Function for the rest of the program
sub program_bulk
{
	
# Initialize Variables	
	
my $name = "tbx";
my $basicFlag = 0;
my $minFlag = 0;
my $findType;
my $tbxMinFlag;
my $printfile;

my $twig_instance = XML::Twig->new(
comments => 'drop',
pretty_print => 'indented',
twig_handlers => {
	
	# Changes for older TBX-Min files
	
	entry => sub { $_->set_tag( 'conceptEntry' ) },
	
	langGroup => sub { $_->set_tag( 'langSec' ) },
	
	termGroup => sub { $_->set_tag( 'termSec' ) },
	
	# Replace tags with updated names
	TBX => sub {	my ($twig,$elt) = @_;
					$tbxMinFlag = $elt->att("dialect");
					$minFlag++;
					
					$_->set_tag( 'tbx' );
					$_->set_att( style => "dct" ); 
					$_->change_att_name( 'dialect', 'type' );
				},
				
	tbxMin => sub {		my ($twig,$elt) = @_;
						$tbxMinFlag = $elt->att("dialect");
				},
				
	martif => sub {	my ($twig,$elt) = @_;
					$findType = $elt->att("type");
					
					$_->set_tag( 'tbx' );
					
					$_->set_att( type => 'TBX-Basic' ) if $findType eq "TBX";  #Enforce TBX-Basic on all "TBX" dialects. They will mostly be invalid.
					$_->set_att( style => "dca" );
				},
	
	martifHeader => sub { $_->set_tag( 'tbxHeader' ) },
	
	bpt => sub { $_->set_tag( 'sc' ) },
	
	ept => sub { $_->set_tag( 'ec' ) },
	
	termEntry => sub { $_->set_tag( 'conceptEntry' ) },
	
	langSet => sub { $_->set_tag( 'langSec' ) },
	
	tig => sub { $_->set_tag( 'termSec' );
				$basicFlag++;
 		   	},
	
	termCompList => sub { $_->set_tag( 'termCompSec' ) },
	
	refObjectList => sub { $_->set_tag( 'refObjectSec' ) },
	
	termComptListSpec => sub { $_->set_tag( 'termCompSecSpec' ) },
	
	# Remove old tags that are no longer used
	
	term => sub {
		    my ($twig, $elt) = @_;
	            my $parent = $elt->parent('ntig');
				
				if(defined($parent))
				{
	           		$elt->cut();
	           	 	$elt->paste($parent);  
				}
			},
				
	ntig => sub { $_->set_tag( 'termSec' );
	 		},			
				
	termGrp => sub { $_->delete() },				
	
},

);

# Parse the instance that was created

$twig_instance->parsefile($ARGV[0]);
$twig_instance->set_doctype(0, 0);
$twig_instance->root->set_att( xmlns => "urn:iso:std:iso:30042:ed-2" );


my $schemas_ref = get_schemas($twig_instance->root->att('type'));
my %schemas = %$schemas_ref if $schemas_ref;

if (%schemas)
{
	my $e = XML::Twig::Elt->new( 'k' => 'v');
	$e->set_pi( 'xml-model', "href=\"$schemas{'dca_rng'}\" type=\"application/xml\" schematypens=\"http://relaxng.org/ns/structure/1.0\"");
	$e->move( before => $twig_instance->root);
	$e = XML::Twig::Elt->new( 'k' => 'v');
	$e->set_pi( 'xml-model', "href=\"$schemas{'dca_sch'}\" type=\"application/xml\" schematypens=\"http://purl.oclc.org/dsdl/schematron\"");
	$e->move( before => $twig_instance->root);
}

##All files are turned into DCT when updated
# elsif (%schemas)
# {
	# my $e = XML::Twig::Elt->new( 'k' => 'v');
	# $e->set_pi( 'xml-model', "href=\"$schemas{'dct_nvdl'}\" type=\"application/xml\" schematypens=\"http://purl.oclc.org/dsdl/nvdl/ns/structure/1.0\"");
	# $e->move( before => $twig_instance->root);
# }


# This section is for command prompt use only and give the user the option to save the console output to a file
# my %schemas = get_schemas($twig_instance->tbx->att('type'));

if (@ARGV == 1)
{
	print "Would you like to save the output to a file? Press (y/n) to continue.\n";
	my $Continue = <STDIN>;
	chomp($Continue); 
	$Continue=~tr/A-Z/a-z/;	
	print "Starting file analysis:\n";
	if($Continue eq 'y')
	{
	
		$printfile = "converted_file.tbx";

		unless(open FILE, '>', $printfile)
		{
			die "\nUnable to create $printfile\n";
		}
		
		$twig_instance->print( \*FILE); 
	}
}
$twig_instance->flush;  

}
