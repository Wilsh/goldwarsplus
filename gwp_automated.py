#!/usr/bin/python3.10

#This script runs continuously to keep the database current.
#Once daily, it checks the GW2 API for previously unseen items and recipes 
#and adds any new items or recipes to the database.
#Once every four hours, it refreshes all Trading Post data.
#Approximately every five minutes, it refreshes the most relevant
#Trading Post data.

#After first running this script to populate a new database, execute 
#the first two code blocks in codesnippets.py to complete the setup.

import os
os.system("export DJANGO_SETTINGS_MODULE=website.settings")

import sys
import django
from django.conf import settings
sys.path.append(settings.BASE_DIR)
django.setup()

import json
import time
from datetime import datetime, timedelta
from urllib.request import Request, urlopen, urlretrieve
from urllib.error import URLError, HTTPError
from django.urls import reverse
from django.db.models import F, Q
from django.utils import timezone
from django.core.exceptions import ObjectDoesNotExist
from threading import Thread
from queue import Queue

from commerce.models import Item, ItemFlag, EconomicsForItem, Icon, Recipe, EconomicsForRecipe, RecipeDiscipline, RecipeIngredient, BuyListing, SellListing

LOG_FILE = os.path.join(settings.BASE_DIR, "script_info.json")
DJANGO_BASE = os.path.join(settings.BASE_DIR, "") #location of manage.py

script_info = {
        "last_update": timezone.now() - timedelta(days=1),
        "last_item_update": timezone.now() - timedelta(days=1),
        "last_full_tp_update": timezone.now() - timedelta(hours=4),
        "get_commerce_listings_failed_at": 0,
        "failed_at_meta_level": 0
    }

#set up thread queue for data processing
queryset_queue = Queue()
def calculate_worker():
    '''This worker operates in a separate thread to calculate Recipe costs
    for Item querysets that have been added to the queryset_queue'''
    while True:
        queryset = queryset_queue.get()
        calculate_recipe_cost(queryset)
        queryset_queue.task_done()
Thread(target=calculate_worker, daemon=True).start()

def setup_script_info():
    '''Load data created from previous runs of this script or
    create a new data file if none exists'''
    try:
        with open(LOG_FILE, "r") as f:
            info = json.load(f)
            script_info["last_update"] = datetime.fromisoformat(info["last_update"])
            script_info["last_item_update"] = datetime.fromisoformat(info["last_item_update"])
            script_info["last_full_tp_update"] = datetime.fromisoformat(info["last_full_tp_update"])
    except (FileNotFoundError, KeyError):
        write_script_info()

def write_script_info():
    '''Save data from script_info to a file'''
    with open(LOG_FILE, "w") as f:
        script_info_json = {}
        for k, v in script_info.items():
            script_info_json[k] = v
        script_info_json["last_update"] = script_info_json["last_update"].isoformat()
        script_info_json["last_item_update"] = script_info_json["last_item_update"].isoformat()
        script_info_json["last_full_tp_update"] = script_info_json["last_full_tp_update"].isoformat()
        json.dump(script_info_json, f)

def update_succeeded():
    script_info["last_update"] = timezone.now()
    write_script_info()

