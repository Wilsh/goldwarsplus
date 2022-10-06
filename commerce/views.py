from django.http import HttpResponse
from django.shortcuts import render, get_object_or_404
from django.urls import reverse
from django.utils import timezone
from django.views import generic
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError
import json
from django.contrib.auth.decorators import login_required
from django.views.generic.base import TemplateView
import random

#from commerce.forms import UpdateForm
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
        return EconomicsForRecipe.objects.exclude(fast_crafting_profit__lte=0).exclude(limited_production=True).order_by('-fast_crafting_profit')

class CraftingProfitDelayListView(generic.ListView):
    model = EconomicsForRecipe
    template_name = 'commerce/craftingprofitdelay_list.html'
    context_object_name = 'recipe_list'
    paginate_by = 20
    
    def get_queryset(self):
        return EconomicsForRecipe.objects.exclude(delayed_crafting_profit__lte=0).exclude(limited_production=True).order_by('-delayed_crafting_profit')
        
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

