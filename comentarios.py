#!/usr/bin/env python3
"""Cada 15 min en GitHub: publica las respuestas pedidas desde la web (respuestas.json)
y recoge los comentarios de Instagram y Facebook en comentarios.json."""
import os, json, urllib.request, urllib.parse

API = 'https://graph.facebook.com/v23.0/'
IGT, IGID = os.environ['IG_TOKEN'], os.environ['IG_USER_ID']
PT, PID = os.environ.get('PAGE_TOKEN', ''), os.environ.get('PAGE_ID', '')
YO = 'bio.andante'

def yt_tok():
    c = json.loads(os.environ['YT_CLIENT'])['installed']
    return json.loads(urllib.request.urlopen(c['token_uri'], urllib.parse.urlencode(dict(refresh_token=os.environ['YT_REFRESH'],
        client_id=c['client_id'], client_secret=c['client_secret'], grant_type='refresh_token')).encode()).read())['access_token']

def yt(path, body=None, method=None):
    r = urllib.request.Request('https://www.googleapis.com/youtube/v3/' + path, data=json.dumps(body).encode() if body is not None else None,
        method=method, headers={'Authorization': 'Bearer ' + YTT, 'Content-Type': 'application/json'})
    t = urllib.request.urlopen(r, timeout=60).read()
    return json.loads(t) if t else {}
YTT = ''

def call(path, data=None, tok=IGT):
    url = API + path; body = None
    if data is not None: body = urllib.parse.urlencode(dict(data, access_token=tok)).encode()
    else: url += ('&' if '?' in url else '?') + 'access_token=' + tok
    return json.loads(urllib.request.urlopen(urllib.request.Request(url, data=body), timeout=60).read())

def pages(path, total, tok=IGT, maxp=8):   # follow the paging of a comment list, only while there are more comments than read
    j = call(path, tok=tok); out = j.get('data', [])
    for _ in range(maxp - 1):
        nxt = j.get('paging', {}).get('next')
        if not nxt or len(out) >= total: break
        j = json.loads(urllib.request.urlopen(nxt, timeout=60).read()); out += j.get('data', [])
    return out

def ya_dicho(a):
    t = a['texto'].strip()
    try:
        if a['red'] == 'youtube':
            return any(i['snippet']['textOriginal'].strip() == t for i in yt(f"comments?part=snippet&parentId={a['id']}&maxResults=100").get('items', []))
        if a['red'] == 'instagram':
            return any(x.get('username') == YO and (x.get('text') or '').strip() == t for x in call(f"{a['id']}/replies?fields=username,text&limit=100")['data'])
        return any((x.get('from') or {}).get('id') == PID and (x.get('message') or '').strip() == t for x in call(f"{a['id']}/comments?fields=from,message&limit=100", tok=PT)['data'])
    except Exception: return False

def clave(a): return a['id'] + '|' + ('ocultar' if a.get('ocultar') else (a.get('texto') or '').strip())

def acciones():
    if not os.path.exists('respuestas.json'): return
    # respuestas.json is written only by the web; what the bot has done goes to enviadas.json, so a reply sent
    # from the web while the bot is busy is never overwritten, and the web knows at once what is already sent.
    pend = json.load(open('respuestas.json'))
    env = json.load(open('enviadas.json')) if os.path.exists('enviadas.json') else {}
    hora = __import__('datetime').datetime.utcnow().isoformat()[:16]
    for a in pend:
        k = clave(a)
        if k in env: continue   # never send the same reply twice
        if not a.get('ocultar') and ya_dicho(a):   # last check against the network itself: is this exact reply already there?
            print('ya estaba, no se repite', a['red']); env[k] = {'id': a['id'], 'hora': hora}; continue
        try:
            if a['red'] == 'youtube':
                if a.get('ocultar'): yt(f"comments/setModerationStatus?id={a['id']}&moderationStatus=heldForReview", None, 'POST')
                else: yt('comments?part=snippet', {'snippet': {'parentId': a['id'], 'textOriginal': a['texto']}})
                print('hecho youtube'); env[k] = {'id': a['id'], 'hora': hora}; continue
            ig = a['red'] == 'instagram'; tok = IGT if ig else PT
            if a.get('ocultar'): call(a['id'], {'hide': 'true'} if ig else {'is_hidden': 'true'}, tok)
            else: call(f"{a['id']}/{'replies' if ig else 'comments'}", {'message': a['texto']}, tok)
            print('hecho', a['red'], 'ocultar' if a.get('ocultar') else 'respuesta'); env[k] = {'id': a['id'], 'hora': hora}
        except Exception as e:
            err = str(getattr(e, 'read', lambda: e)())[:300]; print('FALLO', err)
            if 'is_transient":false' in err or 'code":100' in err: env[k] = {'id': a['id'], 'hora': hora, 'error': err}   # Meta refuses for good: don't retry
    json.dump(env, open('enviadas.json', 'w'), ensure_ascii=False, indent=0)

