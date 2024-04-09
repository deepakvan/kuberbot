from django.apps import AppConfig
#import threading

class BotmanagerConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'BotManager'
    #run_already = False

    # def ready(self):
    #     if BotmanagerConfig.run_already: return
    #     BotmanagerConfig.run_already = True
    #     #print("Hello")
    #     from .views import bot
    #     threading.Thread(target=bot).start()
    #     pass