

def load():
    try: return json.loads(STATE.read_text())
    except (OSError,ValueError): return None


def save(state):
    tmp=STATE.with_suffix('.tmp')
    tmp.write_text(json.dumps(state))
    tmp.replace(STATE)


def token_balances(tx, key):
    meta=tx.get('meta') or {}
    result={}
    for side,sign in (('preTokenBalances',-1),('postTokenBalances',1)):
        for b in meta.get(side) or []:
            if b.get('owner')!=key: continue
            mint=b.get('mint')
            amount=(b.get('uiTokenAmount') or {}).get('amount','0')
            decimals=int((b.get('uiTokenAmount') or {}).get('decimals',0))
            if not mint: continue
            k=(mint,decimals)
            result[k]=result.get(k,0)+sign*int(amount)
    return result


def changes(tx):
    if (tx.get('meta') or {}).get('err') is not None: return []
    msg=(tx.get('transaction') or {}).get('message') or {}
    keys=[x.get('pubkey') if isinstance(x,dict) else x for x in msg.get('accountKeys') or []]
    meta=tx.get('meta') or {}
    result=[]
    if WALLET in keys:
        idx=keys.index(WALLET)
        pre=meta.get('preBalances') or []
        post=meta.get('postBalances') or []
        if idx<len(pre) and idx<len(post):
            delta=post[idx]-pre[idx]
            if delta: result.append(('SOL',Decimal(delta)/Decimal(10**9)))
    for (mint,decimals),delta in token_balances(tx,WALLET).items():
        if delta: result.append((mint,Decimal(delta)/(Decimal(10)**decimals)))
    return result


def alert(sig, items):
    lines=['🔥 <b>PATOSHI HOT WALLET — HAREKET</b>','',f'👛 <code>{WALLET}</code>','']
    for mint,amount in items:
        direction='🟢 GİRİŞ' if amount>0 else '🔴 ÇIKIŞ'
        amount_text=format(abs(amount),'f')
        asset='SOL' if mint=='SOL' else f'<code>{html.escape(mint)}</code>'
        lines.append(f'{direction}: <b>{amount_text}</b> {asset}')
    lines += ['',f'🔗 https://solscan.io/tx/{sig}']
    notify('\n'.join(lines))


def latest():
    return rpc('getSignaturesForAddress',[WALLET,{'limit':100,'commitment':'confirmed'}]) or []


def run():
    if not WALLET or not BOT or not CHAT or not RPC or RPC.endswith('/v2/'):
        raise RuntimeError('HOT_WALLET_ADDRESS, ALCHEMY_API_KEY (or SOLANA_RPC_URL), BOT_TOKEN and CHAT_ID required')
    state=load()
    if state is None:
        rows=latest()
        state={'cursor':rows[0]['signature'] if rows else None}
        save(state)
        logging.info('Initialized at latest signature; no historical spam')
    notify('🛰️ <b>PATOSHI HOT WALLET WATCH AKTİF</b>\n👛 <code>'+html.escape(WALLET)+'</code>')
    while True:
        try:
            rows=latest()
            cursor=state.get('cursor')
            pending=[]
            for row in rows:
                if row.get('signature')==cursor: break
                pending.append(row)
            if cursor and len(rows)==100 and not any(x.get('signature')==cursor for x in rows):
                logging.warning('More than 100 new signatures; pagination needed; retaining cursor and retrying')
                # Backfill the gap using pagination, bounded to avoid runaway credits.
                before=rows[-1]['signature']
                for _ in range(20):
                    extra=rpc('getSignaturesForAddress',[WALLET,{'limit':100,'before':before,'commitment':'confirmed'}]) or []
                    if not extra: break
                    found=False
                    for row in extra:
                        if row.get('signature')==cursor: found=True; break
                        pending.append(row)
                    if found: break
                    before=extra[-1]['signature']
                else:
                    logging.error('Backlog > 2100 signatures, cannot guarantee completeness; retry later')
                    time.sleep(INTERVAL)
                    continue
            for row in reversed(pending):
                sig=row.get('signature')
                if not sig: continue
                tx=rpc('getTransaction',[sig,{'encoding':'jsonParsed','commitment':'confirmed','maxSupportedTransactionVersion':0}])
                if tx is None:
                    logging.warning('Transaction not yet available: %s',sig)
                    break
                deltas=changes(tx)
                if deltas: alert(sig,deltas)
                state['cursor']=sig
                save(state)
            time.sleep(INTERVAL)
        except Exception:
            logging.exception('Watcher error, retrying')
            time.sleep(max(10,INTERVAL))


if __name__=='__main__': run()
