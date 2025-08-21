#add crafting items that can be purchased from a vendor
vendor_items = [ #[item_id, vendor_price]
    [76839, 56],
    [62942, 8],
    [46747, 150],
    [19924, 48],
    [19794, 24],
    [19793, 32],
    [19792, 8],
    [19791, 48],
    [19790, 64],
    [19789, 16],
    [19750, 16],
    [19704, 8],
    [13010, 496],
    [13009, 100000],
    [13008, 20000],
    [13007, 5000],
    [13006, 1480],
    [12156, 8]
]
for entry in vendor_items:
    item = Item.objects.get(item_id=entry[0])
    item.can_purchase_from_vendor = True
    item.vendor_price = entry[1]
    item.save()

#set limited production flag for EconomicsForRecipe objects
limited_items = ['Clay Pot', 'Grow Lamp', 'Plate of Meaty Plant Food', 'Plate of Piquant Plant Food',
                'Vial of Maize Balm', 'Glob of Elder Spirit Residue', 'Lump of Mithrillium', 
                'Spool of Silk Weaving Thread', 'Spool of Thick Elonian Cord', 'Heat Stone',
                'Dragon Hatchling Doll Adornments', 'Dragon Hatchling Doll Eye', 'Dragon Hatchling Doll Frame',
                'Dragon Hatchling Doll Hide', 'Gossamer Stuffing'
                ]
for name in limited_items:
    a = EconomicsForRecipe.objects.filter(for_recipe__output_item_id__name=name)
    for entry in a:
        entry.limited_production = True
        entry.num_limited_production_items = 1
        entry.save()
for entry in EconomicsForRecipe.objects.all():
    if entry.set_limited_production():
        entry.num_limited_production_items = entry.count_limited_production_items()
        entry.save()

#find crafting_meta_level for an Item object
def get_meta_level(item, depth=0):
    recipes = item.recipe_set.all()
    if recipes.count() == 0:
        return depth
    max = 0
    for recipe in recipes:
        branch_max = 0
        for ingredient in recipe.recipeingredient_set.all():
            count = get_meta_level(ingredient.item_id, depth+1)
            if count > branch_max:
                branch_max = count
        if branch_max > max:
            max = branch_max
    return max

#set crafting_meta_level for each Item object
for item in Item.objects.filter(crafting_meta_level=-1):
    level = get_meta_level(item)
    print(item.name + ' ' + str(item.item_id) + ' ' + str(level))
    item.crafting_meta_level = level
    item.save()
    
#create missing EconomicsForItem entries
updated = 0
for item in Item.objects.filter(seen_on_trading_post=True):
    try:
        EconomicsForItem.objects.get(for_item=item)
    except:
        new_economic_entry = EconomicsForItem(for_item=item)
        new_economic_entry.save()
        updated += 1
print(updated)

#populate.py
def print_crafting_tree(context):
    #item = Recipe.objects.get(output_item_id=19714)
    item = Item.objects.get(pk=45868)
    tree = item.buy_or_craft()
    print('For item: ' + item.name)
    shopping_list = {}
    print_list(tree, shopping_list)
    context['shopping_list'] = shopping_list
    
def print_list(list, dict, indent='', multiplier=1):
    if not hasattr(list, '__iter__'):
        return
    else:
        if list[0] == 'craft':
            print(indent + 'Craft ' + str(list[2] * multiplier) + ' ' + list[4] + ' for ' + str(list[1] * list[2] * multiplier))
            print_list(list[3], dict, indent + '    ', list[2] * multiplier)
        elif list[0] == 'buy':
            print(indent + 'Buy ' + str(list[2] * multiplier) + ' ' + list[3] + ' for ' + str(list[1] * multiplier) + ' (' + str(int(list[1] / list[2])) + ' each)')
            try:
                dict[list[3]] += list[2] * multiplier
            except KeyError:
                dict[list[3]] = list[2] * multiplier
        else:
            item_count = len(list)
            counter = 0
            while counter < item_count:
                print_list(list[counter], dict, indent, multiplier)
                counter += 1

