"""Paper trading research assistant. No broker access; all trades virtual.
Uses yfinance's potentially delayed/unverified public quotes. Operates on US weekday
14:30–20:30 UTC schedule; refuses stale data / closed markets. Use at own risk.
"""
import json, os, pathlib, datetime, math, time
from zoneinfo import ZoneInfo
import yfinance as yf

ROOT=pathlib.Path(__file__).parent
FILE=ROOT/'data'/'state.json'
UNIVERSE=['SPY','QQQ','IWM','DIA','XLK','XLF','XLE','XLV','SMH','SOXX','NVDA','MSFT','AAPL','AMZN','GOOGL','META','AVGO','AMD','TSLA','PLTR','JPM','V','COST','WMT','KO']
US=ZoneInfo('America/New_York')
UTC=datetime.timezone.utc
now=datetime.datetime.now(UTC)
local=now.astimezone(US)
state=json.loads(FILE.read_text())

def commit(msg):
    state['updated_at']=now.isoformat(timespec='seconds')
    state['status']=msg
    FILE.write_text(json.dumps(state,ensure_ascii=False,indent=2)+'\n')

def finite(x):
    try:
        x=float(x)
        return x if math.isfinite(x) and x>0 else None
    except (ValueError,TypeError): return None

# No after-hours assumptions. US holidays rejected by quote freshness condition below.
if local.weekday()>4 or not datetime.time(9,35)<=local.time()<datetime.time(16,0):
    commit('미국 정규장 시간이 아니므로 주문하지 않았습니다.')
    raise SystemExit(0)

prices={}; changes={}; history={}
for ticker in UNIVERSE:
    try:
        # Intraday 15-minute bars can lag; latest timestamp is checked below.
        bars=yf.Ticker(ticker).history(period='5d',interval='15m',auto_adjust=True,prepost=False)
        if bars is None or len(bars)<20: continue
        last=bars.index[-1].to_pydatetime().astimezone(UTC)
        if (now-last).total_seconds()>60*65 or last.astimezone(US).date()!=local.date(): continue
        series=[finite(p) for p in bars['Close'].tail(100).tolist()]
        series=[p for p in series if p is not None]
        if len(series)<20: continue
        p=series[-1]
        prices[ticker]=p
        changes[ticker]=round((p/series[-min(26,len(series))]-1)*100,2)
        history[ticker]={'last':round(p,4),'change_approx_pct':changes[ticker],'timestamp':last.isoformat()}
    except Exception as e:
        print('Skip',ticker,str(e)[:160])
if len(prices)<8 or 'SPY' not in prices:
    commit('시세 데이터가 불충분하거나 지연되어 매매를 중단했습니다.')
    raise SystemExit(0)

state['prices'].update(prices)
# Mark-to-market, with historical holdings retained even if a quote is unavailable.
holdings=state['holdings']; cash=float(state['cash'])
def equity(): return cash+sum(float(h['qty'])*prices.get(t,float(h['last_price'])) for t,h in holdings.items())
assets=equity()

# LLM generates suggestions, deterministic validator enforces risk constraints.
# Without key, do not pretend AI acted; hold and report setup requirement.
key=os.environ.get('OPENAI_API_KEY','').strip()
if not key:
    state['snapshots'].append({'time':now.isoformat(),'equity':round(assets,2)})
    state['snapshots']=state['snapshots'][-1000:]
    commit('OPENAI_API_KEY 미설정: 실시간 데이터만 업데이트, AI 매매는 비활성화되었습니다.')
    raise SystemExit(0)

