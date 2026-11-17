#!/usr/bin/env python3
"""Cada vuelta en GitHub: manda por mensaje privado los recursos que se piden en comentarios («Comenta TUBO…»).

1. Comentario de Instagram con la palabra clave (recursos.json) → una sola respuesta privada: «sígueme y contéstame LISTO».
2. Esa persona escribe LISTO → si te sigue, recibe la imagen y las gracias; si no, un único aviso de que aún no te sigue.
Todo queda en dm.json, para no escribir dos veces lo mismo a nadie. Con PRUEBA=1 no manda nada: solo dice lo que haría.
"""
import os, json, re, unicodedata, datetime, urllib.request, urllib.parse
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

TOPE = int(os.environ.get('TOPE', 25)); HECHOS = [0]   # at most this many messages and follow checks per run, so Meta's hourly limit is never hit
lleno = lambda: HECHOS[0] >= TOPE

def manda(recipient, message):
    HECHOS[0] += 1
    if PRUEBA: print('  (prueba) mandaría a', recipient, str(message)[:70]); return {'message_id': 'prueba'}
    return call(f'{U}/messages', {'recipient': json.dumps(recipient), 'message': json.dumps(message)})

R = json.load(open('recursos.json'))
st = json.load(open('dm.json')) if os.path.exists('dm.json') else {'comentarios': {}, 'personas': {}}
hace7 = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=7)).strftime('%Y-%m-%dT%H:%M')

# 1 · comments that ask for a resource (Instagram only lets you answer privately within 7 days)
for m in call(f'{U}/media', fields='id,timestamp,comments_count', limit=25).get('data', []):
    if not m.get('comments_count') or m['timestamp'][:16] < hace7: continue
    for c in todo(m['id'] + '/comments', fields='id,username,text,timestamp', limit=100):
        if c['id'] in st['comentarios'] or c.get('username') == 'bio.andante' or c['timestamp'][:16] < hace7: continue
        if HECHOS[0] >= TOPE // 2: break   # leave half for the images of those who already wrote LISTO
        clave = next((k for k in R if re.search(r'\b' + k + r'\b', norm(c.get('text')))), None)
        if not clave: continue
        if any(p.get('usuario') == c.get('username') and p.get('clave') == clave for p in st['personas'].values()):
            st['comentarios'][c['id']] = 'ya pedido antes'; continue
        r = manda({'comment_id': c['id']}, {'text': R[clave]['pedir']})
        print('pedido', clave, c.get('username'), 'ok' if 'message_id' in r else r)
        if 'message_id' in r and not PRUEBA:
            st['comentarios'][c['id']] = 'pedido'
            if r.get('recipient_id'): st['personas'][r['recipient_id']] = {'usuario': c.get('username'), 'clave': clave, 'pedido': ahora()}
        elif not PRUEBA and 'is_transient' not in str(r) and '"code":4' not in str(r): st['comentarios'][c['id']] = 'fallo: ' + str(r)[:120]   # rate limit: retried next run

# 1b · a public reply under each comment already answered in private, once: so they know to look at their DMs
PUBLICO = '¡Te lo he mandado por mensaje privado! 📩 Mira tu DM. Y si te ha gustado, dale a 🔁'
for cid, estado in list(st['comentarios'].items()):
    if estado != 'pedido': continue
    if lleno(): break
    HECHOS[0] += 1
    if PRUEBA: print('  (prueba) respondería en público a', cid); continue
    r = call(f'{cid}/replies', {'message': PUBLICO})
    st['comentarios'][cid] = 'pedido + aviso público' if 'id' in r else 'pedido (aviso público falló)'
    print('aviso público', cid, 'ok' if 'id' in r else r)

# 2 · who has written LISTO since they were asked
pend = {sid: p for sid, p in st['personas'].items() if not p.get('enviado')}
if pend:
    conv = todo(f'{U}/conversations', 600, platform='instagram', fields='participants,messages.limit(10){message,from,created_time}', limit=100)
    for c in conv:
        sid = next((x['id'] for x in c.get('participants', {}).get('data', []) if x['id'] in pend), None)
        if not sid: continue
        p = pend[sid]
        listo = [m for m in c.get('messages', {}).get('data', []) if (m.get('from') or {}).get('id') == sid
                 and re.search(LISTO_RE, norm(m.get('message'))) and m['created_time'][:19] > p['pedido'][:19].replace('+00:00', '')]
        if not listo: continue   # after the «aún no me sigues» notice, each run checks again whether they follow now
        if lleno(): break
        HECHOS[0] += 1
        fr = call(sid, fields='is_user_follow_business')
        if 'error' in fr: print('no se pudo mirar si sigue (se reintenta en la próxima vuelta)', p['usuario'], fr['error'][:90]); continue
        sigue = fr.get('is_user_follow_business')
        if sigue:
            rec = R[p['clave']]
            if rec.get('enlace'):  # herramienta HTML: el enlace va dentro del texto de gracias ({enlace})
                r = manda({'id': sid}, {'text': rec['gracias'].replace('{enlace}', WEB + rec['enlace'])})
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