#views.py
    def get_item_details(self, context):
        '''Find Item records created with get_items and
        fill in missing details.'''
        processing = True
        total_updated = 0
        while processing:
            #API endpoint allows 200 id requests max
            found_items = Item.objects.filter(name='').filter(icon='')[:200]
            num_found_items = found_items.count()
            if num_found_items > 0:
                #construct URL for items to update
                id_list = []
                for item in found_items:
                    id_list.append(str(item.item_id))
                end_url = ','.join(id_list)
                #pull data from API
                item_list = self.get_api_data('items?ids=' + end_url, context)
                if not item_list:
                    #API error
                    return
                for item in item_list:
                    update_item = Item.objects.get(pk=item['id'])
                    update_item.add_details(item)
                    update_item.save()
                    #create entry in ItemFlag table
                    new_itemflag = ItemFlag(for_item=update_item)
                    new_itemflag.add_details(item['flags'])
                    new_itemflag.save()
                total_updated += num_found_items
            else:
                processing = False
        context['total_items_updated'] = total_updated
    def get_recipe_details(self, context):
        '''Find Recipe records created with get_recipes and
        fill in missing details.'''
        processing = True
        total_updated = 0
        while processing:
            #API endpoint allows 200 id requests max
            found_recipes = Recipe.objects.filter(type='').filter(output_item_id=0)[:200]
            num_found_recipes = found_recipes.count()
            if num_found_recipes > 0:
                #construct URL for recipes to update
                id_list = []
                for recipe in found_recipes:
                    id_list.append(str(recipe.recipe_id))
                end_url = ','.join(id_list)
                #pull data from API
                recipe_list = self.get_api_data('recipes?ids=' + end_url, context)
                if not recipe_list:
                    #API error
                    return
                for recipe in recipe_list:
                    update_recipe = Recipe.objects.get(pk=recipe['id'])
                    update_recipe.add_details(recipe)
                    update_recipe.save()
                    #create entry in RecipeDiscipline table
                    new_recipeflag = RecipeDiscipline(for_recipe=update_recipe)
                    new_recipeflag.add_details(recipe['disciplines'])
                    new_recipeflag.save()
                    #create entries in RecipeIngredient table
                    for ingredient in recipe['ingredients']:
                        recipe_ingredient = RecipeIngredient(for_recipe=update_recipe)
                        recipe_ingredient.add_details(ingredient)
                        recipe_ingredient.save()
                total_updated += num_found_recipes
            else:
                processing = False
        context['total_recipes_updated'] = total_updated
#models.py
class WorthMakingFast(Item):
    '''Item that will produce a profit when buying the components of its Recipe,
     crafting that Item, then immediately selling the Item on the trading post'''
    profit = models.PositiveIntegerField(default=0)
    
    class Meta:
        ordering = ["-profit"]
    
    def __str__(self):
        return "WorthMakingFast " + str(self.item_id) + ": " + self.name + "   profit: " + str(self.profit)
    
#item_list.html
    <dl class="dl-horizontal">
    {% for item in item_list %}
        <dt>{{ item.item_id }}</dt>
        <dd><a href="{% url 'commerce:detail' item.item_id %}">{{ item.name }}</a></dd>
    {% endfor %}
    </dl>

#views.py
class TradeableListView(generic.ListView):
    model = Tradeable
    template_name = 'commerce/tradeable_list.html'
    context_object_name = 'tradeable_list'
    paginate_by = 20

#models.py
class Tradeable(Item):
    '''Subset of Items that can be traded with other players
    or are used as an ingredient to create tradeable Items.
    The main table for the commerce app'''
    recipe = models.IntegerField(default=0)
    
    class Meta:
        ordering = ["item_id"]
    
    def __str__(self):
        return "Tradeable " + str(self.item_id) + ": " + self.name
    
    def add_details(self, Item, getIcon):
        '''Copy details from an Item and create a local copy of
        the image found at the URL in Item.icon (named as <pk>.png)'''
        self.name = Item.name
        self.description = Item.description
        self.type = Item.type
        self.rarity = Item.rarity
        self.level = Item.level
        self.vendor_value = Item.vendor_value
        try:
            recipe_link = Recipe.objects.get(output_item_id=self.item_id)
        except Recipe.DoesNotExist:
            pass
        except Recipe.MultipleObjectsReturned:
            self.recipe = -1
        else:
            self.recipe = recipe_link.recipe_id
        #TODO: avoid using an absolute path
        if getIcon:
            urlretrieve(Item.icon, '/home/turbobear/goldwarsplus/commerce/static/commerce/items/' + str(self.item_id) + '.png')
        
    def get_vendor_value_split(self):
        '''Calculate vendor_value in terms of gold, silver, and copper'''
        coin_list = []
        coin_list.append(int(self.vendor_value / 10000)) #gold
        coin_list.append(int(self.vendor_value / 100) % 100) #silver
        coin_list.append(self.vendor_value % 100) #copper
        return coin_list
    
    def get_market_buy(self, quantity):
        '''Return the cost of the quantity of this item if bought on the trading post'''
        sell_orders = self.sell.all().order_by('unit_price')
        total = 0
        count = 0
        for order in sell_orders:
            if (order.quantity + count) <= quantity:
                count += order.quantity
                total += order.quantity * order.unit_price
            else:
                total += (quantity - count) * order.unit_price
                return total
        #quantity not available
        return 0
    
    def get_market_sell(self):
        '''Return the value of this item if sold immediately on the trading post'''
        buy_orders = self.buy.all().order_by('-unit_price')
        return buy_orders[0].unit_price if buy_orders else 0
    
    def get_market_delay_sell(self):
        '''Return the value of this item if sold one copper below the lowest current 
        selling price on the trading post. Returns 0 if none of these items are listed'''
        sell_orders = self.sell.all().order_by('unit_price')
        return sell_orders[0].unit_price - 1 if sell_orders else 0

