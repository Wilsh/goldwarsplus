import json
import time
#import dateutil.parser #update to python 3.7 to use datetime.fromisoformat() instead of this
from datetime import datetime, timedelta

from django import template
from django.utils import timezone
from django.utils.html import format_html
from commerce.models import Item

register = template.Library()

@register.inclusion_tag('commerce/format_status.html')
def get_database_status():
    '''Display a status based on when the database was last updated'''
    LOG_FILE = '/home/turbobear/gwplog/script_log.txt' #created by gwp_automated.py
    try:
        with open(LOG_FILE, 'r') as f:
            info = json.load(f)
            #last_update = dateutil.parser.parse(info['last_update'])
            last_update = datetime.fromisoformat(info['last_update'])
    except Exception:
        return {'status': 'error'}
    difference = timezone.now() - last_update
    if difference < timedelta(minutes = 7):
        status = 'good'
    elif difference < timedelta(minutes = 25):
        status = 'updating'
    else:
        status = 'bad'
    return {'status': status}

@register.inclusion_tag('commerce/format_coins.html')
def show_coins(value):
    '''Display value with coin icons'''
    coin_list = []
    coin_list.append(int(value / 10000)) #gold
    coin_list.append(int(value / 100) % 100) #silver
    coin_list.append(value % 100) #copper
    return {'context': coin_list}

@register.filter
def is_relic(item):
    '''Return whether the given Item is a relic (all relic Item names start with "Relic of ...")'''
    return True if item.name.find('Relic', 0, 5) == 0 else False

@register.filter
def get_item(dictionary, key):
    '''Allow dictionary lookups by variable in templates'''
    return dictionary.get(key)

@register.filter
def get_item_model_by_id(id):
    '''Return an Item with the given item_id'''
    return Item.objects.get(item_id=id)

@register.inclusion_tag('commerce/format_crafting.html')
def show_crafting_tree(tree):
    '''Display the cheapest route to obtain an Item.
    tree is the return value of buy_or_craft() called on an Item'''
    shopping_list = {}
    format_list = []
    print_list(tree, shopping_list, format_list)
    return {'context': [format_list, shopping_list]}
    
def print_list(list, dict, format_list, indent='', multiplier=1):
    '''Expected format for list:
        ['craft', crafting_price, quantity, ingredient_list, [Item.item_id, Item.name], Recipe.recipe_id]
        ['buy', purchase_price, quantity, [Item.item_id, Item.name]]
        or a list containing one of the above'''
    if not hasattr(list, '__iter__'):
        return
    else:
        row_list = [] #[indent, buy/craft, count, name, cost]
        if list[0] == 'craft':
            row_list.append(format_html(indent))
            row_list.append('Craft')
            row_list.append(str(list[2] * multiplier))
            row_list.append(list[4])
            row_list.append(format_html(show_coins_internal(list[1] * list[2] * multiplier)))
            format_list.append(row_list)
            print_list(list[3], dict, format_list, indent + '&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;', list[2] * multiplier)
        elif list[0] == 'buy':
            row_list.append(format_html(indent))
            row_list.append('Buy')
            row_list.append(str(list[2] * multiplier))
            row_list.append(list[3])
            row_list.append(format_html(show_coins_internal(list[1] * multiplier)))
            format_list.append(row_list)
            try:
                dict[list[3][0]] += list[2] * multiplier
            except KeyError:
                dict[list[3][0]] = list[2] * multiplier
        else:
            item_count = len(list)
            counter = 0
            while counter < item_count:
                print_list(list[counter], dict, format_list, indent, multiplier)
                counter += 1

def show_coins_internal(value):
    '''Display value with coin icons. For use by custom template tags'''
    coin_list = []
    coin_list.append(int(value / 10000)) #gold
    coin_list.append(int(value / 100) % 100) #silver
    coin_list.append(value % 100) #copper
    output = ''
    if coin_list[0] > 0:
        output += str(coin_list[0]) + ' <img src="/static/commerce/goldcoin.png" alt="gold" /> '
    if coin_list[0] or coin_list[1]:
        if coin_list[1] < 10 and coin_list[0]:
            output += '0'
        output += str(coin_list[1]) + ' <img src="/static/commerce/silvercoin.png" alt="silver" /> '
    if coin_list[0] or coin_list[1] or coin_list[2]:
        if coin_list[2] < 10 and (coin_list[0] or coin_list[1]):
            output += '0'
        output += str(coin_list[2]) + ' <img src="/static/commerce/coppercoin.png" alt="copper" /> '
    return output
