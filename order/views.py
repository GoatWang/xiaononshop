import numpy as np
from datetime import datetime, timedelta
import pandas as pd
from uuid import uuid4
from urllib.parse import parse_qs, urlparse
import requests
from base64 import urlsafe_b64decode
import re
import os

from django.shortcuts import render, redirect
from django.http import HttpResponse, HttpResponseBadRequest, HttpResponseForbidden, JsonResponse
from django.views.decorators.csrf import csrf_exempt, csrf_protect

from xiaonon import settings
from django.contrib.auth.models import User
from django.contrib import auth
from order.models import Job, LineProfile, BentoType, Bento, Area, DistributionPlace, AreaLimitation, Order
from order.utl import get_order_detail, parse_url_query_string, create_order, get_redirect_url, get_line_login_api_url, delete_order

from linebot import LineBotApi, WebhookParser ##, WebhookHanlder
from linebot.exceptions import InvalidSignatureError, LineBotApiError
from linebot.models import (
    MessageEvent, FollowEvent, PostbackEvent, UnfollowEvent,
    TextMessage, LocationMessage, 
    TextSendMessage, TemplateSendMessage,ImageSendMessage, StickerSendMessage,
    ButtonsTemplate, ConfirmTemplate, CarouselTemplate,
    PostbackTemplateAction, MessageTemplateAction, URITemplateAction,
    CarouselColumn
)
line_bot_api = LineBotApi(settings.LINE_CHANNEL_ACCESS_TOKEN)
parser = WebhookParser(settings.LINE_CHANNEL_SECRET)
from order.line_messages import get_area_reply_messages, get_distribution_place_reply_messages, get_order_list_reply

# ------------------------following are website----------------------------------------------
def index(request):
    return HttpResponse("Hello, world. You're at the polls index.")

def line_login_callback(request, app_name, view_name):
    post_data = {
        "grant_type": 'authorization_code',
        "code": request.GET['code'],
        "redirect_uri": get_redirect_url(request, "order/line_login_callback/" + app_name + "/" + view_name + "/"),
        "client_id": settings.LINE_LOGIN_CHANNEL_ID,
        "client_secret": settings.LINE_LOGIN_CHANNEL_SECRET,
    }
    headers = {
        "Content-Type":"application/x-www-form-urlencoded",
    }
    res = requests.post('https://api.line.me/oauth2/v2.1/token', data=post_data, headers=headers)

    line_login_profile_b64 = eval(res.text)['id_token']
    line_login_profile_b64_decoded = urlsafe_b64decode(line_login_profile_b64[:-38] + '============')
    line_login_profile = eval(re.findall(b'\{.+?\}', line_login_profile_b64_decoded)[1].decode())
    line_id = line_login_profile.get('sub')

    if LineProfile.objects.filter(line_id=line_id).count() == 0:
        user = User(username = line_id)
        user.save()
        line_profile = LineProfile(
            line_id = line_id,
            friend = False,
            user = user 
        )
        line_profile.save()

    user = LineProfile.objects.get(line_id=line_id).user
    auth.login(request, user)
    return redirect(get_redirect_url(request, app_name + "/" + view_name + "/"))

