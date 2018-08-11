# generate bento
from datetime import datetime, timedelta
from order.models import Bento, AreaLimitation, Area

bentos = Bento.objects.filter(date__lt=datetime(2018, 7, 12, 7))
added_days = datetime.now().date() - bentos[0].date + 1
for b in bentos:
    new_b = Bento(name=b.name, date=b.date + timedelta(added_days), bento_type=b.bento_type, cuisine=b.cuisine, photo=b.photo, price=b.price, ready=b.ready)
    new_b.save()

bentos = Bento.objects.filter(date__gt=datetime.now())
for b in bentos:
    for a in Area.objects.all():
            al = AreaLimitation(bento=b, area=a, remain=50, limitation=50)
            al.save()