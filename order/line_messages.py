from xiaonon import settings
from order.models import Job, LineProfile, BentoType, Bento, Area, DistributionPlace, AreaLimitation, Order
from django.db.models import Sum
import pandas as pd

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



def get_order_list_reply(user):
    current_orders = list(Order.objects.filter(line_profile__user=user, delete_time=None, bento__date__gt=datetime.now()-timedelta(1)).values_list('id', 'number', 'bento__date', 'bento__photo', 'bento__name', 'distribution_place__distribution_place', named=True).order_by('bento__date')[:5])
    if len(current_orders) == 0:
        messages = [TextSendMessage(text="您近期還沒有新的訂單喔~")]
        return messages
    else:
        df_current_orders = pd.DataFrame(current_orders)
        df_current_orders['date'] = df_current_orders['bento__date'].apply(lambda x:str(x.month) + '/' + str(x.day))
        df_current_orders['photo'] = df_current_orders['bento__photo']
        df_current_orders['name'] = df_current_orders['bento__name']
        df_current_orders['number'] = df_current_orders['number']
        df_current_orders['distribution_place'] = df_current_orders['distribution_place__distribution_place']
        df_current_orders = df_current_orders[['id','date', 'photo', 'name','number','distribution_place']]
        current_orders = list(df_current_orders.T.to_dict().values())

        carousel_columns = []
        for order in current_orders:
            carousel_column = CarouselColumn(
                        thumbnail_image_url='https://s3-ap-southeast-1.amazonaws.com/ogbento/' + str(order['photo']),
                        title=order['date'] + ' ' + order['name'],
                        text="個數: " + str(order['number']) + "個\n取餐地點: " + order['distribution_place'],
                        actions=[
                            PostbackTemplateAction(
                                label='取消訂單',
                                data='action=order_delete&id=' + str(order['id'])
                            )
                        ]
                    )
            carousel_columns.append(carousel_column)

        carousel_template_message = TemplateSendMessage(
            alt_text='近期訂單',
            template=CarouselTemplate(
                columns=carousel_columns
            )
        )

        buttons_template_message = TemplateSendMessage(
            alt_text='查看訂單提醒',
            template=ButtonsTemplate(
                text='本頁面僅提供五筆訂單資訊，查看完整訂單資訊，請點擊下面按鈕。',
                actions=[
                    URITemplateAction(
                        label='完整訂單資訊',
                        uri=settings.DOMAIN + 'order/order_list/'
                    )
                ]
            )
        )
        return [carousel_template_message, buttons_template_message]



def get_weekly_bentos_reply():
    available_bentos = AreaLimitation.objects.filter(bento__date__gt=datetime.now(), bento__date__lte=datetime.now()+timedelta(5), bento__ready=True).values('bento__id').annotate(total_remain=Sum('remain')).values('bento__id', 'bento__name', 'bento__date', 'bento__bento_type__bento_type', 'bento__cuisine', 'bento__photo', 'bento__price', 'total_remain')
    if len(available_bentos) == 0:
        messages = [TextSendMessage(text="目前沒有便當供應，請開學後再來找我喔。")]
        return messages
    else:
        aws_url = settings.AWS_BENTO_IMG_URL
        df_available_bentos = pd.DataFrame(list(available_bentos))
        df_available_bentos['id'] = df_available_bentos['bento__id']
        df_available_bentos['name'] = df_available_bentos['bento__name']
        df_available_bentos['date'] = df_available_bentos['bento__date'].apply(lambda x:str(x.month) + '/' + str(x.day))
        df_available_bentos['bento_type'] = df_available_bentos['bento__bento_type__bento_type']
        df_available_bentos['cuisine'] = df_available_bentos['bento__cuisine']
        df_available_bentos['photo'] = df_available_bentos['bento__photo'].apply(lambda x:aws_url + x)
        df_available_bentos['price'] = df_available_bentos['bento__price']
        df_available_bentos['remain'] = df_available_bentos['total_remain'].astype(str)

        df_available_bentos = df_available_bentos[[ "id", "name", "date", "bento_type", "cuisine", "photo", "price", "remain"]]
        available_bentos = df_available_bentos.T.to_dict().values()

        carousel_columns = []
        for bento in available_bentos:
            carousel_column = CarouselColumn(
                        thumbnail_image_url=settings.AWS_BENTO_IMG_URL + str(bento['photo']),
                        title=bento['date'] + ' ' + bento['name'],
                        text=bento['bento_type'] + ": " + bento['cuisine'] + "\n" +  str(bento['price'])  + "元/個(剩" + str(bento['remain']) + "個)",
                        actions=[
                            MessageTemplateAction(
                                label='馬上訂購',
                                text='動作: 馬上訂購'
                            )
                        ]
                    )
            carousel_columns.append(carousel_column)

        carousel_template_message = TemplateSendMessage(
            alt_text='本週菜單',
            template=CarouselTemplate(
                columns=carousel_columns
            )
        )

        buttons_template_message = TemplateSendMessage(
            alt_text='查看訂單提醒',
            template=ButtonsTemplate(
                text='本頁面僅提供五筆訂單資訊，查看完整訂單資訊，請點擊下面按鈕。',
                actions=[
                    URITemplateAction(
                        label='完整訂單資訊',
                        uri=settings.DOMAIN + 'order/order_list/'
                    )
                ]
            )
        )
        return [carousel_template_message]