@csrf_exempt #TODO: add csrf protect
def order_create(request, area_id=1, distribution_place_id=1):
    if not request.user.is_authenticated:
        state =  uuid4().hex
        return redirect(get_line_login_api_url(request, state, 'order', 'order_create'))
    else:
        if request.method == "GET":
            areas = Area.objects.all()
            output_adps = [] # area and distributions
            selected_adp_option_text = ""
            for a in areas:
                distribution_places = DistributionPlace.objects.filter(area=a)
                for dp in distribution_places:
                    adp_dict = {
                        "option_text":a.area + "--" + dp.distribution_place,
                        "area_id":a.id,
                        "distribution_place_id":dp.id,
                    }
                    if area_id==a.id and distribution_place_id==dp.id:
                        adp_dict['selected'] = True  
                        selected_adp_option_text = a.area + "--" + dp.distribution_place
                    else:
                        adp_dict['selected'] = False
                    output_adps.append(adp_dict)

            available_bentos = AreaLimitation.objects.filter(area=area_id, bento__date__gt=datetime.now(), bento__date__lte=datetime.now()+timedelta(5), bento__ready=True).reverse().values('bento__id', 'bento__name', 'bento__date', 'bento__bento_type__bento_type', 'bento__cuisine', 'bento__photo', 'bento__price', 'remain')
            if len(available_bentos) == 0:
                message = "目前沒有便當供應，請開學後再來找我喔。"
                context = {
                    "title":"目前沒有便當供應",
                    "message": message
                    }
                # maybe directly redirect to order_list view
                return render(request, 'order/message.html', context)
            else:
                available_bentos = sorted(available_bentos, key=lambda x:x['remain'], reverse=True)
                # {'bento__id': 26, 
                # 'bento__name': '避風塘鮮雞', 'bento__bento_type__bento_type': '均衡吃飽飽', 'bento__cuisine': '洋菇青江菜、蒜酥馬鈴薯&地瓜、涼拌小黃瓜', 'bento__photo': 'bento_imgs/避風塘鮮雞_2018-06-22_a9ad7545a61545759f08a31569a89fad.png', 'bento__price': 120, 'remain': 100}]
                aws_url = "https://s3.amazonaws.com/xiaonon/"
                df_available_bentos = pd.DataFrame(available_bentos)
                df_available_bentos['id'] = df_available_bentos['bento__id']
                df_available_bentos['name'] = df_available_bentos['bento__name']
                df_available_bentos['date'] = df_available_bentos['bento__date'].apply(lambda x:str(x.month) + '/' + str(x.day))
                df_available_bentos['bento_type'] = df_available_bentos['bento__bento_type__bento_type']
                df_available_bentos['cuisine'] = df_available_bentos['bento__cuisine']
                df_available_bentos['photo'] = df_available_bentos['bento__photo'].apply(lambda x:aws_url + x)
                df_available_bentos['price'] = df_available_bentos['bento__price']
                df_available_bentos['remain'] = df_available_bentos['remain'].astype(str)
                df_available_bentos['select_range'] = df_available_bentos['remain'].apply(lambda x:list(range(0, 11)) if int(x)>=10 else list(range(0, int(x)+1)))

                df_available_bentos = df_available_bentos[["id", "name", 'date', "bento_type", "cuisine", "photo", "price", "remain", "select_range"]]
                df_available_bentos = df_available_bentos.sort_values(by=['date', 'bento_type'])
                available_bentos = df_available_bentos.T.to_dict().values()

                context = {
                    'title':'馬上訂購',
                    'apds':output_adps,
                    'selected_adp_option_text':selected_adp_option_text,
                    'available_bentos':available_bentos,
                    'user_phone':LineProfile.objects.get(user=request.user).phone
                }
                return render(request, 'order/order_create.html', context)
        if request.method == "POST":
            post_data = request.POST
            order_data = post_data['orderData']
            line_profile = LineProfile.objects.get(user=request.user)
            line_profile.phone = post_data['user_phone']
            line_profile.save()
            line_id = line_profile.line_id
            
            all_success = True
            for od in eval(order_data):
                bento_id = int(od['bento_id'])
                order_number = int(od['order_number'])
                area_id = int(od['area_id'])
                distribution_place_id = int(od['distribution_place_id'])
                #TODO: add price column
                success = create_order(line_id, bento_id, order_number, area_id, distribution_place_id)
                if not success: all_success=False
            
            if all_success: 
                res_message = "謝謝你選擇照顧這片土地也照顧自己，我們午餐時間見！\n若想查看或取消訂單，請直接點選'我的訂單'就可以囉！" #TODO: 回饋訂單查詢URL
            else: 
                res_message = "部分訂單因數量不足，請從新訂購。" #TODO: 回饋失敗部分

            line_bot_api.push_message(
                line_id,
                TextSendMessage(text=res_message)
            )
            return JsonResponse({"success":all_success, 'message':res_message})
            # return JsonResponse({"state":True})

