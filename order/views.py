from django.shortcuts import render, redirect
from django.http import HttpResponse, HttpResponseBadRequest, HttpResponseForbidden, JsonResponse

from django.views.decorators.csrf import csrf_exempt, csrf_protect

from xiaonon import settings
from django.contrib.auth.models import User
from django.contrib import auth
from order.models import Job, LineProfile, BentoType, Bento, Area, DistributionPlace, AreaLimitation, Order
from order.utl import get_order_detail, parse_url_query_string, create_order

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
from order.line_messages import get_order_date_reply_messages, get_area_reply_messages, get_distribution_place_reply_messages, get_bento_reply_messages, get_order_number_messages, get_order_confirmation_messages#, get_web_create_order_messages

import numpy as np
from datetime import datetime, timedelta
import pandas as pd
from uuid import uuid4
from urllib.parse import parse_qs, urlparse
import requests
from base64 import urlsafe_b64decode
import re
def redirect_self(request, to):
    domain = request.META['HTTP_HOST']
    if domain.startswith("127"):
        return redirect("http://" + domain + "/" + to)
    else:
        return redirect("https://" + domain + "/" + to)

def get_line_login_api_url(state, callback):
    return "https://access.line.me/oauth2/v2.1/authorize?response_type=code&client_id=1594806265&redirect_uri=" + callback + "&state=" + state + "&scope=openid"

# ------------------------following are website----------------------------------------------
def index(request):
    return HttpResponse("Hello, world. You're at the polls index.")
    # return redirect_self(request, "order/order_create/")

def line_login_callback(request, app_name, view_name):
    url = request.path

    post_data = {
        "grant_type": 'authorization_code',
        "code": request.GET['code'],
        "redirect_uri": settings.LINE_CALLBACK_URL,
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

    line_profile = LineProfile.objects.get(line_id=line_id)
    user = line_profile.user
    auth.login(request, user)
    return redirect_self(request, app_name + "/" + view_name + "/")


@csrf_exempt
def order_create(request, area_id=1, distribution_place_id=1):
    if not request.user.is_authenticated:
        state =  uuid4().hex
        callback = settings.LINE_CALLBACK_URL + 'order/order_create/'
        return redirect(get_line_login_api_url(state, callback))

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
                'title':'多筆訂購',
                'apds':output_adps,
                'selected_adp_option_text':selected_adp_option_text,
                'available_bentos':available_bentos,
            }
            return render(request, 'order/order_create.html', context)
        if request.method == "POST":
            post_data = request.POST
            order_data = post_data['orderData']
            user = request.user
            line_profile = LineProfile.objects.get(user=user)
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
                res_message = "已經訂購成功，以下是您的訂單資訊。" #TODO: 回饋訂單查詢URL
            else: 
                res_message = "部分訂單因數量不足，請從新訂購。" #TODO: 回饋失敗部分

            line_bot_api.push_message(
                line_id,
                TextSendMessage(text=res_message)
            )
            return JsonResponse({"success":all_success, 'message':res_message})
            # return JsonResponse({"state":True})

@csrf_exempt
def order_list(request):
    if not request.user.is_authenticated:
        state =  uuid4().hex
        callback = settings.LINE_CALLBACK_URL + 'order/order_list/'
        return redirect(get_line_login_api_url(state, callback))
    else:
        user = request.user
        line_profile = LineProfile.objects.get(user=user)
        line_id = line_profile.line_id
        line_profile = LineProfile.objects.get(line_id=line_id)
        current_orders = list(Order.objects.filter(line_profile=line_profile, delete_time=None, bento__date__gt=datetime.now()-timedelta(1)).values_list('id', 'number', 'price', 'bento__date', 'bento__name', 'bento__bento_type__bento_type', 'bento__cuisine', named=True).order_by('bento__date'))
        df_current_orders = pd.DataFrame(current_orders)
        df_current_orders['row_id'] = pd.Series(df_current_orders.index).apply(lambda x:x+1)
        df_current_orders['date'] = df_current_orders['bento__date'].apply(lambda x:str(x.month) + '/' + str(x.day))
        df_current_orders['name'] = df_current_orders['bento__name']
        df_current_orders['type'] = df_current_orders['bento__bento_type__bento_type']
        df_current_orders['number'] = df_current_orders['number']
        df_current_orders['cuisine'] = df_current_orders['bento__cuisine']
        df_current_orders = df_current_orders[['row_id', 'id','date','name','type', 'price','number','cuisine']]

        history_orders = list(Order.objects.filter(line_profile=line_profile, bento__date__lt=datetime.now()).values_list('id', 'number', 'price', 'bento__date', 'bento__name', 'bento__bento_type__bento_type', 'bento__cuisine', named=True).order_by('bento__date').reverse()[:10])
        df_history_orders = pd.DataFrame(history_orders)
        df_history_orders['row_id'] = pd.Series(df_history_orders.index).apply(lambda x:x+1)
        df_history_orders['date'] = df_history_orders['bento__date'].apply(lambda x:str(x.month) + '/' + str(x.day))
        df_history_orders['name'] = df_history_orders['bento__name']
        df_history_orders['type'] = df_history_orders['bento__bento_type__bento_type']
        df_history_orders['number'] = df_history_orders['number']
        df_history_orders['cuisine'] = df_history_orders['bento__cuisine']
        df_history_orders = df_history_orders[['row_id', 'id','date','name','type', 'price','number','cuisine']]

        context = {
            "current_orders":df_current_orders.T.to_dict().values,
            "history_orders":df_history_orders.T.to_dict().values
        }
        return render(request, 'order/order_list.html', context)

