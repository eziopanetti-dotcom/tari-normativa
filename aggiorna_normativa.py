import json, ssl, sys, time
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

OUT = Path('normativa_tari.json')
TIMEOUT = 25
SOURCES = [
 {'name':'Gazzetta Ufficiale','url':'https://www.gazzettaufficiale.it/eli/id/2025/12/13/25A06705','patterns':['1,60','1.60','10 dicembre 2025']},
 {'name':'Normattiva Open Data','url':'https://dati.normattiva.it/','patterns':['Normattiva','Open Data']},
 {'name':'Roma Capitale - TARI','url':'https://www.comune.roma.it/web/it/scheda-servizi.page?contentId=INF656833','patterns':['TARI']},
 {'name':'Roma Capitale - Deliberazioni','url':'https://www.comune.roma.it/web/it/deliberazioni-atti-e-regolamenti.page','patterns':['Deliberazioni','atti']},
 {'name':'AMA Roma - Normativa TARI','url':'https://www.amaroma.it/it/tari/normativa','patterns':['TARI','120','121','239'],'allow403':True},
 {'name':'AMA Roma - Ravvedimento operoso','url':'https://www.amaroma.it/it/tari/ravvedimento-operoso','patterns':['Ravvedimento','31/03/2026','31/05/2026','31/08/2026','30/11/2026'],'allow403':True},
]

def iso_now():
    return datetime.now(timezone.utc).isoformat(timespec='seconds')

def load_cfg():
    if not OUT.exists():
        raise SystemExit('normativa_tari.json non trovato nella root del repository')
    return json.loads(OUT.read_text(encoding='utf-8'))

def browser_headers(url):
    return {
      'User-Agent':'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36',
      'Accept':'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
      'Accept-Language':'it-IT,it;q=0.9,en;q=0.7',
      'Cache-Control':'no-cache',
      'Pragma':'no-cache',
      'Referer':'https://www.amaroma.it/' if 'amaroma.it' in url else url,
    }

def result(src, started, t, status, message, **extra):
    x={'name':src['name'],'url':src['url'],'checkedAt':started,'status':status,'message':message,'elapsedMs':round((time.time()-t)*1000)}
    x.update(extra)
    return x

def check(src):
    started=iso_now(); t=time.time(); req=Request(src['url'], headers=browser_headers(src['url']))
    try:
        with urlopen(req, timeout=TIMEOUT, context=ssl.create_default_context()) as r:
            raw=r.read(2000000); code=getattr(r,'status',200); ctype=r.headers.get('Content-Type','')
        text=raw.decode('utf-8','ignore'); hits=[p for p in src['patterns'] if p.lower() in text.lower()]
        if 200 <= code < 400 and hits:
            return result(src,started,t,'OK','Fonte raggiunta; riscontri: '+', '.join(hits),httpStatus=code,responseBytes=len(raw),contentType=ctype)
        if 200 <= code < 400:
            return result(src,started,t,'DA_VERIFICARE','Fonte raggiunta, ma nessun riscontro configurato trovato',httpStatus=code,responseBytes=len(raw),contentType=ctype)
        return result(src,started,t,'ERRORE',f'HTTP {code}',httpStatus=code)
    except HTTPError as e:
        # AMA currently rejects GitHub-hosted automated requests with HTTP 403.
        # Do not turn this into a false OK: record it explicitly as access blocked.
        if e.code == 403 and src.get('allow403'):
            return result(src,started,t,'BLOCCO_ACCESSO','HTTP 403: la fonte ufficiale e online ma rifiuta la richiesta automatizzata dal runner GitHub. Nessun dato e stato considerato verificato.',httpStatus=403)
        return result(src,started,t,'ERRORE',f'HTTP {e.code}',httpStatus=e.code)
    except (URLError, TimeoutError) as e:
        return result(src,started,t,'ERRORE',str(e)[:300],httpStatus=None)
    except Exception as e:
        return result(src,started,t,'ERRORE',str(e)[:300],httpStatus=None)

def main():
    cfg=load_cfg(); started=iso_now(); results=[check(s) for s in SOURCES]
    cfg['checkedAt']=started
    cfg['sourceStatus']=results
    cfg['monitoring']={
      'checkedAt':started,'total':len(results),
      'ok':sum(x['status']=='OK' for x in results),
      'warning':sum(x['status'] in ('DA_VERIFICARE','BLOCCO_ACCESSO') for x in results),
      'blocked':sum(x['status']=='BLOCCO_ACCESSO' for x in results),
      'error':sum(x['status']=='ERRORE' for x in results)
    }
    cfg['sources']=[{'name':s['name'],'url':s['url']} for s in SOURCES]
    OUT.write_text(json.dumps(cfg,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(cfg['monitoring'],ensure_ascii=False))
    for x in results:
        print(f"{x['name']}: {x['status']} - HTTP {x.get('httpStatus')} - {x['checkedAt']} - {x['message']}")
    return 0

if __name__=='__main__':
    sys.exit(main())