def get_api_data(url_postfix, context):
    '''Return decoded json object from GW2 API. Will retry API call if HTTPError occurs'''
    req = Request('https://api.guildwars2.com/v2/' + url_postfix)
    retries = 10
    while True:
        try:
            response = urlopen(req)
        except HTTPError as e:
            print(e)
            retries -= 1
            if retries == 0:
                print('Aborting API call: too many failed attempts')
                print('API call that failed: https://api.guildwars2.com/v2/' + url_postfix)
                context['api_error'] = e
                break
            print('API call failed. Retries remaining: ' + str(retries))
            time.sleep(20)
            continue
        except URLError as e:
            context['api_error'] = e.reason
            print(e)
            #print('URLError: ' + e.reason)
        else:
            try:
                try:
                    del context['api_error']
                except KeyError:
                    pass
                if retries < 10:
                    print('API retry successful')
                return json.loads(response.read().decode('utf-8'))
            except Exception as e:
                context['api_error'] = e
                print(e)
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
                    except KeyError:
                        #ignore item without icon (api bug)
                        print(f"Item found with no corresponding icon, ID: {object['id']}")
                        continue
                    except Exception as e:
                        print(f"Unchecked exception in get_api_objects: {type(e).__name__}, Item ID: {object['id']}")
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
                        known_bad = ['9018', '36578', '39424', '39425', '89011', '89073', '89014', 
                            '89394', '89407', '90002', '90083', '90088', '90089', '91275', '91362', 
                            '91290', '91358', '91402', '92170', '92149', '92608', '92571', '92581', 
                            '92651', '93297', '93301', '93305', '93314', '93674', '93684', '94114', 
                            '94111', '94440', '94388', '94426', '94918', '94916', '94915', '94909', 
                            '95066', '95042', '95257', '95250', '95400', '95372', '95357', '98209', 
                            '98202', '98177', '98182', '98206', '98196', '98200', '98612', '98697',
                            '99048', '99081', '99841', '99835', '99931', '101084', '101350', '101384',
                            '101436', '101697', '104125', '104155', '104169',  '104611', '104591', '104645',
                            ]
                        if str(object['output_item_id']) in known_bad:
                            #ignore known error in api
                            continue
                        print('Create Recipe ' + str(object['id']) + ' failed: related Item ' + str(object['output_item_id']) + ' does not exist')
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
                            print('Create RecipeIngredient ' + str(object['id']) + ' failed: related Item ' + str(ingredient['item_id']) + ' does not exist')
                            continue
                        recipe_ingredient = RecipeIngredient(for_recipe=new_recipe, item_id=for_Item)
                        recipe_ingredient.add_details(ingredient)
                        recipe_ingredient.save()
                    #create EconomicsForRecipe entry
                    new_economics = EconomicsForRecipe(for_recipe=new_recipe)
                    if new_economics.set_limited_production():
                        new_economics.num_limited_production_items = new_economics.count_limited_production_items()
                    new_economics.save()
                total_added += 1
            start += 200
            end += 200
    if api_endpoint == 'items':
        context['total_items_added'] = total_added
    elif api_endpoint == 'recipes':
        context['total_recipes_added'] = total_added

def find_listed_items(context):
    '''Retrieve a list of all Items on the trading post and 
    set each Item's seen_on_trading_post field as True'''
    item_list = get_api_data('commerce/listings', context)
    if not item_list:
        context['api_error'] = "no response from api"
        return
    total_updated = 0
    known_bad = ['9018', '9590', '14907', '14913', '14915', '14918', '20216', 
        '21651', '36401', '36666', '37243', '37306', '37312', '37321', 
        '37343', '37374', '37379', '37401', '37427', '37445', '37464',
        '37492', '37505', '37513', '37525', '37531', '37534', '37558',
        '37608', '37648', '37685', '37704', '37708', '37711', '37727',
        '37732', '37756', '41592', '41598', '41607', '41636', '41667',
        '41670', '41703', '41725', '41732', '43983', '43984', '43986',
        '43987', '43988', '43999', '103719',
        ]
    for item in item_list:
        try:
            update = Item.objects.get(item_id=item)
        except Item.DoesNotExist:
            if not str(item) in known_bad:
                print('Item ' + str(item) + ' does not exist')
            continue
        if not update.seen_on_trading_post:
            update.seen_on_trading_post = True
            update.save()
            new_economic_entry = EconomicsForItem(for_item=update)
            new_economic_entry.save()
            total_updated += 1
    context['total_new_tp_items'] = total_updated

def update_buy_sell_listings(item, buy_or_sell, context):
    '''Update or create BuyListings or SellListings for item.
    Called by get_commerce_listings'''
    try:
        entry = Item.objects.get(item_id=item['id'])
    except Item.DoesNotExist:
        print('Item ' + str(item['id']) + ' not found')
        return
    except TypeError:
        print('item ' + str(item) + ' passed in as non-Item object to update_buy_sell_listings()')
        return
    #delete old listings
    if buy_or_sell == 'buys':
        entry.buylisting_set.all().delete()
    if buy_or_sell == 'sells':
        old_price = entry.get_market_buy()
        entry.selllisting_set.all().delete()
    counter = 0
    added_vendor_listing = False
    for listing in item[buy_or_sell]:
        #limit saved listings to 10
        if counter < 10:
            #create listing
            if listing['quantity'] > 0 and listing['unit_price'] > 0:
                #only need one buy listing
                if buy_or_sell == 'buys':
                    new_entry = BuyListing(for_item=entry)  
                    new_entry.add_details(listing)
                    new_entry.save()
                    return
                elif buy_or_sell == 'sells':
                    #detect price fluctuations to optimize listing update frequency (not currently used)
                    if counter == 0 and abs(listing['unit_price'] - old_price) > (old_price * 0.02):
                        EconomicsForItem.objects.filter(for_item=entry).update(price_change_count=F('price_change_count') + 1)
                    #now add sell listing
                    new_entry = SellListing(for_item=entry)
                    if entry.can_purchase_from_vendor:
                        if counter == 0 and not added_vendor_listing:
                            #add listing for vendor price
                            new_entry.add_details({'quantity':99999,'unit_price':entry.vendor_price})
                            new_entry.save()
                            added_vendor_listing = True
                            continue
                        elif listing['unit_price'] >= entry.vendor_price:
                            #ignore listings that are more expensive than vendor
                            break
                new_entry.add_details(listing)
                new_entry.save()
                counter += 1
        else:
            break
    #calculate profit from reselling Item
    '''buy_price = entry.get_market_sell()
    profit = (entry.get_market_delay_sell() * 0.85) - buy_price
    if profit > 0 and profit < buy_price:
        # economics = EconomicsForItem.objects.get(for_item=entry)
        # economics.relist_profit = profit
        # economics.save()
        entry.economicsforitem.relist_profit = profit
        entry.economicsforitem.save()'''

