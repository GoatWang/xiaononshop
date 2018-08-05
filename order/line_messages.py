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



def get_order_list_reply(request):
    user = request.user
    current_orders = list(Order.objects.filter(line_profile__user=user, delete_time=None, bento__date__gt=datetime.now()-timedelta(1)).values_list('id', 'number', 'price', 'bento__date', 'bento__photo', 'bento__name', 'bento__bento_type__bento_type', 'bento__cuisine', named=True).order_by('bento__date')[:5])
    if len(current_orders) == 0:
        messages = [TextSendMessage(text="您近期還沒有新的訂單喔~")]
    else:
        df_current_orders = pd.DataFrame(current_orders)
        df_current_orders['row_id'] = pd.Series(df_current_orders.index).apply(lambda x:x+1)
        df_current_orders['date'] = df_current_orders['bento__date'].apply(lambda x:str(x.month) + '/' + str(x.day))
        df_current_orders['photo'] = df_current_orders['bento__photo']
        df_current_orders['name'] = df_current_orders['bento__name']
        df_current_orders['type'] = df_current_orders['bento__bento_type__bento_type']
        df_current_orders['number'] = df_current_orders['number']
        df_current_orders['cuisine'] = df_current_orders['bento__cuisine']
        df_current_orders['today'] = df_current_orders['bento__date'].apply(lambda x:x==datetime.now().date())
        df_current_orders = df_current_orders[['row_id', 'id','date','name','type', 'price','number','cuisine', 'today']]
        current_orders = df_current_orders.T.to_dict().values

        CarouselColumns = []
        for order in current_orders:
            ccol = CarouselColumn(
                        thumbnail_image_url=order['photo'],
                        title='this is menu1',
                        text='description1',
                        actions=[
                            PostbackTemplateAction(
                                label='取消訂單',
                                data='action=order_delete&id=' + str(order['id'])
                            )
                        ]
                    )

        carousel_template_message = TemplateSendMessage(
            alt_text='Carousel template',
            template=CarouselTemplate(
                columns=[
                    CarouselColumn(
                        thumbnail_image_url='https://example.com/item1.jpg',
                        title='this is menu1',
                        text='description1',
                        actions=[
                            PostbackAction(
                                label='postback1',
                                text='postback text1',
                                data='action=buy&itemid=1'
                            ),
                            MessageAction(
                                label='message1',
                                text='message text1'
                            ),
                            URIAction(
                                label='uri1',
                                uri='http://example.com/1'
                            )
                        ]
                    ),
                    CarouselColumn(
                        thumbnail_image_url='https://example.com/item2.jpg',
                        title='this is menu2',
                        text='description2',
                        actions=[
                            PostbackAction(
                                label='postback2',
                                text='postback text2',
                                data='action=buy&itemid=2'
                            ),
                            MessageAction(
                                label='message2',
                                text='message text2'
                            ),
                            URIAction(
                                label='uri2',
                                uri='http://example.com/2'
                            )
                        ]
                    )
                ]
            )
        )