def order_list(request):
    if not request.user.is_authenticated:
        state =  uuid4().hex
        return redirect(get_line_login_api_url(request, state, 'order', 'order_list'))
    else:
        user = request.user
        current_orders = list(Order.objects.filter(line_profile__user=user, delete_time=None, bento__date__gt=datetime.now()-timedelta(1)).values_list('id', 'number', 'price', 'bento__date', 'bento__name', 'bento__bento_type__bento_type', 'bento__cuisine', named=True).order_by('bento__date'))
        if len(current_orders) != 0:
            df_current_orders = pd.DataFrame(current_orders)
            df_current_orders['row_id'] = pd.Series(df_current_orders.index).apply(lambda x:x+1)
            df_current_orders['date'] = df_current_orders['bento__date'].apply(lambda x:str(x.month) + '/' + str(x.day))
            df_current_orders['name'] = df_current_orders['bento__name']
            df_current_orders['type'] = df_current_orders['bento__bento_type__bento_type']
            df_current_orders['number'] = df_current_orders['number']
            df_current_orders['cuisine'] = df_current_orders['bento__cuisine']
            df_current_orders['today'] = df_current_orders['bento__date'].apply(lambda x:x==datetime.now().date())
            df_current_orders = df_current_orders[['row_id', 'id','date','name','type', 'price','number','cuisine', 'today']]
            current_orders = df_current_orders.T.to_dict().values
        else:
            current_orders = []
            
        history_orders = list(Order.objects.filter(line_profile__user=user, bento__date__lt=datetime.now()).values_list('id', 'number', 'price', 'bento__date', 'bento__name', 'bento__bento_type__bento_type', 'bento__cuisine', named=True).order_by('bento__date').reverse()[:10])
        if len(history_orders) != 0:
            df_history_orders = pd.DataFrame(history_orders)
            df_history_orders['row_id'] = pd.Series(df_history_orders.index).apply(lambda x:x+1)
            df_history_orders['date'] = df_history_orders['bento__date'].apply(lambda x:str(x.month) + '/' + str(x.day))
            df_history_orders['name'] = df_history_orders['bento__name']
            df_history_orders['type'] = df_history_orders['bento__bento_type__bento_type']
            df_history_orders['number'] = df_history_orders['number']
            df_history_orders['cuisine'] = df_history_orders['bento__cuisine']
            df_history_orders = df_history_orders[['row_id', 'id','date','name','type', 'price','number','cuisine']]
            history_orders = df_history_orders.T.to_dict().values
        else:
            history_orders = []
            
        context = {
            "title":"查看訂單",
            "current_orders":current_orders,
            "history_orders":history_orders
        }
        return render(request, 'order/order_list.html', context)

def order_delete(request, order_id):
    line_id=LineProfile.objects.get(user=request.user).line_id
    message = delete_order(order_id, line_id)
    line_bot_api.push_message(
        line_id,
        TextSendMessage(text=message)
    )
    return redirect(get_redirect_url(request, 'order/order_list/'))


def backend_main_view(request):
    if not request.user.is_authenticated:
        state =  uuid4().hex
        return redirect(get_line_login_api_url(request, state, 'order', 'backend_friend_list'))
    else:
        if not request.user.is_staff:
            context = {
                "title":"您沒有查閱權限",
                "message": "此頁面必須具有員工身分方能查閱。"
                }
            return render(request, 'order/message.html', context)
        else:
            areas = Area.objects.all()
            context = {
                "title":"後臺主頁",
                "areas":areas
            }
            return render(request, 'order/backend_main_view.html', context)

def backend_friend_list(request):
    if not request.user.is_authenticated:
        state =  uuid4().hex
        return redirect(get_line_login_api_url(request, state, 'order', 'backend_friend_list'))
    else:
        if not request.user.is_superuser:
            context = {
                "title":"您沒有查閱權限",
                "message": "此頁面必須具有管理員身分方能查閱。"
                }
            return render(request, 'order/message.html', context)
        else:
            superuser_profile = LineProfile.objects.filter(user__is_superuser=True).values_list('line_id', 'line_name', 'line_picture_url', 'phone', named=True)
            df_superuser_profile = pd.DataFrame(list(superuser_profile))
            staff_profile = LineProfile.objects.filter(user__is_staff=True, user__is_superuser=False).values_list('line_id', 'line_name', 'line_picture_url', 'phone', named=True)
            df_staff_profile = pd.DataFrame(list(staff_profile))
            friend_profile = LineProfile.objects.filter(user__is_staff=False).values_list('line_id', 'line_name', 'line_picture_url', 'phone', named=True).order_by('create_time').reverse()[:10]
            df_friend_profile = pd.DataFrame(list(friend_profile))

            context = {
                "title":"好友清單",
                "superuser_profile":list(df_superuser_profile.T.to_dict().values()),
                "staff_profile":list(df_staff_profile.T.to_dict().values()),
                "friend_profile":list(df_friend_profile.T.to_dict().values())  
            }
            return render(request, 'order/backend_friend_list.html', context)