def get_context_data(self, **kwargs):
    context = super(TradeableListView, self).get_context_data(**kwargs)
    list = self.get_queryset()
    for item in list:
        coin_list = []
        vendor_value = item.vendor_value
        coin_list.append(int(vendor_value / 10000)) #gold
        coin_list.append(int(vendor_value / 100 % 100)) #silver
        coin_list.append(vendor_value % 100) #copper
        context[str(item.item_id)+'_coins'] = coin_list
    return context

{% if item.rarity == 'Fine' %}
style="color:#62a4da"
{% elif item.rarity == 'Masterwork' %}
style="color:#1a9306"
{% elif item.rarity == 'Rare' %}
style="color:#fcd00b"
{% elif item.rarity == 'Exotic' %}
style="color:#ffa405"
{% elif item.rarity == 'Ascended' %}
style="color:#fb3e8d"
{% elif item.rarity == 'Legendary' %}
style="color:#4c139d"
{% endif %}

if form.cleaned_data['action'] == 'get_items':
    self.get_items(context)
elif form.cleaned_data['action'] == 'get_item_details':
    self.get_item_details(context)
elif form.cleaned_data['action'] == 'get_recipes':
    self.get_recipes(context)
elif form.cleaned_data['action'] == 'get_recipe_details':
    self.get_recipe_details(context)

def get_recipe_details(request):
    '''Find Recipe records created with get_recipes and
    fill in missing details.'''
    context = {'num_items': Item.objects.count(),
    'num_recipes': Recipe.objects.count()
    }
    base_url = 'https://api.guildwars2.com/v2/recipes?ids='
    processing = True
    total_updated = 0
    while processing:
        #API endpoint allows 200 id requests max
        found_recipes = Recipe.objects.filter(type='').filter(output_item_id=0)[0:200]
        num_found_recipes = found_recipes.count()
        if num_found_recipes > 0:
            #construct URL for recipes to update
            recipe_list = []
            for recipe in found_recipes:
                recipe_list.append(str(recipe.recipe_id))
            end_url = ','.join(recipe_list)
            req = Request(base_url + end_url)
            #pull data from API
            try:
                response = urlopen(req)
            except HTTPError as e:
                context['api_error'] = e
                processing = False
            except URLError as e:
                context['api_error'] = e.reason
                processing = False
            else:
                #decode API response
                recipe_list = json.loads(response.read().decode('utf-8'))
                for recipe in recipe_list:
                    update_recipe = Recipe.objects.get(pk=recipe['id'])
                    update_recipe.add_details(recipe)
                    update_recipe.save()
                    #create entry in RecipeDiscipline table
                    new_recipeflag = RecipeDiscipline(for_recipe=update_recipe)
                    new_recipeflag.add_details(recipe['disciplines'])
                    new_recipeflag.save()
                    #create entries in RecipeIngredient table
                    for ingredient in recipe['ingredients']:
                        recipe_ingredient = RecipeIngredient(for_recipe=update_recipe)
                        recipe_ingredient.add_details(ingredient)
                        recipe_ingredient.save()
                total_updated += num_found_recipes
        else:
            processing = False
    context['total_recipes_updated'] = total_updated
    return render(request, 'commerce/update.html', context)