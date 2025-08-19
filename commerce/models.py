from django.db import models
from django.utils import timezone
from urllib.request import urlretrieve
import hashlib
import os
from django.conf import settings
from math import ceil

# Create your models here.
class Item(models.Model):
    '''All items discovered by players in the game'''
    item_id = models.PositiveIntegerField(primary_key=True)
    chat_link = models.CharField(max_length=120, default='')
    name = models.CharField(max_length=200, default='[no name provided]')
    icon = models.ForeignKey('Icon', on_delete=models.CASCADE)
    description = models.TextField(default='No description provided')
    type = models.CharField(max_length=20, default='')
    rarity = models.CharField(max_length=10, default='')
    level = models.PositiveSmallIntegerField(default=0)
    vendor_value = models.PositiveIntegerField(default=0)
    seen_on_trading_post = models.BooleanField(default=False)
    can_be_crafted = models.BooleanField(default=False)
    historically_profitable = models.BooleanField(default=False)
    can_purchase_from_vendor = models.BooleanField(default=False)
    vendor_price = models.PositiveIntegerField(default=0)
    date_added = models.DateTimeField(auto_now_add=True)
    crafting_meta_level = models.IntegerField(default=-1)
    
    class Meta:
        ordering = ["-date_added"]

    def __str__(self):
        return "Item " + str(self.item_id) + ": " + self.name
    
    def add_details(self, itemdetails):
        self.item_id = itemdetails['id']
        self.chat_link = itemdetails['chat_link']
        if itemdetails['name'] != '':
            self.name = itemdetails['name']
        try:
            if itemdetails['description'] != '':
                self.description = itemdetails['description']
        except KeyError:
            pass
        self.type = itemdetails['type']
        self.rarity = itemdetails['rarity']
        self.level = itemdetails['level']
        self.vendor_value = itemdetails['vendor_value']
    
    def get_meta_level(self, depth=0):
        '''Calculate the maximum depth of recipe traversal necessary to craft this item'''
        recipes = self.recipe_set.all()
        if recipes.count() == 0:
            return depth
        max = 0
        for recipe in recipes:
            branch_max = 0
            for ingredient in recipe.recipeingredient_set.all():
                count = ingredient.item_id.get_meta_level(depth+1)
                if count > branch_max:
                    branch_max = count
            if branch_max > max:
                max = branch_max
        return max
    
    def get_market_buy(self, quantity=1):
        '''Return the cost of the quantity of this item if bought on the trading post'''
        sell_orders = self.selllisting_set.all().order_by('unit_price')
        total = 0
        count = 0
        for order in sell_orders:
            if (order.quantity + count) < quantity:
                count += order.quantity
                total += order.quantity * order.unit_price
            else:
                total += (quantity - count) * order.unit_price
                return total
        #quantity not available
        return 0
    
    def get_market_sell(self):
        '''Return the value of this item if sold immediately on the trading post'''
        buy_order = self.buylisting_set.order_by('-unit_price').first()
        return buy_order.unit_price if buy_order else 0
    
    def get_market_delay_sell(self):
        '''Return the value of this item if sold one copper below the lowest current 
        selling price on the trading post. Returns 0 if none of these items are listed'''
        sell_order = self.selllisting_set.order_by('unit_price').first()
        return sell_order.unit_price - 1 if sell_order else 0
    
    def buy_or_craft(self, quantity=1):
        '''Return the cheapest method to obtain this Item as a nested list of 
        Items designated as 'buy' or 'craft' depending upon whether it is cheaper 
        to buy that Item on the trading post or craft the Item after buying its 
        base components'''
        purchase_price = self.get_market_buy(quantity)
        if purchase_price == 0: #not available
            purchase_price = 999999999
        if not self.can_be_crafted:
            return ['buy', purchase_price, quantity, [self.item_id, self.name]]
        recipe_id_list = []
        recipe_name_list = []
        cheapest_recipe_idx = 0
        ingredient_list = []
        crafting_price = 0
        num_recipes = 0
        for recipe in self.recipe_set.all():
            ingredient_sublist = []
            recipe_id_list.append(recipe.recipe_id)
            recipe_name_list.append([recipe.output_item_id.item_id, recipe.output_item_id.name])
            for ingredient in recipe.recipeingredient_set.all():
                should_buy = ingredient.item_id.buy_or_craft(ceil(ingredient.count / recipe.output_item_count))
                if should_buy[0] == 'buy':
                    cost_multiplier = 1
                else:
                    cost_multiplier = ceil(ingredient.count / recipe.output_item_count)
                ingredient_sublist.append([should_buy, cost_multiplier])
            ingredient_list.append(ingredient_sublist)
            num_recipes += 1
        if num_recipes > 1:
            ingredient_list, cheapest_recipe_idx, crafting_price = self.get_cheapest_recipe(ingredient_list)
        else:
            ingredient_list = ingredient_list[0]
            for ingredient, count in ingredient_list:
                crafting_price += self.get_component_cost(ingredient, count)
        if crafting_price < purchase_price:
            return ['craft', crafting_price, quantity, ingredient_list, recipe_name_list[cheapest_recipe_idx], recipe_id_list[cheapest_recipe_idx]]
        else:
            return ['buy', purchase_price, quantity, [self.item_id, self.name]]
    
    def get_cheapest_recipe(self, recipe_list):
        '''Given a list of lists of ingredients for multiple Recipes, return 
        the list of Recipe ingredients that are the cheapest to obtain along
        with the index of the recipe_list containing the cheapest ingredients
        and the total cost of those ingredients.
        Intended for Items that can be crafted by more than one Recipe'''
        cheapest_idx = 0
        current_idx = 0
        cheapest_price = 999999999
        for ingredient_list in recipe_list:
            crafting_price = 0
            for ingredient, count in ingredient_list:
                crafting_price += self.get_component_cost(ingredient, count)
            if crafting_price < cheapest_price:
                cheapest_price = crafting_price
                cheapest_idx = current_idx
            current_idx += 1
        return (recipe_list[cheapest_idx], cheapest_idx, cheapest_price)
    
    def get_component_cost(self, list, num_items):
        '''Return the cost of an Item in a list instantiated by buy_or_craft'''
        cost = 0
        if list[0] == 'buy' or list[0] == 'craft':
            cost = list[1] * num_items
        return cost

