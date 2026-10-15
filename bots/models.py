import uuid
from django.contrib.auth.models import User
from django.db import models


class Chatbot(models.Model):
    TRAIN = [('idle', 'idle'), ('training', 'training'), ('trained', 'trained'), ('failed', 'failed')]

    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='chatbots')
    name = models.CharField(max_length=80)
    description = models.CharField(max_length=255, blank=True)
    public_key = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    language = models.CharField(max_length=10, default='en')
    train_status = models.CharField(max_length=10, choices=TRAIN, default='idle')
    train_log = models.TextField(blank=True)
    run_pid = models.IntegerField(null=True, blank=True)
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created']

    @property
    def port(self):
        from django.conf import settings
        return settings.RASA_BASE_PORT + self.id

    def __str__(self):
        return self.name


class Intent(models.Model):
    bot = models.ForeignKey(Chatbot, on_delete=models.CASCADE, related_name='intents')
    name = models.CharField(max_length=80)

    class Meta:
        ordering = ['name']
        unique_together = ('bot', 'name')


class Example(models.Model):
    intent = models.ForeignKey(Intent, on_delete=models.CASCADE, related_name='examples')
    text = models.CharField(max_length=500)


class Slot(models.Model):
    TYPES = [('text', 'text'), ('float', 'float'), ('bool', 'bool'), ('categorical', 'categorical'), ('any', 'any')]
    bot = models.ForeignKey(Chatbot, on_delete=models.CASCADE, related_name='slots')
    name = models.CharField(max_length=80)
    type = models.CharField(max_length=12, choices=TYPES, default='text')
    from_entity = models.CharField(max_length=80, blank=True, help_text='Entity that fills this slot')
    influence = models.BooleanField(default=False)

    class Meta:
        ordering = ['name']
        unique_together = ('bot', 'name')


class Response(models.Model):
    bot = models.ForeignKey(Chatbot, on_delete=models.CASCADE, related_name='responses')
    name = models.CharField(max_length=80)  # e.g. utter_greet
    texts = models.JSONField(default=list)  # list of variations

    class Meta:
        ordering = ['name']
        unique_together = ('bot', 'name')


class Rule(models.Model):
    bot = models.ForeignKey(Chatbot, on_delete=models.CASCADE, related_name='rules')
    name = models.CharField(max_length=200)
    only_at_start = models.BooleanField(default=False)
    wait_for_user = models.BooleanField(default=True)
    steps = models.JSONField(default=list)  # [{"type": "intent"|"action", "value": "..."}]

    class Meta:
        ordering = ['id']


class ChatMessage(models.Model):
    bot = models.ForeignKey(Chatbot, on_delete=models.CASCADE, related_name='messages')
    session = models.CharField(max_length=100, db_index=True)
    sender = models.CharField(max_length=4)  # 'user' | 'bot'
    text = models.TextField()
    source = models.CharField(max_length=20, default='widget')  # widget | test
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created', 'id']