def backend_add_staff(request, line_id):
    if not request.user.is_authenticated:
        state =  uuid4().hex
        return redirect(get_line_login_api_url(request, state, 'order', 'backend_friend_list'))
    else:
        if not request.user.is_superuser:
            context = {
                "title":"您沒有查閱權限",
                "message": "此頁面必須具有管理員身分方能查閱。"
                }
            return render(request, 'order/message.html', context)
        else:
            user = LineProfile.objects.get(line_id=line_id).user
            user.is_staff = True
            user.save()
            return redirect(get_redirect_url(request, 'order/backend_friend_list/'))



def backend_add_superuser(request, line_id):
    if not request.user.is_authenticated:
        state =  uuid4().hex
        return redirect(get_line_login_api_url(request, state, 'order', 'backend_friend_list'))
    else:
        if not request.user.is_superuser:
            context = {
                "title":"您沒有查閱權限",
                "message": "此頁面必須具有管理員身分方能查閱。"
                }
            return render(request, 'order/message.html', context)
        else:
            user = LineProfile.objects.get(line_id=line_id).user
            user.is_staff = True
            user.is_superuser = True
            user.save()
            return redirect(get_redirect_url(request, 'order/backend_friend_list/'))

def backend_delete_staff(request, line_id):
    if not request.user.is_authenticated:
        state =  uuid4().hex
        return redirect(get_line_login_api_url(request, state, 'order', 'backend_friend_list'))
    else:
        if not request.user.is_superuser:
            context = {
                "title":"您沒有查閱權限",
                "message": "此頁面必須具有管理員身分方能查閱，"
                }
            return render(request, 'order/message.html', context)
        else:
            user = LineProfile.objects.get(line_id=line_id).user
            user.is_staff = False
            user.save()
            return redirect(get_redirect_url(request, 'order/backend_friend_list/'))

def backend_delete_superuser(request, line_id):
    if not request.user.is_authenticated:
        state =  uuid4().hex
        return redirect(get_line_login_api_url(request, state, 'order', 'backend_friend_list'))
    else:
        if not request.user.is_superuser:
            context = {
                "title":"您沒有查閱權限",
                "message": "此頁面必須具有管理員身分方能查閱。"
                }
            return render(request, 'order/message.html', context)
        else:
            user = LineProfile.objects.get(line_id=line_id).user
            user.is_superuser = False
            user.save()
            return redirect(get_redirect_url(request, 'order/backend_friend_list/'))





def backend_daily_output_order(request, area_id):
    if not request.user.is_authenticated:
        state =  uuid4().hex
        return redirect(get_line_login_api_url(request, state, 'order', 'backend_main_view'))
    else:
        if not request.user.is_staff:
            context = {
                "title":"您沒有查閱權限",
                "message": "此頁面必須具有員工身分方能查閱。"
                }
            return render(request, 'order/message.html', context)
        else:
            order_list = Order.objects.filter(bento__date=datetime.now(), area=area_id, delete_time=None).values_list('id', "line_profile__line_id", 'line_profile__line_name', 'line_profile__phone', 'bento__name', 'area__area', 'distribution_place__distribution_place', 'number', 'price', 'received', named=True).order_by("line_profile__line_name", "distribution_place__distribution_place", "bento__name")
            if order_list.count() != 0:
                df_order_list = pd.DataFrame(list(order_list))
                df_order_list['order_id'] = df_order_list['id']
                df_order_list['line_id'] = df_order_list['line_profile__line_id']
                df_order_list['line_name'] = df_order_list['line_profile__line_name']
                df_order_list['phone'] = df_order_list['line_profile__phone']
                df_order_list['phone_last3'] = df_order_list['line_profile__phone'].apply(lambda x:x[-3:])
                df_order_list['area'] = df_order_list['area__area']
                df_order_list['distribution_place'] = df_order_list['distribution_place__distribution_place']
                df_order_list['bento_name'] = df_order_list['bento__name']
                df_order_list['number'] = df_order_list['number']
                df_order_list['price'] = df_order_list['price']
                df_order_list = df_order_list[['order_id', 'line_id', 'line_name', 'phone', 'phone_last3', 'area', 'distribution_place', 'bento_name', 'number', 'price', 'received']]
                order_list = list(df_order_list.T.to_dict().values()).copy()

                df_order_list_group = df_order_list.groupby(['area', 'distribution_place', 'bento_name', 'received']).sum().reset_index()
                df_order_list_group_received = df_order_list_group.loc[df_order_list_group['received']==True]
                df_order_list_group_received.loc[:, 'received_number'] = df_order_list_group_received['number']
                df_order_list_group_remain = df_order_list_group.loc[df_order_list_group['received']==False]
                df_order_list_group_remain.loc[:, 'remain_number'] = df_order_list_group_remain['number']
                df_order_list_group = pd.merge(df_order_list_group_received, df_order_list_group_remain, on=['area', 'distribution_place', 'bento_name'])
                df_order_list_group = df_order_list_group[['area', 'distribution_place', 'bento_name', 'received_number', 'remain_number']]
                order_list_group = list(df_order_list_group.T.to_dict().values()).copy()
            else:
                order_list = []
                order_list_group = []
            area = Area.objects.get(id=area_id).area
            context ={
                "title": area + "當日訂單",
                "order_list":order_list,
                "order_list_group":order_list_group
            }
        return render(request, 'order/backend_daily_output_order.html', context)

