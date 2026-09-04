# PATOSHI RADAR V5.2 - Alchemy Activity + SPL Transfer Watch
import os, time, threading, requests
from transfer_watch import scan_token
from transfer_classifier import classify_transfers
from round3_watch import check_transfers

ALCHEMY_API_KEY = os.getenv('ALCHEMY_API_KEY','').strip()
RPC_URL = f'https://solana-mainnet.g.alchemy.com/v2/{ALCHEMY_API_KEY}'
WATCH_SECONDS = int(os.getenv('WATCH_SECONDS','60'))
POLL_SECONDS = int(os.getenv('POLL_SECONDS','5'))
MAX_WATCHES = int(os.getenv('MAX_WATCHES','25'))
RAYDIUM_PROGRAM_ID='675kPX9MHTjS2zt1qfr1NYHuzeLXfQM9H24wFSUt1Mp8'

watch_tokens={}
lock=threading.RLock()
running=False
worker_thread=None
callback=None
round3_callback=None
req_id=1000
req_lock=threading.Lock()
TOKEN_ACCOUNT_REFRESH_EVERY = 3

def log(x): print(x, flush=True)

def _id():
    global req_id
    with req_lock:
        req_id += 1
        return req_id

def _rpc(method, params):
    if not ALCHEMY_API_KEY: return None
    try:
        r=requests.post(
            RPC_URL,
            json={'jsonrpc':'2.0','id':_id(),'method':method,'params':params},
            timeout=10
        )
        if r.status_code==429:
            log(f'⚠️ ALCHEMY RATE LIMIT => {method}')
            return None
        r.raise_for_status()
        d=r.json()
        if 'error' in d:
            log(f"❌ ALCHEMY RPC => {d['error']}")
            return None
        return d.get('result')
    except Exception as e:
        log(f'⚠️ ALCHEMY HTTP => {method} | {e}')
        return None

def _strings(v,out=None):
    out=[] if out is None else out
    if isinstance(v,str): out.append(v.lower())
    elif isinstance(v,dict):
        for x in v.values(): _strings(x,out)
    elif isinstance(v,list):
        for x in v: _strings(x,out)
    return out

def _event(tx):
    text=' '.join(_strings(tx))
    programs=set()
    msg=(tx.get('transaction') or {}).get('message') or {}
    for ix in msg.get('instructions') or []:
        if isinstance(ix,dict) and ix.get('programId'): programs.add(ix['programId'])
    meta=tx.get('meta') or {}
    for g in meta.get('innerInstructions') or []:
        for ix in g.get('instructions') or []:
            if isinstance(ix,dict) and ix.get('programId'): programs.add(ix['programId'])
    dex=None
    if RAYDIUM_PROGRAM_ID in programs or 'raydium' in text: dex='Raydium'
    elif 'pumpswap' in text or 'pump swap' in text: dex='PumpSwap'
    elif any(x in text for x in ('swap','amm','cpmm','route')): dex='DEX'
    lp=any(x in text for x in ('initialize_pool','create_pool','add_liquidity','liquidity'))
    buy=any(x in text for x in ('exact_tokens_for_sol','exact_sol_for_tokens','buy'))
    return lp,dex,buy

def set_result_callback(cb):
    global callback
    callback=cb

def set_round3_callback(cb):
    global round3_callback
    round3_callback=cb
    log("🧩 V5.2 ROUND 3 CALLBACK HAZIR")

def add_token(mint,name='',symbol='',creator='',launch_signature=''):
    if not mint: return False
    with lock:
        if mint in watch_tokens or len(watch_tokens)>=MAX_WATCHES: return False
        watch_tokens[mint]={
            'mint':mint,'name':name,'symbol':symbol,'creator':creator,
            'launch_signature':launch_signature,'started':time.time(),
            'seen':set(),'transfer_seen':set(),'transfer_summary':[],
            'token_accounts':[],'scan_count':0,'lp':False,'dex':None,
            'buy':False,'lp_sig':None,'dex_sig':None,'buy_sig':None
        }
    log(f'👁️ V5.2 WATCH BAŞLADI => {mint} | {WATCH_SECONDS}s')
    return True

