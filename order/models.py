from django.db import models
from django.contrib.auth.models import User
from django.db import models

class LineProfile(models.Model):
    # user = models.OneToOneField(User, on_delete=models.CASCADE)
    line_id = models.CharField(max_length=50, primary_key=True)
    line_name = models.CharField(max_length=100)
    picture_url = models.URLField()
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=15, blank=True)
    GRADE_CHOICES = (
        ("G", "Graduate"), 
        ("U", "UnderGraduate"),
        ("P", "Professor"), 
        ("O", "Other")
        )
    grade = models.CharField(max_length=1, choices=GRADE_CHOICES, blank=True)
    state = models.CharField(max_length=10, blank=True)
    unfollow = models.BooleanField(default=False)

class Bento(models.Model):
    name = models.TextField(max_length=100)
    bento_type = models.CharField(max_length=1, choices=(('L', 'Light'),('B', 'Balance')), default='L')
    cuisine = models.TextField(max_length=200)
    photo = models.ImageField(upload_to="bento_imgs/")
    description = models.TextField(max_length=200)

class DailyMenu(models.Model):
    date = models.DateField(auto_now=True)
    bento = models.ForeignKey('Bento', on_delete=models.CASCADE)
    remain = models.IntegerField()

class Order(models.Model):
    line_profile = models.ForeignKey('LineProfile', on_delete=models.CASCADE)
    daily_menu = models.ForeignKey('DailyMenu', on_delete=models.CASCADE)
    create_time = models.DateTimeField(auto_now=True)



