"""Bridge between Django models and a real Rasa installation.

For every chatbot a Rasa project is generated in  rasa_projects/bot_<id>/
    config.yml, domain.yml, data/nlu.yml, data/rules.yml
`rasa train` is run in a background thread and `rasa run --enable-api` is started
as a separate process on port RASA_BASE_PORT + bot.id.
"""
import os
import re
import shutil
import signal
import subprocess
import threading

import requests
import yaml
from django.conf import settings
from django.db import connection

TAG = re.compile(r'\[([^\]]+)\]\((\w+)\)')

CONFIG = """recipe: default.v1
language: {lang}
pipeline:
  - name: WhitespaceTokenizer
  - name: RegexFeaturizer
  - name: LexicalSyntacticFeaturizer
  - name: CountVectorsFeaturizer
  - name: CountVectorsFeaturizer
    analyzer: char_wb
    min_ngram: 1
    max_ngram: 4
  - name: DIETClassifier
    epochs: 100
    constrain_similarities: true
  - name: EntitySynonymMapper
  - name: ResponseSelector
    epochs: 100
    constrain_similarities: true
  - name: FallbackClassifier
    threshold: 0.3
    ambiguity_threshold: 0.1
policies:
  - name: MemoizationPolicy
  - name: RulePolicy
  - name: UnexpecTEDIntentPolicy
    max_history: 5
    epochs: 100
  - name: TEDPolicy
    max_history: 5
    epochs: 100
    constrain_similarities: true
assistant_id: botai-{id}
"""


class _Str(str):
    pass


def _literal(dumper, data):
    return dumper.represent_scalar('tag:yaml.org,2002:str', data, style='|')


yaml.add_representer(_Str, _literal)


def workspace(bot):
    return settings.RASA_PROJECTS_DIR / f'bot_{bot.id}'


def write_project(bot):
    ws = workspace(bot)
    (ws / 'data').mkdir(parents=True, exist_ok=True)

    intents, entities, nlu = [], set(), []
    for it in bot.intents.prefetch_related('examples'):
        exs = [e.text for e in it.examples.all()]
        if not exs:
            continue
        intents.append(it.name)
        for e in exs:
            entities.update(m[1] for m in TAG.findall(e))
        nlu.append({'intent': it.name, 'examples': _Str('\n'.join('- ' + e for e in exs) + '\n')})

    slots = {}
    for s in bot.slots.all():
        spec = {'type': s.type, 'influence_conversation': s.influence}
        if s.type == 'categorical':
            spec['values'] = ['other']
        spec['mappings'] = [{'type': 'from_entity', 'entity': s.from_entity}] if s.from_entity else [{'type': 'custom'}]
        slots[s.name] = spec
        if s.from_entity:
            entities.add(s.from_entity)

    resp = {r.name: [{'text': t} for t in r.texts if t.strip()] for r in bot.responses.all()}

    domain = {'version': '3.1', 'intents': intents}
    if entities:
        domain['entities'] = sorted(entities)
    if slots:
        domain['slots'] = slots
    if resp:
        domain['responses'] = resp
    domain['session_config'] = {'session_expiration_time': 60, 'carry_over_slots_to_new_session': True}

    rules = []
    for r in bot.rules.all():
        d = {'rule': r.name}
        if r.only_at_start:
            d['conversation_start'] = True
        d['steps'] = [{s['type']: s['value']} for s in r.steps if s.get('value')]
        if not r.wait_for_user:
            d['wait_for_user_input'] = False
        if d['steps']:
            rules.append(d)

    (ws / 'config.yml').write_text(CONFIG.format(lang=bot.language, id=bot.id))
    (ws / 'domain.yml').write_text(yaml.dump(domain, sort_keys=False, allow_unicode=True))
    (ws / 'data' / 'nlu.yml').write_text(yaml.dump({'version': '3.1', 'nlu': nlu}, sort_keys=False, allow_unicode=True))
    (ws / 'data' / 'rules.yml').write_text(yaml.dump({'version': '3.1', 'rules': rules}, sort_keys=False, allow_unicode=True))
    return ws


def rasa_bin():
    return shutil.which(settings.RASA_BIN) or settings.RASA_BIN


def _train_job(bot_id):
    from .models import Chatbot
    bot = Chatbot.objects.get(pk=bot_id)
    ws = workspace(bot)
    try:
        proc = subprocess.run(
            [rasa_bin(), 'train', '--out', 'models', '--fixed-model-name', 'bot', '--force'],
            cwd=ws, capture_output=True, text=True)
        log = (proc.stdout or '') + '\n' + (proc.stderr or '')
        bot.train_status = 'trained' if proc.returncode == 0 else 'failed'
        bot.train_log = log[-6000:]
    except FileNotFoundError:
        bot.train_status = 'failed'
        bot.train_log = f'Could not find the "rasa" executable ({settings.RASA_BIN}). Install Rasa or set RASA_BIN.'
    except Exception as exc:  # pragma: no cover
        bot.train_status = 'failed'
        bot.train_log = str(exc)
    bot.save(update_fields=['train_status', 'train_log'])
    connection.close()


def train(bot):
    if bot.train_status == 'training':
        return
    stop(bot)
    write_project(bot)
    bot.train_status, bot.train_log = 'training', ''
    bot.save(update_fields=['train_status', 'train_log'])
    threading.Thread(target=_train_job, args=(bot.id,), daemon=True).start()


def is_running(bot):
    try:
        return requests.get(f'http://127.0.0.1:{bot.port}/', timeout=1).status_code == 200
    except requests.RequestException:
        return False


def start(bot):
    """Returns (ok, message)."""
    if is_running(bot):
        return True, 'Already running'
    model = workspace(bot) / 'models' / 'bot.tar.gz'
    if not model.exists():
        return False, 'Train the bot first.'
    log = open(workspace(bot) / 'rasa.log', 'ab')
    kw = {'start_new_session': True} if os.name == 'posix' else {'creationflags': 0x00000200}
    try:
        p = subprocess.Popen(
            [rasa_bin(), 'run', '--enable-api', '--cors', '*', '-p', str(bot.port), '-m', str(model)],
            cwd=workspace(bot), stdout=log, stderr=log, **kw)
    except FileNotFoundError:
        return False, f'Could not find the "rasa" executable ({settings.RASA_BIN}).'
    bot.run_pid = p.pid
    bot.save(update_fields=['run_pid'])
    return True, 'Starting… Rasa needs ~20-60 seconds to load the model.'


def stop(bot):
    if bot.run_pid:
        try:
            if os.name == 'posix':
                os.killpg(os.getpgid(bot.run_pid), signal.SIGTERM)
            else:
                subprocess.run(['taskkill', '/PID', str(bot.run_pid), '/T', '/F'], capture_output=True)
        except (ProcessLookupError, PermissionError, OSError):
            pass
        bot.run_pid = None
        bot.save(update_fields=['run_pid'])


def send(bot, sender, message):
    r = requests.post(f'http://127.0.0.1:{bot.port}/webhooks/rest/webhook',
                      json={'sender': sender, 'message': message}, timeout=30)
    r.raise_for_status()
    return [m.get('text') for m in r.json() if m.get('text')]