def order_delete(request, order_id):
    order = Order.objects.get(id=order_id)
    order.delete_time = datetime.now()
    order.save()
    area_limitation = AreaLimitation.objects.get(bento=order.bento, area=order.area)
    area_limitation.remain += order.number
    area_limitation.save()
    # return JsonResponse(data={"success":True})
    return redirect_self(request,  "order/order_list/")

# ------------------------following are line bot---------------------------------------------

def _handle_follow_event(event):
    line_id = event.source.user_id
    profile = line_bot_api.get_profile(line_id)
    
    profile_exists = User.objects.filter(username=line_id).count()
    if profile_exists == 0:
        user = User(username = line_id)
        user.save()
        line_profile = LineProfile(
            line_id = line_id,
            line_name = profile.display_name,
            line_picture_url = profile.picture_url,
            line_status_message=profile.status_message,
            user = user
        )
        line_profile.save()
    else:
        user = User.objects.get(username = line_id)
        line_profile = LineProfile.objects.get(user = user)
        line_profile.unfollow = False

def _handle_unfollow_event(event):
    line_id = event.source.user_id
    line_profile = LineProfile.objects.get(line_id=line_id)
    line_profile.unfollow = True


## handle message and event
def _handle_text_msg(event):
    text = event.message.text
    line_id = event.source.user_id
    # user_name = line_bot_api.get_profile(line_id).display_name
    line_profile = LineProfile.objects.get(line_id=line_id)
    line_profile_state = line_profile.state

    if text == "動作: 開始訂購":
        messages = get_order_date_reply_messages(event)
    # elif text == "動作: 多筆訂購":
    #     pwd = ''.join(np.random.randint(0, 9, 6).astype(str))
    #     line_profile.state = "web_pwd:" + pwd
    #     line_profile.save()
    #     messages = get_web_create_order_messages(event, pwd, line_id)

    elif line_profile_state == "phone":
        line_profile.phone = str(text)
        line_profile.state = "None"
        line_profile.save()
        messages = [TextSendMessage(text="您的電話號碼已經設定完成，謝謝您的配合。")]
    else:
        messages = [TextSendMessage(text="小農聽不懂您的意思，麻煩妳連絡客服人員喔!")]
        
    # elif text == "動作: 飯盒菜單":
    # elif text == "動作: 聯絡我們":
    # messages = [TextSendMessage(text=user_name+": "+text)]
    line_bot_api.reply_message(
        event.reply_token,
        messages
    )

def _handle_postback_event(event):
    line_id = event.source.user_id
    postback_data = parse_url_query_string(event.postback.data)
    
    if postback_data['action'] == 'get_order_date_reply_messages':
        date_string = postback_data['date_string']
        messages = get_area_reply_messages(event, date_string)
    elif postback_data['action'] == 'get_area_reply_messages':
        date_string = postback_data['date_string']
        area_id = postback_data['area_id']
        messages = get_distribution_place_reply_messages(event, date_string, area_id)
    elif postback_data['action'] == 'get_distribution_place_reply_messages':
        date_string = postback_data['date_string']
        area_id = postback_data['area_id']
        distribution_place_id = postback_data['distribution_place_id']
        messages = get_bento_reply_messages(event, date_string, area_id, distribution_place_id)
    elif postback_data['action'] == 'get_bento_reply_messages':
        date_string = postback_data['date_string']
        area_id = postback_data['area_id']
        distribution_place_id = postback_data['distribution_place_id']
        bento_id = postback_data['bento_id']
        messages = get_order_number_messages(event, date_string, area_id, distribution_place_id, bento_id)
    elif postback_data['action'] == 'get_order_number_messages':
        date_string = postback_data['date_string']
        area_id = postback_data['area_id']
        distribution_place_id = postback_data['distribution_place_id']
        bento_id = postback_data['bento_id']
        order_number = postback_data['order_number']
        messages = get_order_confirmation_messages(event, date_string, area_id, distribution_place_id, bento_id, order_number, line_id)
    elif postback_data['action'] == 'get_order_confirmation_messages':
        date_string = postback_data['date_string']
        area_id = postback_data['area_id']
        distribution_place_id = postback_data['distribution_place_id']
        bento_id = postback_data['bento_id']
        order_number = postback_data['order_number']

        success = create_order(line_id, bento_id, order_number, area_id, distribution_place_id)
        if success:
            order_detail = get_order_detail(date_string, area_id, distribution_place_id, bento_id, order_number, line_id)
            messages = [TextSendMessage(text="恭喜您訂購成功" + order_detail)]

            line_profile = LineProfile.objects.get(line_id=line_id)
            if not line_profile.phone:
                line_profile.state = 'phone'
                line_profile.save()
                messages.extend([TextSendMessage(text="請留下您的電話，以方便我們聯絡您取餐: \nex. 0912345678")])
    
            # print("date_string", date_string)
            # print("area_id", area_id)
            # print("distribution_place_id", distribution_place_id)
            # print("bento_id", bento_id)
        else:
            messages = [TextSendMessage(text="抱歉，剩餘便當不足，請從新開始訂購。")]

    line_bot_api.reply_message(
        event.reply_token,
        messages
    )

@csrf_exempt
def callback(request):
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
                if isinstance(event.message, TextMessage):
                    _handle_text_msg(event)
            #     if isinstance(event.message, LocationMessage):
            #         _handle_location_msg(event)
            if isinstance(event, FollowEvent):
                _handle_follow_event(event)
            if isinstance(event, UnfollowEvent):
                _handle_unfollow_event(event)
            if isinstance(event, PostbackEvent):
                _handle_postback_event(event)
        return HttpResponse()
    else:
        return HttpResponseBadRequest()


