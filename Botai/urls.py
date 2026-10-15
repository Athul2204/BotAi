from django.contrib import admin
from django.urls import path
from django.views.generic import RedirectView

from bots import views as b
from home import views as h

urlpatterns = [
    path('django-admin/', admin.site.urls),
    # friendly aliases: /admin and /admin/ -> admin panel
    path('admin', RedirectView.as_view(pattern_name='admin_dashboard')),
    path('admin/', RedirectView.as_view(pattern_name='admin_dashboard')),
    # auth
    path('', h.index, name='index'),
    path('signup/', h.sign, name='signup'),
    path('logout/', h.logout_view, name='logout'),
    # admin area
    path('manage/', h.admin_dashboard, name='admin_dashboard'),
    path('manage/requests/', h.admin_requests, name='admin_requests'),
    path('manage/user/<int:pk>/<str:action>/', h.admin_action, name='admin_action'),
    # chatbot owner area
    path('dashboard/', b.dashboard, name='dashboard'),
    path('chatbots/new/', b.bot_create, name='bot_create'),
    path('chatbots/<int:pk>/delete/', b.bot_delete, name='bot_delete'),
    path('chatbots/<int:pk>/', b.intents, name='intents'),
    path('chatbots/<int:pk>/intents/save/', b.intent_save, name='intent_save'),
    path('chatbots/<int:pk>/intents/<int:item>/delete/', b.intent_delete, name='intent_delete'),
    path('chatbots/<int:pk>/slots/', b.slots, name='slots'),
    path('chatbots/<int:pk>/slots/save/', b.slot_save, name='slot_save'),
    path('chatbots/<int:pk>/slots/<int:item>/delete/', b.slot_delete, name='slot_delete'),
    path('chatbots/<int:pk>/rules/', b.rules, name='rules'),
    path('chatbots/<int:pk>/rules/save/', b.rule_save, name='rule_save'),
    path('chatbots/<int:pk>/rules/<int:item>/delete/', b.rule_delete, name='rule_delete'),
    path('chatbots/<int:pk>/responses/', b.responses, name='responses'),
    path('chatbots/<int:pk>/responses/save/', b.response_save, name='response_save'),
    path('chatbots/<int:pk>/responses/<int:item>/delete/', b.response_delete, name='response_delete'),
    path('chatbots/<int:pk>/run/', b.run_bot, name='run_bot'),
    path('chatbots/<int:pk>/run/<str:action>/', b.bot_action, name='bot_action'),
    path('chatbots/<int:pk>/status/', b.bot_status, name='bot_status'),
    path('chatbots/<int:pk>/test-chat/', b.bot_test_chat, name='bot_test_chat'),
    path('chatbots/<int:pk>/chats/', b.chats, name='chats'),
    # public API used by other websites
    path('api/chat/<uuid:key>/', b.public_chat, name='public_chat'),
    path('widget/<uuid:key>.js', b.widget_js, name='widget_js'),
]
