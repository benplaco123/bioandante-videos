#!/usr/bin/env python3
"""Cada 15 min en GitHub: publica las respuestas pedidas desde la web (respuestas.json)
y recoge los comentarios de Instagram y Facebook en comentarios.json."""
import os, json, urllib.request, urllib.parse

API = 'https://graph.facebook.com/v23.0/'
IGT, IGID = os.environ['IG_TOKEN'], os.environ['IG_USER_ID']
PT, PID = os.environ.get('PAGE_TOKEN', ''), os.environ.get('PAGE_ID', '')
YO = 'bio.andante'

def call(path, data=None, tok=IGT):
    url = API + path; body = None
    if data is not None: body = urllib.parse.urlencode(dict(data, access_token=tok)).encode()
    else: url += ('&' if '?' in url else '?') + 'access_token=' + tok
    return json.loads(urllib.request.urlopen(urllib.request.Request(url, data=body), timeout=60).read())

def acciones():
    if not os.path.exists('respuestas.json'): return
    pend = json.load(open('respuestas.json')); quedan = []
    for a in pend:
        try:
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
    out.sort(key=lambda c: c['hora'] or '', reverse=True)
    json.dump(out, open('comentarios.json', 'w'), ensure_ascii=False, indent=1)
    print(len(out), 'comentarios')

if __name__ == '__main__':
    acciones(); recoge()
