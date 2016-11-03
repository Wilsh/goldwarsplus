#!/usr/bin/python3.5
#in command prompt:
#export DJANGO_SETTINGS_MODULE=goldwarsplus.settings
import sys
sys.path.append('/home/turbobear/goldwarsplus/')
import django
from django.conf import settings
django.setup()

from django.urls import reverse
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

def update_crafting_material_listings(context):
    '''Update BuyListings or SellListings for Items of type 'CraftingMaterial'.'''
    materials = Item.objects.filter(type='CraftingMaterial')
    begin = 0
    end = 200
    total_updated = 0
    processing = True
    while processing:
        #API endpoint allows 200 id requests max
        found_items = materials.filter(seen_on_trading_post=True)[begin:end]
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
                return
            for item in item_list:
                if update_buy_sell_listings(item, 'buys', context):
                    return
                if update_buy_sell_listings(item, 'sells', context):
                    return
            begin += 200
            end += 200
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
                        entry.economicsforitem.update(price_change_count=F('price_change_count') + 1)
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
        entry.economicsforitem.relist_profit = profit
        entry.economicsforitem.save()

context = {}
#update_crafting_material_listings(context)
#print(context)


# for item in Item.objects.all():
    # if item.seen_on_trading_post and item.recipe_set.count() > 1:
        # print(str(item.item_id)+' '+item.name)

# list = [['Lump of Tin', 80],
# ['Lump of Coal', 16],
# ['Lump of Primordium', 480]]
# for itemname, cost in list:
    # a = Item.objects.get(name=itemname)
    # a.can_purchase_from_vendor = True
    # a.vendor_price = cost
    # a.save()
    # a.selllisting_set.all().delete()
    # new_entry = SellListing(for_item=a)
    # new_entry.add_details({'quantity':99999,'unit_price':cost})
    # new_entry.save()
    
# for item in Item.objects.filter(seen_on_trading_post=True):
    # entry = EconomicsForItem(for_item=item)
    # entry.save()

# for item in Recipe.objects.all():
    # entry = EconomicsForRecipe(for_recipe=item)
    # entry.save()

# for item in Item.objects.all():
    # if item.recipe_set.exists():
        # item.can_be_crafted = True
        # item.save()

# a = EconomicsForItem.objects.all().order_by('-price_change_count')
# b = 0
# print(a[22].price_change_count)
# for item in a:
    # if b > 22:
        # break
    # item.price_change_count = 0
    # item.save()
    # b += 1
# print(a[22].price_change_count)

# list = ['Clay Pot', 'Grow Lamp', 'Plate of Meaty Plant Food', 'Plate of Piquant Plant Food',
# 'Vial of Maize Balm', 'Glob of Elder Spirit Residue', 'Lump of Mithrillium', 
# 'Spool of Silk Weaving Thread', 'Spool of Thick Elonian Cord', 'Heat Stone'
# ]
# for itemname in list:
    # a = Item.objects.get(name=itemname)
    # for recipe in a.recipe_set.all():
        # recipe.economicsforrecipe.limited_production = True
        # recipe.economicsforrecipe.save()
