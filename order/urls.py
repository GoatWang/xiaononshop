from django.urls import path
from . import views


app_name = 'order'
urlpatterns = [
    path('', views.index, name='index'),
    path('index/', views.index, name='index'),
    path('order_create/', views.order_create, name='order_create'),
    path('order_create/<int:area_id>/<int:distribution_place_id>/', views.order_create, name='order_create'),

    path('order_list/', views.order_list, name='order_list'),
    path('order_delete/<int:order_id>/', views.order_delete, name='order_delete'),

    path('line_login_callback/<str:app_name>/<str:view_name>/', views.line_login_callback, name='line_login_callback'),

    # backend
    path('backend_main_view/', views.backend_main_view, name='backend_main_view'),
    path('backend_friend_list/', views.backend_friend_list, name='backend_friend_list'),
    path('backend_add_staff/<str:line_id>/', views.backend_add_staff, name='backend_add_staff'),
    path('backend_add_superuser/<str:line_id>/', views.backend_add_superuser, name='backend_add_superuser'),
    path('backend_delete_staff/<str:line_id>/', views.backend_delete_staff, name='backend_delete_staff'),
    path('backend_delete_superuser/<str:line_id>/', views.backend_delete_superuser, name='backend_delete_superuser'),
    path('backend_daily_output_order/<str:area_id>/', views.backend_daily_output_order, name='backend_daily_output_order'),
    path('backend_receive_order/<str:order_id>/', views.backend_receive_order, name='backend_receive_order'),
    path('backend_daily_ouput_stats/', views.backend_daily_ouput_stats, name='backend_daily_ouput_stats'),
    path('backend_tomorrow_ouput_stats/', views.backend_tomorrow_ouput_stats, name='backend_tomorrow_ouput_stats'),

    #bot
    path('callback/', views.callback, name='callback'),
]