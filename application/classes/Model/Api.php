<?php defined('SYSPATH') or die('No direct script access.');

class Model_Api extends Model {

	const API_BASE = 'https://api.guildwars2.com/v2/';
	private $response = '';

	function __construct($ext)
	{
		$request = Request::factory(self::API_BASE.$ext);
		$json = $request->execute();
		$this->response = json_decode($json, TRUE);
   }

   function get_api_call()
   {
   		return $this->response;
   }
}