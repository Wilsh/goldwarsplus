from django.http import HttpResponse
from django.utils import timezone
from django.views import generic
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError
import requests
import json
from django.views.generic.base import TemplateView
import random

from .models import Item, ItemFlag, EconomicsForItem, Icon, Recipe, EconomicsForRecipe, RecipeDiscipline, RecipeIngredient, BuyListing, SellListing

# Create your views here.
def index(request):
    return HttpResponse("It works")

class HomeView(TemplateView):
    template_name = 'commerce/home.html'
    
    def get_context_data(self, **kwargs):
        context = super(HomeView, self).get_context_data(**kwargs)
        #get a random item
        id_list = Item.objects.values_list('item_id', flat=True)
        context['item_info'] = Item.objects.filter(item_id=random.choice(id_list))[0]
        #get item and recipe count
        context['count'] = [Item.objects.count(), Recipe.objects.count()]
        return context

class PriceChangeView(generic.ListView):
    model = EconomicsForItem
    template_name = 'commerce/pricechange_list.html'
    context_object_name = 'item_list'
    paginate_by = 100
    
    def get_queryset(self):
        return EconomicsForItem.objects.order_by('-price_change_count')

class ItemListView(generic.ListView):
    model = Item
    template_name = 'commerce/item_list.html'
    context_object_name = 'item_list'
    paginate_by = 18

class ItemDetailView(generic.DetailView):
    model = Item
    template_name = 'commerce/item_detail.html'
    context_object_name = 'item_info'

class RecipeListView(generic.ListView):
    model = Recipe
    template_name = 'commerce/recipe_list.html'
    context_object_name = 'recipe_list'
    paginate_by = 18

class RecipeDetailView(generic.DetailView):
    model = Recipe
    template_name = 'commerce/recipe_detail.html'
    context_object_name = 'recipe_info'

class CraftingProfitListView(generic.ListView):
    model = EconomicsForRecipe
    template_name = 'commerce/craftingprofit_list.html'
    context_object_name = 'recipe_list'
    paginate_by = 18
    
    def get_queryset(self):
        #Sanity check required due to lag between updating Trading Post prices and calculation of profits.
        #This avoids a situation where the "Profit" data is out of date but "Sell For" is accurate.
        base_queryset = EconomicsForRecipe.objects.filter(fast_crafting_profit__range=(1,500000)).exclude(limited_production=True).order_by('-fast_crafting_profit')[:30]
        for economics in base_queryset:
            profit = int((economics.for_recipe.output_item_id.get_market_sell() * 0.85) - economics.ingredient_cost)
            if profit != economics.fast_crafting_profit:
                economics.fast_crafting_profit = profit
                economics.save()
        
        return EconomicsForRecipe.objects.filter(fast_crafting_profit__range=(1,500000)).exclude(limited_production=True).order_by('-fast_crafting_profit')

class CraftingProfitDelayListView(generic.ListView):
    model = EconomicsForRecipe
    template_name = 'commerce/craftingprofitdelay_list.html'
    context_object_name = 'recipe_list'
    paginate_by = 18
    
    def get_queryset(self):
        return EconomicsForRecipe.objects.filter(delayed_crafting_profit__range=(1,200000)).exclude(limited_production=True).order_by('-delayed_crafting_profit')
        #return EconomicsForRecipe.objects.exclude(delayed_crafting_profit__lte=0).exclude(limited_production=True).order_by('-delayed_crafting_profit')

