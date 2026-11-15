#!/usr/bin/env python3
"""Se ejecuta en GitHub cada 15 min. Publica lo de cola.json cuya hora ya ha llegado.

Cada entrada: {"nombre", "hora": "2026-11-17T20:45:00+01:00", "video": "<archivo en la release 'cola'>",
  "texto", "portada_ms" (opcional), "prueba": false, "facebook": true, "youtube": false, "titulo" (para YouTube)}
Los vídeos esperan como archivos de la release 'cola'; tras publicarse se borran.
Las claves vienen de los secretos del repositorio y nunca se imprimen.
"""
import os, sys, json, time, subprocess, datetime, urllib.request, urllib.parse

REPO = os.environ['GITHUB_REPOSITORY']
API = 'https://graph.facebook.com/v23.0/'
IGT, IGID = os.environ['IG_TOKEN'], os.environ['IG_USER_ID']
PT, PID = os.environ.get('PAGE_TOKEN', ''), os.environ.get('PAGE_ID', '')

def call(path, data=None, tok=IGT):
    url = API + path; body = None
    if data is not None: body = urllib.parse.urlencode(dict(data, access_token=tok)).encode()
    else: url += ('&' if '?' in url else '?') + 'access_token=' + tok
    try: return json.loads(urllib.request.urlopen(urllib.request.Request(url, data=body), timeout=120).read())
    except urllib.error.HTTPError as e: raise RuntimeError(path.split('?')[0] + ': ' + e.read().decode()[:300])

def instagram(url, e):
    d = {'media_type': 'REELS', 'video_url': url, 'caption': e['texto'], 'share_to_feed': 'true'}
    if e.get('portada'): d['cover_url'] = f"https://github.com/{REPO}/releases/download/cola/{e['portada']}"
    elif e.get('portada_ms') is not None: d['thumb_offset'] = str(e['portada_ms'])
    if e.get('prueba'): d['trial_params'] = json.dumps({'graduation_strategy': 'MANUAL'})
    c = call(f'{IGID}/media', d)
    for _ in range(90):
        st = call(f"{c['id']}?fields=status_code,status")
        if st.get('status_code') == 'FINISHED': break
        if st.get('status_code') == 'ERROR': raise RuntimeError('Instagram: ' + str(st.get('status')))
        time.sleep(10)
    p = call(f'{IGID}/media_publish', {'creation_id': c['id']})
    return call(f"{p['id']}?fields=permalink").get('permalink')

def facebook(path, e):
    s = call(f'{PID}/video_reels', {'upload_phase': 'start'}, tok=PT)
    r = subprocess.run(['curl', '-s', '-X', 'POST', s['upload_url'], '-H', 'Authorization: OAuth ' + PT, '-H', 'offset: 0',
        '-H', f'file_size: {os.path.getsize(path)}', '--data-binary', '@' + path], capture_output=True, text=True)
    if '"success":true' not in r.stdout: raise RuntimeError('Facebook: ' + r.stdout[:200])
    if e.get('portada'): subprocess.run(['curl', '-s', '-X', 'POST', f"{API}{s['video_id']}/thumbnails", '-F', f'access_token={PT}', '-F', 'is_preferred=true', '-F', 'source=@p.jpg'], capture_output=True)
    call(f'{PID}/video_reels', {'upload_phase': 'finish', 'video_id': s['video_id'], 'video_state': 'PUBLISHED',
        'description': e['texto']}, tok=PT)
    return 'https://www.facebook.com/reel/' + s['video_id']

def youtube(path, e):
    c = json.loads(os.environ['YT_CLIENT'])['installed']
    a = json.loads(urllib.request.urlopen(c['token_uri'], urllib.parse.urlencode(dict(refresh_token=os.environ['YT_REFRESH'],
        client_id=c['client_id'], client_secret=c['client_secret'], grant_type='refresh_token')).encode()).read())['access_token']
    meta = {'snippet': {'title': e.get('titulo', e['nombre'])[:100], 'description': e['texto'], 'categoryId': '28'},
        'status': {'privacyStatus': 'private', 'selfDeclaredMadeForKids': False}}
    r = urllib.request.Request('https://www.googleapis.com/upload/youtube/v3/videos?uploadType=resumable&part=snippet,status',
        data=json.dumps(meta).encode(), headers={'Authorization': 'Bearer ' + a, 'Content-Type': 'application/json',
        'X-Upload-Content-Type': 'video/mp4', 'X-Upload-Content-Length': str(os.path.getsize(path))})
    loc = urllib.request.urlopen(r).headers['Location']
    out = subprocess.run(['curl', '-s', '-X', 'PUT', loc, '-H', 'Authorization: Bearer ' + a, '-H', 'Content-Type: video/mp4',
        '--data-binary', '@' + path], capture_output=True, text=True).stdout
    vid = json.loads(out)['id']
    if e.get('portada'): subprocess.run(['curl', '-s', '-X', 'POST', f'https://www.googleapis.com/upload/youtube/v3/thumbnails/set?videoId={vid}', '-H', 'Authorization: Bearer ' + a, '-H', 'Content-Type: image/jpeg', '--data-binary', '@p.jpg'], capture_output=True)
    return 'https://youtube.com/shorts/' + vid + ' (privado)'

def main():
    cola = json.load(open('cola.json'))
    now = datetime.datetime.now(datetime.timezone.utc)
    hecho = json.load(open('hecho.json')) if os.path.exists('hecho.json') else []
    toca = [e for e in cola if datetime.datetime.fromisoformat(e['hora']) <= now]
    if not toca: print('Nada que publicar'); return
    e = toca[0]  # una por pasada
    url = f"https://github.com/{REPO}/releases/download/cola/{e['video']}"
    res = {'nombre': e['nombre'], 'hora_real': now.isoformat()}
    subprocess.run(['curl', '-sL', '-o', 'v.mp4', url], check=True)
    if e.get('portada'): subprocess.run(['curl', '-sL', '-o', 'p.jpg', f"https://github.com/{REPO}/releases/download/cola/{e['portada']}"])
    for k, f, arg in (('instagram', instagram, url), ('facebook', facebook, 'v.mp4'), ('youtube', youtube, 'v.mp4')):
        if not e.get(k, k == 'instagram'): continue
        try: res[k] = f(arg, e); print(k, 'OK', res[k])
        except Exception as x: res[k] = 'FALLO ' + str(x); print(k, 'FALLO', x)
    cola.remove(e); hecho.append(res)
    json.dump(cola, open('cola.json', 'w'), ensure_ascii=False, indent=1)
    json.dump(hecho, open('hecho.json', 'w'), ensure_ascii=False, indent=1)
    if 'FALLO' not in json.dumps(res):
        for a in (e['video'], e.get('portada')):
            if a: subprocess.run(['gh', 'release', 'delete-asset', 'cola', a, '-y', '-R', REPO])

if __name__ == '__main__': main()
