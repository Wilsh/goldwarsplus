#!/usr/bin/python3.5
#run in command prompt first:
#export DJANGO_SETTINGS_MODULE=website.settings

#this script checks the gw2 api for previously unseen items and recipes 
#and adds any new items or recipes to the database

import sys
from django.conf import settings
sys.path.append(settings.BASE_DIR)
import django
django.setup()

from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError
import json
from django.utils import timezone

from commerce.models import Item, ItemFlag, Icon, Recipe, EconomicsForRecipe, RecipeDiscipline, RecipeIngredient

def get_api_data(url_postfix, context):
    '''Return decoded json object from GW2 API'''
    req = Request('https://api.guildwars2.com/v2/' + url_postfix)
    try:
        response = urlopen(req)
    except HTTPError as e:
        context['api_error'] = e
    except URLError as e:
        context['api_error'] = e.reason
    else:
        return json.loads(response.read().decode('utf-8'))
    return None
    
def get_api_objects(api_endpoint, context):
    '''Retrieve a list of ids from the specified API endpoint then 
    add any missing objects to their corresponding table'''
    if api_endpoint != 'items' and api_endpoint != 'recipes':
        context['api_error'] = 'Invalid api_endpoint value'
        return
    object_id_list = get_api_data(api_endpoint, context)
    if not object_id_list:
        return
    total_added = 0
    start = 0
    end = 200
    processing = True
    while processing:
        #API endpoint allows 200 id requests max
        part_object_id_list = object_id_list[start:end]
        if len(part_object_id_list) == 0:
            processing = False
        else:
            #construct URL for object details
            end_url = api_endpoint + '?ids='
            no_new_object = True
            for id in part_object_id_list:
                try:
                    #ensure object does not already exist
                    if api_endpoint == 'items':
                        Item.objects.get(pk=id)
                    if api_endpoint == 'recipes':
                        Recipe.objects.get(pk=id)
                except (Item.DoesNotExist, Recipe.DoesNotExist):
                    no_new_object = False
                    end_url += str(id) + ','
            if no_new_object:
                start += 200
                end += 200
                continue
            end_url = end_url[:len(end_url)-1] #remove trailing comma or API will return error
            #pull data from API
            object_details = get_api_data(end_url, context)
            if not object_details:
                return
            for object in object_details:
                if api_endpoint == 'items':
                    #create Icon if necessary
                    try:
                        item_icon = Icon.objects.get(url=object['icon'])
                    except Icon.DoesNotExist:
                        item_icon = Icon(pk=object['icon'])
                        item_icon.add_details()
                        item_icon.save()
                    #create Item entry
                    new_item = Item(icon=item_icon)
                    new_item.add_details(object)
                    new_item.save()
                    #create ItemFlag entry
                    new_itemflag = ItemFlag(for_item=new_item)
                    new_itemflag.add_details(object['flags'])
                    new_itemflag.save()
                elif api_endpoint == 'recipes':
                    try:
                        for_Item = Item.objects.get(pk=object['output_item_id'])
                    except Item.DoesNotExist:
                        known_bad = ['82171', '82435', '82438', '82765', '82830', '83193', '83271', 
                            '83326', '83354', '83459', '83672', '83935', '84002', '84004', '84085', 
                            '84158', '84220', '84325', '84363', '84413', '84632', '84718']
                        if str(object['output_item_id']) in known_bad:
                            #ignore known error in api
                            continue
                        context['api error using recipe ' + str(object['id'])] = 'Create Recipe ' + str(object['id']) + ' failed: related Item ' + str(object['output_item_id']) + ' does not exist'
                        continue
                    #update can_be_crafted flag for Item
                    for_Item.can_be_crafted = True
                    for_Item.save()
                    #create Recipe entry
                    new_recipe = Recipe(output_item_id=for_Item)
                    new_recipe.add_details(object)
                    new_recipe.save()
                    #create RecipeDiscipline entry
                    new_recipeflag = RecipeDiscipline(for_recipe=new_recipe)
                    new_recipeflag.add_details(object['disciplines'])
                    new_recipeflag.save()
                    #create RecipeIngredient entries
                    for ingredient in object['ingredients']:
                        try:
                            for_Item = Item.objects.get(pk=ingredient['item_id'])
                        except Item.DoesNotExist:
                            context['api error using ingredient ' + str(object['id'])] = 'Create RecipeIngredient ' + str(object['id']) + ' failed: related Item ' + str(ingredient['item_id']) + ' does not exist'
                            return
                        recipe_ingredient = RecipeIngredient(for_recipe=new_recipe, item_id=for_Item)
                        recipe_ingredient.add_details(ingredient)
                        recipe_ingredient.save()
                    #create EconomicsForRecipe entry
                    new_economics = EconomicsForRecipe(for_recipe=new_recipe)
                    new_economics.save()
                total_added += 1
            start += 200
            end += 200
    if api_endpoint == 'items':
        context['total_items_added'] = total_added
    elif api_endpoint == 'recipes':
        context['total_recipes_added'] = total_added

print(timezone.now())
context = {'total_items_added':0, 'total_recipes_added':0}
print("checking for new items")
get_api_objects('items', context) #36 min for empty database
print(timezone.now())
print("checking for new recipes")
get_api_objects('recipes', context) #5 min for empty database
print(timezone.now())
try:
    if context['api_error']:
        pass
except KeyError:
    if context['total_items_added'] or context['total_recipes_added']:
        print("updating new items")
        for item in Item.objects.all():
            if item.recipe_set.exists():
                item.can_be_crafted = True
                item.save()
print(context)
