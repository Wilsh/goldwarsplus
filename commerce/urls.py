from django.urls import path
from . import views

app_name = 'commerce'
urlpatterns = [
    #path('', views.index, name='index'),
    path('', views.HomeView.as_view(), name='home'),
    path('items/', views.ItemListView.as_view(), name='item_list'),
    path('items/detail/<int:pk>/', views.ItemDetailView.as_view(), name='item_detail'),
    path('recipes/', views.RecipeListView.as_view(), name='recipe_list'),
    path('recipes/detail/<int:pk>/', views.RecipeDetailView.as_view(), name='recipe_detail'),
    path('crafting/', views.CraftingProfitListView.as_view(), name='craftingprofit_list'),
    path('crafting/max/', views.CraftingProfitDelayListView.as_view(), name='craftingprofitdelay_list'),
    path('crafting/limited/', views.LimitedProductionListView.as_view(), name='limitedproduction_list'),
    path('relist/', views.RelistListView.as_view(), name='relist_list'),
    path('pricechange/', views.PriceChangeView.as_view(), name='pricechange_list'),
    path('crafting/custom/', views.CustomCraftingProfitDelayListView.as_view(), name='customcraftingprofitdelay_list'),
    path('crafting/test/', views.TestListView.as_view(), name='test_list'),
]