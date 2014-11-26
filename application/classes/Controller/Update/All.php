<?php defined('SYSPATH') or die('No direct script access.');

class Controller_Update_All extends Controller {

	public function action_index()
	{
		$call = new Model_Allitems();
		$view = new View('basic');
		$view->param = $call->get_response();
		$this->response->body($view);
	}

	public function action_items()
	{

		$this->response->body('Update items is working');
	}

	public function action_commerce()
	{
		$this->response->body('Update commerce is working');
	}

} // End Welcome
