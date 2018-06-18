from django.shortcuts import render
from django.http import HttpResponse, HttpResponseBadRequest, HttpResponseForbidden, JsonResponse
from django.views.decorators.csrf import csrf_exempt

from xiaonon import settings
from order.models import Job, LineProfile, BentoType, Bento, Area, DistributionPlace, AreaLimitation, Order

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
from order.line_messages import get_order_date_reply_messages

def index(request):
    return HttpResponse("Hello, world. You're at the polls index.")


def parse_url_query_string(query_string):
    data = {}
    pairs = query_string.split('&')
    for pair in pairs:
        key, value = pair.split('=')
        data[key] = value
    return data

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
    user_name = line_bot_api.get_profile(line_id).display_name

    if text == "動作: 開始訂購":
        messages = get_order_date_reply_messages(event)
        
    #     "香茅檸檬嫩雞"
    #     "紅麴燒豬肉"
    # elif text == "動作: 飯盒菜單":
    # elif text == "動作: 聯絡我們":
    # messages = [TextSendMessage(text=user_name+": "+text)]
    line_bot_api.reply_message(
        event.reply_token,
        messages
    )

def _handle_postback_event(event):
    line_id = event.source.user_id
    user_name = line_bot_api.get_profile(line_id).display_name

    user_searching_status = LineProfile.objects.get(line_id=line_id).state
    print(event.postback.data)
    postback_data = parse_url_query_string(event.postback.data)
    print(postback_data)
    
    if postback_data['action'] == 'get_order_date_reply_messages':
        messages = TextSendMessage(text=postback_data['date'])
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


