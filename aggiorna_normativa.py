import json, ssl, sys, time
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

OUT = Path('normativa_tari.json')
TIMEOUT = 25
SOURCES = [
 {'name':'Gazzetta Ufficiale','url':'https://www.gazzettaufficiale.it/eli/id/2025/12/13/25A06705','patterns':['1,60','1.60','10 dicembre 2025']},
 {'name':'Normattiva Open Data','url':'https://dati.normattiva.it/','patterns':['OpenData','Ricerca nel catalogo','Atti Repubblica']},
 {'name':'Roma Capitale - TARI','url':'https://www.comune.roma.it/web/it/scheda-servizi.page?contentId=INF656833','patterns':['TARI','121/2026','120/2026']},
 {'name':'Roma Capitale - Deliberazioni','url':'https://www.comune.roma.it/web/it/scheda-servizi.page?contentId=INF41468','patterns':['Regolamenti entrate','318-2025','98 del 4 giugno 2026','239 del 30 luglio 2026']},
 {'name':'AMA Roma - Normativa TARI','url':'https://www.amaroma.it/it/tari/normativa','patterns':['TARI','120','121','239'],'officialMirror':'https://www.comune.roma.it/web/it/scheda-servizi.page?contentId=INF656833','mirrorPatterns':['121/2026','120/2026','Regolamento Tari']},
 {'name':'AMA Roma - Ravvedimento operoso','url':'https://www.amaroma.it/it/tari/ravvedimento-operoso','patterns':['Ravvedimento','31/03/2026','31/05/2026','31/08/2026','30/11/2026'],'officialMirror':'https://www.comune.roma.it/web/it/scheda-servizi.page?contentId=INF1200274','mirrorPatterns':['1,60%','Ravvedimento operoso Tari','Sanzioni applicabili']},
]

def iso_now(): return datetime.now(timezone.utc).isoformat(timespec='seconds')
def load_cfg():
    if not OUT.exists(): raise SystemExit('normativa_tari.json non trovato nella root del repository')
    return json.loads(OUT.read_text(encoding='utf-8'))
def headers(url):
    return {'User-Agent':'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/140 Safari/537.36','Accept':'text/html,application/xhtml+xml,application/json,text/plain;q=0.9,*/*;q=0.8','Accept-Language':'it-IT,it;q=0.9,en;q=0.7'}
def make(src,started,t,status,message,http=None,**extra):
    x={'name':src['name'],'url':src['url'],'checkedAt':started,'status':status,'httpStatus':http,'message':message,'elapsedMs':round((time.time()-t)*1000)}; x.update(extra); return x
def fetch_text(url):
    req=Request(url,headers=headers(url))
    with urlopen(req,timeout=TIMEOUT,context=ssl.create_default_context()) as r:
        raw=r.read(2000000); return raw.decode('utf-8','ignore'),getattr(r,'status',200),r.headers.get('Content-Type',''),len(raw)
def mirror(src,started,t,reason):
    u=src.get('officialMirror')
    if not u: return None
    try:
        text,code,ctype,n=fetch_text(u); hits=[p for p in src.get('mirrorPatterns',[]) if p.lower() in text.lower()]
        if 200 <= code < 400 and hits:
            return make(src,started,t,'OK_FONTE_EQUIVALENTE',f'{reason}; contenuto normativo verificato sulla fonte ufficiale Roma Capitale. Riscontri: '+', '.join(hits),403,verificationUrl=u,verificationHttpStatus=code,verificationType='fonte_ufficiale_equivalente',responseBytes=n,contentType=ctype)
        return make(src,started,t,'DA_VERIFICARE',f'{reason}; fonte ufficiale equivalente raggiunta ma riscontri attesi non trovati.',403,verificationUrl=u,verificationHttpStatus=code)
    except Exception as e:
        return make(src,started,t,'BLOCCO_ACCESSO',f'{reason}; verifica equivalente non conclusiva: {str(e)[:180]}',403,verificationUrl=u)
def check(src):
    started=iso_now(); t=time.time()
    try:
        text,code,ctype,n=fetch_text(src['url']); hits=[p for p in src['patterns'] if p.lower() in text.lower()]
        if 200 <= code < 400 and hits: return make(src,started,t,'OK','Fonte raggiunta; riscontri: '+', '.join(hits),code,responseBytes=n,contentType=ctype)
        if 200 <= code < 400: return make(src,started,t,'DA_VERIFICARE','Fonte raggiunta, ma nessun riscontro configurato trovato',code,responseBytes=n,contentType=ctype)
        return make(src,started,t,'ERRORE',f'HTTP {code}',code)
    except HTTPError as e:
        if e.code == 403 and src.get('officialMirror'):
            return mirror(src,started,t,'AMA blocca la richiesta automatizzata con HTTP 403')
        return make(src,started,t,'ERRORE',f'HTTP {e.code}',e.code)
    except (URLError,TimeoutError) as e: return make(src,started,t,'ERRORE',str(e)[:300])
    except Exception as e: return make(src,started,t,'ERRORE',str(e)[:300])
def main():
    cfg=load_cfg(); started=iso_now(); results=[check(s) for s in SOURCES]
    cfg['checkedAt']=started; cfg['sourceStatus']=results
    cfg['monitoring']={'checkedAt':started,'total':len(results),'ok':sum(x['status'] in ('OK','OK_FONTE_EQUIVALENTE') for x in results),'directOk':sum(x['status']=='OK' for x in results),'verifiedByEquivalentOfficialSource':sum(x['status']=='OK_FONTE_EQUIVALENTE' for x in results),'warning':sum(x['status'] in ('DA_VERIFICARE','BLOCCO_ACCESSO') for x in results),'blocked':sum(x['status']=='BLOCCO_ACCESSO' for x in results),'error':sum(x['status']=='ERRORE' for x in results)}
    cfg['sources']=[{'name':s['name'],'url':s['url']} for s in SOURCES]
    OUT.write_text(json.dumps(cfg,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(cfg['monitoring'],ensure_ascii=False))
    for x in results: print(f"{x['name']}: {x['status']} - HTTP {x.get('httpStatus')} - {x['checkedAt']} - {x['message']}")
    return 0
if __name__=='__main__': sys.exit(main())