class CustomCraftingProfitDelayListView(generic.ListView):
    model = EconomicsForRecipe
    template_name = 'commerce/customcraftingprofitdelay_list.html'
    context_object_name = 'recipe_list'
    
    def get_queryset(self):
        a = EconomicsForRecipe.objects.filter(for_recipe__output_item_id__name__icontains='viper').exclude(delayed_crafting_profit__lte=20000)
        b = EconomicsForRecipe.objects.filter(for_recipe__output_item_id__name__icontains='minstrel').exclude(delayed_crafting_profit__lte=20000)
        c = EconomicsForRecipe.objects.filter(for_recipe__output_item_id__name__icontains='trailblazer').exclude(delayed_crafting_profit__lte=20000)
        d = EconomicsForRecipe.objects.filter(for_recipe__output_item_id__name__icontains='sinister').exclude(delayed_crafting_profit__lte=20000)
        e = EconomicsForRecipe.objects.filter(for_recipe__output_item_id__name__icontains='marauder').exclude(delayed_crafting_profit__lte=20000)
        f = EconomicsForRecipe.objects.filter(for_recipe__output_item_id__name__icontains='relic').exclude(delayed_crafting_profit__lte=20000)
        return a.union(b, c, d, e, f).order_by('-delayed_crafting_profit')
    
    def get_context_data(self, **kwargs):
        context = super(CustomCraftingProfitDelayListView, self).get_context_data(**kwargs)
        #get TP listed items using API key
        API_KEY = 'BFB61861-2731-2643-A6CB-8AFD679021DF57D52DBC-E62F-4BEE-A25F-C0DF639C7FDD'
        base_url = 'https://api.guildwars2.com'
        url = base_url + '/v2/commerce/transactions/current/sells?page_size=200'
        headers = {'Authorization': 'Bearer ' + API_KEY}
        context['api_error'] = ''
        sell_list = {}
        while True:
            try:
                response = requests.get(url, headers=headers)
                response.raise_for_status()
            except requests.exceptions.HTTPError as e:
                context['api_error'] = e
            except requests.exceptions.ConnectionError as e:
                context['api_error'] = e
            except requests.exceptions.ConnectTimeout as e:
                context['api_error'] = e
            except requests.exceptions.RequestException as e:
                context['api_error'] = 'generic connection error'
            else:
                try:
                    listed = response.json()
                except requests.exceptions.JSONDecodeError as e:
                    context['api_error'] = 'json decode error'
                except Exception as e:
                    context['api_error'] = 'generic exception in JSON decode'
                else:
                    for item in listed:
                        try:
                            if sell_list[item['item_id']] > item['price']:
                                sell_list[item['item_id']] = item['price']
                            else:
                                continue
                        except KeyError:
                            sell_list[item['item_id']] = item['price']
                if response.links['self']['url'] == response.links['last']['url']:
                    break
                url = base_url + response.links['next']['url']
            finally:
                if context['api_error']:
                    break
        if sell_list:
            context['listed'] = sell_list
        return context

class CustomCraftingProfitDelayListView2(CustomCraftingProfitDelayListView):
    model = EconomicsForRecipe
    template_name = 'commerce/customcraftingprofitdelay_list.html'
    context_object_name = 'recipe_list'
    #paginate_by = 200
    
    def get_queryset(self):
        a = EconomicsForRecipe.objects.filter(for_recipe__output_item_id__name__icontains='zealot').exclude(delayed_crafting_profit__lte=30000).exclude(delayed_crafting_profit__gte=60000)
        b = EconomicsForRecipe.objects.filter(for_recipe__output_item_id__name__icontains='soldier').exclude(delayed_crafting_profit__lte=30000).exclude(delayed_crafting_profit__gte=60000)
        c = EconomicsForRecipe.objects.filter(for_recipe__output_item_id__name__icontains='commander').exclude(delayed_crafting_profit__lte=30000).exclude(delayed_crafting_profit__gte=60000)
        d = EconomicsForRecipe.objects.filter(for_recipe__output_item_id__name__icontains='rampager').exclude(delayed_crafting_profit__lte=30000).exclude(delayed_crafting_profit__gte=60000).exclude(for_recipe__output_item_id__name__icontains='box of')
        e = EconomicsForRecipe.objects.filter(for_recipe__output_item_id__name__icontains='assassin').exclude(delayed_crafting_profit__lte=30000).exclude(delayed_crafting_profit__gte=60000).exclude(for_recipe__output_item_id__name__icontains='satchel of')
        f = EconomicsForRecipe.objects.filter(for_recipe__output_item_id__name__icontains='knight').exclude(delayed_crafting_profit__lte=30000).exclude(delayed_crafting_profit__gte=60000).exclude(for_recipe__output_item_id__name__icontains='box of').exclude(for_recipe__output_item_id__name__icontains='satchel of')
        g = EconomicsForRecipe.objects.filter(for_recipe__output_item_id__name__icontains='valkyrie').exclude(delayed_crafting_profit__lte=30000).exclude(delayed_crafting_profit__gte=60000)
        h = EconomicsForRecipe.objects.filter(for_recipe__output_item_id__name__icontains='cleric').exclude(delayed_crafting_profit__lte=30000).exclude(delayed_crafting_profit__gte=60000).exclude(for_recipe__output_item_id__name__icontains='box of')
        i = EconomicsForRecipe.objects.filter(for_recipe__output_item_id__name__icontains='nomad').exclude(delayed_crafting_profit__lte=30000).exclude(delayed_crafting_profit__gte=60000)
        j = EconomicsForRecipe.objects.filter(for_recipe__output_item_id__name__icontains='sentinel').exclude(delayed_crafting_profit__lte=30000).exclude(delayed_crafting_profit__gte=60000)
        k = EconomicsForRecipe.objects.filter(for_recipe__output_item_id__name__icontains='giver').exclude(delayed_crafting_profit__lte=30000).exclude(delayed_crafting_profit__gte=60000).exclude(for_recipe__output_item_id__name__icontains='box of')
        l = EconomicsForRecipe.objects.filter(for_recipe__output_item_id__name__icontains='carrion').exclude(delayed_crafting_profit__lte=30000).exclude(delayed_crafting_profit__gte=60000)
        m = EconomicsForRecipe.objects.filter(for_recipe__output_item_id__name__icontains='bringer').exclude(delayed_crafting_profit__lte=30000).exclude(delayed_crafting_profit__gte=60000)
        n = EconomicsForRecipe.objects.filter(for_recipe__output_item_id__name__icontains="dragon's").exclude(delayed_crafting_profit__lte=30000).exclude(delayed_crafting_profit__gte=60000)
        return a.union(b,c,d,e,f,g,h,i,j,k,l,m,n).order_by('-delayed_crafting_profit')
        #d = EconomicsForRecipe.objects.filter(for_recipe__output_item_id__name__icontains='sinister')
        #return d.order_by('-delayed_crafting_profit')
        
