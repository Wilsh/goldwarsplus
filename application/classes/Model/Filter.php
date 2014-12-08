<?php defined('SYSPATH') or die('No direct script access.');

//Retrieve item details from api and store tradable items in database
class Model_Filter extends Model {

	private $num_added = 0;

	//Update data in commerce_items table
	public function update_commerce_items()
	{
		$offset = 0;
		$max = 180;

		while (TRUE)
		{
			$ext = 'items?ids=';

			$query = DB::select('id')
					->from('all_items')
					->where('evaluated', '=', FALSE)
					->offset($offset)
					->limit($max);
			$result = $query->execute();
			
			if ($result->count() == 0)
				break;

			foreach ($result as $row)
			{
				$id = $row['id'];
				
				if ( ! $id)
				{
					//throw new Exception
				}
				else
				{
					$ext .= $id.',';
				}
			}

			$this->add_to_commerce($ext);
			$offset += $max;
		}
	}

	//Call GW2 API and store items that match criteria in commerce_items table
	//$ext is the URI for items to retrieve from the API
	private function add_to_commerce($ext)
	{
		$restrictions = array('AccountBound',
							  'SoulbindOnAcquire', 
							  'NoSell',
							  'MonsterOnly',
							  'Unique'
							  );

		$api = new Model_Api($ext);
		$result = $api->get_decoded_data();

		foreach ($result as $key => $item)
		{
			$added_flag = TRUE;

			$array = array_intersect($restrictions, $item['flags']);
			$array = array_values($array);

			if (array_key_exists(0, $array))
			{
				$added_flag = FALSE;
			}
			else
			{
				try
				{
					$description = $item['description'];
				}
				catch (ErrorException $e)
				{
					$description = '';
				}
				
				$salvageable = array_search('NoSalvage', $item['flags']) === FALSE;
				//Because api does not mark all consumables as NoSalvage:
				$salvageable = $salvageable && ($item['type'] != 'Consumable');

				$item_data = array('id' => $item['id'],
								   'name' => $item['name'],
								   'icon' => $item['icon'],
								   'description' => $description,
								   'type' => $item['type'],
								   'rarity' => $item['rarity'],
								   'level' => $item['level'],
								   'can_salvage' => $salvageable
								   );

				$query = DB::insert('commerce_items', array_keys($item_data))
						->values(array_values($item_data));
				$returned = $query->execute();
				//TODO: error check
				$this->num_added += $returned[1];
			}

			//Set flag in all_items that item has been evaluated for inclusion
			$updated = DB::update('all_items')
					->set(array('in_commerce' => $added_flag, 'evaluated' => TRUE))
					->where('id', '=', $item['id'])
					->execute();

			if ( ! $updated[2])
			{
				//throw new Exception
				continue;
			}
		}
	}

	public function get_num_added()
	{
		return $this->num_added;
	}
}