from openai import OpenAI
prompt={
 'asof':now.isoformat(), 'note':'Intraday delayed public quotes; change is approximate last 26 15-min bars, not daily return.',
 'quotes':history,'cash':round(cash,2),'total_assets':round(assets,2),'holdings':holdings,
 'rules':('Return 0 to 3 virtual trade proposals. Choose only tickers from quotes. BUY maximum total 20% equity each run, '
          'max 15% equity per position after trade, keep >=30% equity as cash, no leverage or short sales, '
          'SELL no more than held shares. Avoid unnecessary turnover. Explain briefly in Korean. '
          'Do not use information not provided. Exact JSON object: {"decisions":[{"ticker":"SPY","side":"BUY","allocation_pct":5,"reason":"..."}]} '
          'For SELL allocation_pct is percent of current holding quantity. BUY allocation_pct is percent of total equity. '
          'If data is insufficient, return empty decisions.')
}
try:
    response=OpenAI(api_key=key,timeout=35).chat.completions.create(
        model=os.getenv('OPENAI_MODEL','gpt-4.1-mini'),
        messages=[{'role':'system','content':'You are a cautious PAPER trading decision engine. Never imply real trades. Output strict JSON only.'},
                  {'role':'user','content':json.dumps(prompt,ensure_ascii=False)}],
        temperature=0,response_format={'type':'json_object'})
    proposal=json.loads(response.choices[0].message.content)
except Exception as e:
    commit('AI 분석 실패로 거래하지 않았습니다: '+str(e)[:120])
    raise SystemExit(0)

orders=proposal.get('decisions',[])
if not isinstance(orders,list): orders=[]
used_buy=0.0; executed=[]; seen=set()
for order in orders[:3]:
    if not isinstance(order,dict): continue
    ticker=str(order.get('ticker','')).upper()
    side=str(order.get('side','')).upper()
    pct=finite(order.get('allocation_pct'))
    reason=str(order.get('reason',''))[:240]
    if ticker not in prices or (ticker,side) in seen or side not in ('BUY','SELL') or not pct: continue
    seen.add((ticker,side)); price=prices[ticker]
    if side=='BUY':
        # Hard cap: 20% equity per batch, 15% per ticker, 30% cash buffer.
        existing=holdings.get(ticker,{}).get('qty',0)*price
        amount=min(assets*min(pct,20)/100,assets*0.20-used_buy,
                   max(0,assets*0.15-existing),max(0,cash-assets*0.30))
        qty=math.floor(amount/price*10000)/10000
        if qty<0.0001:continue
        cost=round(qty*price,6)
        if cost>cash:continue
        cash-=cost;used_buy+=cost
        h=holdings.setdefault(ticker,{'qty':0.0,'cost':0.0,'last_price':price})
        h['qty']+=qty;h['cost']+=cost;h['last_price']=price
    else:
        h=holdings.get(ticker)
        if not h or h['qty']<=0: continue
        qty=min(h['qty'],math.floor(h['qty']*min(pct,100)/100*10000)/10000)
        if qty<0.0001:continue
        avg=h['cost']/h['qty'];h['cost']=max(0,h['cost']-avg*qty);h['qty']-=qty;cash+=qty*price
        if h['qty']<0.0001: holdings.pop(ticker,None)
    trade={'time':now.isoformat(),'ticker':ticker,'side':side,'qty':round(qty,4),'price':round(price,4),
           'amount':round(qty*price,2),'reason':reason,'source':'yfinance intraday (possibly delayed) / OpenAI proposal / validated simulation'}
    executed.append(trade)
    state['trades'].append(trade)
state['cash']=round(cash,6)
for t,h in holdings.items():h['last_price']=prices.get(t,h.get('last_price',0))
state['signals']=[{'time':now.isoformat(),'ticker':str(o.get('ticker',''))[:12],
                   'side':str(o.get('side',''))[:8],'reason':str(o.get('reason',''))[:240]}
                  for o in orders[:3] if isinstance(o,dict)]
state['snapshots'].append({'time':now.isoformat(),'equity':round(equity(),2)})
state['snapshots']=state['snapshots'][-1000:]
commit(f'AI 분석 완료: 가상 체결 {len(executed)}건. 시세 {len(prices)}종목. 무료 공개 시세는 지연될 수 있습니다.')
print(state['status'])
