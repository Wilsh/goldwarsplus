from django.http import HttpResponse
from django.shortcuts import render, get_object_or_404
from django.urls import reverse
from django.utils import timezone
from django.views import generic
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError
import json

from commerce.forms import UpdateForm
from .models import Item, ItemFlag, EconomicsForItem, Icon, Recipe, EconomicsForRecipe, RecipeDiscipline, RecipeIngredient, BuyListing, SellListing

# Create your views here.
def index(request):
    return HttpResponse("It works")

class ItemListView(generic.ListView):
    model = Item
    template_name = 'commerce/item_list.html'
    context_object_name = 'item_list'
    paginate_by = 20

class ItemDetailView(generic.DetailView):
    model = Item
    template_name = 'commerce/item_detail.html'
    context_object_name = 'item_info'

class RecipeListView(generic.ListView):
    model = Recipe
    template_name = 'commerce/recipe_list.html'
    context_object_name = 'recipe_list'
    paginate_by = 20

class RecipeDetailView(generic.DetailView):
    model = Recipe
    template_name = 'commerce/recipe_detail.html'
    context_object_name = 'recipe_info'

class CraftingProfitListView(generic.ListView):
    model = EconomicsForRecipe
    template_name = 'commerce/craftingprofit_list.html'
    context_object_name = 'recipe_list'
    paginate_by = 20
    
    def get_queryset(self):
        return EconomicsForRecipe.objects.exclude(fast_crafting_profit=0).order_by('-fast_crafting_profit')

class CraftingProfitDelayListView(generic.ListView):
    model = EconomicsForRecipe
    template_name = 'commerce/craftingprofitdelay_list.html'
    context_object_name = 'recipe_list'
    paginate_by = 20
    
    def get_queryset(self):
        return EconomicsForRecipe.objects.exclude(delayed_crafting_profit=0).order_by('-delayed_crafting_profit')

class RelistListView(generic.ListView):
    model = EconomicsForItem
    ordering = '-relist_profit'
    template_name = 'commerce/relist_list.html'
    context_object_name = 'item_list'
    paginate_by = 20
    
    def get_queryset(self):
        return EconomicsForItem.objects.exclude(relist_profit=0).order_by('-relist_profit')

class UpdateForm(generic.edit.FormView):
    template_name = 'commerce/update.html'
    form_class = UpdateForm
    success_url = 'commerce/update.html'
    
    def get(self, request):
        context = self.get_context_data()
        context['num_items'] = Item.objects.count()
        context['num_recipes'] = Recipe.objects.count()
        return render(self.request, 'commerce/update.html', context)

    def form_valid(self, form):
        context = self.get_context_data()
        self.get_api_objects(form.cleaned_data['action'], context)
        context['num_items'] = Item.objects.count()
        context['num_recipes'] = Recipe.objects.count()
        return render(self.request, 'commerce/update.html', context)
    
    def get_api_data(self, url_postfix, context):
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
        
    def get_api_objects(self, api_endpoint, context):
        '''Retrieve a list of ids from the specified API endpoint then 
        add any missing objects to their corresponding table'''
        if api_endpoint != 'items' and api_endpoint != 'recipes':
            context['api_error'] = 'Invalid api_endpoint value'
            return
        object_id_list = self.get_api_data(api_endpoint, context)
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
                object_details = self.get_api_data(end_url, context)
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
                            context['api_error'] = 'Create Recipe ' + str(object['id']) + ' failed: related Item does not exist'
                            #return
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
                                context['api_error'] = 'Create RecipeIngredient ' + str(object['id']) + ' failed: related Item does not exist'
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

