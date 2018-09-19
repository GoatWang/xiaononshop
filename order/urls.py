from django.urls import path
from . import views


app_name = 'order'
urlpatterns = [
    path('', views.index, name='index'),
    path('index/', views.index, name='index'),
    path('areas/', views.show_areas, name='show_areas'),
    path('order_create/', views.order_create, name='order_create'),
    path('order_create/<int:area_id>/<int:distribution_place_id>/', views.order_create, name='order_create'),
    path('order_number_update/', views.realtime_update_bt_number, name='order_number_update'),
    
    path('order_list/', views.order_list, name='order_list'),
    path('order_delete/<int:order_id>/', views.order_delete, name='order_delete'),

    path('line_login_callback/<str:app_name>/<str:view_name>/', views.line_login_callback, name='line_login_callback'),
    path('login/',views.login, name = 'login'),
    path('logout/',views.logout,name = 'logout'),
    path('message/', views.message, name='message'),

    # backend
    path('backend_main_view/', views.backend_main_view, name='backend_main_view'),
    path('backend_friend_list/', views.backend_friend_list, name='backend_friend_list'),
    path('backend_add_staff/<str:line_id>/', views.backend_add_staff, name='backend_add_staff'),
    path('backend_add_superuser/<str:line_id>/', views.backend_add_superuser, name='backend_add_superuser'),
    path('backend_delete_staff/<str:line_id>/', views.backend_delete_staff, name='backend_delete_staff'),
    path('backend_delete_superuser/<str:line_id>/', views.backend_delete_superuser, name='backend_delete_superuser'),
    path('backend_daily_output_order/<str:area_id>/', views.backend_daily_output_order, name='backend_daily_output_order'),
    path('toggle_receive_bento/', views.toggle_receive_bento, name = 'toggle_receive_bento'),
    path('backend_receive_order/<str:order_id>/', views.backend_receive_order, name='backend_receive_order'),
    path('backend_daily_ouput_stats/<int:add_days>/', views.backend_daily_ouput_stats, name='backend_daily_ouput_stats'),
    path('backend_weekly_ouput_stats/<int:week>/', views.backend_weekly_ouput_stats, name='backend_weekly_ouput_stats'),
    path('backend_bento_transfer/<int:add_days>/', views.backend_bento_transfer,name = 'backend_bento_transfer'),
    path('backend_transfer_change/',views.backend_transfer_change, name = 'backend_transfer_change'),

    #bot
    path('callback/', views.callback, name='callback'),
]