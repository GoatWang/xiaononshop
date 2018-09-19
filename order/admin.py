from django.contrib import admin
from django import forms
import json
from datetime import datetime, timedelta
from order.models import Job, LineProfile, BentoType, Bento, Area, DistributionPlace, AreaLimitation, Order, DPlimitation
from django.db.models import Sum

admin.site.register(Job)

# --------------------------------------------------------------------------
# LineProfile
class LineProfileAdmin(admin.ModelAdmin):
    list_display = ['line_name', 'email', 'phone', 'job', 'unfollow', 'create_time']
    ordering = ['line_name', 'email', 'phone', 'job', 'unfollow', 'create_time']

admin.site.register(LineProfile, LineProfileAdmin)
admin.site.register(BentoType)


# --------------------------------------------------------------------------
# Bento
def make_ready(modeladmin, request, queryset):
    queryset.update(ready=True)
make_ready.short_description = "上架"
def make_non_ready(modeladmin, request, queryset):
    queryset.update(ready=False)
make_non_ready.short_description = "下架"

class BentoModelForm(forms.ModelForm):
    # initiate distribution place number
    def __init__(self, *args, **kwargs):
        super(BentoModelForm, self).__init__(*args, **kwargs)
        for dp in DistributionPlace.objects.all():
            if DPlimitation.objects.filter(distribution_place=dp,bento = self.instance).exists():
                self.fields['dp_{}'.format(dp.distribution_place)].initial = DPlimitation.objects.get(distribution_place=dp,bento = self.instance).dp_limitation


    initall_data = dict([(a.distribution_place, 100)for a in DistributionPlace.objects.all()])
    set_limitation_for_all_dp = forms.BooleanField(initial=False, label="啟用下面設定限制欄位(注意: 將會同時重設「上限數量」與「剩餘數量」，勿在此便當有訂單的時候更改！！！)", required=False)

    for dp in DistributionPlace.objects.all():
        locals()['dp_{}'.format(dp.distribution_place)] = forms.IntegerField(initial= 10,label=dp)

    def save(self, commit=True):
        set_limitation_for_all_dp = self.cleaned_data.get('set_limitation_for_all_dp')
        limitation_for_all_dp_dict = {}
        limitation_for_all_area_dict = {}
        for dp in DistributionPlace.objects.all():
            limitation_for_all_dp_dict[dp.distribution_place] = self.cleaned_data.get('dp_{}'.format(dp.distribution_place))
            for a in Area.objects.all():
                if dp.area == a:
                    if a.area in limitation_for_all_area_dict:
                        limitation_for_all_area_dict[a.area] += self.cleaned_data.get('dp_{}'.format(dp.distribution_place))
                    else:
                        limitation_for_all_area_dict[a.area] = 0
                        limitation_for_all_area_dict[a.area] += self.cleaned_data.get('dp_{}'.format(dp.distribution_place))
        
        saved_bento = super(BentoModelForm, self).save()

        if set_limitation_for_all_dp:
            for dp in DistributionPlace.objects.all():
                current_limitation = limitation_for_all_dp_dict.get(dp.distribution_place, None)
                current_limitation = int(current_limitation) if current_limitation else 0
                if DPlimitation.objects.filter(bento=saved_bento, distribution_place_id = dp).exists():
                    current_dp_limitation = DPlimitation.objects.get(bento=saved_bento, distribution_place_id = dp)
                    current_dp_limitation.dp_limitation = current_limitation
                    current_dp_limitation.dp_remain = current_limitation
                    current_dp_limitation.save()
                else:
                    DPlimitation.objects.create(
                        bento=saved_bento,
                        area = dp.area,
                        dp_limitation = current_limitation,
                        dp_remain = current_limitation,
                        distribution_place = dp)
            
            for area in Area.objects.all():
                area_limitation = limitation_for_all_area_dict.get(area.area, None)
                area_limitation = int(area_limitation) if area_limitation else 0
                if AreaLimitation.objects.filter(area = area, bento = saved_bento).exists():
                    current_area_limitation = AreaLimitation.objects.get(area = area, bento = saved_bento)
                    current_area_limitation.limitation = area_limitation
                    current_area_limitation.remain = area_limitation
                    current_area_limitation.save()
                else:
                    AreaLimitation.objects.create(
                        bento = saved_bento, 
                        area = area, 
                        limitation = area_limitation,
                        remain = area_limitation
                    )

        return saved_bento

    def save_m2m(self):
        pass

    class Meta:
        model = Bento
        fields = "__all__"

class BentoAdmin(admin.ModelAdmin):
    list_display = ['date', 'bento_type', 'name', 'ready']
    ordering = ['-date', 'bento_type', 'name', 'ready']
    actions = [make_ready, make_non_ready]
    form = BentoModelForm

admin.site.register(Bento, BentoAdmin)
admin.site.register(Area)



# --------------------------------------------------------------------------
# AreaLimitation
class AreaLimitationAdmin(admin.ModelAdmin):
    list_display = ["bento", "area", "limitation", "remain"]
    ordering = ["bento", "area", "limitation", "remain"]
admin.site.register(AreaLimitation, AreaLimitationAdmin)


# --------------------------------------------------------------------------
# Order
class OrderAdmin(admin.ModelAdmin):
    list_display = ["line_profile", "bento", "distribution_place", "number", "create_time"]
    ordering = ["bento", "distribution_place", "create_time"]
admin.site.register(Order, OrderAdmin)

# --------------------------------------------------------------------------
# Distribution Place
class DistributionPlaceAdmin(admin.ModelAdmin):
    list_display = ["area" ,"distribution_place", "start_time","end_time"]
    ordering = ["area" ,"distribution_place", "start_time","end_time"]

admin.site.register(DistributionPlace,DistributionPlaceAdmin)

# --------------------------------------------------------------------------
# DPlimitation
class DPlimitationAdmin(admin.ModelAdmin):
    list_display = ["bento","area" ,"distribution_place", "dp_limitation","dp_remain"]
    ordering = ["bento","area" ,"distribution_place", "dp_limitation","dp_remain"]
admin.site.register(DPlimitation,DPlimitationAdmin)

# --------------------------------------------------------------------------
# Order Custom
class CustomOrder(Order):
    class Meta:
        proxy = True

# class CustomOrderAdmin(admin.ModelAdmin):
#     list_display = ['bento', 'distribution_place', 'total_count_count']
#     # ordering = ["bento__date", "bento__name", 'area__area', "create_time"]

#     def total_count_count(self, obj):
#       return obj.total_count
#     total_count_count.short_description = 'Total Order Count'
#     # total_count_count.admin_order_field = 'total_count'

#     def queryset(self, request):
#         qs = super(CustomOrderAdmin, self).queryset(request)
#         return qs.filter(bento__date__gt=datetime.now().date()-timedelta(1)).annotate(total_count=Sum('number')) #.values('bento__date', 'bento__name', 'area__area', 'distribution_place__distribution_place', 'total_count')

# admin.site.register(CustomOrder, CustomOrderAdmin)