def beckend_receive_order(request, order_id):
    if not request.user.is_authenticated:
        state =  uuid4().hex
        return redirect(get_line_login_api_url(request, state, 'order', 'backend_main_view'))
    else:
        if not request.user.is_staff:
            context = {
                "title":"您沒有查閱權限",
                "message": "此頁面必須具有員工身分方能查閱。"
                }
            return render(request, 'order/message.html', context)
        else:
            order = Order.objects.get(pk=order_id)
            order.received = True
            order.save()
            return JsonResponse({"message":"Success"})

def beckend_daily_ouput_stats(request):
    if not request.user.is_authenticated:
        state =  uuid4().hex
        return redirect(get_line_login_api_url(request, state, 'order', 'backend_main_view'))
    else:
        if not request.user.is_superuser:
            context = {
                "title":"您沒有查閱權限",
                "message": "此頁面必須具有管理員身分方能查閱。"
                }
            return render(request, 'order/message.html', context)
        else:
            order_list_groupby_area = Order.objects.filter(bento__date=datetime.now().date()).values_list('bento__name', 'bento__bento_type__bento_type', 'area__area', 'number', named=True).order_by('area__id', 'bento__bento_type__bento_type')
            df_order_list_groupby_area = pd.DataFrame(list(order_list_groupby_area))
            df_order_list_groupby_area['area'] = df_order_list_groupby_area['area__area']
            df_order_list_groupby_area['bento_name'] = df_order_list_groupby_area['bento__name']
            df_order_list_groupby_area['bento_type'] = df_order_list_groupby_area['bento__bento_type__bento_type']
            df_order_list_groupby_area = df_order_list_groupby_area.groupby(['area', 'bento_type', 'bento_name']).sum().reset_index()[['area', 'bento_type', 'bento_name', 'number']]
            order_list_groupby_area = list(df_order_list_groupby_area.T.to_dict().values()).copy()

            order_list_groupby_distribution_place = Order.objects.filter(bento__date=datetime.now().date()).values_list('bento__name', 'bento__bento_type__bento_type', 'area__area', 'distribution_place__distribution_place', 'number', named=True).order_by('area__id',  'distribution_place__distribution_place', 'bento__bento_type__bento_type')
            df_order_list_groupby_distribution_place = pd.DataFrame(list(order_list_groupby_distribution_place))
            df_order_list_groupby_distribution_place['area'] = df_order_list_groupby_distribution_place['area__area']
            df_order_list_groupby_distribution_place['distribution_place'] = df_order_list_groupby_distribution_place['distribution_place__distribution_place']
            df_order_list_groupby_distribution_place['bento_name'] = df_order_list_groupby_distribution_place['bento__name']
            df_order_list_groupby_distribution_place['bento_type'] = df_order_list_groupby_distribution_place['bento__bento_type__bento_type']
            df_order_list_groupby_distribution_place = df_order_list_groupby_distribution_place.groupby(['area', 'distribution_place', 'bento_type', 'bento_name']).sum().reset_index()[['area', 'distribution_place', 'bento_type', 'bento_name', 'number']]
            order_list_groupby_distribution_place = list(df_order_list_groupby_distribution_place.T.to_dict().values()).copy()

            context ={
                "title": "當日出貨統計",
                "order_list_groupby_area":order_list_groupby_area,
                "order_list_groupby_distribution_place":order_list_groupby_distribution_place
            }
            return render(request, 'order/beckend_daily_ouput_stats.html', context)
                   

