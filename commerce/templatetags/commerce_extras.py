from django import template
from django.utils.html import format_html

register = template.Library()

@register.inclusion_tag('commerce/format_coins.html')
def show_coins(value):
    '''Display value with coin icons'''
    coin_list = []
    coin_list.append(int(value / 10000)) #gold
    coin_list.append(int(value / 100) % 100) #silver
    coin_list.append(value % 100) #copper
    return {'context': coin_list}

@register.filter
def get_item(dictionary, key):
    '''Allow dictionary lookups by variable in templates'''
    return dictionary.get(key)

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
        if list[0] == 'craft':
            format_list.append(format_html(str(indent + 'Craft ' + str(list[2] * multiplier) + ' ' + list[4][1] + ' for ' + str(list[1] * list[2] * multiplier))))
            print_list(list[3], dict, format_list, indent + '&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;', list[2] * multiplier)
        elif list[0] == 'buy':
            format_list.append(format_html(str(indent + 'Buy ' + str(list[2] * multiplier) + ' ' + list[3][1] + ' for ' + str(list[1] * multiplier) + ' (' + str(int(list[1] / list[2])) + ' each)')))
            try:
                dict[list[3][1]] += list[2] * multiplier
            except KeyError:
                dict[list[3][1]] = list[2] * multiplier
        else:
            item_count = len(list)
            counter = 0
            while counter < item_count:
                print_list(list[counter], dict, format_list, indent, multiplier)
                counter += 1
