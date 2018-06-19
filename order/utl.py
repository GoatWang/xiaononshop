from datetime import datetime
from order.models import Job, LineProfile, BentoType, Bento, Area, DistributionPlace, AreaLimitation, Order

weekday_zh_mapping = {
    1: "一",
    2: "二",
    3: "三",
    4: "四",
    5: "五",
    6: "六",
    7: "日"
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