# ------------------------following are line bot---------------------------------------------

def _handle_follow_event(event):
    line_id = event.source.user_id
    profile = line_bot_api.get_profile(line_id)
    
    profile_exists = User.objects.filter(username=line_id).count() != 0
    if profile_exists:
        user = User.objects.get(username = line_id)
        line_profile = LineProfile.objects.get(user = user)
        line_profile.line_name = profile.display_name
        line_profile.line_picture_url = profile.picture_url
        line_profile.line_status_message = profile.status_message
        line_profile.unfollow = False
        line_profile.friend = True
        line_profile.save()
    else:
        user = User(username = line_id)
        user.save()
        line_profile = LineProfile(
            line_id = line_id,
            line_name = profile.display_name,
            line_picture_url = profile.picture_url,
            line_status_message=profile.status_message,
            friend=True,
            user = user
        )
        line_profile.save()

def _handle_unfollow_event(event):
    line_id = event.source.user_id
    line_profile = LineProfile.objects.get(line_id=line_id)
    line_profile.unfollow = True
    line_profile.friend = False
    line_profile.save()

## handle message and event
def _handle_text_msg(event, request):
    text = event.message.text
    # user_name = line_bot_api.get_profile(line_id).display_name
    line_profile = LineProfile.objects.get(line_id=event.source.user_id)
    line_profile_state = line_profile.state

    if text == "動作: 馬上訂購":
        messages = get_area_reply_messages()
    elif text == "動作: 本周菜色":
        print("動作: 本周菜色")
        print("動作: 本周菜色")
        print("動作: 本周菜色")
        print("動作: 本周菜色")
        messages = [TextSendMessage(text="本功能即將推出，敬請期待!")]
    elif text == "動作: 查看訂單":
        messages = get_order_list_reply(request)
    else:
        messages = [TextSendMessage(text="小農聽不懂您的意思，麻煩妳連絡客服人員喔!")]
        
    # elif text == "動作: 飯盒菜單":
    # elif text == "動作: 聯絡我們":
    line_bot_api.reply_message(
        event.reply_token,
        messages
    )

def _handle_postback_event(event, request):
    postback_data = parse_url_query_string(event.postback.data)
    if postback_data['action'] == 'get_area_reply_messages':
        area_id = postback_data['area_id']
        messages = get_distribution_place_reply_messages(request, area_id)
    
    elif postback_data['action'] == 'order_delete':
        line_id = event.source.user_id
        order_id=postback_data['id']
        message = delete_order(order_id, line_id)
        messages = [message]
        
    line_bot_api.reply_message(
        event.reply_token,
        messages
    )

@csrf_exempt
def callback(request):
    print("callback")
    print("callback")
    print("callback")
    print("callback")
    print("callback")
    if request.method == 'POST':
        signature = request.META['HTTP_X_LINE_SIGNATURE']
        body = request.body.decode('utf-8')
        
        try:
            events = parser.parse(body, signature)
        except InvalidSignatureError:
            return HttpResponseForbidden()
        except LineBotApiError:
            return HttpResponseBadRequest()

        for event in events:
            if isinstance(event, MessageEvent):
                print("MessageEvent")
                print("MessageEvent")
                print("MessageEvent")
                print("MessageEvent")
                if isinstance(event.message, TextMessage):
                    _handle_text_msg(event, request)
            #     if isinstance(event.message, LocationMessage):
            #         _handle_location_msg(event)
            if isinstance(event, FollowEvent):
                _handle_follow_event(event)
            if isinstance(event, UnfollowEvent):
                _handle_unfollow_event(event)
            if isinstance(event, PostbackEvent):
                print("PostbackEvent")
                print("PostbackEvent")
                print("PostbackEvent")
                print("PostbackEvent")
                _handle_postback_event(event, request)
        return HttpResponse()
    else:
        return HttpResponseBadRequest()


