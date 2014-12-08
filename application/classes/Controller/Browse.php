<?php defined('SYSPATH') or die('No direct script access.');

class Controller_Browse extends Controller {

	public function action_index()
	{
		$twig = Twig::factory('template');
		$twig->text = 'hello, world!';
		$this->response->body($twig); 
	}

} // End Welcome
 