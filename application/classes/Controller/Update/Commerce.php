<?php defined('SYSPATH') or die('No direct script access.');

class Controller_Update_Commerce extends Controller {

	public function action_index()
	{
		$call = new Model_Filter();
		$call->update_commerce_items();
		$view = new View('basic');
		$view->param = $call->get_num_added();
		$this->response->body($view);
	}
}
