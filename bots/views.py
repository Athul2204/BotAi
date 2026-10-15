import json
import re
import uuid

from django.contrib import messages
from django.core.paginator import Paginator
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from home.decorators import approved_required
from home.models import get_profile

from . import rasa_manager as rasa
from .models import ChatMessage, Chatbot, Example, Intent, Response, Rule, Slot

NAME_RE = re.compile(r'^[A-Za-z0-9_]+$')


def _bot(request, pk):
    qs = Chatbot.objects.all() if get_profile(request.user).role == 'admin' else Chatbot.objects.filter(owner=request.user)
    return get_object_or_404(qs, pk=pk)


def _ctx(bot, page, **kw):
    return {'bot': bot, 'page': page, **kw}


def _json(request):
    try:
        return json.loads(request.body or '{}')
    except ValueError:
        return {}


# ------------------------------------------------------------------ dashboard
@approved_required
def dashboard(request):
    qs = Chatbot.objects.filter(owner=request.user)
    page = Paginator(qs, 6).get_page(request.GET.get('page'))
    return render(request, 'bots/dashboard.html', {'page_obj': page, 'total': qs.count(), 'page': 'dashboard'})


@approved_required
@require_POST
def bot_create(request):
    name = request.POST.get('name', '').strip()
    if not name:
        messages.error(request, 'Give your chatbot a name.')
        return redirect('dashboard')
    bot = Chatbot.objects.create(owner=request.user, name=name, description=request.POST.get('description', '').strip(),
                                 language=request.POST.get('language', 'en') or 'en')
    messages.success(request, f'Chatbot "{bot.name}" created.')
    return redirect('intents', pk=bot.pk)


@approved_required
@require_POST
def bot_delete(request, pk):
    bot = _bot(request, pk)
    rasa.stop(bot)
    bot.delete()
    return redirect('dashboard')


# --------------------------------------------------------------- generic save
def _clean_name(data):
    name = (data.get('name') or '').strip().replace(' ', '_')
    return name if NAME_RE.match(name) else None


@approved_required
def intents(request, pk):
    bot = _bot(request, pk)
    items = Paginator(bot.intents.prefetch_related('examples'), 9).get_page(request.GET.get('page'))
    data = {i.id: {'id': i.id, 'name': i.name, 'examples': [e.text for e in i.examples.all()]} for i in items}
    return render(request, 'bots/intents.html', _ctx(bot, 'intents', items=items, data=json.dumps(list(data.values()))))


@approved_required
@require_POST
def intent_save(request, pk):
    bot, d = _bot(request, pk), None
    d = _json(request)
    name = _clean_name(d)
    if not name:
        return JsonResponse({'error': 'Intent name may only contain letters, numbers and underscores.'}, status=400)
    examples = [e.strip() for e in d.get('examples', []) if e.strip()]
    if d.get('id'):
        it = get_object_or_404(Intent, pk=d['id'], bot=bot)
        it.name = name
    else:
        it = Intent(bot=bot, name=name)
    if Intent.objects.filter(bot=bot, name=name).exclude(pk=it.pk).exists():
        return JsonResponse({'error': 'An intent with this name already exists.'}, status=400)
    it.save()
    it.examples.all().delete()
    Example.objects.bulk_create(Example(intent=it, text=t) for t in examples)
    return JsonResponse({'ok': True})


@approved_required
@require_POST
def intent_delete(request, pk, item):
    get_object_or_404(Intent, pk=item, bot=_bot(request, pk)).delete()
    return JsonResponse({'ok': True})


@approved_required
def slots(request, pk):
    bot = _bot(request, pk)
    data = [{'id': s.id, 'name': s.name, 'type': s.type, 'from_entity': s.from_entity, 'influence': s.influence} for s in bot.slots.all()]
    return render(request, 'bots/slots.html', _ctx(bot, 'slots', items=bot.slots.all(), data=json.dumps(data)))


