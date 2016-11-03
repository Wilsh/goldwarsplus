#!/usr/bin/python3.5
#in command prompt:
#export DJANGO_SETTINGS_MODULE=goldwarsplus.settings
import sys
sys.path.append('/home/turbobear/goldwarsplus/')
import django
from django.conf import settings
django.setup()

from django.urls import reverse
from django.db.models import F
from urllib.request import Request, urlopen, urlretrieve
from urllib.error import URLError, HTTPError
import json
import time
from django.utils import timezone
import os.path

from commerce.forms import UpdateForm
from commerce.models import Item, ItemFlag, EconomicsForItem, Icon, Recipe, EconomicsForRecipe, RecipeDiscipline, RecipeIngredient, BuyListing, SellListing

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

def find_listed_items(context):
    '''Retrieve a list of all Items on the trading post and 
    set each Item's seen_on_trading_post field as True'''
    item_list = get_api_data('commerce/listings', context)
    if not item_list:
        #API error
        return
    total_updated = 0
    for item in item_list:
        try:
            update = Item.objects.get(item_id=item)
        except Item.DoesNotExist:
            print('Item ' + str(item) + ' does not exist')
            continue
        if update.seen_on_trading_post == False:
            update.seen_on_trading_post = True
            update.save()
            new_economic_entry = EconomicsForItem(for_item=update)
            new_economic_entry.save()
            total_updated += 1
    context['total_new_items'] = total_updated

def get_commerce_listings(context, begin=0):
    '''Update buy and sell orders for each Item that has been seen 
    on the trading post. Up to 10 orders of each type will be saved'''
    step = 200
    end = begin + step
    total_updated = 0
    processing = True
    while processing:
        #API endpoint allows 200 id requests max
        found_items = Item.objects.filter(seen_on_trading_post=True)[begin:end]
        num_found_items = found_items.count()
        if num_found_items > 0:
            #construct URL for recipes to update
            id_list = []
            for item in found_items:
                id_list.append(str(item.item_id))
            end_url = ','.join(id_list)
            #pull data from API
            item_list = get_api_data('commerce/listings?ids=' + end_url, context)
            if not item_list:
                #API error
                context['get_commerce_listings_failed_at_begin'] = begin
                return
            for item in item_list:
                if update_buy_sell_listings(item, 'buys', context):
                    return
                if update_buy_sell_listings(item, 'sells', context):
                    return
            begin += step
            end += step
            total_updated += num_found_items
        else:
            processing = False
    context['total_commerce_listings_updated'] = total_updated

def update_buy_sell_listings(item, buy_or_sell, context):
    '''Update or create BuyListings or SellListings for item.
    Called by get_commerce_listings'''
    if buy_or_sell != 'buys' and buy_or_sell != 'sells':
        context['update_buy_sell_listings'] = 'Invalid argument for buy_or_sell'
        return -1
    try:
        entry = Item.objects.get(item_id=item['id'])
    except Item.DoesNotExist:
        print('Item ' + str(item['id']) + ' not found')
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
        if counter < 4:
            #create listing
            if listing['quantity'] > 0 and listing['unit_price'] > 0:
                #only need one buy listing
                if buy_or_sell == 'buys':
                    new_entry = BuyListing(for_item=entry)  
                    new_entry.add_details(listing)
                    new_entry.save()
                    return
                elif buy_or_sell == 'sells':
                    #detect price fluctuations to optimize listing update frequency
                    if counter == 0 and abs(listing['unit_price'] - old_price) > (old_price * 0.05):
                        # economics = EconomicsForItem.objects.filter(for_item=entry)
                        # economics.update(price_change_count=F('price_change_count') + 1)
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
    buy_price = entry.get_market_sell()
    profit = (entry.get_market_delay_sell() * 0.85) - buy_price
    if profit > 0 and profit < buy_price:
        # economics = EconomicsForItem.objects.get(for_item=entry)
        # economics.relist_profit = profit
        # economics.save()
        entry.economicsforitem.relist_profit = profit
        entry.economicsforitem.save()

def calculate_recipe_cost(context):
    '''For each Item that is craftable and can be traded, calculate the lowest cost 
    of the ingredients needed to craft the Item if that cost is lower than just buying the Item. 
    Save that cost in the EconomicsForRecipe for the Item. Calculate the profit from crafting 
    the Item and save if > 0'''
    EconomicsForRecipe.objects.all().update(ingredient_cost=0, delayed_crafting_profit=0, fast_crafting_profit=0)
    num_updated = 0
    for item in Item.objects.filter(seen_on_trading_post=True, can_be_crafted=True):
        result = item.buy_or_craft()
        if result[0] == 'buy':
            continue
        elif result[0] == 'craft':
            # economics = EconomicsForRecipe.objects.get(for_recipe=Recipe.objects.get(recipe_id=result[5]))
            economics = Recipe.objects.get(recipe_id=result[5]).economicsforrecipe
            economics.ingredient_cost = result[1] * result[2]
            profit = int((item.get_market_sell() * 0.85) - economics.ingredient_cost)
            if profit > 0:
                economics.fast_crafting_profit = profit
                num_updated += 1
            #items with sell listings much greater than buy listings are not likely to sell
            if (item.get_market_sell() * 2.5) - item.get_market_delay_sell() > 0:
                profit = int((item.get_market_delay_sell() * 0.85) - economics.ingredient_cost)
                if profit > 0:
                    economics.delayed_crafting_profit = profit
                    num_updated += 1
            economics.save()
    context['profitable_recipes_found'] = num_updated


print(timezone.now())
context = {}
find_listed_items(context) #40 sec
print(context)
EconomicsForItem.objects.update(relist_profit=0)
# get_commerce_listings(context, 23600) #35 min
get_commerce_listings(context) #35 min
try:
    if context['get_commerce_listings_failed_at_begin']:
        print(context)
except KeyError:
    print(timezone.now())
    calculate_recipe_cost(context) #12 min
# calculate_recipe_cost(context) #12 min
print(timezone.now())
print(context)

