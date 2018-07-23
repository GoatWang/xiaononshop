from xiaonon import settings
from order.models import Job, LineProfile, BentoType, Bento, Area, DistributionPlace, AreaLimitation, Order
from django.db.models import Sum

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

from datetime import datetime, timedelta
from order.utl import weekday_zh_mapping, college_simplify_mapping, date_to_zh_string, date_to_url_string, url_string_to_date, get_order_detail, get_redirect_url

def get_area_reply_messages():
    areas = Area.objects.all()
    messages_count = len(areas) // 4
    messages_count = messages_count + 1 if len(areas) %4 != 0 else messages_count
    messages_with_btns = []
    for i in range(messages_count):
        messages_with_btns.append(areas[i*4:(i+1)*4].copy())

    messages = []
    for message_with_btns in messages_with_btns:
        actions = []
        for btn in message_with_btns:
            remain = sum(AreaLimitation.objects.filter(area=btn, bento__date__gt=datetime.now().date(), bento__date__lte=datetime.now()+timedelta(5)).values_list('remain', flat=True))
            label = btn.area+"(餘"+ str(remain) +"個)" if remain < 20 else btn.area
            actions.append(
                    PostbackTemplateAction(
                            label= label,
                            data= "action=get_area_reply_messages&area_id="+str(btn.id)
                        )
                    )
        
        buttons_template_message = TemplateSendMessage(
                alt_text='學校選擇',
                template=ButtonsTemplate(
                    title='學校選擇',
                    text='請問你想在哪一間學校領取小農飯盒呢?',
                    actions=actions
                )
            )
        messages.append(buttons_template_message)
    return messages


def get_distribution_place_reply_messages(request, area_id):
    availables_distribution_places = DistributionPlace.objects.filter(area=int(area_id))
    availables_distribution_places_len = len(availables_distribution_places)

    messages_count = availables_distribution_places_len // 4
    messages_count = messages_count + 1 if availables_distribution_places_len%4 != 0 else messages_count

    messages_with_btns = []
    for i in range(messages_count):
        messages_with_btns.append(availables_distribution_places[i*4:(i+1)*4].copy())

    messages = []
    for message_with_btns in messages_with_btns:
        actions = []
        for btn in message_with_btns:
            actions.append(
                    URITemplateAction(
                            label=btn.distribution_place,
                            uri=get_redirect_url(request, 'order/order_create/'+str(area_id) + '/' + str(btn.id) + '/')
                        )
                    )
        
        buttons_template_message = TemplateSendMessage(
                alt_text='領取地點選擇',
                template=ButtonsTemplate(
                    title='領取地點選擇',
                    text='請問你想在哪一個位置領取小農飯盒呢?',
                    actions=actions
                )
            )
        messages.append(buttons_template_message)
    return messages