@approved_required
@require_POST
def slot_save(request, pk):
    bot, d = _bot(request, pk), None
    d = _json(request)
    name = _clean_name(d)
    if not name:
        return JsonResponse({'error': 'Slot name may only contain letters, numbers and underscores.'}, status=400)
    s = get_object_or_404(Slot, pk=d['id'], bot=bot) if d.get('id') else Slot(bot=bot)
    if Slot.objects.filter(bot=bot, name=name).exclude(pk=s.pk).exists():
        return JsonResponse({'error': 'A slot with this name already exists.'}, status=400)
    s.name, s.type = name, d.get('type', 'text')
    s.from_entity, s.influence = (d.get('from_entity') or '').strip(), bool(d.get('influence'))
    s.save()
    return JsonResponse({'ok': True})


@approved_required
@require_POST
def slot_delete(request, pk, item):
    get_object_or_404(Slot, pk=item, bot=_bot(request, pk)).delete()
    return JsonResponse({'ok': True})


@approved_required
def responses(request, pk):
    bot = _bot(request, pk)
    data = [{'id': r.id, 'name': r.name, 'texts': r.texts} for r in bot.responses.all()]
    return render(request, 'bots/responses.html', _ctx(bot, 'responses', items=bot.responses.all(), data=json.dumps(data)))


@approved_required
@require_POST
def response_save(request, pk):
    bot, d = _bot(request, pk), None
    d = _json(request)
    name = _clean_name(d)
    if not name or not name.startswith('utter_'):
        return JsonResponse({'error': 'Response names must start with utter_ (letters, numbers, underscores).'}, status=400)
    texts = [t.strip() for t in d.get('texts', []) if t.strip()]
    if not texts:
        return JsonResponse({'error': 'Add at least one reply text.'}, status=400)
    r = get_object_or_404(Response, pk=d['id'], bot=bot) if d.get('id') else Response(bot=bot)
    if Response.objects.filter(bot=bot, name=name).exclude(pk=r.pk).exists():
        return JsonResponse({'error': 'A response with this name already exists.'}, status=400)
    r.name, r.texts = name, texts
    r.save()
    return JsonResponse({'ok': True})


@approved_required
@require_POST
def response_delete(request, pk, item):
    get_object_or_404(Response, pk=item, bot=_bot(request, pk)).delete()
    return JsonResponse({'ok': True})


@approved_required
def rules(request, pk):
    bot = _bot(request, pk)
    items = Paginator(bot.rules.all(), 9).get_page(request.GET.get('page'))
    data = [{'id': r.id, 'name': r.name, 'only_at_start': r.only_at_start, 'wait_for_user': r.wait_for_user, 'steps': r.steps} for r in items]
    return render(request, 'bots/rules.html', _ctx(bot, 'rules', items=items, data=json.dumps(data),
                  intent_names=json.dumps(list(bot.intents.values_list('name', flat=True))),
                  action_names=json.dumps(list(bot.responses.values_list('name', flat=True)))))


@approved_required
@require_POST
def rule_save(request, pk):
    bot, d = _bot(request, pk), None
    d = _json(request)
    name = (d.get('name') or '').strip()
    steps = [{'type': s['type'], 'value': s['value'].strip()} for s in d.get('steps', [])
             if s.get('type') in ('intent', 'action') and (s.get('value') or '').strip()]
    if not name or not steps:
        return JsonResponse({'error': 'A rule needs a name and at least one step.'}, status=400)
    r = get_object_or_404(Rule, pk=d['id'], bot=bot) if d.get('id') else Rule(bot=bot)
    r.name, r.steps = name, steps
    r.only_at_start, r.wait_for_user = bool(d.get('only_at_start')), bool(d.get('wait_for_user', True))
    r.save()
    return JsonResponse({'ok': True})


@approved_required
@require_POST
def rule_delete(request, pk, item):
    get_object_or_404(Rule, pk=item, bot=_bot(request, pk)).delete()
    return JsonResponse({'ok': True})


