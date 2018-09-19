import numpy as np
from datetime import datetime, timedelta
import pandas as pd
from uuid import uuid4
from urllib.parse import parse_qs, urlparse
from base64 import urlsafe_b64decode
import re
import requests
import os
import json

from django.shortcuts import render, redirect
from django.http import HttpResponse, HttpResponseBadRequest, HttpResponseForbidden, JsonResponse
from django.views.decorators.csrf import csrf_exempt, csrf_protect

from django.conf import settings
from django.contrib.auth.models import User
from django.contrib import auth, messages
from django.db.models import Sum
from order.models import (
    Job, LineProfile, BentoType, Bento,
    Area, DistributionPlace, AreaLimitation, Order, DPlimitation
)
from order.utl import *

from linebot import LineBotApi, WebhookParser  # , WebhookHanlder
from linebot.exceptions import InvalidSignatureError, LineBotApiError
from linebot.models import (
    MessageEvent, FollowEvent, PostbackEvent, UnfollowEvent,
    TextMessage, LocationMessage,
    TextSendMessage, TemplateSendMessage, ImageSendMessage, StickerSendMessage,
    ButtonsTemplate, ConfirmTemplate, CarouselTemplate,
    PostbackTemplateAction, MessageTemplateAction, URITemplateAction,
    CarouselColumn, MessageAction, URIImagemapAction
)
line_bot_api = LineBotApi(settings.LINE_CHANNEL_ACCESS_TOKEN)
parser = WebhookParser(settings.LINE_CHANNEL_SECRET)
from order.line_messages import *

from apscheduler.schedulers.background import BackgroundScheduler
from django_apscheduler.jobstores import DjangoJobStore, register_events, register_job

# ------------------------following are scheduler jobs------------------------
# https://github.com/jarekwg/django-apscheduler

scheduler = BackgroundScheduler()
scheduler.add_jobstore(DjangoJobStore(), "default")

def send_notification():
    remind_message()

scheduler.add_job(send_notification, 'cron', hour='10', minute='30', second='0',
                  timezone='Asia/Taipei', misfire_grace_time=30,coalesce=False , replace_existing=True, id='remind_msg_1030')
scheduler.add_job(send_notification, 'cron', hour='12', minute='30', second='0',
                  timezone='Asia/Taipei', misfire_grace_time=30,coalesce= False, replace_existing=True, id='remind_msg_1230')
scheduler.start()

# ------------------------following are website----------------------------------------------


def index(request):
    return render(request, 'order/index.html')

def login(request):
    state = uuid4().hex
    return redirect(get_line_login_api_url(request, state, 'order', 'index'))


def logout(request):
    auth.logout(request)
    return redirect('/order/')


def message(request, title="Welcome", msg="Nothing happens here"):
    ref = request.META.get('HTTP_REFERER')

    if "order_create" in str(ref):
        title = "訂購成功"
        msg = "您已訂購成功，相關取餐資訊請回到LINE查看唷！"

    context = {
        "title": title,
        "message": msg,
    }
    return render(request, 'order/message.html', context)


def line_login_callback(request, app_name, view_name):
    # 有些 User 沒有 code 這個 Key?
    post_data = {
        "grant_type": 'authorization_code',
        "code": request.GET['code'],
        "redirect_uri": get_redirect_url(request, "order/line_login_callback/" + app_name + "/" + view_name + "/"),
        "client_id": settings.LINE_LOGIN_CHANNEL_ID,
        "client_secret": settings.LINE_LOGIN_CHANNEL_SECRET,
    }
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
    }
    res = requests.post('https://api.line.me/oauth2/v2.1/token',
                        data=post_data, headers=headers)

    line_login_profile_b64 = eval(res.text)['id_token']
    line_login_profile_b64_decoded = urlsafe_b64decode(
        line_login_profile_b64[:-38] + '============')
    line_login_profile = eval(re.findall(
        b'\{.+?\}', line_login_profile_b64_decoded)[1].decode())
    line_id = line_login_profile.get('sub')

    if LineProfile.objects.filter(line_id=line_id).count() == 0:
        # TODO: https://docs.djangoproject.com/en/2.1/ref/models/querysets/#get-or-create 可以用get_or_create()
        # duplicate key value violates unique constraint "auth_user_username_key" DETAIL:  Key (username)=(Uc0117edb449753ceb936caabee70bfe1) already exists.
        if User.objects.filter(username=line_id).count() == 0:
            user = User(username=line_id)
            user.save()

        profile = line_bot_api.get_profile(line_id)
        user = User.objects.get(username=line_id)
        line_profile = LineProfile(
            user=user,
            line_id=line_id,
            line_name=profile.display_name,
            line_picture_url='' if profile.picture_url is None else profile.picture_url,
            line_status_message=profile.status_message,
            friend=True
        )
        line_profile.save()

    user = LineProfile.objects.get(line_id=line_id).user
    auth.login(request, user)
    return redirect(get_redirect_url(request, app_name + "/" + view_name + "/"))