def _emit_round3(item,event):
    if not event or round3_callback is None: return
    payload={
        'round3':True,'mint':item['mint'],'name':item['name'],
        'symbol':item['symbol'],'creator':item['creator'],
        'signature':event.get('signature',''),
        'label':event.get('label',''),'reason':event.get('reason',''),
        'transfers':event.get('transfers') or [],
        'round3_new_matches':event.get('round3_new_matches') or [],
        'round3_matches':event.get('round3_matches') or [],
        'round3_total':event.get('round3_total',0),
        'elapsed_seconds':int(time.time()-item['started'])
    }
    try: round3_callback(payload)
    except Exception as e: log(f'❌ V5.2 ROUND 3 CALLBACK => {e}')

def _process(mint):
    with lock:
        item=watch_tokens.get(mint)
    if not item: return

    rows=_rpc('getSignaturesForAddress',[mint,{'limit':20,'commitment':'confirmed'}]) or []
    for row in reversed(rows):
        sig=row.get('signature') if isinstance(row,dict) else None
        if not sig or sig in item['seen'] or sig==item['launch_signature']: continue
        item['seen'].add(sig)
        tx=_rpc('getTransaction',[sig,{'encoding':'jsonParsed','commitment':'confirmed','maxSupportedTransactionVersion':0}])
        if not tx: continue
        lp,dex,buy=_event(tx)
        if lp and not item['lp']: item['lp']=True; item['lp_sig']=sig
        if dex and not item['dex']: item['dex']=dex; item['dex_sig']=sig
        if buy and not item['buy']: item['buy']=True; item['buy_sig']=sig

    try:
        item['scan_count'] += 1
        token_accounts = None if (
            not item.get('token_accounts')
            or item['scan_count'] % TOKEN_ACCOUNT_REFRESH_EVERY == 0
        ) else item.get('token_accounts')

        transfers,item['token_accounts']=scan_token(
            _rpc,item['mint'],item['launch_signature'],
            item['transfer_seen'],token_accounts
        )
        if transfers:
            round3_event=check_transfers(item['mint'],transfers)
            if round3_event:
                _emit_round3(item,round3_event)

            classified=classify_transfers(transfers,item['creator'])
            existing={x['signature'] for x in item['transfer_summary']}
            for x in classified:
                if x['signature'] not in existing:
                    item['transfer_summary'].append(x)
                    existing.add(x['signature'])
    except Exception as e:
        log(f'⚠️ V5.2 TRANSFER WATCH => {e}')

def _finish(mint):
    with lock:
        item=watch_tokens.pop(mint,None)
    if not item: return
    result={
        'mint':item['mint'],'name':item['name'],'symbol':item['symbol'],
        'creator':item['creator'],'lp_detected':item['lp'],
        'dex_detected':bool(item['dex']),'dex_name':item['dex'],
        'buy_detected':item['buy'],'first_buy_signature':item['buy_sig'],
        'lp_signature':item['lp_sig'],'dex_signature':item['dex_sig'],
        'transfer_summary':item['transfer_summary'],
        'elapsed_seconds':int(time.time()-item['started'])
    }
    if callback:
        try: callback(result)
        except Exception as e: log(f'❌ V5.2 CALLBACK => {e}')

def worker():
    while running:
        try:
            for mint in list(watch_tokens):
                with lock:
                    expired=time.time()-watch_tokens[mint]['started']>=WATCH_SECONDS
                if expired:
                    _finish(mint)
                    continue
                _process(mint)
            time.sleep(POLL_SECONDS)
        except Exception as e:
            log(f'❌ V5.2 WORKER => {e}')
            time.sleep(2)

def start():
    global running,worker_thread
    if running: return
    if not ALCHEMY_API_KEY:
        log('❌ ALCHEMY_API_KEY yok; watch başlatılmadı.')
        return
    running=True
    worker_thread=threading.Thread(
        target=worker,daemon=True,name='PatoshiV52Watch'
    )
    worker_thread.start()
    log('📡 V5.2 ACTIVITY + TRANSFER WATCH AKTİF')

def stop():
    global running
    running=False

def status():
    with lock:
        return {k:dict(v) for k,v in watch_tokens.items()}
