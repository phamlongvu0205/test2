from django.urls import path
from . import views

urlpatterns = [
    path('', views.get_stock_data),
    path('gold/', views.gold),  
    path('financial-statement/', views.financial_statement),
    path('exchange-rate/', views.forex),
]
