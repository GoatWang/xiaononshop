from linebot import LineBotApi, WebhookParser ##, WebhookHanlder
from xiaonon import settings
line_bot_api = LineBotApi(settings.LINE_CHANNEL_ACCESS_TOKEN)
from datetime import datetime
from order.models import Job, LineProfile, BentoType, Bento, Area, DistributionPlace, AreaLimitation, Order

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
    "國立臺灣大學":"臺大",
    "國立政治大學":"政大",
    "國立臺北教育大學":"北教大",
    "國立師範大學":"師大",
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
    distrbution_place_string = DistributionPlace.objects.get(id=distribution_place_id).distribution_place

    order_detail = "日期: " + date_to_zh_string(url_string_to_date(date_string)) + "\n" + \
                "訂購人: " + user_name + "\n" + \
                "品項: " + bento_string + "(" + str(order_number) + "個)\n" + \
                "取餐地點: " + area_string + distrbution_place_string

    return order_detail

def create_order(line_id, bento_id, order_number, area_id, distribution_place_id):
    target_line_profile = LineProfile.objects.get(line_id=line_id)
    target_bento = Bento.objects.get(id=bento_id)
    target_area = Area.objects.get(id=area_id)
    target_distribution_place = DistributionPlace.objects.get(id=distribution_place_id)

    area_limitation = AreaLimitation.objects.get(bento=target_bento, area=target_area)
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
    callback = get_redirect_url(request, "order/line_login_callback/" + app_name + "/" + view_name + "/")
    return "https://access.line.me/oauth2/v2.1/authorize?response_type=code&client_id=1594806265&redirect_uri=" + callback + "&state=" + state + "&scope=openid"