def recoge():
    out = []
    for m in call(f'{IGID}/media?fields=id,caption,permalink,timestamp,comments_count&limit=40')['data']:
        if not m.get('comments_count'): continue
        for c in pages(f"{m['id']}/comments?fields=id,text,username,timestamp,hidden,replies.limit(100){{username,text,timestamp}}&limit=100", m['comments_count']):
            rs = c.get('replies', {}).get('data', [])
            out.append(dict(red='instagram', id=c['id'], quien=c.get('username'), texto=c.get('text'), hora=c.get('timestamp'),
                oculto=c.get('hidden', False), respuestas=[dict(quien=r.get('username'), texto=r.get('text')) for r in rs],
                respondido=any(r.get('username') == YO for r in rs), video=(m.get('caption') or '')[:70], enlace=m.get('permalink')))
    if PT:
        try:
            for v in call(f'{PID}/video_reels?fields=id,description,permalink_url&limit=40', tok=PT)['data']:
                for c in pages(f"{v['id']}/comments?fields=id,message,from,created_time,comments.limit(100){{from,message}}&limit=100", 1000, tok=PT):
                    rs = c.get('comments', {}).get('data', [])
                    out.append(dict(red='facebook', id=c['id'], quien=(c.get('from') or {}).get('name', 'alguien'), texto=c.get('message'),
                        hora=c.get('created_time'), oculto=False, respuestas=[dict(quien=(r.get('from') or {}).get('name'), texto=r.get('message')) for r in rs],
                        respondido=any((r.get('from') or {}).get('id') == PID for r in rs), video=(v.get('description') or '')[:70],
                        enlace='https://www.facebook.com' + v.get('permalink_url', '')))
        except Exception as e: print('Facebook comentarios:', e)
    try:
        ch = yt('channels?part=id&mine=true')['items'][0]['id']
        th, tok_ = [], ''
        for _ in range(5):   # every page of threads, not just the first 100
            j = yt(f'commentThreads?part=snippet,replies&allThreadsRelatedToChannelId={ch}&maxResults=100' + (f'&pageToken={tok_}' if tok_ else '')); th += j.get('items', [])
            tok_ = j.get('nextPageToken')
            if not tok_: break
        for t in th:
            top = t['snippet']['topLevelComment']; sn = top['snippet']; rs = t.get('replies', {}).get('comments', [])
            if t['snippet'].get('totalReplyCount', 0) > len(rs):   # the thread only brings the first 5 replies: fetch them all
                try: rs = yt(f"comments?part=snippet&maxResults=100&parentId={top['id']}")['items']
                except Exception as e: print('YouTube respuestas:', e)
            out.append(dict(red='youtube', id=top['id'], quien=sn.get('authorDisplayName'), texto=sn.get('textOriginal'), hora=sn.get('publishedAt'),
                oculto=False, respuestas=[dict(quien=r['snippet'].get('authorDisplayName'), texto=r['snippet'].get('textOriginal')) for r in rs],
                respondido=any(r['snippet'].get('authorChannelId', {}).get('value') == ch for r in rs), video='YouTube',
                enlace='https://youtube.com/shorts/' + sn.get('videoId', '')))
    except Exception as e: print('YouTube comentarios:', e)
    out.sort(key=lambda c: c['hora'] or '', reverse=True)
    json.dump(out, open('comentarios.json', 'w'), ensure_ascii=False, indent=1)
    print(len(out), 'comentarios')

if __name__ == '__main__':
    try: YTT = yt_tok()
    except Exception as e: print('YouTube clave:', e)
    acciones()
    if 'enviar' not in __import__('sys').argv: recoge()
