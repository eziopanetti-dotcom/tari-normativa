import json, re, urllib.request, urllib.error
from datetime import datetime, timezone
from pathlib import Path

P = Path('normativa_tari.json')
TIMEOUT = 20
UA = 'TARI-Normativa-Monitor/1.0 (+GitHub Actions)'

def fetch(url):
    req = urllib.request.Request(url, headers={'User-Agent': UA, 'Accept':'text/html,application/json,text/plain,*/*'})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        body = r.read(2000000)
        return getattr(r, 'status', 200), r.geturl(), body.decode('utf-8','ignore')

def meaningful(text):
    clean = re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', text)).strip()
    return len(clean) >= 200

def main():
    data = json.loads(P.read_text(encoding='utf-8'))
    now = datetime.now(timezone.utc).isoformat(timespec='seconds').replace('+00:00','Z')
    ok_count = 0
    for src in data.get('sources', []):
        src['checkedAt'] = now
        src['verified'] = False
        src['status'] = 'UNVERIFIABLE'
        src.pop('error', None)
        try:
            code, final_url, text = fetch(src['url'])
            src['httpStatus'] = code
            src['finalUrl'] = final_url
            src['bytesRead'] = len(text.encode('utf-8'))
            if 200 <= code < 400 and meaningful(text):
                src['verified'] = True
                src['status'] = 'VERIFIED'
                ok_count += 1
            else:
                src['status'] = 'UNVERIFIABLE'
                src['error'] = 'Risposta non significativa'
        except Exception as e:
            src['error'] = str(e)[:300]
    data['sourceVerification'] = {
        'checkedAt': now,
        'verified': ok_count,
        'total': len(data.get('sources', [])),
        'allVerified': ok_count == len(data.get('sources', [])) and ok_count > 0
    }
    P.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f'Fonti verificate: {ok_count}/{len(data.get("sources", []))}')

if __name__ == '__main__': main()