class ItemFlag(models.Model):
    '''Flags applying to an Item'''
    for_item = models.OneToOneField('Item', on_delete=models.CASCADE)
    AccountBindOnUse = models.BooleanField(default=False)
    AccountBound = models.BooleanField(default=False)
    HideSuffix = models.BooleanField(default=False)
    MonsterOnly = models.BooleanField(default=False)
    NoMysticForge = models.BooleanField(default=False)
    NoSalvage = models.BooleanField(default=False)
    NoSell = models.BooleanField(default=False)
    NotUpgradeable = models.BooleanField(default=False)
    NoUnderwater = models.BooleanField(default=False)
    SoulbindOnAcquire = models.BooleanField(default=False)
    SoulBindOnUse = models.BooleanField(default=False)
    Unique = models.BooleanField(default=False)
    
    class Meta:
        ordering = ["for_item"]
        
    def __str__(self):
        return "Flags for item " + str(self.for_item.item_id) + ": " + self.for_item.name
    
    def add_details(self, flaglist):
        for entry in flaglist:
            setattr(self, entry, True)

class EconomicsForItem(models.Model):
    '''Economic data applying to an Item that can be found on the trading post 
    or used as a RecipeIngredient'''
    for_item = models.OneToOneField('Item', on_delete=models.CASCADE)
    price_change_count = models.PositiveIntegerField(default=0)
    relist_profit = models.PositiveIntegerField(default=0)
    cheaper_by_crafting = models.BooleanField(default=False)
    cost_to_obtain = models.PositiveIntegerField(default=999999999)
    
    def __str__(self):
        return "Economic data for Item " + str(self.for_item.item_id) + ": " + self.for_item.name
    
    def set_cost_by_meta(self):
        '''Calculate the cost to obtain the related Item based on its immediate components and determine 
        whether it should be crafted or bought. This info is not saved automatically.
        This method differs from Item.buy_or_craft() in three important ways:
            1) it runs iteratively instead of recursively
            2) it requires up-to-date information for Items below this Item's meta level
            3) because of the bottom-up approach, crafting costs are calculated according 
                to the TP price of a single base Item; exact prices and availability of 
                RecipeIngredients are not guaranteed
        '''
        cheapest = 999999999
        recipe_id = 0
        buy_or_craft = 'buy'
        self.cheaper_by_crafting = False
        market_buy = self.for_item.get_market_buy()
        if self.for_item.crafting_meta_level == -1:
            #fix unknown crafting_meta_level but assume the related Item cannot be bought 
            #or crafted because condition 2) as above is not guaranteed
            new_meta = self.for_item
            new_meta.crafting_meta_level = new_meta.get_meta_level()
            new_meta.save()
            self.cost_to_obtain = cheapest
        elif self.for_item.crafting_meta_level == 0:
            #self.cost_to_obtain = market_buy if market_buy > 0 else cheapest
            return ('buy', market_buy if market_buy > 0 else cheapest)
        else:
            crafting_cost, recipe_id = self.get_crafting_cost_by_meta()
            if market_buy == 0:
                #cannot buy; just figure out if Item can be crafted
                self.cost_to_obtain = crafting_cost
                if crafting_cost < cheapest:
                    self.cheaper_by_crafting = True
                    buy_or_craft = 'craft'
            else:
                if crafting_cost < market_buy:
                    self.cheaper_by_crafting = True
                    buy_or_craft = 'craft'
                    self.cost_to_obtain = crafting_cost
                else:
                    self.cost_to_obtain = market_buy
        return (buy_or_craft, self.cost_to_obtain, recipe_id)
        
    def get_crafting_cost_by_meta(self):
        '''Return the lowest cost to craft this related Item. 
        Returns 999999999 if it cannot be crafted'''
        lowest = 999999999
        recipe_id = 0
        for recipe in self.for_item.recipe_set.all():
            branch_min = 0
            for ingredient in recipe.recipeingredient_set.all():
                item = ingredient.item_id
                if not item.seen_on_trading_post:
                    try:
                        item.economicsforitem
                    except Item.economicsforitem.RelatedObjectDoesNotExist:
                        new_economic_entry = EconomicsForItem(for_item=item)
                        new_economic_entry.save()
                #print(f"{item.item_id} {item.name} cost: {item.economicsforitem.cost_to_obtain} count: {ingredient.count}")
                if item.crafting_meta_level == 0:
                    cost = item.get_market_buy(ingredient.count)
                    if cost == 0: #get_market_buy returns 0 if unavailable
                        cost = 999999999
                else:
                    cost = item.economicsforitem.cost_to_obtain * ingredient.count
                branch_min += cost
            branch_min = int(branch_min / recipe.output_item_count)
            if branch_min < lowest:
                lowest = branch_min
                recipe_id = recipe.recipe_id
        #print(f"{self.for_item.item_id} {self.for_item.name} lowest: {lowest}")
        return (lowest, recipe_id)

