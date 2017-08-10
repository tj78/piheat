<!DOCTYPE html>
<html>
    <head>
        <link rel="stylesheet" type="text/css" href="mystyle.css">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
    </head>
    <body>
        <?php
            // Does initial connection to the database, & keeps it open!
            function db_connect() {
                // Define connection as a static variable, to avoid connecting more than once
                static $connection;
                // Try and connect to the database, if a connection has not been established yet
                if(!isset($connection)) {
                    // Load configuration as an array. Use the actual location of your configuration file
                    $config = parse_ini_file('../config.ini');
                    // Try and connect to the database
                    $connection = mysqli_connect($config['host'], $config['username'], $config['password'], $config['dbname']);
                }
                // If connection was not successful, handle the error
                if($connection === false) {
                    // Handle error - notify administrator, log to a file, show an error screen, etc.
                    print("ERROR ---   Could not connect!<br />");
                }
                return $connection;
            }



            // Used to display MySQL error messages
            function db_error() {
                $connection = db_connect();
                return mysqli_error($connection);
            }


            // Queries a MySQL database with command provided
            function db_query($query) {
                // Connect to the database
                $connection = db_connect();
                // Query the database
                $result = mysqli_query($connection,$query);
                return $result;
            }


            // Performs the provided 'SELECT' command & returns the data in a displayable form
            function db_select($query, $field) {
                $rows = array();
                $result = db_query($query);
                // If query failed, return `false`
                if($result === false) {
                    $error = db_error();
                    // Handle error - inform administrator, log to file, show error page, etc.
                    print("ERROR --- when performing 'SELECT' command!<br />");
                    print("$error<br />");
                    return false;
                }
                // If query was successful, retrieve all the rows into an array
                while ($row = mysqli_fetch_assoc($result)) {
                    $rows[] = $row;
                }
                if($rows === false) {
                    $error = db_error();
                    // Handle error - inform administrator, log to file, show error page, etc.
                    print("ERROR --- when performing 'SELECT' command!<br />");
                    print("$error<br />");
                } else {
                    foreach($rows as $record) {
                        $data = $record[$field];
                    }
                }
                return $data;
            }
        ?>
	<?php
        $st699 = db_select("SELECT piheat_control FROM piheat WHERE piheat_function='st699'", piheat_control);
        if($st699 === 'on') {
            echo("<div class='st699on'><h3>PROGRAMMER IS ON</h3></div>");
        }
        else {
            echo("<div class='st699off'><h3>PROGRAMMER IS OFF</h3></div>");
        }
        
		$hw = db_select("SELECT piheat_control FROM piheat WHERE piheat_function='HW'", piheat_control);
		if($hw === 'on') {
            echo("<div class='controllerOn'><h1>HOT WATER</h1></div>");
        }
        else {
            echo("<div class='controllerOff'><h1>HOT WATER</h1></div>");
		}
        $ch = db_select("SELECT piheat_control FROM piheat WHERE piheat_function='CH'", piheat_control);
        
        if($ch === 'on') {
            echo("<div class='controllerOn'><h1>CENTRAL HEATING</h1>");
        }
        else {
            echo("<div class='controllerOff'><h1>CENTRAL HEATING</h1>");
        }
        $livtemp = db_select("SELECT livtemp FROM temp_log", livtemp);
        $target_temp = db_select("SELECT temp FROM target_temp", temp);
        if($target_temp > $livtemp) {
            echo("<div class='statusLow'><h3>ACTUAL:   " . $livtemp . "&degC</h3></div>");
            echo("<div class='status'></div>");
            echo("<div class='statusHigh'><h3>TARGET:   " . $target_temp . "&degC</h3></div>");
        }
        else {
            echo("<div class='statusHigh'><h3>ACTUAL:   " . $livtemp . "&degC</h3></div>");
            echo("<div class='status'></div>");
            echo("<div class='statusLow'><h3>TARGET:   " . $target_temp . "&degC</h3></div>");
        }
	?>
    </body>
</html>
