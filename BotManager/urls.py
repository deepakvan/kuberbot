from . import views
from django.urls import path

urlpatterns = [
    path('', views.home),
]


# import threading
# from .views import bot
# threading.Thread(target=bot).start()


