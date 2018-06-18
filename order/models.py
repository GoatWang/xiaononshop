from django.db import models
from django.contrib.auth.models import User
from django.db import models
import os
from uuid import uuid4

class Job(models.Model):
    job = models.CharField(max_length=10)
    def __str__(self):
        return str(self.job)

class LineProfile(models.Model):
    # user = models.OneToOneField(User, on_delete=models.CASCADE)
    line_id = models.CharField(max_length=50, primary_key=True, verbose_name="LineID")
    line_name = models.CharField(max_length=100, verbose_name="Line名稱")
    line_picture_url = models.URLField(verbose_name="Line照片網址")
    line_status_message = models.CharField(max_length=100, blank=True, null=True, verbose_name="Line狀態訊息")
    email = models.EmailField(blank=True, null=True, verbose_name="電子郵件")
    phone = models.CharField(max_length=15, blank=True, null=True, verbose_name="電話")
    job = models.ForeignKey('Job', blank=True, null=True, on_delete=models.CASCADE, verbose_name="職業")
    state = models.CharField(max_length=10, blank=True, null=True, verbose_name="狀態")
    unfollow = models.BooleanField(default=False, verbose_name="封鎖")
    create_time = models.DateTimeField(auto_now=True, verbose_name="創建時間")
    def __str__(self):
        return str(self.line_name)

class BentoType(models.Model):
    bento_type = models.CharField(max_length=10)
    def __str__(self):
        return str(self.bento_type)

def image_path_wrapper(instance, filename):
    ext = filename.split('.')[-1]
    filename = '{}.{}'.format(instance.name + "_" + str(instance.date) + "_" + uuid4().hex, ext)
    return os.path.join("bento_imgs/", filename)
class Bento(models.Model):
    date = models.DateField(verbose_name="日期")
    name = models.CharField(max_length=100, verbose_name="名稱")
    bento_type = models.ForeignKey("BentoType", on_delete=models.CASCADE, verbose_name="類型")
    cuisine = models.TextField(max_length=200, verbose_name="菜色")
    photo = models.ImageField(upload_to=image_path_wrapper, verbose_name="照片")
    price = models.IntegerField(default=120, verbose_name="價格")
    ready = models.BooleanField(default=False, verbose_name="上架")
    def __str__(self):
        return str(self.date) + "_" + str(self.name)
    
class Area(models.Model):
    area = models.CharField(max_length=10, verbose_name="地區")
    def __str__(self):
        return str(self.area)

class DistributionPlace(models.Model):
    area = models.ForeignKey('Area', on_delete=models.CASCADE, verbose_name="地區")
    distribution_place = models.CharField(max_length=20, verbose_name="發放地點")
    def __str__(self):
        return str(self.area) + "_" + str(self.distribution_place)

class AreaLimitation(models.Model):
    bento = models.ForeignKey('Bento', on_delete=models.CASCADE, verbose_name="飯盒")
    area = models.ForeignKey('Area', on_delete=models.CASCADE, verbose_name="地區")
    remain = models.IntegerField(verbose_name="剩於個數")
    limitation = models.IntegerField(verbose_name="上限個數")
    def __str__(self):
        return str(self.bento) + "_" + str(self.area)
    class Meta:
        unique_together = (("bento", "area"),)
    
class Order(models.Model):
    line_profile = models.ForeignKey('LineProfile', on_delete=models.CASCADE, verbose_name="Line名稱")
    bento = models.ForeignKey('Bento', on_delete=models.CASCADE, verbose_name="飯盒")
    area = models.ForeignKey("Area", on_delete=models.CASCADE, verbose_name="地區")
    distribution_place = models.ForeignKey("DistributionPlace", on_delete=models.CASCADE, verbose_name="發放地點")
    number = models.IntegerField(verbose_name="數量")
    create_time = models.DateTimeField(auto_now_add=True, verbose_name="創建時間")
    def __str__(self):
        return str(self.line_profile) + "_" + str(self.bento) + "_" + str(self.number)



    


