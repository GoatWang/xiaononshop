from linebot import LineBotApi, WebhookParser  # WebhookHanlder
from django.conf import settings
line_bot_api = LineBotApi(settings.LINE_CHANNEL_ACCESS_TOKEN)
from datetime import datetime, timedelta, timezone
from order.models import (Job, LineProfile, BentoType, Bento,
                          Area, DistributionPlace, AreaLimitation, Order, DPlimitation)

from linebot.models import TextSendMessage

weekday_zh_mapping = {
    0: "一",
    1: "二",
    2: "三",
    3: "四",
    4: "五",
    5: "六",
    6: "日"
}

college_simplify_mapping = {
    "國立臺灣大學": "臺大",
    "國立政治大學": "政大",
    "國立臺北教育大學": "北教大",
    "國立台灣師範大學": "師大",
}

def date_to_zh_string(date):
    """accept datetime or date filed"""
    return str(date.month) + "月" + str(date.day) + "日" + "(" + weekday_zh_mapping[date.weekday()] + ")"

def date_to_url_string(date):
    return str((date.year, date.month, date.day))

def url_string_to_date(url_string):
    return datetime(*eval(url_string))

def parse_url_query_string(query_string):
    data = {}
    pairs = query_string.split('&')
    for pair in pairs:
        key, value = pair.split('=')
        data[key] = value
    return data

def get_order_detail(date_string, area_id, distribution_place_id, bento_id, order_number, line_id):
    user_name = line_bot_api.get_profile(line_id).display_name
    bento_string = Bento.objects.get(id=bento_id).name
    area_string = Area.objects.get(id=area_id).area
    area_string = college_simplify_mapping.get(area_string, area_string)
    distrbution_place_string = DistributionPlace.objects.get(
        id=distribution_place_id).distribution_place

    order_detail = "日期: " + date_to_zh_string(url_string_to_date(date_string)) + "\n" + \
        "訂購人: " + user_name + "\n" + \
        "品項: " + bento_string + "(" + str(order_number) + "個)\n" + \
        "取餐地點: " + area_string + distrbution_place_string

    return order_detail

def check_if_block_order(lineid):
    not_received_count = Order.objects.filter(
        line_profile__line_id = lineid,
        bento__date__gt = get_taiwan_current_datetime() - timedelta(days = 30),
        bento__date__lte = get_taiwan_current_datetime() - timedelta(days = 1),
        delete_time = None,
        received = False
        ).count()
    
    if not_received_count >= 2:
        last_not_received_date = Order.objects.filter(
        line_profile__line_id = lineid,
        bento__date__gt = get_taiwan_current_datetime() - timedelta(days = 30),
        bento__date__lte = get_taiwan_current_datetime() - timedelta(days = 1),
        delete_time = None,
        received = False
        ).order_by('-bento__date')[0].bento.date
        
        next_order_date = last_not_received_date + timedelta(days = 30)
        next_order_date_str = next_order_date.strftime('%Y年%m月%d日')
        return True, next_order_date_str
    else:
        return False, None

def create_order(line_id, bento_id, order_number, area_id, distribution_place_id):
    target_line_profile = LineProfile.objects.get(line_id=line_id)
    target_bento = Bento.objects.get(id=bento_id)
    target_area = Area.objects.get(id=area_id)
    target_distribution_place = DistributionPlace.objects.get(
        id=distribution_place_id)
    area_limitation = AreaLimitation.objects.get(
        bento=target_bento, area=target_area)
    dp_limitation = DPlimitation.objects.get(
        bento=target_bento, distribution_place=target_distribution_place)

    if area_limitation.remain >= int(order_number):
        Order.objects.create(
            line_profile=target_line_profile,
            bento=target_bento,
            area=target_area,
            distribution_place=target_distribution_place,
            number=order_number
        )

        area_limitation.remain -= int(order_number)
        area_limitation.save()

        dp_limitation.dp_remain -= int(order_number)
        dp_limitation.save()

        # print("Hello")
        # print("Order.objects.all().count()", Order.objects.all().count())

        return True
    else:
        return False

def get_redirect_url(request, to):
    domain = request.META['HTTP_HOST']
    if domain.startswith("127"):
        return "http://" + domain + "/" + to
    else:
        return "https://" + domain + "/" + to

