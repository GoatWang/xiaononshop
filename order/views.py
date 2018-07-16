from django.shortcuts import render
from django.http import HttpResponse, HttpResponseBadRequest, HttpResponseForbidden, JsonResponse
from django.views.decorators.csrf import csrf_exempt

from xiaonon import settings
from order.models import Job, LineProfile, BentoType, Bento, Area, DistributionPlace, AreaLimitation, Order
from order.utl import get_order_detail, parse_url_query_string

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
from order.line_messages import get_order_date_reply_messages, get_area_reply_messages, get_distribution_place_reply_messages, get_bento_reply_messages, get_order_number_messages, get_order_confirmation_messages, get_web_create_order_messages
import numpy as np


# ------------------------following are website----------------------------------------------
def index(request):
    return HttpResponse("Hello, world. You're at the polls index.")

def order_create(request, line_id):
    if request.method == "GET":
        context = {
            'title':'多筆訂購',
            'areas':Area.objects.all()
        }
        return render(request, 'order/order_create.html', context)
    else:
        pass


# ------------------------following are line bot---------------------------------------------

def _handle_follow_event(event):
    line_id = event.source.user_id
    profile = line_bot_api.get_profile(line_id)
    
    LineProfile.objects.create(
        line_id = line_id,
        line_name = profile.display_name,
        line_picture_url = profile.picture_url,
        line_status_message=profile.status_message,
    )

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
    elif text == "動作: 多筆訂購":
        pwd = ''.join(np.random.randint(0, 9, 6).astype(str))
        line_profile.state = "web_pwd:" + pwd
        line_profile.save()
        messages = get_web_create_order_messages(event, pwd, line_id)

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

        target_line_profile = LineProfile.objects.get(line_id=line_id)
        target_bento = Bento.objects.get(id=bento_id)
        target_area = Area.objects.get(id=area_id)
        target_distribution_place = DistributionPlace.objects.get(id=distribution_place_id)

        Order.objects.create(
            line_profile=target_line_profile,
            bento=target_bento,
            area=target_area,
            distribution_place=target_distribution_place,
            number=order_number
        )

        area_limitation = AreaLimitation.objects.get(bento=target_bento, area=target_area)
        area_limitation.remain -= int(order_number)
        area_limitation.save()

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