def get_commerce_listings(item_queryset, begin=0, meta_level=0):
    '''Update buy and sell orders for each Item in the given QuerySet'''
    context={}
    step = 200
    end = begin + step
    total_updated = 0
    processing = True
    while processing:
        #API endpoint allows 200 id requests max
        item_subset = item_queryset[begin:end]
        num_found_items = item_subset.count()
        if num_found_items > 0:
            #construct URL for recipes to update
            id_list = []
            for item in item_subset:
                id_list.append(str(item.item_id))
            end_url = ','.join(id_list)
            #pull data from API
            item_list = get_api_data('commerce/listings?ids=' + end_url, context)
            if not item_list:
                #API error
                script_info['get_commerce_listings_failed_at'] = begin
                script_info['failed_at_meta_level'] = meta_level
                write_script_info()
                return -1
            for item in item_list:
                update_buy_sell_listings(item, 'buys', context)
                update_buy_sell_listings(item, 'sells', context)
            begin += step
            end += step
            total_updated += num_found_items
        else:
            processing = False
    #context['total_commerce_listings_updated'] = total_updated

def calculate_recipe_cost(item_queryset, skip_limited_production=False):
    '''For each Item in the given QuerySet, calculate the lowest cost of the ingredients 
    needed to craft the Item if that cost is lower than just buying the Item. Save that 
    cost in the EconomicsForRecipe for the Item. Calculate the profit from crafting the Item'''
    num_updated = 0
    for item in item_queryset:
        try:
            economics = item.economicsforitem
            result = economics.set_cost_by_meta() #set_cost_by_meta() must be saved manually
            economics.save()
        except ObjectDoesNotExist:
            print(f"Invalid Item in queryset given to calculate_recipe_cost(): EconomicsForItem does not exist for item {item}")
            continue
        if result[0] == 'buy':
            for recipe in Recipe.objects.filter(output_item_id=item):
                EconomicsForRecipe.objects.filter(for_recipe=recipe).update(ingredient_cost=result[1], delayed_crafting_profit=0, fast_crafting_profit=0, limited_production_profit_ratio=0)
            continue
        elif result[0] == 'craft':
            ingredient_cost = result[1]
            market_sell = item.get_market_sell()
            market_delay_sell = item.get_market_delay_sell()
            fast_crafting_profit = int((market_sell * 0.85) - ingredient_cost)
            #items with sell listings much greater than buy listings are not likely to sell
            if (market_sell * 10) - market_delay_sell > 0:
                delayed_crafting_profit = int((market_delay_sell * 0.85) - ingredient_cost)
            else:
                delayed_crafting_profit = 0
            EconomicsForRecipe.objects.filter(for_recipe=Recipe.objects.get(recipe_id=result[2])).update(ingredient_cost=ingredient_cost, delayed_crafting_profit=delayed_crafting_profit, fast_crafting_profit=fast_crafting_profit)
            if fast_crafting_profit > 1000 or delayed_crafting_profit > 1000:
                num_updated += 1
                item.historically_profitable = True
                item.save()
    '''if not skip_limited_production:
        for economics in EconomicsForRecipe.objects.filter(limited_production=True):
            try: 
                economics.limited_production_profit_ratio = int(economics.delayed_crafting_profit / economics.num_limited_production_items)
                economics.save()
            except ZeroDivisionError:
                print("Division by zero error in Recipe: " + str(economics.for_recipe))
                continue'''
    #context['profitable_recipes_found'] = num_updated
    #update_succeeded() **moved to end of queue execution**

