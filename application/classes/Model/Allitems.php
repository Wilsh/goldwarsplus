<?php defined('SYSPATH') or die('No direct script access.');

class Model_Allitems extends Model {

	private $result = NULL;
	private $num_added = 0;

	function __construct() {
		$api = new Model_Api('items');
		$this->result = $api->get_api_call();

		if ($this->result)
		{
			$date = date("Y-m-d");

			foreach ($this->result as $key => $item)
			{
				//check if item already exists in database
				$query = DB::select()->from('all_items')->where('id', '=', $item);
				$exists = $query->execute()->count();

				if ( ! $exists)
				{
					$query = DB::insert('all_items', array('id', 'date'))
							->values(array($item, $date));
					$list = $query->execute();
					//TODO: error check
					$this->num_added += $list[1];
				}
			}
		}
		else
		{
			//throw new Exception
		}
   }

   function get_response() {
		return $this->num_added;
   }
}