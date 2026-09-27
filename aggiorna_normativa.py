import json, re, ssl, sys, time
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
 {'name':'AMA Roma - Normativa TARI','url':'https://www.amaroma.it/it/tari/normativa','patterns':['TARI']},
 {'name':'AMA Roma - Ravvedimento operoso','url':'https://www.amaroma.it/it/tari/ravvedimento-operoso','patterns':['Ravvedimento','31/03/2026','30/11/2026']},
]

def iso_now(): return datetime.now(timezone.utc).astimezone().isoformat(timespec='seconds')
def load_cfg():
    if not OUT.exists(): raise SystemExit('normativa_tari.json non trovato nella root del repository')
    return json.loads(OUT.read_text(encoding='utf-8'))
def check(src):
    started=iso_now(); t=time.time()
    req=Request(src['url'], headers={'User-Agent':'TARI-Normativa-Monitor/1.0 (+GitHub Actions)','Accept':'text/html,application/xhtml+xml,application/json,text/plain;q=0.9,*/*;q=0.8'})
    try:
        with urlopen(req, timeout=TIMEOUT, context=ssl.create_default_context()) as r:
            raw=r.read(2000000); status=getattr(r,'status',200); ctype=r.headers.get('Content-Type','')
        text=raw.decode('utf-8','ignore'); hits=[p for p in src['patterns'] if p.lower() in text.lower()]
        ok=(200 <= status < 400)
        result='OK' if ok and hits else ('DA_VERIFICARE' if ok else 'ERRORE')
        msg=('Fonte raggiunta; riscontri: '+', '.join(hits)) if hits else 'Fonte raggiunta, ma nessun riscontro configurato trovato'
        return {'name':src['name'],'url':src['url'],'checkedAt':started,'status':result,'httpStatus':status,'message':msg,'responseBytes':len(raw),'contentType':ctype,'elapsedMs':round((time.time()-t)*1000)}
    except HTTPError as e: return {'name':src['name'],'url':src['url'],'checkedAt':started,'status':'ERRORE','httpStatus':e.code,'message':f'HTTP {e.code}','elapsedMs':round((time.time()-t)*1000)}
    except (URLError, TimeoutError, Exception) as e: return {'name':src['name'],'url':src['url'],'checkedAt':started,'status':'ERRORE','httpStatus':None,'message':str(e)[:300],'elapsedMs':round((time.time()-t)*1000)}

def main():
    cfg=load_cfg(); started=iso_now(); results=[check(s) for s in SOURCES]
    cfg['checkedAt']=started
    cfg['sourceStatus']=results
    cfg['monitoring']={'checkedAt':started,'total':len(results),'ok':sum(x['status']=='OK' for x in results),'warning':sum(x['status']=='DA_VERIFICARE' for x in results),'error':sum(x['status']=='ERRORE' for x in results)}
    # sources is the authoritative six-source catalogue; normative values are deliberately not inferred from arbitrary page changes.
    cfg['sources']=[{'name':s['name'],'url':s['url']} for s in SOURCES]
    OUT.write_text(json.dumps(cfg,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(cfg['monitoring'],ensure_ascii=False))
    # Network/source failures are recorded in JSON rather than failing the job; malformed JSON/program failures still fail.
    return 0
if __name__=='__main__': sys.exit(main())