class TestListView(generic.ListView):
    model = EconomicsForRecipe
    template_name = 'commerce/test_list.html'
    context_object_name = 'recipe_list'
    paginate_by = 200
    
    def get_queryset(self):
        #a = EconomicsForRecipe.objects.filter(for_recipe__output_item_id__name__icontains='viper').exclude(delayed_crafting_profit__lte=9000)
        #b = EconomicsForRecipe.objects.filter(for_recipe__output_item_id__name__icontains='minstrel').exclude(delayed_crafting_profit__lte=10000)
        #c = EconomicsForRecipe.objects.filter(for_recipe__output_item_id__name__icontains='trailblazer').exclude(delayed_crafting_profit__lte=10000)
        d = EconomicsForRecipe.objects.filter(for_recipe__output_item_id__name__icontains='sinister').exclude(delayed_crafting_profit__lte=10000)
        #e = EconomicsForRecipe.objects.filter(for_recipe__output_item_id__name__icontains='marauder').exclude(delayed_crafting_profit__lte=9000)
        #valkyrie zealot soldier commander marauder dragon's rampager assassin knight nomad sentinel giver carrion cleric bringer
        #return a.union(b, c, d, e).order_by('-delayed_crafting_profit')
        #d = EconomicsForRecipe.objects.filter(for_recipe__output_item_id__name__icontains='sinister')
        return d.order_by('-delayed_crafting_profit')
    
    def get_context_data(self, **kwargs):
        context = super(TestListView, self).get_context_data(**kwargs)
        #get TP listed items using API key
        API_KEY = 'BFB61861-2731-2643-A6CB-8AFD679021DF57D52DBC-E62F-4BEE-A25F-C0DF639C7FDD'
        base_url = 'https://api.guildwars2.com'
        url = base_url + '/v2/commerce/transactions/current/sells?page_size=200'
        headers = {'Authorization': 'Bearer ' + API_KEY}
        context['api_error'] = 'test'
        '''sell_list = {}
        while True:
            try:
                response = requests.get(url, headers=headers)
                response.raise_for_status()
            #except requests.HTTPError as e:
                #context['api_error'] = e
            #except requests.RequestException as e:
                #context['api_error'] = e
            except HTTPError as e:
                context['api_error'] = e
            except URLError as e:
                context['api_error'] = e.reason
            except Exception as e:
                context['api_error'] = 'connection error: ' + e.reason
            else:
                try:
                    listed = response.json()
                except Exception as e:
                    context['api_error'] = 'json decode error: ' + e.reason
                else:
                    for item in listed:
                        try:
                            if sell_list[item['item_id']] > item['price']:
                                sell_list[item['item_id']] = item['price']
                            else:
                                continue
                        except KeyError:
                            sell_list[item['item_id']] = item['price']
                if response.links['self']['url'] == response.links['last']['url']:
                    break
                url = base_url + response.links['next']['url']
        if sell_list:
            context['listed'] = sell_list'''
        return context

class LimitedProductionListView(generic.ListView):
    model = EconomicsForRecipe
    template_name = 'commerce/limitedproduction_list.html'
    context_object_name = 'recipe_list'
    paginate_by = 18
    
    def get_queryset(self):
        return EconomicsForRecipe.objects.exclude(limited_production_profit_ratio__lte=0).exclude(limited_production=False).order_by('-limited_production_profit_ratio')

class RelistListView(generic.ListView):
    model = EconomicsForItem
    ordering = '-relist_profit'
    template_name = 'commerce/relist_list.html'
    context_object_name = 'item_list'
    paginate_by = 20
    
    def get_queryset(self):
        return EconomicsForItem.objects.exclude(relist_profit=0).order_by('-relist_profit')