def get_line_login_api_url(request, state, app_name, view_name):
    # if 'LINE_CHANNEL_SECRET' not in os.environ:
    #     user = LineProfile.objects.get(line_id="U3df9bb2a931d31b2ca900011f6bfda83").user
    #     auth.login(request, user)
    #     return get_redirect_url(request, app_name + "/" + view_name + "/")
    # else:
    #     callback = get_redirect_url(request, "/order/line_login_callback/" + app_name + "/" + view_name + "/")
    #     return "https://access.line.me/oauth2/v2.1/authorize?response_type=code&client_id=1594806265&redirect_uri=" + callback + "&state=" + state + "&scope=openid"
    callback = get_redirect_url(
        request, "order/line_login_callback/" + app_name + "/" + view_name + "/")
    return "https://access.line.me/oauth2/v2.1/authorize?response_type=code&client_id="+settings.LINE_LOGIN_CHANNEL_ID+"&redirect_uri=" + callback + "&state=" + state + "&scope=openid&bot_prompt=aggressive"

def delete_order(order_id, line_id):
    order = Order.objects.get(id=order_id)
    if order.delete_time is None:
        order.delete_time = datetime.now()
        order.save()
        area_limitation = AreaLimitation.objects.get(
            bento=order.bento, area=order.area)
        area_limitation.remain += order.number
        area_limitation.save()

        dp_limitation = DPlimitation.objects.get(
            bento=order.bento, distribution_place=order.distribution_place)
        dp_limitation.dp_remain += order.number
        dp_limitation.save()
        
        message_date = str(order.bento.date.month) + \
        "/" + str(order.bento.date.day)
        message = TextSendMessage(
            text="您已成功取消「" + message_date + " " + order.bento.name + "」訂單!")
        return message

    else:
        message_date = str(order.bento.date.month) + \
        "/" + str(order.bento.date.day)
        message = TextSendMessage(
            text= message_date + " 的訂單 " + order.bento.name + "已經取消過囉!")
        return message




def get_taiwan_current_datetime():
    dt = datetime.utcnow()
    dt = dt.replace(tzinfo=timezone.utc)
    tzutc_8 = timezone(timedelta(hours=8))
    local_dt = dt.astimezone(tzutc_8)
    return local_dt
    # return datetime.utcnow() + (datetime(2005,1,1,8) - datetime(2005,1,1,0))

def get_datetime_filter():
    current_time = get_taiwan_current_datetime()
    weekday = current_time.weekday()
    if weekday == 0:
        n = 4
    elif weekday == 1:
        n = 3
    elif weekday == 2:
        n = 2
    elif weekday == 3:
        n = 1
    elif weekday == 4:
        n = 7
    elif weekday == 5:
        n = 6
    elif weekday == 6:
        n = 5
    return n
    # return current_time + timedelta(n)

def get_current_week_daterange():
    dt = get_taiwan_current_datetime()
    start = dt - timedelta(days=dt.weekday())
    end = start + timedelta(days=6)
    return start, end

def weekday_to_zhweekday(weekday):
    return "星期" + weekday_zh_mapping[weekday]

def get_push_notification_list():
    customer_list = []
    today = datetime.today().date()
    order_ppl_today = list(Order.objects.filter(
        bento__date=today,
        delete_time=None,
        received = False
    ).values_list(
        'line_profile',
        'line_profile__line_name',
    ).distinct())
    
    for customer in order_ppl_today:
        customer_info = {
            'name': None,
            'line_id': None,
            'orders': []
        }

        customer_info['line_id'] = customer[0]
        customer_info['name'] = customer[1]

        customer_orders = list(Order.objects.filter(
            bento__date=today,
            line_profile__line_id=customer_info['line_id'],
            delete_time=None,
            received = False
            ).order_by('distribution_place__distribution_place').
            values_list(
                'distribution_place__distribution_place',
                'bento__name',
                'number',
            ))
        for order in customer_orders:
            temp = {
                'dp': None,
                'bento': None,
                'quantity': 0
            }
            temp['dp'] = order[0]
            temp['bento'] = order[1]
            temp['quantity'] = order[2]
            customer_info['orders'].append(temp)

        customer_list.append(customer_info)
    return customer_list

def get_first_dp_in_area(area_id):
    return DistributionPlace.objects.filter(area_id = area_id)[0]