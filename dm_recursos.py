#!/usr/bin/env python3
"""Cada vuelta en GitHub: manda por mensaje privado los recursos que se piden en comentarios («Comenta TUBO…»).

1. Comentario de Instagram con la palabra clave (recursos.json) → una sola respuesta privada: «sígueme y contéstame LISTO».
2. Esa persona escribe LISTO → si te sigue, recibe la imagen y las gracias; si no, un único aviso de que aún no te sigue.
Todo queda en dm.json, para no escribir dos veces lo mismo a nadie. Con PRUEBA=1 no manda nada: solo dice lo que haría.
"""
import os, time, json, re, unicodedata, datetime, urllib.request, urllib.parse
API = 'https://graph.facebook.com/v23.0/'
T, U = os.environ['IG_TOKEN'], os.environ['IG_USER_ID']
REPO = os.environ.get('GITHUB_REPOSITORY', 'benplaco123/bioandante-videos')
WEB = f"https://{REPO.split('/')[0]}.github.io/{REPO.split('/')[1]}/"
PRUEBA = os.environ.get('PRUEBA') == '1'
NO_SIGUE = 'Aún no me sigues 🙂 Sígueme en @bio.andante y vuelve a escribirme «LISTO», y te lo mando.'
ahora = lambda: datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='seconds')
norm = lambda s: unicodedata.normalize('NFD', (s or '')).encode('ascii', 'ignore').decode().upper()

def call(path, data=None, **q):
    q['access_token'] = T
    if data is None: req = urllib.request.Request(API + path + '?' + urllib.parse.urlencode(q))
    else: req = urllib.request.Request(API + path, data=urllib.parse.urlencode({**data, **q}).encode())
    try: return json.loads(urllib.request.urlopen(req, timeout=60).read())
    except urllib.error.HTTPError as e: return {'error': e.read().decode()[:300]}

def todo(path, maxn=1000, **q):   # every page of a list (comments, conversations), not just the first
    r = call(path, **q); out = r.get('data', [])
    while r.get('paging', {}).get('next') and len(out) < maxn:
        try: r = json.loads(urllib.request.urlopen(r['paging']['next'], timeout=60).read())
        except Exception: break
        out += r.get('data', [])
    return out

LISTO_RE = r'\b(LISTO|LISTA|LISTOO+|YA|HECHO|TE SIGO|YA TE SIGO|SIGUIENDO|DONE|OK)\b'

TOPE = int(os.environ.get('TOPE', 14)); HECHOS = [0]; LIMITE = [False]; PUB = [0]; TOPE_PUB = int(os.environ.get('TOPE_PUB', 20))   # at most this many messages and follow checks per run, so Meta's hourly limit is never hit
lleno = lambda: HECHOS[0] >= TOPE

def manda(recipient, message):
    HECHOS[0] += 1
    if not PRUEBA: time.sleep(3)   # spaced out: Meta cuts bursts of private replies
    if PRUEBA: print('  (prueba) mandaría a', recipient, str(message)[:70]); return {'message_id': 'prueba'}
    return call(f'{U}/messages', {'recipient': json.dumps(recipient), 'message': json.dumps(message)})

R = json.load(open('recursos.json'))
st = json.load(open('dm.json')) if os.path.exists('dm.json') else {'comentarios': {}, 'personas': {}}
hace7 = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=7)).strftime('%Y-%m-%dT%H:%M')

# 1 · comments that ask for a resource (Instagram only lets you answer privately within 7 days)
for m in call(f'{U}/media', fields='id,timestamp,comments_count', limit=25).get('data', []):
    if LIMITE[0] or HECHOS[0] >= TOPE: break
    if not m.get('comments_count') or m['timestamp'][:16] < hace7: continue
    for c in sorted(todo(m['id'] + '/comments', fields='id,username,text,timestamp', limit=100), key=lambda c: c['timestamp']):   # oldest first: nobody waits hours behind newer comments
        if c['id'] in st['comentarios'] or c.get('username') == 'bio.andante' or c['timestamp'][:16] < hace7: continue
        if HECHOS[0] >= TOPE: break   # the LISTO images go by hand now, so the whole quota is for the DMs
        clave = next((k for k in R if re.search(r'\b' + k + r'\b', norm(c.get('text')))), None)
        if not clave: continue
        if any(p.get('usuario') == c.get('username') and p.get('clave') == clave for p in st['personas'].values()):
            st['comentarios'][c['id']] = 'ya pedido antes'; continue
        r = manda({'comment_id': c['id']}, {'text': R[clave]['pedir']})
        print('pedido', clave, c.get('username'), 'ok' if 'message_id' in r else r)
        if 'message_id' in r and not PRUEBA:
            st['comentarios'][c['id']] = 'pedido'
            if r.get('recipient_id'): st['personas'][r['recipient_id']] = {'usuario': c.get('username'), 'clave': clave, 'pedido': ahora()}
        elif '"code":4' in str(r) or 'is_transient' in str(r): LIMITE[0] = True; break   # Meta's limit: stop here, retried next run
        elif not PRUEBA: st['comentarios'][c['id']] = 'fallo: ' + str(r)[:120]