def get_new_items():
    '''Check the API for previously unseen Items and Recipes'''
    context = {'total_items_added':0, 'total_recipes_added':0}
    print("Checking for new items")
    get_api_objects('items', context) #36 min for empty database
    print(timezone.now())
    print("Checking for new recipes")
    get_api_objects('recipes', context) #5 min for empty database
    print(timezone.now())
    try:
        if context['api_error']:
            pass
    except KeyError:
        if context['total_items_added'] or context['total_recipes_added']:
            print("Updating new items")
            #for item in Item.objects.all(): ##########why check every item?
            #    if item.recipe_set.exists():
            #        item.can_be_crafted = True
            #        item.save()
            for item in Item.objects.filter(crafting_meta_level=-1):
                item.crafting_meta_level = item.get_meta_level()
                if item.crafting_meta_level > 0:
                    item.can_be_crafted = True
                item.save()
            os.system("python " + DJANGO_BASE + "manage.py collectstatic --no-input")
        script_info["last_item_update"] = timezone.now()
        write_script_info()
    print(context)
    print("Checking for new items on the trading post")
    context = {}
    find_listed_items(context)
    print(context)

def should_check_for_items():
    return timezone.now() - script_info["last_item_update"] > timedelta(days = 1)
    
def should_full_tp_update():
    if script_info['get_commerce_listings_failed_at'] == 0:
        return timezone.now() - script_info["last_full_tp_update"] > timedelta(hours = 4)
    return True

def update_and_calculate_all():
    '''Refresh buy and sell orders for every Item on the trading post 
    and calculate profits for every craftable Item that can be sold'''
    begin = script_info['get_commerce_listings_failed_at']
    meta_level = script_info['failed_at_meta_level']
    all_items = Item.objects.filter(seen_on_trading_post=True)
    calculate_items = Item.objects.filter(economicsforitem__isnull=False, can_be_crafted=True)
    
    if update_item_queryset(all_items, calculate_items, meta_level, begin) == -1:
        return
    script_info["last_full_tp_update"] = timezone.now()
    script_info['get_commerce_listings_failed_at'] = 0
    script_info['failed_at_meta_level'] = 0
    write_script_info()

def update_and_calculate_limited():
    '''Refresh buy and sell orders for commonly-used crafting components on the trading post 
    and calculate profits for known-profitable Items'''
    limited_items = Item.objects.filter(Q(type="CraftingMaterial") | Q(type="UpgradeComponent") | Q(historically_profitable=True), seen_on_trading_post=True)
    profitable_items_with_recipes = Item.objects.filter(historically_profitable=True)
    update_item_queryset(limited_items, profitable_items_with_recipes)

def update_item_queryset(item_queryset, calculate_queryset, meta_level=0, begin=0):
    '''Update Item prices for the given item_queryset and calculate profits for crafting
    the given calculate_queryset. Profit calculations are performed in a separate thread
    to take advantage of CPU downtime while waiting for API calls on Items with higher
    meta levels'''
    while meta_level < 7:
        item_subset = item_queryset.filter(crafting_meta_level=meta_level)
        calculate_subset = calculate_queryset.filter(crafting_meta_level=meta_level)
        if meta_level > 0:
            #calculate recipe costs
            queryset_queue.put(calculate_subset)
        #pull API data
        if get_commerce_listings(item_subset, begin, meta_level) == -1:
            return -1
        begin = 0
        meta_level += 1
    #there are few items with crafting_meta_level > 6, so combine the remaining meta_levels
    item_subset = item_queryset.filter(crafting_meta_level__gte=7)
    if get_commerce_listings(item_subset, begin, meta_level) == -1:
        return -1
    #API updates finished; still need to calculate recipe costs in order of meta_level
    calculate_subset = calculate_queryset.filter(crafting_meta_level=meta_level)
    while calculate_subset.count():
        queryset_queue.put(calculate_subset)
        meta_level += 1
        calculate_subset = calculate_queryset.filter(crafting_meta_level=meta_level)
    #wait for final recipe calculation
    queryset_queue.join()
    update_succeeded()

setup_script_info()
requires_update = False
while True:
    a = timezone.now()
    if should_check_for_items():
        get_new_items()
    if should_full_tp_update():
        print("Updating all item prices on trading post")
        update_and_calculate_all()
        requires_update = True
        print("Finished updating all item prices")
    else:
        print("Updating limited item prices on trading post")
        update_and_calculate_limited()
        print("Finished updating limited item prices")
    print(timezone.now()-a)
    print("Sleeping")
    time.sleep(60)