class Icon(models.Model):
    '''Icons used for Items'''
    url = models.CharField(primary_key=True, max_length=120)
    static_id = models.CharField(max_length=36, default='unknown.png')
    
    def __str__(self):
        return "Icon for Items " + self.static_id
    
    def add_details(self):
        self.static_id = hashlib.md5(self.url.encode('utf-8')).hexdigest()
        self.static_id += '.png'
        urlretrieve(self.url, os.path.join(settings.BASE_DIR, 'commerce/static/commerce/items/') + self.static_id)

class Recipe(models.Model):
    '''All recipes for craftable Items discovered by
    players in the game'''
    recipe_id = models.PositiveIntegerField(primary_key=True)
    type = models.CharField(max_length=30, default='')
    output_item_id = models.ForeignKey('Item', on_delete=models.CASCADE) #TODO change field name to output_item
    output_item_count = models.PositiveSmallIntegerField(default=0)
    min_rating = models.PositiveSmallIntegerField(default=0)
    AutoLearned = models.BooleanField(default=False)
    LearnedFromItem = models.BooleanField(default=False)
    date_added = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ["-date_added"]
    
    def __str__(self):
        return "Recipe " + str(self.recipe_id) + " for item " + str(self.output_item_id.item_id) + ": " + self.output_item_id.name
    
    def add_details(self, recipedetails):
        self.recipe_id = recipedetails['id']
        self.type = recipedetails['type']
        self.output_item_count = recipedetails['output_item_count']
        self.min_rating = recipedetails['min_rating']
        for entry in recipedetails['flags']:
            setattr(self, entry, True)

class EconomicsForRecipe(models.Model):
    '''Economic data applying to a Recipe'''
    for_recipe = models.OneToOneField('Recipe', on_delete=models.CASCADE)
    limited_production = models.BooleanField(default=False)
    num_limited_production_items = models.PositiveSmallIntegerField(default=0)
    ingredient_cost = models.PositiveIntegerField(default=0)
    fast_crafting_profit = models.IntegerField(default=0)
    delayed_crafting_profit = models.IntegerField(default=0)
    limited_production_profit_ratio = models.IntegerField(default=0)
    
    def __str__(self):
        return "Economic data for Recipe " + str(self.for_recipe.recipe_id) + ": " + self.for_recipe.output_item_id.name
        
    def set_limited_production(self):
        '''Search for time-gated Items used in the production of the Recipe 
        linked to this EconomicsForRecipe. If any time-gated items are found,
        set self.limited_production = True. Called recursively for Items that
        can be crafted'''
        for ingredient in self.for_recipe.recipeingredient_set.all(): #RecipeIngredient
            item = ingredient.item_id #Item
            if item.can_be_crafted:
                for recipe in item.recipe_set.all(): #Recipe
                    if recipe.economicsforrecipe.limited_production or recipe.economicsforrecipe.set_limited_production():
                        self.limited_production = True
                        self.save()
                        return True
        return False
        
    def count_limited_production_items(self):
        '''Return the number of time-gated items used in the production of the Recipe 
        linked to this EconomicsForRecipe'''
        limited_items = ['Clay Pot', 'Grow Lamp', 'Plate of Meaty Plant Food', 'Plate of Piquant Plant Food',
                'Vial of Maize Balm', 'Glob of Elder Spirit Residue', 'Lump of Mithrillium', 
                'Spool of Silk Weaving Thread', 'Spool of Thick Elonian Cord', 'Heat Stone',
                'Dragon Hatchling Doll Adornments', 'Dragon Hatchling Doll Eye', 'Dragon Hatchling Doll Frame',
                'Dragon Hatchling Doll Hide', 'Gossamer Stuffing'
                ]
        if self.for_recipe.output_item_id.name in limited_items:
            return 1
        total = 0
        for ingredient in self.for_recipe.recipeingredient_set.all(): #RecipeIngredient
            item = ingredient.item_id #Item
            if item.can_be_crafted:
                if item.name in limited_items:
                    return ingredient.count
                #recipe_count = 0
                #old_recipe = None
                for recipe in item.recipe_set.all(): #Recipe
                    total += recipe.economicsforrecipe.count_limited_production_items() * ingredient.count
                    #recipe_count += 1
                    #if recipe_count > 1 and recipe.economicsforrecipe.limited_production:
                        #print("Potential issue with multiple recipes to create a single item: " + str(recipe.recipe_id) + " " + str(recipe.output_item_id.item_id) + " " + recipe.output_item_id.name)
                        #print("Previous: " + str(old_recipe.recipe_id) + " " + str(old_recipe.output_item_id.item_id) + " " + old_recipe.output_item_id.name)
                    #old_recipe = recipe
        return total

