<?php defined('SYSPATH') or die('No direct script access.');

class Controller_Browse extends Controller {

	public function action_index()
	{
		$this->response->body('hello, world!2');
	}

} // End Welcome
 