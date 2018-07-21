from django.urls import path
from . import views


app_name = 'order'
urlpatterns = [
    path('', views.index, name='index'),
    path('index/', views.index, name='index'),
    path('order_create/', views.order_create, name='order_create'),
    # path('order_create/<str:line_id>/', views.order_create, name='order_create'),
    path('order_create/<int:area_id>/<int:distribution_place_id>/', views.order_create, name='order_create'),
    path('order_list/<str:line_id>/', views.order_list, name='order_list'),
    path('line_login_callback/', views.line_login_callback, name='line_login_callback'),
    path('line_login_callback/<str:app_name>/<str:view_name>', views.line_login_callback, name='line_login_callback'),
    path('callback/', views.callback, name='callback'),
]