from django.urls import path
from . import views


app_name = 'order'
urlpatterns = [
    path('', views.index, name='index'),
    path('order_create/<str:line_id>/', views.order_create, name='order_create'),
    path('callback/', views.callback, name='callback'),
]