class RecipeDiscipline(models.Model):
    '''Discipline flags applying to a Recipe'''
    for_recipe = models.OneToOneField('Recipe', on_delete=models.CASCADE)
    Artificer = models.BooleanField(default=False)
    Armorsmith = models.BooleanField(default=False)
    Chef = models.BooleanField(default=False)
    Huntsman = models.BooleanField(default=False)
    Jeweler = models.BooleanField(default=False)
    Leatherworker = models.BooleanField(default=False)
    Tailor = models.BooleanField(default=False)
    Weaponsmith = models.BooleanField(default=False)
    Scribe = models.BooleanField(default=False)
    
    class Meta:
        ordering = ["for_recipe"]
    
    def __str__(self):
        return "Disciplines for recipe " + str(self.for_recipe.recipe_id) + ": " + self.for_recipe.output_item_id.name
    
    def add_details(self, disciplines):
        for entry in disciplines:
            setattr(self, entry, True)
    
    def get_disciplines(self):
        disciplines = []
        disciplines.append(['Artificer', self.Artificer])
        disciplines.append(['Armorsmith', self.Armorsmith])
        disciplines.append(['Chef', self.Chef])
        disciplines.append(['Huntsman', self.Huntsman])
        disciplines.append(['Jeweler', self.Jeweler])
        disciplines.append(['Leatherworker', self.Leatherworker])
        disciplines.append(['Tailor', self.Tailor])
        disciplines.append(['Weaponsmith', self.Weaponsmith])
        disciplines.append(['Scribe', self.Scribe])
        return disciplines
        
class RecipeIngredient(models.Model):
    '''An Item and its quantity required for a Recipe'''
    for_recipe = models.ForeignKey('Recipe', on_delete=models.CASCADE)
    item_id = models.ForeignKey('Item', on_delete=models.CASCADE)
    count = models.PositiveSmallIntegerField()
    
    class Meta:
        ordering = ["for_recipe"]
    
    def __str__(self):
        return "Ingredient for recipe " + str(self.for_recipe.recipe_id) + ": " + self.for_recipe.output_item_id.name
    
    def add_details(self, ingredient):
        self.count = ingredient['count']

class BuyListing(models.Model):
    '''A buy order for an Item listed on the trading post'''
    for_item = models.ForeignKey('Item', on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField()
    unit_price = models.PositiveIntegerField()
    date_added = models.DateTimeField()
    
    class Meta:
        ordering = ["-unit_price"]
    
    def __str__(self):
        return "Buy order for item " + str(self.for_item.item_id) + ": " + self.for_item.name + " at price: " + str(self.unit_price)
    
    def add_details(self, listing):
        self.quantity = listing['quantity']
        self.unit_price = listing['unit_price']
        self.date_added = timezone.now()

class SellListing(models.Model):
    '''A sell order for an Item listed on the trading post'''
    for_item = models.ForeignKey('Item', on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField()
    unit_price = models.PositiveIntegerField()
    date_added = models.DateTimeField()
    
    class Meta:
        ordering = ["unit_price"]
    
    def __str__(self):
        return "Sell order for item " + str(self.for_item.item_id) + ": " + self.for_item.name + " at price: " + str(self.unit_price)
    
    def add_details(self, listing):
        self.quantity = listing['quantity']
        self.unit_price = listing['unit_price']
        self.date_added = timezone.now()
