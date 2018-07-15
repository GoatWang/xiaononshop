from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('order_create', views.order_create, name='order_create'),
    path('callback', views.callback, name='callback'),
]