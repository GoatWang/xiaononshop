from django.urls import path
from . import views


app_name = 'order'
urlpatterns = [
    path('', views.index, name='index'),
    path('order_create/', views.order_create, name='order_create'),
    # path('order_create/<str:line_id>/', views.order_create, name='order_create'),
    path('order_create/<int:area_id>/<int:distribution_place_id>', views.order_create, name='order_create'),
    path('line_login_callback/<str:callback_viewfun>', views.line_login_callback, name='line_login_callback'),
    path('callback/', views.callback, name='callback'),
]