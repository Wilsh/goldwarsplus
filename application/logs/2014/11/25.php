<?php defined('SYSPATH') OR die('No direct script access.'); ?>

2014-11-25 23:34:10 --- EMERGENCY: Kohana_Exception [ 0 ]: A valid cookie salt is required. Please set Cookie::$salt in your bootstrap.php. For more information check the documentation ~ SYSPATH/classes/Kohana/Cookie.php [ 151 ] in /home/wil/Dropbox/Git stuff/goldwars/system/classes/Kohana/Cookie.php:67
2014-11-25 23:34:10 --- DEBUG: #0 /home/wil/Dropbox/Git stuff/goldwars/system/classes/Kohana/Cookie.php(67): Kohana_Cookie::salt('PHPSESSID', NULL)
#1 /home/wil/Dropbox/Git stuff/goldwars/system/classes/Kohana/Request.php(151): Kohana_Cookie::get('PHPSESSID')
#2 /home/wil/Dropbox/Git stuff/goldwars/index.php(117): Kohana_Request::factory(true, Array, false)
#3 {main} in /home/wil/Dropbox/Git stuff/goldwars/system/classes/Kohana/Cookie.php:67