# 1b · a public reply under each comment already answered in private, once: so they know to look at their DMs
PUBLICO = '¡Te lo he mandado por mensaje privado! 📩 Y si te ha gustado, compártelo con 🔁 para que le llegue a más gente del labo 🙌'
PUBLICOS = [PUBLICO,   # several wordings, so hundreds of identical comments don't look like spam to Instagram
  '¡Mira tu DM! 📩 Te lo acabo de mandar. Si te ha servido, compártelo con 🔁 🙌',
  'Te lo he enviado por privado 📩 ¿Me ayudas compartiendo el vídeo con 🔁? ¡Gracias! 🙌',
  '¡Enviado a tu DM! 🧪 Y si conoces a alguien del labo que lo necesite, compártelo con 🔁',
  '¡Ya lo tienes en mensajes! 📩 Si te gusta, dale a 🔁 para que llegue a más gente 🙌']
try: YA = {c['id'] for c in json.load(open('comentarios.json')) if any('bio' in (x.get('quien') or '') and 'andante' in (x.get('quien') or '') for x in c.get('respuestas') or [])}
except Exception: YA = set()
for cid, estado in list(st['comentarios'].items()):
    if os.environ.get('AVISO_PUBLICO', '1') != '1': break   # on again 17 nov (asks to share); AVISO_PUBLICO=0 turns it off
    if PUB[0] >= TOPE_PUB: break   # own quota: Meta's limit on private replies does not stop the public ones (18 nov: 271 were waiting)
    if estado != 'pedido': continue
    if cid in YA: st['comentarios'][cid] = 'pedido + respondido a mano'; continue   # never answer the same comment twice
    PUB[0] += 1; time.sleep(2)
    if PRUEBA: print('  (prueba) respondería en público a', cid); continue
    r = call(f'{cid}/replies', {'message': PUBLICOS[int(cid) % len(PUBLICOS)]})
    if '"code":4' in str(r) or 'is_transient' in str(r): print('aviso público: límite de Meta'); break   # stays «pedido», retried next run
    st['comentarios'][cid] = 'pedido + aviso público' if 'id' in r else 'pedido (aviso público falló)'
    print('aviso público', cid, 'ok' if 'id' in r else r)

# 2 · who has written LISTO since they were asked. Off since 2026-11-17: the user sends the resource by hand (ENVIO_AUTO=1 turns it back on)
pend = {sid: p for sid, p in st['personas'].items() if not p.get('enviado')}
if pend and os.environ.get('ENVIO_AUTO') == '1':
    conv = todo(f'{U}/conversations', 25, platform='instagram', fields='participants,messages.limit(4){message,from,created_time}', limit=25)
    for c in conv:
        sid = next((x['id'] for x in c.get('participants', {}).get('data', []) if x['id'] in pend), None)
        if not sid: continue
        p = pend[sid]
        # answered by hand (an image or any message of ours that the script did not write) → never send again
        auto = {R[p['clave']]['pedir'], NO_SIGUE}
        if any((m.get('from') or {}).get('username') == 'bio.andante' and m['created_time'][:19] > p['pedido'][:19].replace('+00:00', '')
               and (m.get('message') or '') not in auto for m in c.get('messages', {}).get('data', [])):
            if not PRUEBA: p['enviado'] = 'a mano'
            print('respondido a mano', p['usuario']); continue
        listo = [m for m in c.get('messages', {}).get('data', []) if (m.get('from') or {}).get('id') == sid
                 and re.search(LISTO_RE, norm(m.get('message'))) and m['created_time'][:19] > p['pedido'][:19].replace('+00:00', '')]
        if not listo: continue
        # the follow check uses Meta's tiny per-app quota (~200/h), unlike sending messages: only ask again when there is a NEW
        # LISTO since the last check, or, after the «aún no me sigues» notice, at most every 3 hours
        nuevo = max(m['created_time'][:19] for m in listo)
        hace3h = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=3)).isoformat()[:19]
        if p.get('visto') and nuevo <= p['visto'] and p.get('revisado', '') > hace3h: continue
        if lleno(): break
        HECHOS[0] += 1
        fr = call(sid, fields='is_user_follow_business')
        if 'error' in fr and '"code":4' not in fr['error']: print('no se pudo mirar si sigue', p['usuario'], fr['error'][:90]); continue
        # the user (17 nov): trust LISTO. Meta often refuses this one check for hours («Application request limit», a tiny per-app
        # quota) while messages still go out; then whoever wrote LISTO gets it anyway
        sigue = True if 'error' in fr else fr.get('is_user_follow_business')
        if 'error' in fr: print('límite de Meta al mirar si sigue: se lo mando igual', p['usuario'])
        if not PRUEBA: p['visto'], p['revisado'] = nuevo, ahora()[:19]
        if sigue:
            rec = R[p['clave']]
            if rec.get('enlace'):  # herramienta HTML: el enlace va dentro del texto de gracias ({enlace})
                r = manda({'id': sid}, {'text': rec['gracias'].replace('{enlace}', rec['enlace'] if rec['enlace'].startswith('http') else WEB + rec['enlace'])})
            else:
                r = manda({'id': sid}, {'attachment': {'type': 'image', 'payload': {'url': WEB + rec['imagen']}}})
                if 'message_id' in r: manda({'id': sid}, {'text': rec['gracias']})
            if 'message_id' in r:
                if not PRUEBA: p['enviado'] = ahora()
            print('imagen', p['usuario'], 'ok' if 'message_id' in r else r)
        elif not p.get('aviso_no_sigue'):
            manda({'id': sid}, {'text': NO_SIGUE})
            if not PRUEBA: p['aviso_no_sigue'] = ahora()
            print('aún no sigue', p['usuario'])
        else: print('sigue sin seguir', p['usuario'])

if not PRUEBA: json.dump(st, open('dm.json', 'w'), ensure_ascii=False, indent=1)
