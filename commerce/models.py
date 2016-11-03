from django.db import models
from django.utils import timezone
from urllib.request import urlretrieve
import hashlib
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
    can_purchase_from_vendor = models.BooleanField(default=False)
    vendor_price = models.PositiveIntegerField(default=0)
    date_added = models.DateTimeField()
    
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
        self.date_added = timezone.now()
    
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
            purchase_price = 9999999999
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
            recipe_name_list.append([recipe.output_item_id, recipe.output_item_id.name])
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
        cheapest_price = 9999999999
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
    '''Economic data applying to an Item that can be found on the trading post'''
    for_item = models.OneToOneField('Item', on_delete=models.CASCADE)
    price_change_count = models.PositiveIntegerField(default=0)
    relist_profit = models.PositiveIntegerField(default=0)
    
    def __str__(self):
        return "Economic data for Item " + str(self.for_item.item_id) + ": " + self.for_item.name

class Icon(models.Model):
    '''Icons used for Items'''
    url = models.CharField(primary_key=True, max_length=120)
    static_id = models.CharField(max_length=36, default='unknown.png')
    
    def __str__(self):
        return "Icon for Items " + self.static_id
    
    def add_details(self):
        self.static_id = hashlib.md5(self.url.encode('utf-8')).hexdigest()
        self.static_id += '.png'
        #TODO: avoid using an absolute path
        urlretrieve(self.url, '/home/turbobear/goldwarsplus/commerce/static/commerce/items/' + self.static_id)

class Recipe(models.Model):
    '''All recipes for craftable Items discovered by
    players in the game'''
    recipe_id = models.PositiveIntegerField(primary_key=True)
    type = models.CharField(max_length=30, default='')
    output_item_id = models.ForeignKey('Item', on_delete=models.CASCADE)
    output_item_count = models.PositiveSmallIntegerField(default=0)
    min_rating = models.PositiveSmallIntegerField(default=0)
    AutoLearned = models.BooleanField(default=False)
    LearnedFromItem = models.BooleanField(default=False)
    date_added = models.DateTimeField()
    
    class Meta:
        ordering = ["-date_added"]
    
    def __str__(self):
        return "Recipe for item " + str(self.output_item_id.item_id) + ": " + self.output_item_id.name
    
    def add_details(self, recipedetails):
        self.recipe_id = recipedetails['id']
        self.type = recipedetails['type']
        self.output_item_count = recipedetails['output_item_count']
        self.min_rating = recipedetails['min_rating']
        for entry in recipedetails['flags']:
            setattr(self, entry, True)
        self.date_added = timezone.now()

class EconomicsForRecipe(models.Model):
    '''Economic data applying to a Recipe'''
    for_recipe = models.OneToOneField('Recipe', on_delete=models.CASCADE)
    limited_production = models.BooleanField(default=False)
    ingredient_cost = models.PositiveIntegerField(default=0)
    fast_crafting_profit = models.IntegerField(default=0)
    delayed_crafting_profit = models.IntegerField(default=0)
    
    def __str__(self):
        return "Economic data for Recipe " + str(self.for_recipe.recipe_id) + ": " + self.for_recipe.output_item_id.name

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

