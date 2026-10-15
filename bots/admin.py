from django.contrib import admin
from .models import Chatbot, Intent, Example, Slot, Response, Rule, ChatMessage

for m in (Chatbot, Intent, Example, Slot, Response, Rule, ChatMessage):
    admin.site.register(m)
