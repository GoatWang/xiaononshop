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

from datetime import datetime

def index(request):
    return HttpResponse("Hello, world. You're at the polls index.")


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

def get_order_date_reply_messages(event):
    maximum_futere_days_for_ordering = 14
    available_dates = sorted(list(set(Bento.objects.filter(date__gt=datetime.now().date(), ready=True).values_list('date', flat=True))))[:maximum_futere_days_for_ordering]
    available_dates_len = len(available_dates)
    
    messages_count = available_dates_len // 4
    messages_count = messages_count + 1 if available_dates_len%4 != 0 else messages_count

    messages_with_btns = []
    for i in range(available_dates_len):
        messages_with_btns.append(available_dates[i*4:(i+1)*4].copy())

    messages = []
    for message_with_btns in messages_with_btns:
        actions = []
        for btn in message_with_btns:
            actions.append(
                    PostbackTemplateAction(
                            label=btn,
                            data='date='+str(btn)
                        )
                    )
        
        buttons_template_message = TemplateSendMessage(
                alt_text='訂餐日期選擇',
                template=ButtonsTemplate(
                    title='訂餐日期選擇',
                    text='請問哪一天想吃小農飯盒呢?',
                    actions=actions
                )
            )

        messages.append(buttons_template_message)
    return messages


# def get_bento_info(bento_id):



# def get_bento_menu(data):
#     columns = []
#     for idx, row in enumerate(data):
#         store_name = row['公司商號']
#         address = parse_address(row['地址'])
#         phone_num = parse_phone_num(row['電話'])
#         _id = str(row['_id'])

#         print(store_name)
#         print(address)
#         print(phone_num)
#         carousel = CarouselColumn(
#                     thumbnail_image_url='https://example.com/item2.jpg'
#                     title=store_name[:39],
#                     text=address[:119],
#                     actions=[

#                         PostbackTemplateAction(
#                             label='優惠項目',
#                             data='action=authorized_store_detail&_id=' + _id 
#                         )
#                     ]
#                 )
#         columns.append(carousel)
#     carousel_template_message = TemplateSendMessage(
#         alt_text='回應店家搜尋',
#         template=CarouselTemplate(columns=columns)
#     )
#     return carousel_template_message


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
            # if isinstance(event, PostbackEvent):
            #     _handle_postback_event(event)
        return HttpResponse()
    else:
        return HttpResponseBadRequest()


