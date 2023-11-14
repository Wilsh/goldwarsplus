from django.conf.urls import url
from . import views

app_name = 'commerce'
urlpatterns = [
    #url(r'^$', views.index, name='index'),
    url(r'^$', views.HomeView.as_view(), name='home'),
    url(r'^items/$', views.ItemListView.as_view(), name='item_list'),
    url(r'^items/detail/(?P<pk>[0-9]+)/$', views.ItemDetailView.as_view(), name='item_detail'),
    url(r'^recipes/$', views.RecipeListView.as_view(), name='recipe_list'),
    url(r'^recipes/detail/(?P<pk>[0-9]+)/$', views.RecipeDetailView.as_view(), name='recipe_detail'),
    url(r'^crafting/$', views.CraftingProfitListView.as_view(), name='craftingprofit_list'),
    url(r'^crafting/max/$', views.CraftingProfitDelayListView.as_view(), name='craftingprofitdelay_list'),
    url(r'^crafting/limited/$', views.LimitedProductionListView.as_view(), name='limitedproduction_list'),
    url(r'^relist/$', views.RelistListView.as_view(), name='relist_list'),
    url(r'^pricechange/$', views.PriceChangeView.as_view(), name='pricechange_list'),
    url(r'^crafting/custom/$', views.CustomCraftingProfitDelayListView.as_view(), name='customcraftingprofitdelay_list'),
    url(r'^crafting/test/$', views.TestListView.as_view(), name='test_list'),
]