# ------------------------------------------------------------------- run bot
@approved_required
def run_bot(request, pk):
    bot = _bot(request, pk)
    return render(request, 'bots/run.html', _ctx(bot, 'run', running=rasa.is_running(bot),
                  origin=f'{request.scheme}://{request.get_host()}'))


@approved_required
@require_POST
def bot_action(request, pk, action):
    bot = _bot(request, pk)
    if action == 'train':
        if not Intent.objects.filter(bot=bot, examples__isnull=False).exists():
            return JsonResponse({'ok': False, 'message': 'Add at least one intent with training examples first.'})
        rasa.train(bot)
        return JsonResponse({'ok': True, 'message': 'Training started…'})
    if action == 'start':
        ok, msg = rasa.start(bot)
        return JsonResponse({'ok': ok, 'message': msg})
    if action == 'stop':
        rasa.stop(bot)
        return JsonResponse({'ok': True, 'message': 'Stopped.'})
    return JsonResponse({'ok': False}, status=400)


@approved_required
def bot_status(request, pk):
    bot = _bot(request, pk)
    return JsonResponse({'train_status': bot.train_status, 'train_log': bot.train_log, 'running': rasa.is_running(bot)})


@approved_required
@require_POST
def bot_test_chat(request, pk):
    bot = _bot(request, pk)
    return _reply(bot, f'test-{request.user.id}-{_json(request).get("sid", "x")}', _json(request).get('message', ''), 'test')


# --------------------------------------------------------------------- chats
@approved_required
def chats(request, pk):
    bot = _bot(request, pk)
    sessions = {}
    for m in bot.messages.all():
        s = sessions.setdefault(m.session, {'id': m.session, 'source': m.source, 'first': m.text, 'last': m.text, 'time': m.created, 'count': 0})
        s['last'], s['time'], s['count'] = m.text, m.created, s['count'] + 1
    lst = sorted(sessions.values(), key=lambda s: s['time'], reverse=True)
    sel = request.GET.get('s') or (lst[0]['id'] if lst else None)
    msgs = bot.messages.filter(session=sel) if sel else []
    return render(request, 'bots/chats.html', _ctx(bot, 'chats', sessions=lst, selected=sel, msgs=msgs))


# ------------------------------------------ public widget API (other websites)
def _cors(resp):
    resp['Access-Control-Allow-Origin'] = '*'
    resp['Access-Control-Allow-Headers'] = 'Content-Type'
    resp['Access-Control-Allow-Methods'] = 'POST, GET, OPTIONS'
    return resp


def _reply(bot, session, text, source):
    text = (text or '').strip()
    if not text:
        return JsonResponse({'replies': []})
    ChatMessage.objects.create(bot=bot, session=session, sender='user', text=text, source=source)
    try:
        replies = rasa.send(bot, session, text)
    except Exception:
        return JsonResponse({'replies': [], 'error': 'The bot is offline. Train and start it from "Run bot".'}, status=503)
    ChatMessage.objects.bulk_create(ChatMessage(bot=bot, session=session, sender='bot', text=t, source=source) for t in replies)
    return JsonResponse({'replies': replies})


@csrf_exempt
def public_chat(request, key):
    """POST {session, message} -> {replies: [...]}  — called by the embeddable widget."""
    if request.method == 'OPTIONS':
        return _cors(HttpResponse())
    bot = get_object_or_404(Chatbot, public_key=key)
    d = _json(request)
    sid = re.sub(r'[^A-Za-z0-9_-]', '', str(d.get('session') or uuid.uuid4().hex))[:60]
    return _cors(_reply(bot, f'web-{sid}', d.get('message'), 'widget'))


def widget_js(request, key):
    """<script src="http://botai-host/widget/<key>.js"></script>  adds a floating chat bubble."""
    bot = get_object_or_404(Chatbot, public_key=key)
    base = f'{request.scheme}://{request.get_host()}'
    js = render(request, 'bots/widget.js', {'bot': bot, 'api': f'{base}/api/chat/{bot.public_key}/'}, content_type='application/javascript')
    return _cors(js)