def show_areas(request):
    areas = Area.objects.all()
    area_list = []
    for area in areas:
        area_list.append([area.id,area.area,get_first_dp_in_area(area.id).id])
    
    domain = request.META['HTTP_HOST']
    if domain.startswith("127"):
        url_head = "http://" + domain + "/"
    else:
        url_head = "https://" + domain + "/"
    
    context = {
        'area_list':area_list,
        'url_head': url_head
    }
    return render(request, 'order/areas.html',context)

@csrf_exempt  # TODO: add csrf protect
def order_create(request, area_id=1, distribution_place_id=1):
    if not request.user.is_authenticated:
        state = uuid4().hex
        return redirect(get_line_login_api_url(request, state, 'order', 'areas'))
        # return redirect(get_line_login_api_url(request, state, 'order', 'order_create'))
    else:
        if request.method == "GET":
            areas = Area.objects.all()
            output_adps = []  # area and distributions
            selected_adp_option_text = ""
            for a in areas:
                distribution_places = DistributionPlace.objects.filter(area=a)
                for dp in distribution_places:
                    adp_dict = {
                        "option_text": a.area + "--" + dp.distribution_place,
                        "area_name": a.area,
                        "dp_name": dp.distribution_place,
                        "area_id": a.id,
                        "distribution_place_id": dp.id,
                    }
                    if area_id == a.id and distribution_place_id == dp.id:
                        adp_dict['selected'] = True
                        # selected_adp_option_text = a.area + "--" + dp.distribution_place
                        selected_adp_option_text = dp.distribution_place
                    else:
                        adp_dict['selected'] = False
                    output_adps.append(adp_dict)
            select_dp_opts = []

            days = get_datetime_filter()
            available_bentos = DPlimitation.objects.filter(
                distribution_place=distribution_place_id,
                bento__date__gt=get_taiwan_current_datetime() - timedelta(days=0),
                bento__date__lte=get_taiwan_current_datetime() + timedelta(days=days),
                bento__ready=True
            ).order_by(
                'bento__date',
                'bento__bento_type__bento_type'
            ).values(
                'bento__id', 'bento__name', 'bento__date',
                'bento__bento_type__bento_type', 'bento__cuisine',
                'bento__photo', 'bento__price', 'dp_remain'
            )

            if len(available_bentos) == 0:
                message = "目前沒有便當供應，請開學後再來找我喔。"
                context = {
                    "title": "目前沒有便當供應",
                    "message": message
                }
                # maybe directly redirect to order_list view
                return render(request, 'order/message.html', context)
            else:
                # {'bento__id': 26,
                # 'bento__name': '避風塘鮮雞', 'bento__bento_type__bento_type': '均衡吃飽飽', 'bento__cuisine': '洋菇青江菜、蒜酥馬鈴薯&地瓜、涼拌小黃瓜', 'bento__photo': 'bento_imgs/避風塘鮮雞_2018-06-22_a9ad7545a61545759f08a31569a89fad.png', 'bento__price': 120, 'remain': 100}]
                aws_url = settings.AWS_BUCKET_URL
                df_available_bentos = pd.DataFrame(list(available_bentos))
                df_available_bentos['id'] = df_available_bentos['bento__id']
                df_available_bentos['name'] = df_available_bentos['bento__name']
                df_available_bentos['date'] = df_available_bentos['bento__date'].apply(
                    lambda x: str(x.month) + '/' + str(x.day))
                df_available_bentos['weekday'] = df_available_bentos['bento__date'].apply(
                    lambda x: x.weekday())
                df_available_bentos['bento_type'] = df_available_bentos['bento__bento_type__bento_type']
                df_available_bentos['cuisine'] = df_available_bentos['bento__cuisine']
                df_available_bentos['photo'] = df_available_bentos['bento__photo'].apply(
                    lambda x: aws_url + x)
                df_available_bentos['price'] = df_available_bentos['bento__price']
                df_available_bentos['remain'] = df_available_bentos['dp_remain'].astype(
                    str)
                df_available_bentos['select_range'] = df_available_bentos['dp_remain'].apply(
                    lambda x: list(range(0, 6)) if int(x) >= 5 else list(range(0, int(x)+1)))

                df_available_bentos = df_available_bentos[[
                    "id", "name", 'date', "weekday", "bento_type", "cuisine", "photo", "price", "remain", "select_range"]]
                available_bentos = df_available_bentos.T.to_dict().values()

                first_dp_in_area = DistributionPlace.objects.filter(area_id = area_id)[0]
                area_receive_time = [first_dp_in_area.start_time.strftime('%H:%M'),first_dp_in_area.end_time.strftime('%H:%M')]

                context = {
                    'title': '馬上訂購',
                    'today': get_taiwan_current_datetime().weekday(),
                    'weekdays': weekday_zh_mapping,
                    'area': Area.objects.get(id=area_id),
                    'area_receive_time': area_receive_time,
                    'dp_items': DistributionPlace.objects.filter(area=area_id).values('id', 'distribution_place', 'area_id'),
                    'apds': output_adps,
                    'selected_adp_option_text': selected_adp_option_text,
                    'available_bentos': available_bentos,
                    'user_phone': LineProfile.objects.get(user=request.user).phone
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
            ods = json.loads(order_data)
            # for od in eval(order_data):
            for od in ods:
                bento_id = int(od['bento_id'])
                order_number = int(od['order_number'])
                area_id = int(od['area_id'])
                distribution_place_id = int(od['distribution_place_id'])
                # TODO: add price column
                success = create_order(
                    line_id, bento_id, order_number, area_id, distribution_place_id)
                if not success:
                    all_success = False

            if all_success:
                # 政大領取時間不同
                res_message = "訂購成功。"

                for dp in DistributionPlace.objects.all():

                    if distribution_place_id == dp.id:
                        start_time = dp.start_time.strftime('%H:%M')
                        end_time = dp.end_time.strftime('%H:%M')
                        text_content = "我們已經收到您的訂購，恭喜你選擇了更好的午餐！\n──────────\n米米醬小提醒：\n1. 若想查看本周訂單資訊，請按下方「我的訂單」按紐。\n2. 取餐時間為：{}~{}。\n3. 若想查看各校取餐點街景，請按下方「查看取餐點」按紐\n4.若無法領取請記得於當天11:00前取消哦\n5. 取餐時只需要提供電話後3碼，即可核對取餐\n──────────".format(start_time,end_time)
                        #TODO: 回饋訂單查詢URL
                    
                actions = [
                    MessageAction(
                        label='我的訂單',
                        text='動作: 我的訂單'
                    ),
                    MessageAction(
                        label='查看取餐地點',
                        text='動作: 查看取餐地點'
                    )
                ]

                line_message = [
                    TextSendMessage(text = text_content),
                    TemplateSendMessage(
                        alt_text='訂購成功',
                        template=ButtonsTemplate(
                            title='訂購成功',
                            text=' ',
                            actions=actions
                        )
                    )   
                ]

            else:
                line_message = TextSendMessage(
                    text="部分訂單因數量不足，請重新訂購。")  # TODO: 回饋失敗部分
                res_message = "部分訂單因數量不足，請重新訂購。"

            line_bot_api.push_message(
                line_id,
                line_message
            )
            return JsonResponse({"success": all_success, 'message': res_message})
            # return JsonResponse({"state":True})


def realtime_update_bt_number(request):
    data = request.POST
    data = data.dict()
    dp_id = data['dp_id']
    bento_id = data['bento_id']

    remain = DPlimitation.objects.get(
        bento=bento_id, distribution_place=dp_id).dp_remain
    res = {'remain': remain}
    return JsonResponse(res)


def order_list(request):
    if not request.user.is_authenticated:
        state = uuid4().hex
        return redirect(get_line_login_api_url(request, state, 'order', 'order_list'))
    else:
        user = request.user
        current_orders = list(Order.objects.filter(
            line_profile__user=user, delete_time=None,
            bento__date__gt=get_taiwan_current_datetime()-timedelta(1)
        ).order_by(
            'bento__date', 'bento__bento_type__bento_type'
        ).values_list(
            'id', 'number', 'price', 'distribution_place__distribution_place', 'bento__date', 'bento__name',
            'bento__bento_type__bento_type', 'bento__cuisine', named=True
        ).order_by('bento__date')
        )
        if len(current_orders) != 0:
            df_current_orders = pd.DataFrame(current_orders)
            df_current_orders['row_id'] = pd.Series(
                df_current_orders.index).apply(lambda x: x+1)
            df_current_orders['date'] = df_current_orders['bento__date'].apply(
                lambda x: str(x.month) + '/' + str(x.day))
            df_current_orders['weekday'] = df_current_orders['bento__date'].apply(
                lambda x: weekday_zh_mapping[x.weekday()])
            df_current_orders['name'] = df_current_orders['bento__name']
            df_current_orders['type'] = df_current_orders['bento__bento_type__bento_type']
            df_current_orders['number'] = df_current_orders['number']
            df_current_orders['cuisine'] = df_current_orders['bento__cuisine']
            df_current_orders['today'] = df_current_orders['bento__date'].apply(
                lambda x: x == get_taiwan_current_datetime().date())
            df_current_orders['distribution_place'] = df_current_orders['distribution_place__distribution_place']
            df_current_orders = df_current_orders[[
                'row_id', 'id', 'date', 'weekday', 'name', 'type', 'price', 'number', 'cuisine', 'today', 'distribution_place']]
            current_orders = df_current_orders.T.to_dict().values()
        else:
            current_orders = []

        history_orders = list(Order.objects.filter(
            line_profile__user=user, bento__date__lt=get_taiwan_current_datetime(), delete_time = None
        ).values_list(
            'id', 'number', 'price', 'distribution_place__distribution_place',
            'bento__date', 'bento__name', 'bento__bento_type__bento_type', 'bento__cuisine', 'received', named=True
        ).order_by('bento__date').reverse()[:10])

        if len(history_orders) != 0:
            df_history_orders = pd.DataFrame(history_orders)
            df_history_orders['row_id'] = pd.Series(
                df_history_orders.index).apply(lambda x: x+1)
            df_history_orders['date'] = df_history_orders['bento__date'].apply(
                lambda x: str(x.month) + '/' + str(x.day))
            df_history_orders['weekday'] = df_history_orders['bento__date'].apply(
                lambda x: weekday_zh_mapping[x.weekday()])
            df_history_orders['name'] = df_history_orders['bento__name']
            df_history_orders['type'] = df_history_orders['bento__bento_type__bento_type']
            df_history_orders['number'] = df_history_orders['number']
            df_history_orders['cuisine'] = df_history_orders['bento__cuisine']
            df_history_orders['distribution_place'] = df_history_orders['distribution_place__distribution_place']
            df_history_orders['received'] = df_history_orders['received']
            df_history_orders = df_history_orders[[
                'row_id', 'id', 'date', 'weekday', 'name', 'type', 'price', 'number', 'cuisine', 'distribution_place', 'received']]
            history_orders = df_history_orders.T.to_dict().values()
        else:
            history_orders = []

        context = {
            "title": "我的訂單",
            "current_orders": current_orders,
            "history_orders": history_orders,
            "now": get_taiwan_current_datetime().hour
        }
        return render(request, 'order/order_list.html', context)


def order_delete(request, order_id):
    order_id = int(order_id)
    line_id = LineProfile.objects.get(user=request.user).line_id
    message = delete_order(order_id, line_id)
    line_bot_api.push_message(
        line_id,
        message
    )
    return redirect(get_redirect_url(request, 'order/order_list/'))


def backend_main_view(request):
    if not request.user.is_authenticated:
        state = uuid4().hex
        return redirect(get_line_login_api_url(request, state, 'order', 'backend_main_view'))
    else:
        if not request.user.is_staff:
            context = {
                "title": "您沒有查閱權限",
                "message": "此頁面必須具有員工身分方能查閱。"
            }
            return render(request, 'order/message.html', context)
        else:
            areas = Area.objects.all()
            context = {
                "title": "後臺主頁",
                "areas": areas
            }
            return render(request, 'order/backend_main_view.html', context)


def backend_friend_list(request):
    if not request.user.is_authenticated:
        state = uuid4().hex
        return redirect(get_line_login_api_url(request, state, 'order', 'backend_friend_list'))
    else:
        if not request.user.is_superuser:
            context = {
                "title": "您沒有查閱權限",
                "message": "此頁面必須具有管理員身分方能查閱。"
            }
            return render(request, 'order/message.html', context)
        else:
            superuser_profile = LineProfile.objects.filter(user__is_superuser=True).values_list(
                'line_id', 'line_name', 'line_picture_url', 'phone', named=True)
            df_superuser_profile = pd.DataFrame(list(superuser_profile))
            staff_profile = LineProfile.objects.filter(user__is_staff=True, user__is_superuser=False).values_list(
                'line_id', 'line_name', 'line_picture_url', 'phone', named=True)
            df_staff_profile = pd.DataFrame(list(staff_profile))
            friend_profile = LineProfile.objects.filter(user__is_staff=False).values_list(
                'line_id', 'line_name', 'line_picture_url', 'phone', named=True).order_by('create_time').reverse()
            df_friend_profile = pd.DataFrame(list(friend_profile))

            context = {
                "title": "好友清單",
                "superuser_profile": list(df_superuser_profile.T.to_dict().values()),
                "staff_profile": list(df_staff_profile.T.to_dict().values()),
                "friend_profile": list(df_friend_profile.T.to_dict().values())
            }
            return render(request, 'order/backend_friend_list.html', context)


def backend_add_staff(request, line_id):
    if not request.user.is_authenticated:
        state = uuid4().hex
        return redirect(get_line_login_api_url(request, state, 'order', 'backend_friend_list'))
    else:
        if not request.user.is_superuser:
            context = {
                "title": "您沒有查閱權限",
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
        state = uuid4().hex
        return redirect(get_line_login_api_url(request, state, 'order', 'backend_friend_list'))
    else:
        if not request.user.is_superuser:
            context = {
                "title": "您沒有查閱權限",
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
        state = uuid4().hex
        return redirect(get_line_login_api_url(request, state, 'order', 'backend_friend_list'))
    else:
        if not request.user.is_superuser:
            context = {
                "title": "您沒有查閱權限",
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
        state = uuid4().hex
        return redirect(get_line_login_api_url(request, state, 'order', 'backend_friend_list'))
    else:
        if not request.user.is_superuser:
            context = {
                "title": "您沒有查閱權限",
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
        state = uuid4().hex
        return redirect(get_line_login_api_url(request, state, 'order', 'backend_main_view'))
    else:
        if not request.user.is_staff:
            context = {
                "title": "您沒有查閱權限",
                "message": "此頁面必須具有員工身分方能查閱。"
            }
            return render(request, 'order/message.html', context)
        else:
            searching_date = get_taiwan_current_datetime() + timedelta(0)
            order_list = Order.objects.filter(
                bento__date=searching_date, area=area_id, delete_time=None
            ).values_list(
                'id', "line_profile__line_id", 'line_profile__line_name',
                'line_profile__phone', 'bento__id', 'bento__name', 'bento__bento_type__bento_type',
                'area__area', 'distribution_place__id', 'distribution_place__distribution_place',
                'number', 'price', 'received', named=True
            ).order_by("line_profile__line_name",
                       "distribution_place__distribution_place", "bento__name"
                       )

            if order_list.count() != 0:
                df_order_list = pd.DataFrame(list(order_list))
                df_order_list['order_id'] = df_order_list['id']
                df_order_list['line_id'] = df_order_list['line_profile__line_id']
                df_order_list['line_name'] = df_order_list['line_profile__line_name']
                df_order_list['phone'] = df_order_list['line_profile__phone']
                df_order_list['phone_last3'] = df_order_list['line_profile__phone'].apply(
                    lambda x: x[-3:])
                df_order_list['area'] = df_order_list['area__area']
                df_order_list['distribution_place_id'] = df_order_list['distribution_place__id']
                df_order_list['distribution_place'] = df_order_list['distribution_place__distribution_place']
                df_order_list['bento_id'] = df_order_list['bento__id']
                df_order_list['bento_name'] = df_order_list['bento__name']
                df_order_list['bento_type'] = df_order_list['bento__bento_type__bento_type']
                df_order_list['number'] = df_order_list['number']
                df_order_list['price'] = df_order_list['price']
                order_list = df_order_list[['order_id', 'line_id', 'line_name',
                                            'phone', 'phone_last3', 'area', 'distribution_place',
                                            'bento_name', 'number', 'price', 'received', 'bento_id']]
                order_list = list(df_order_list.T.to_dict().values()).copy()

                df_order_list['received'] = df_order_list['received'].apply(
                    lambda x: int(x))

                order_stats = []
                for dp in DistributionPlace.objects.filter(area=area_id):
                    dp_stats = {
                        "dp": dp.distribution_place,
                        "dp_limits": []
                    }
                    dp_limits = DPlimitation.objects.filter(distribution_place=dp,
                                                            bento__date=get_taiwan_current_datetime())
                    for dp_limit in dp_limits:
                        total_order_bt = Order.objects.filter(
                            distribution_place=dp, bento=dp_limit.bento, delete_time=None)
                        total_order_bt_received = Order.objects.filter(
                            distribution_place=dp, bento=dp_limit.bento, delete_time=None, received=True)
                        totol_order_bt_notreceived = Order.objects.filter(
                            distribution_place=dp, bento=dp_limit.bento, delete_time=None, received=False)

                        total_order_bt_number = 0 if total_order_bt.aggregate(Sum('number'))[
                            'number__sum'] == None else total_order_bt.aggregate(Sum('number'))['number__sum']
                        total_order_bt_received_number = 0 if total_order_bt_received.aggregate(Sum('number'))[
                            'number__sum'] == None else total_order_bt_received.aggregate(Sum('number'))['number__sum']
                        totol_order_bt_notreceived_number = 0 if totol_order_bt_notreceived.aggregate(Sum('number'))[
                            'number__sum'] == None else totol_order_bt_notreceived.aggregate(Sum('number'))['number__sum']

                        limit_temp = {
                            "bento_id": dp_limit.bento.id,
                            "bento": dp_limit.bento.name,
                            "type": dp_limit.bento.bento_type,
                            "limitation": dp_limit.dp_limitation,
                            "remain": dp_limit.dp_remain,
                            "unreceived": totol_order_bt_notreceived_number,
                            "received": total_order_bt_received_number,
                            "total_order_number": total_order_bt_number

                        }
                        dp_stats["dp_limits"].append(limit_temp)
                    order_stats.append(dp_stats)

            else:
                order_list = []
                order_list_group = []
                order_stats = []
            area = Area.objects.get(id=area_id).area
            context = {
                "title": area + "當日訂單",
                "order_list": order_list,
                "order_stats": order_stats
            }
        return render(request, 'order/backend_daily_output_order.html', context)


def toggle_receive_bento(request):
    if not request.user.is_authenticated:
        state = uuid4().hex
        return redirect(get_line_login_api_url(request, state, 'order', 'backend_main_view'))
    else:
        if not request.user.is_staff:
            context = {
                "title": "您沒有查閱權限",
                "message": "此頁面必須具有員工身分方能查閱。"
            }
            return render(request, 'order/message.html', context)
        else:
            post_data = request.POST
            post_data = post_data.dict()
            order_id = int((post_data["order_id"]))
            order = Order.objects.get(id=order_id)
            order_number = order.number
            order_area = AreaLimitation.objects.get(
                bento=order.bento, area=order.area)
            order_dp = DPlimitation.objects.get(
                bento=order.bento, distribution_place=order.distribution_place)

            if order.received == True:
                order.received = False
                order.save()

                # order_area.remain += order_number
                # order_area.save()

                # order_dp.dp_remain += order_number
                # order_dp.save()

            else:
                order.received = True
                order.save()

                # order_area.remain -= order_number
                # order_area.save()

                # order_dp.dp_remain -= order_number
                # order_dp.save()

            # print(order, order_id)
            return JsonResponse({"success": True})


def backend_receive_order(request, order_id):
    if not request.user.is_authenticated:
        state = uuid4().hex
        return redirect(get_line_login_api_url(request, state, 'order', 'backend_main_view'))
    else:
        if not request.user.is_staff:
            context = {
                "title": "您沒有查閱權限",
                "message": "此頁面必須具有員工身分方能查閱。"
            }
            return render(request, 'order/message.html', context)
        else:
            order = Order.objects.get(pk=order_id)
            order.received = True
            order.save()
            return JsonResponse({"message": "Success"})


def backend_daily_ouput_stats(request, add_days=0):
    if not request.user.is_authenticated:
        state = uuid4().hex
        return redirect(get_line_login_api_url(request, state, 'order', 'backend_main_view'))
    else:
        if not request.user.is_superuser:
            context = {
                "title": "您沒有查閱權限",
                "message": "此頁面必須具有管理員身分方能查閱。"
            }
            return render(request, 'order/message.html', context)
        else:
            order_list_groupped_table = []
            for area in Area.objects.all():
                area_order = {}
                area_order['area'] = area.area
                area_order['distribution_place_order'] = []
                distribution_places = DistributionPlace.objects.filter(
                    area=area)
                for dp in distribution_places:
                    distribution_place_order = {}
                    distribution_place_order['distribution_place'] = dp.distribution_place
                    if add_days != 0:
                        searching_date = get_taiwan_current_datetime().date() + timedelta(days = add_days)
                    else:
                        searching_date = get_taiwan_current_datetime().date() 
                    
                    orders = Order.objects.filter(bento__date=searching_date, distribution_place=dp, delete_time=None).values_list(
                        'bento__id', 'bento__name', 'bento__bento_type__bento_type', 'number', named=True).order_by('bento__bento_type__bento_type')
                    # print(orders)
                    if len(orders) != 0:
                        df_orders = pd.DataFrame(list(orders))
                        df_orders['bento_id'] = df_orders['bento__id']
                        df_orders['bento_name'] = df_orders['bento__name']
                        df_orders['bento_type'] = df_orders['bento__bento_type__bento_type']
                        # df.groupby(): 合併特定欄位相同的值，並回傳為 DataFrameGroupBy object
                        df_orders_groupped = df_orders.groupby(
                            ['bento_name', 'bento_id', 'bento_type']).sum().reset_index()
                        
                        def combine_dp_limitation(row):
                            dp_l = DPlimitation.objects.get(
                                bento=row['bento_id'], distribution_place=dp)
                            row['limitation'] = dp_l.dp_limitation
                            row['remain'] = dp_l.dp_remain
                            return row

                        df_orders_groupped = df_orders_groupped.apply(combine_dp_limitation, axis=1)[
                            ['bento_name', 'bento_id', 'bento_type', 'number', 'limitation', 'remain']]

                        distribution_place_order['order_list'] = list(
                            df_orders_groupped.T.to_dict().values())
                    else:
                        distribution_place_order['order_list'] = []
                    area_order['distribution_place_order'].append(
                        distribution_place_order)
                order_list_groupped_table.append(area_order)
            context = {
                "title": "當日出貨統計",
                "order_list_groupped_table": order_list_groupped_table,
            }
            return render(request, 'order/backend_daily_ouput_stats.html', context)


def backend_weekly_ouput_stats(request,week=0):
    if not request.user.is_authenticated:
        state = uuid4().hex
        return redirect(get_line_login_api_url(request, state, 'order', 'backend_main_view'))
    else:
        if not request.user.is_superuser:
            context = {
                "title": "您沒有查閱權限",
                "message": "此頁面必須具有管理員身分方能查閱。"
            }
            return render(request, 'order/message.html', context)
        else:
            week_start, week_end = get_current_week_daterange()
            # set which week, this week  = weekstart + 0 day and so on
            week_start += timedelta(days = week*7)
            week_end += timedelta(days = week*7)
            total_orders = {}

            for dp in DistributionPlace.objects.all():
                dp_temp = []
                weekday_range = {
                    0: {},
                    1: {},
                    2: {},
                    3: {},
                    4: {},
                    5: {},
                    6: {}
                }

                remains_in_dp = list(DPlimitation.objects.filter(
                    distribution_place=dp,
                    bento__ready = True,
                    bento__date__gt=week_start-timedelta(days=1),
                    bento__date__lte=week_end))

                for remain in remains_in_dp:
                    for key, value in weekday_range.items():
                        if remain.bento.date.weekday() == key:
                            weekday_range[key][remain.bento_id] = {}
                            weekday_range[key][remain.bento_id]['bento_name'] = remain.bento.name
                            weekday_range[key][remain.bento_id]['limitation'] = remain.dp_limitation
                            weekday_range[key][remain.bento_id]['remain'] = remain.dp_remain

                total_orders[dp.distribution_place] = weekday_range

        context = {
            "title": "當週出貨統計",
            "total_orders": total_orders
        }

    # print(total_orders)

    return render(request, 'order/backend_weekly_output_stats.html', context)


def backend_bento_transfer(request, add_days=0):
    if not request.user.is_authenticated:
        state = uuid4().hex
        return redirect(get_line_login_api_url(request, state, 'order', 'backend_main_view'))
    else:
        if not request.user.is_staff:
            context = {
                "title": "您沒有查閱權限",
                "message": "此頁面必須具有員工身分方能查閱。"
            }
            return render(request, 'order/message.html', context)
        else:
            date = get_taiwan_current_datetime().date() + timedelta(days=add_days)

            if request.method == "GET":
                dp_list = []
                for dp in DistributionPlace.objects.all():
                    temp = {}
                    temp['name'] = dp.distribution_place
                    temp['id'] = dp.id
                    dp_list.append(temp)

                area_limitation_infos = []

                for area in Area.objects.all():
                    area_limitation_info = {}
                    area_limitation_info['area'] = area
                    area_limitation_info['dps'] = {}
                    for dp in DistributionPlace.objects.filter(area=area):
                        dp_limitations = DPlimitation.objects.filter(distribution_place=dp,
                                                                     bento__date=date)
                        area_limitation_info['dps'][dp.distribution_place] = []
                        for dpl in dp_limitations:
                            totoal_order_number = Order.objects.filter(
                                bento=dpl.bento, distribution_place=dp, delete_time=None,
                                bento__date=date).aggregate(Sum('number'))['number__sum']
                            totoal_order_number = 0 if totoal_order_number == None else totoal_order_number
                            temp = {}
                            temp['bento_name'] = dpl.bento.name
                            temp['bento_type'] = dpl.bento.bento_type
                            temp['total_order_number'] = totoal_order_number
                            temp['remain_number'] = dpl.dp_remain
                            temp['dp_limitation'] = dpl.dp_limitation

                            area_limitation_info['dps'][dp.distribution_place].append(
                                temp)

                    area_limitation_infos.append(area_limitation_info)

                # print(dp_list)
                context = {
                    'title': '調貨頁面',
                    'Date': date,
                    'days_from_today': add_days,
                    'Area_limitation_infos': area_limitation_infos,
                    'dp_list': dp_list
                }
                return render(request, 'order/backend_bento_transfer.html/', context)
            if request.method == "POST":
                context = {
                    'title': '調貨頁面',
                }
                return render(request, 'order/backend_bento_transfer.html', context)


def backend_transfer_change(request):
    if not request.user.is_authenticated:
        state = uuid4().hex
        return redirect(get_line_login_api_url(request, state, 'order', 'backend_main_view'))
    else:
        if not request.user.is_staff:
            context = {
                "title": "您沒有查閱權限",
                "message": "此功能必須具有員工身分方能使用。"
            }
            return render(request, 'order/message.html', context)
        else:
            post_data = request.POST
            post_data = post_data.dict()
            filed = post_data['filed']
            days_from_today = post_data['days_from_today']
            date = get_taiwan_current_datetime() + timedelta(days=int(days_from_today))
            if filed == 'transferFrom':
                dp_id = post_data['from']
                bentos_in_dp = DPlimitation.objects.filter(
                    bento__date=date, distribution_place=dp_id)

                bento_list = []
                for dpl in bentos_in_dp:
                    tmp = {}
                    tmp['name'] = dpl.bento.name
                    tmp['id'] = dpl.bento.id
                    tmp['remain'] = dpl.dp_remain
                    bento_list.append(tmp)

                response = {
                    'bento_list': bento_list,
                    'success': 'success'
                }

                return HttpResponse(json.dumps(response), content_type='application/json')
            elif filed == 'submit':
                dp_from = int(post_data['from'])
                dp_to = int(post_data['to'])
                bento = int(post_data['bento'])
                number = int(post_data['number'])

                # check if out of stock
                remain_dp_from = DPlimitation.objects.get(
                    bento=bento, bento__date=date, distribution_place=dp_from).dp_remain

                if remain_dp_from >= int(number):
                    dpl_from = DPlimitation.objects.get(
                        bento=bento, bento__date=date, distribution_place=dp_from)
                    dpl_to = DPlimitation.objects.get(
                        bento=bento, bento__date=date, distribution_place=dp_to)
                    al_dpl_from = AreaLimitation.objects.get(
                        bento=bento, bento__date=date, area=dpl_from.area)
                    al_dpl_to = AreaLimitation.objects.get(
                        bento=bento, bento__date=date, area=dpl_to.area)

                    dpl_from.dp_remain -= number
                    dpl_from.dp_limitation -= number
                    dpl_from.save()

                    dpl_to.dp_remain += number
                    dpl_to.dp_limitation += number
                    dpl_to.save()

                    al_dpl_from.limitation -= number
                    al_dpl_from.remain -= number
                    al_dpl_from.save()

                    al_dpl_to.limitation += number
                    al_dpl_to.remain += number
                    al_dpl_to.save()

                    if_success = True
                    message = "調貨完成"
                else:
                    if_success = False
                    message = "調貨地區便當數量不足，請重新選擇"

                response = {
                    'success': if_success,
                    'message': message
                }

                return HttpResponse(json.dumps(response), content_type='application/json')


# ------------------------followings are line bot---------------------------------------------

def _handle_follow_event(event):
    line_id = event.source.user_id
    profile = line_bot_api.get_profile(line_id)

    profile_exists = User.objects.filter(username=line_id).count() != 0
    if profile_exists:
        user = User.objects.get(username=line_id)
        line_profile = LineProfile.objects.get(user=user)
        line_profile.line_name = profile.display_name
        line_profile.line_picture_url = '' if profile.picture_url is None else profile.picture_url
        line_profile.line_status_message = profile.status_message
        line_profile.unfollow = False
        line_profile.friend = True
        line_profile.save()
    else:
        user = User(username=line_id)
        user.save()
        line_profile = LineProfile(
            line_id=line_id,
            line_name=profile.display_name,
            line_picture_url='' if profile.picture_url is None else profile.picture_url,
            line_status_message=profile.status_message,
            friend=True,
            user=user
        )
        line_profile.save()


def _handle_unfollow_event(event):
    line_id = event.source.user_id
    profile_exists = User.objects.filter(username=line_id).count() != 0
    if profile_exists:
        line_profile = LineProfile.objects.get(line_id=line_id)
        line_profile.unfollow = True
        line_profile.friend = False
        line_profile.save()
    else:
        user = User(username=line_id)
        user.save()
        line_profile = LineProfile(
            line_id=line_id,
            line_name=profile.display_name,
            line_picture_url='' if profile.picture_url is None else profile.picture_url,
            line_status_message=profile.status_message,
            friend=False,
            user=user
        )
        line_profile.save()
    


# handle message and event


def _handle_text_msg(event, request):
    line_id = event.source.user_id
    profile = line_bot_api.get_profile(line_id)
    
    if User.objects.filter(username = line_id).count() == 0:
        user = User(username=line_id)
        user.save()
        line_profile = LineProfile(
            line_id=line_id,
            line_name=profile.display_name,
            line_picture_url='' if profile.picture_url is None else profile.picture_url,
            line_status_message=profile.status_message,
            friend=True,
            user=user
        )
        line_profile.save()
    
    user = User.objects.get(username = line_id)
    text = event.message.text
    reply = True

    if text == "動作: 馬上訂購":
        messages = get_area_reply_messages(request, user)
    elif text == "動作: 本週菜色":
        messages = get_weekly_bentos_reply()
    elif text == "動作: 我的訂單":
        messages = get_order_list_reply(user)
    elif text == "動作: 查看取餐地點":
        messages = get_dp_images()
    elif text == "動作: 關於初衷":
        text_content = "小農飯盒，是個大學生組成的團隊，我們解決人們均衡飲食的問題，而一切的初衷，是希望為台灣，創造一個更透明、安全、環境友善的飲食環境。\n\n ❓ 什麼是好的食物？好的食物該怎樣被生產，好的食物該包含哪些營養？這是我們一直在追尋的。\n\n 💫 為了這個答案，小農飯盒走訪全台，和專業的農業團隊合作，找到正在落實「友善耕作」的農民，和他們一同用科學化的方式管理農地，試圖去減少化學及石化資源的使用，努力去創造一個能永續循環的生產系統。短期內或許犧牲部分產量，但長期來看也避免了土壤礦物質含量不均，甚至是土壤鹽化的問題。\n\n除此之外，非食品相關科系的我們，去考了廚師證照、更請營養師規劃菜色，並隨時與合作餐廳溝通調整，設計出符合大學生的均衡餐點，調高蔬菜的比例，調低烹調用油、鹽的比例，同時設計特別的菜色，讓大家吃到均衡、吃到美味、更吃的無負擔。\n\n總結來說：我們想做的，就是讓大家從飲食出發，用更好的選擇、過更好的生活！😁"
        messages = [TextSendMessage(text=text_content)]
    else:
        reply = False

    if reply == True:                
        line_bot_api.reply_message(
            event.reply_token,
            messages
        )


def _handle_postback_event(event, request):
    postback_data = parse_url_query_string(event.postback.data)
    # 下面這個狀況不會發生，Line 會直接把學校的order_create link回傳給User
    if postback_data['action'] == 'get_area_reply_messages':
        area_id = postback_data['area_id']
        messages = get_distribution_place_reply_messages(request, area_id)

    elif postback_data['action'] == 'order_delete':
        line_id = event.source.user_id
        order_id = int(postback_data['id'])
        message = delete_order(order_id, line_id)
        messages = [message]

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
                    _handle_text_msg(event, request)
            #     if isinstance(event.message, LocationMessage):
            #         _handle_location_msg(event)
            if isinstance(event, FollowEvent):
                _handle_follow_event(event)
            if isinstance(event, UnfollowEvent):
                _handle_unfollow_event(event)
            if isinstance(event, PostbackEvent):
                _handle_postback_event(event, request)
        return HttpResponse()
    else:
        return HttpResponseBadRequest()
