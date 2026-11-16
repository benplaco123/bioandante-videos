#!/usr/bin/env python3
"""Lista los reels de la página de Facebook y borra los que se le pasen (ids separados por comas en BORRAR).
Se lanza a mano desde GitHub (workflow «facebook-reels»). Las claves vienen de los secretos y nunca se imprimen."""
import os, json, urllib.request, urllib.parse
API, PT, PID = 'https://graph.facebook.com/v23.0/', os.environ['PAGE_TOKEN'], os.environ['PAGE_ID']
def call(path, method='GET', **q):
    q['access_token'] = PT
    url, body = API + path, None
    if method == 'GET': url += '?' + urllib.parse.urlencode(q)
    else: body = urllib.parse.urlencode(q).encode()
    try: return json.loads(urllib.request.urlopen(urllib.request.Request(url, data=body, method=method), timeout=60).read())
    except urllib.error.HTTPError as e: return {'error': e.read().decode()[:300]}
for ep in ('video_reels', 'videos'):
    r = call(f'{PID}/{ep}', fields='id,created_time,description', limit=50)
    print(f'--- {ep}'); print(r['error']) if 'error' in r else None
    for v in r.get('data', []): print(v.get('created_time', '')[:16], v['id'], (v.get('description') or '').split('\n')[0][:70])
for vid in [x.strip() for x in os.environ.get('BORRAR', '').split(',') if x.strip()]:
    print('borrar', vid, call(vid, method='DELETE'))
