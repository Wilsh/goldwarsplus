from django.contrib import admin
from .models import Item, ItemFlag, Icon, Recipe, RecipeDiscipline, RecipeIngredient, BuyListing, SellListing

# Register your models here.
admin.site.register(Item)
admin.site.register(ItemFlag)
admin.site.register(Icon)
admin.site.register(Recipe)
admin.site.register(RecipeDiscipline)
admin.site.register(RecipeIngredient)
admin.site.register(BuyListing)
admin.site.register(SellListing)
