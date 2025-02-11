<?php

    // check the TBX-ness of a file

    $temp_file_name = $_FILES['upload']['tmp_name'];
    if ($_FILES["upload"]["error"] > 0)
    {
        echo "<p>Error: " . $_FILES["file"]["error"] . "</p>\n";
    }
    $file_ext = end((explode('.', $_FILES['upload']['name'])));
	
    $out_file_name = $temp_file_name . '.log';

    // Define which version of Perl we will use

    //$perl = "~/.plenv/versions/5.18.0/bin/perl";
    $perl = "perl";  //Use this on production if you get an error
    $lib = "~/perl5/lib/perl5";
    $script = "./main.pl";

    $reroute_stderr = "2>$out_file_name";

    $command = "$perl ". "-I $lib " .
        escapeshellarg($script). ' ' .
        escapeshellarg($temp_file_name) . ' ' .
        escapeshellarg($file_ext) .
        ' -s ' .
        $reroute_stderr;

    $ret_val = 0;

    // Execute the command, store terminal output in the $printed_output variable
    exec($command, $printed_output, $ret_val);
    
    $error = 0;
    $image = "x_red.png";
	$linkToUpdate = 0;
	
    //if $ret_val is not 0 or if the log file wasn't created, there was a problem
    if(($ret_val != 0) || (!file_exists($out_file_name)) ){
        #print problems
        header('HTTP/1.1 400 Bad Request');
        if (ob_get_contents()) ob_end_clean();
        flush();
        $error = 1;
    }

    // If it did work, download a text file using the output stored in the $printed_output variable
    else{
        if (preg_match("/v3/", $printed_output[0]))
        {
            $image = "check_green.png";
        }
        else if (preg_match("/v2/", $printed_output[0]))
        {
            $image = "check_yellow.png";
            $linkToUpdate = 1;
        }
    }
?>

<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<meta http-equiv="X-UA-Compatible" content="ie=edge">
	<title>TBX Spyglass Results</title>
    
    <link rel="stylesheet" href="./TBXSpyglassWebBridge.css">
</head>

<body>
    <div class="header">
        <span><a href="/tbx-spyglass">Return to Spyglass</a></span>
    </div>
    <h1 class="title">TBX Spyglass Results</h1>
    <p class="validation_notice">This app does *not* validate TBX files.</p>
    <div class="container">
        <img class="results_image" src="<? echo $image ?>"/>
        <p><? 
            if ($error)
            {
                readfile($out_file_name);
            }
            else
            {
                print ($linkToUpdate) ? $printed_output[0] . ' <a href="/tbx-updater">Update this file to TBX v3</a>' : $printed_output[0];   
            }
            ?></p>
    </div>
</body>
</html>
