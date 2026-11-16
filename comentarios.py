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

def ya_dicho(a):
    t = a['texto'].strip()
    try:
        if a['red'] == 'youtube':
            return any(i['snippet']['textOriginal'].strip() == t for i in yt(f"comments?part=snippet&parentId={a['id']}&maxResults=100").get('items', []))
        if a['red'] == 'instagram':
            return any(x.get('username') == YO and (x.get('text') or '').strip() == t for x in call(f"{a['id']}/replies?fields=username,text&limit=100")['data'])
        return any((x.get('from') or {}).get('id') == PID and (x.get('message') or '').strip() == t for x in call(f"{a['id']}/comments?fields=from,message&limit=100", tok=PT)['data'])
    except Exception: return False

def acciones():
    if not os.path.exists('respuestas.json'): return
    pend = json.load(open('respuestas.json')); quedan = []; vistos = set()
    for a in pend:
        if (a['id'], a.get('texto'), a.get('ocultar')) in vistos: continue   # never send the same reply twice
        vistos.add((a['id'], a.get('texto'), a.get('ocultar')))
        if not a.get('ocultar') and ya_dicho(a):   # last check against the network itself: is this exact reply already there?
            print('ya estaba, no se repite', a['red']); continue
        try:
            if a['red'] == 'youtube':
                if a.get('ocultar'): yt(f"comments/setModerationStatus?id={a['id']}&moderationStatus=heldForReview", None, 'POST')
                else: yt('comments?part=snippet', {'snippet': {'parentId': a['id'], 'textOriginal': a['texto']}})
                print('hecho youtube'); continue
            ig = a['red'] == 'instagram'; tok = IGT if ig else PT
            if a.get('ocultar'): call(a['id'], {'hide': 'true'} if ig else {'is_hidden': 'true'}, tok)
            else: call(f"{a['id']}/{'replies' if ig else 'comments'}", {'message': a['texto']}, tok)
            print('hecho', a['red'], 'ocultar' if a.get('ocultar') else 'respuesta')
        except Exception as e:
            a['error'] = str(getattr(e, 'read', lambda: e)())[:200]; quedan.append(a); print('FALLO', a['error'])
    json.dump(quedan, open('respuestas.json', 'w'), ensure_ascii=False, indent=1)

def recoge():
    out = []
    for m in call(f'{IGID}/media?fields=id,caption,permalink,timestamp,comments_count&limit=25')['data']:
        if not m.get('comments_count'): continue
        for c in call(f"{m['id']}/comments?fields=id,text,username,timestamp,hidden,replies{{username,text,timestamp}}&limit=50")['data']:
            rs = c.get('replies', {}).get('data', [])
            out.append(dict(red='instagram', id=c['id'], quien=c.get('username'), texto=c.get('text'), hora=c.get('timestamp'),
                oculto=c.get('hidden', False), respuestas=[dict(quien=r.get('username'), texto=r.get('text')) for r in rs],
                respondido=any(r.get('username') == YO for r in rs), video=(m.get('caption') or '')[:70], enlace=m.get('permalink')))
    if PT:
        try:
            for v in call(f'{PID}/video_reels?fields=id,description,permalink_url&limit=25', tok=PT)['data']:
                for c in call(f"{v['id']}/comments?fields=id,message,from,created_time,comments{{from,message}}&limit=50", tok=PT)['data']:
                    rs = c.get('comments', {}).get('data', [])
                    out.append(dict(red='facebook', id=c['id'], quien=(c.get('from') or {}).get('name', 'alguien'), texto=c.get('message'),
                        hora=c.get('created_time'), oculto=False, respuestas=[dict(quien=(r.get('from') or {}).get('name'), texto=r.get('message')) for r in rs],
                        respondido=any((r.get('from') or {}).get('id') == PID for r in rs), video=(v.get('description') or '')[:70],
                        enlace='https://www.facebook.com' + v.get('permalink_url', '')))
        except Exception as e: print('Facebook comentarios:', e)
    try:
        ch = yt('channels?part=id&mine=true')['items'][0]['id']
        for t in yt(f'commentThreads?part=snippet,replies&allThreadsRelatedToChannelId={ch}&maxResults=100')['items']:
            top = t['snippet']['topLevelComment']; sn = top['snippet']; rs = t.get('replies', {}).get('comments', [])
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
    acciones(); recoge()
