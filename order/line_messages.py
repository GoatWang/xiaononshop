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

from datetime import datetime
from order.utl import weekday_zh_mapping, college_simplify_mapping, date_to_zh_string, date_to_url_string, url_string_to_date, get_order_detail

def get_order_date_reply_messages(event):
    maximum_futere_days_for_ordering = 14
    available_dates = sorted(list(set(Bento.objects.filter(date__gt=datetime.now().date(), ready=True).values_list('date', flat=True))))[:maximum_futere_days_for_ordering]
    available_dates_len = len(available_dates)
    
    if available_dates_len <= 0:
        return [TextSendMessage(text="近期沒有供應餐盒，開學才會開始供應餐盒喔!")]

    messages_count = available_dates_len // 4
    messages_count = messages_count + 1 if available_dates_len%4 != 0 else messages_count

    messages_with_btns = []
    for i in range(messages_count):
        messages_with_btns.append(available_dates[i*4:(i+1)*4].copy())

    messages = []
    for message_with_btns in messages_with_btns:
        actions = []
        for btn in message_with_btns:
            actions.append(
                    PostbackTemplateAction(
                            label=date_to_zh_string(btn),
                            data= 'action=get_order_date_reply_messages&date_string='+date_to_url_string(btn)
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

def get_area_reply_messages(event, date_string):
    date = url_string_to_date(date_string)
    bentos = Bento.objects.filter(date=date, ready=True)
    area_limitations = AreaLimitation.objects.filter(bento__in=bentos).values('area__id', 'area__area').annotate(total_remain=Sum('remain')).filter(total_remain__gt=0)
    # available_area_limitations = [(al['area__area'], al['total_remain']) for al in list(area_limitations) if al['total_remain'] > 0]
    available_area_limitations = list(area_limitations)
    available_area_limitations_len = len(available_area_limitations)

    messages_count = available_area_limitations_len // 4
    messages_count = messages_count + 1 if available_area_limitations_len%4 != 0 else messages_count

    messages_with_btns = []
    for i in range(messages_count):
        messages_with_btns.append(available_area_limitations[i*4:(i+1)*4].copy())

    messages = []
    for message_with_btns in messages_with_btns:
        actions = []
        for btn in message_with_btns:
            actions.append(
                    PostbackTemplateAction(
                            label=college_simplify_mapping.get(btn['area__area'], btn['area__area']) + '(剩餘' + str(btn['total_remain']) + '個)',
                            data= 'action=get_area_reply_messages&date_string='+date_string+"&area_id="+str(btn['area__id'])
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


def get_distribution_place_reply_messages(event, date_string, area_id):
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
                    PostbackTemplateAction(
                            label=btn.distribution_place,
                            data= 'action=get_distribution_place_reply_messages&date_string='+date_string+"&area_id="+str(area_id)+"&distribution_place_id="+str(btn.id)
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


def get_bento_reply_messages(event, date_string, area_id, distribution_place_id):
    date = url_string_to_date(date_string)
    available_bentos = AreaLimitation.objects.filter(area=int(area_id), bento__date=date, bento__ready=True).reverse().values('bento__id', 'bento__name', 'bento__bento_type__bento_type', 'bento__cuisine', 'bento__photo', 'bento__price', 'remain')
    available_bentos = sorted(available_bentos, key=lambda x:x['remain'], reverse=True)

    carousel_columns = []
    for bento in available_bentos:
        if bento['remain'] > 0:
            carousel_column = CarouselColumn(
                thumbnail_image_url='https://s3.amazonaws.com/xiaonon/' + bento['bento__photo'],
                title=bento['bento__name'] + '(剩餘'+ str(bento['remain']) + '個)',
                # text="類型: " + bento['bento__bento_type__bento_type'] + "\n" + "價格: " + str(bento['bento__price']) + "元\n" + "配菜: " + bento['bento__cuisine'],
                text=bento['bento__bento_type__bento_type'] + str(bento['bento__price']) + "元\n" + bento['bento__cuisine'],
                actions=[
                    PostbackTemplateAction(
                        label='我要吃這個',
                        data='action=get_bento_reply_messages&date_string='+date_string+"&area_id="+str(area_id)+"&distribution_place_id="+str(distribution_place_id)+"&bento_id="+str(bento['bento__id'])
                    ),
                ]
            )
        else:
            carousel_column = CarouselColumn(
                thumbnail_image_url='https://s3.amazonaws.com/xiaonon/' + bento['bento__photo'],
                title=bento['bento__name'] + "(已售完)",
                text=bento['bento__bento_type__bento_type'] + str(bento['bento__price']) + "元\n" + bento['bento__cuisine'],
                actions=[
                    PostbackTemplateAction(
                        label='重新開始訂購流程',
                        text ='動作: 開始訂購',
                        data ='action=restart'
                        # data='action=get_distribution_place_reply_messages&date_string='+date_string+"&area_id="+str(area_id)+"&distribution_place_id="+str(distribution_place_id)+"&bento_id="+str(bento['bento__id'])
                    ),
                ]
            )
        carousel_columns.append(carousel_column)
    carousel_template_message = TemplateSendMessage(
        alt_text='飯盒類型選擇',
        template=CarouselTemplate(
            columns=carousel_columns
        )
    )
    print(carousel_template_message)
    messages = [carousel_template_message]
    return messages


def get_order_number_messages(event, date_string, area_id, distribution_place_id, bento_id):
    order_count = 7
    availables_order_count = [i+1 for i in range(order_count)]
    # availables_order_count.append(-1) # 更多數量
    availables_order_count_len = len(availables_order_count)

    messages_count = availables_order_count_len // 4
    messages_count = messages_count + 1 if availables_order_count_len%4 != 0 else messages_count

    messages_with_btns = []
    for i in range(messages_count):
        messages_with_btns.append(availables_order_count[i*4:(i+1)*4].copy())

    messages = []
    for message_with_btns in messages_with_btns:
        actions = []
        for btn in message_with_btns:
            if btn > 0:
                actions.append(
                        PostbackTemplateAction(
                                label=str(btn) + "個",
                                data= 'action=get_order_number_messages&date_string='+date_string+"&area_id="+str(area_id)+"&distribution_place_id="+str(distribution_place_id)+"&bento_id="+str(bento_id)+'&order_number=' + str(btn)
                            )
                        )
            else: # '更多數量'
                # actions.append(
                #         PostbackTemplateAction(
                #                 label=str(btn),
                #                 data= 'action=get_order_number_messages&date_string='+date_string+"&area_id="+str(area_id)+"&distribution_place_id="+str(distribution_place_id)+"&bento_id="+str(bento_id)+'&order_number=' + str(-1)
                #             )
                #         )
                pass

        buttons_template_message = TemplateSendMessage(
                alt_text='訂購個數選擇',
                template=ButtonsTemplate(
                    title='訂購個數選擇',
                    text='想吃幾個餐盒呢?',
                    actions=actions
                )
            )
        messages.append(buttons_template_message)
    return messages

def get_order_confirmation_messages(event, date_string, area_id, distribution_place_id, bento_id, order_number, line_id):
    order_detail = get_order_detail(date_string, area_id, distribution_place_id, bento_id, order_number, line_id)
    confirm_text = "請確認以下訂單資訊: \n" + order_detail
    
    confirm_template_message = TemplateSendMessage(
        alt_text='訂單確認',
        template=ConfirmTemplate(
            text=confirm_text,
            actions=[
                PostbackTemplateAction(
                    label='確認',
                    data= 'action=get_order_confirmation_messages&date_string='+date_string+"&area_id="+str(area_id)+"&distribution_place_id="+str(distribution_place_id)+"&bento_id="+str(bento_id)+'&order_number=' + str(order_number)
                ),
                MessageTemplateAction(
                    label='取消',
                    text='動作: 開始訂購'
                )
            ]
        )
    )

    messages = [confirm_template_message]
    return messages