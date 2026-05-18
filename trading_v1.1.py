import os
import time
import requests
import json
from datetime import datetime
from dotenv import load_dotenv

# 1. 환경 변수 로드 (Load Environment Variables)
load_dotenv()
APP_KEY = os.getenv('KIWOOM_APP_KEY')
APP_SECRET = os.getenv('KIWOOM_APP_SECRET')
ACC_NO = os.getenv('KIWOOM_ACC_NO')
# 설정 변수
MARKET_SELECT = '1'
TOP_N = 10
PRICE_MAX = 60000
DAILY_CCI_THRESHOLD = 100
MIN_30T_CCI = -150
MIN_SENTI = -30
BARS_LOOKBACK = 26
UNIT_MIN = '30'
BUY_QTY = '1'

# 토큰 발급 함수 (Token Generation)
def get_access_token():
    host = 'https://api.kiwoom.com'
    endpoint = '/oauth2/token'
    url = host + endpoint
    params = {
        'grant_type': 'client_credentials',
        'appkey': APP_KEY,
        'secretkey': APP_SECRET
    }
    headers = {
        'Content-Type': 'application/json;charset=UTF-8',
    }
    
    try:
        response = requests.post(url, headers=headers, json=params)
        print('Code:', response.status_code)
        print('Header:', json.dumps({key: response.headers.get(key) for key in ['next-key', 'cont-yn', 'api-id']}, indent=4, ensure_ascii=False))

        if response.status_code == 200:
            token_data = response.json()
            print(f"토큰 발급 성공! 만료시간: {token_data.get('expires_dt')}")
            print(token_data.get('token'))
            return token_data
        else:
            try:
                err = response.json()
                print('Body:', json.dumps(err, indent=4, ensure_ascii=False))
            except ValueError:
                print('응답 본문이 JSON이 아닙니다.')    
                print(f"토큰 발급 실패: {response.status_code}, {response.text}")
            return None
    except requests.RequestException as e:
        print('HTTP 요청 중 예외 발생:', str(e))
        return None        

# --- API 호출 함수들 (API Wrapper Functions) ---
def fn_kiwoom_api(api_id, token, data, endpoint, cont_yn='N', next_key=''):
    host = 'https://api.kiwoom.com'
    url = host + endpoint
    headers = {
        'Content-Type': 'application/json;charset=UTF-8',
        'Authorization': f'Bearer {token}',
        'cont-yn': cont_yn,
        'next-key': next_key,
        'api-id': api_id,
    }
    response = requests.post(url, headers=headers, json=data)
    print(f"API {api_id} Response Code:", response.status_code)
    return response

# 보조지표 계산 및 유틸리티 함수
def calculate_cci(prices, period=20):
    if len(prices) < period: 
        return None
    typical = [(p['high'] + p['low'] + p['close'])/3.0 for p in prices]
    sma = sum(typical[-period:]) / period
    mean_dev = sum([abs(t - sma) for t in typical[-period:]]) / period
    if mean_dev == 0: 
        return 0
    return (typical[-1] - sma) / (0.015 * mean_dev)

def example_sentiment_indicator(prices):
    if not prices: 
        return 0
    recent = prices[-5:]
    return (recent[-1]['close'] - recent[0]['close']) / max(1, recent[0]['close']) * 100

# --- 메인 로직 (Main Trading Logic) ---
def find_and_trade(token):
    if not token:
        print("유효한 토큰이 없어 프로그램을 종료합니다.")
        return

    print("거래량 상위 종목 분석 중...")
    res = fn_kiwoom_api('ka00198', token, {'qry_tp': '1'}, '/api/dostk/stkinfo')
    if res.status_code != 200:
        print('상위 종목 조회 에러:', res.text)
        return

    items = res.json().get('item_inq_rank', [])[:TOP_N]
    
    for it in items:
        stk_cd = it.get('stk_cd')
        curr = it.get('past_curr_prc', '0').replace('+','').replace('-','')
        curr_price = int(curr) if curr.isdigit() else 0
        
        if curr_price > PRICE_MAX or curr_price == 0: 
            continue

        # 2) 일봉 CCI 확인 (ka10081)
        daily_res = fn_kiwoom_api('ka10081', token, {'stk_cd': stk_cd, 'base_dt': datetime.now().strftime('%Y%m%d'), 'upd_stkpc_tp': '1'}, '/api/dostk/chart')
        if daily_res.status_code != 200: 
            continue
        
        daily_list = daily_res.json().get('stk_dt_pole_chart_qry', [])
        if not daily_list: 
            continue

        daily_prices = []
        for d in reversed(daily_list):
            daily_prices.append({
                'high': float(d.get('high_pric', 0).replace('+','').replace('-','')),
                'low': float(d.get('low_pric', 0).replace('+','').replace('-','')),
                'close': float(d.get('cur_prc', 0).replace('+','').replace('-',''))
            })
        
        cci_daily = calculate_cci(daily_prices, period=20)
        if cci_daily is None or cci_daily > DAILY_CCI_THRESHOLD:
            continue

        # 3) 분봉(30분) CCI 및 신심리 확인 (ka10080)
        min_res = fn_kiwoom_api('ka10080', token, {'stk_cd': stk_cd, 'tic_scope': UNIT_MIN, 'upd_stkpc_tp': '1'}, '/api/dostk/chart')
        if min_res.status_code != 200:
            continue

        min_list = min_res.json().get('stk_min_pole_chart_qry', [])
        if not min_list: 
            continue

        min_prices = []
        for m in reversed(min_list):
            min_prices.append({
                'high': float(m.get('high_pric', 0).replace('+','').replace('-','')),
                'low': float(m.get('low_pric', 0).replace('+','').replace('-','')),
                'close': float(m.get('cur_prc', 0).replace('+','').replace('-',''))
            })

        cci_30 = calculate_cci(min_prices, period=20)
        if cci_30 is None or cci_30 >= MIN_30T_CCI:
            continue

        senti = example_sentiment_indicator(min_prices)
        if senti > MIN_SENTI:
            continue

        # 4) 26봉 내 저점 반등 확인
        if len(min_prices) < BARS_LOOKBACK:
            continue

        recent_window = min_prices[-BARS_LOOKBACK:]
        lows = [p['low'] for p in recent_window]
        min_val = min(lows)
        min_idx = lows.index(min_val)   

        if min_idx < len(recent_window) - 1 and recent_window[-1]['close'] > min_val:
            print(f"🔥 매수 조건 적합 종목 발견: {stk_cd} (CCI_D: {cci_daily:.2f}, CCI_30: {cci_30:.2f}, Senti: {senti:.2f})")
            
            # [보완] 수량이 0이 되지 않도록 최소 1주 보장 예외처리
            calculated_qnt = int(PRICE_MAX / curr_price) if curr_price > 0 else 0
            Real_Buy_Qnt = max(1, calculated_qnt)
            
            order_params = {
                'dmst_stex_tp': 'KRX',
                'stk_cd': stk_cd,
                'ord_qty': str(Real_Buy_Qnt),  # 문자열로 전송 요구 대응
                'ord_uv': '', 
                'trde_tp': '3', 
                'cond_uv': ''
            }
            buy_res = fn_kiwoom_api('kt10000', token, order_params, '/api/dostk/ordr')

            if buy_res.status_code == 200:
                print(f"✅ [{stk_cd}] 매수 주문 성공! 응답: {buy_res.json()}")
            else:
                print(f"❌ [{stk_cd}] 매수 주문 실패: {buy_res.text}")
            
            break

def check_and_sell(token):
    print("보유 종목 매도 조건 감시 중...")
    
    # [주의] '내계좌번호' 부분은 반드시 자신의 실제 계좌번호 문자열로 채워야 작동합니다.
    res = fn_kiwoom_api('ka10085', token, {'acc_no': ACC_NO, 'pw': ''}, '/api/dostk/accinfo')
    if res.status_code != 200:
        print("잔고 조회 실패")
        return

    my_stocks = res.json().get('stk_acc_rat_qry', [])

    for stock in my_stocks:
        stk_cd = stock.get('stk_cd')
        buy_price = float(stock.get('buy_avg_pric', 0))
        curr_price = float(stock.get('cur_prc', 0).replace('+', '').replace('-', ''))
        hold_qty = stock.get('hold_qty')

        profit_rate = ((curr_price - buy_price) / buy_price) * 100 if buy_price > 0 else 0

        should_sell = False
        reason = ""

        if profit_rate >= 5.0:
            should_sell = True
            reason = f"익절 달성 ({profit_rate:.2f}%)"
        elif profit_rate <= -3.0:
            should_sell = True
            reason = f"손절 범위 도달 ({profit_rate:.2f}%)"
        else:
            min_res = fn_kiwoom_api('ka10080', token, {'stk_cd': stk_cd, 'tic_scope': UNIT_MIN, 'upd_stkpc_tp': '1'}, '/api/dostk/chart')
            if min_res.status_code == 200:
                min_list = min_res.json().get('stk_min_pole_chart_qry', [])
                min_prices = []
                for m in reversed(min_list):
                    min_prices.append({
                        'high': float(m.get('high_pric', 0).replace('+','').replace('-','')),
                        'low': float(m.get('low_pric', 0).replace('+','').replace('-','')),
                        'close': float(m.get('cur_prc', 0).replace('+','').replace('-',''))
                    })
                
                cci_30 = calculate_cci(min_prices, period=20)
                if cci_30 and cci_30 > 150:
                    should_sell = True
                    reason = f"CCI 과열 ({cci_30:.2f})"

        if should_sell:
            print(f"🚨 매도 신호 발생: {stk_cd} | 사유: {reason}")
            sell_params = {
                'dmst_stex_tp': 'KRX',
                'stk_cd': stk_cd,
                'ord_qty': str(hold_qty),
                'ord_uv': '', 
                'trde_tp': '3', 
                'cond_uv': ''
            }
            sell_res = fn_kiwoom_api('kt10001', token, sell_params, '/api/dostk/ordr')
            
            if sell_res.status_code == 200:
                print(f"✅ [{stk_cd}] 매도 완료: {reason}")
            else:
                print(f"❌ [{stk_cd}] 매도 실패: {sell_res.text}")

# 3. 프로그램 실행 진입점 (Execution Point)
if __name__ == "__main__":
    print("=== 키움 자동매매 프로그램 시작 ===")
       
    access_token_data = get_access_token()
    if access_token_data:
        actual_token = access_token_data.get('token') or access_token_data.get('access_token')
        if actual_token:
            print(f"로그인 성공. 토큰(앞 10자): {actual_token[:10]}...")

            while True:
                # 1. 새로운 매수 종목 찾기
                find_and_trade(actual_token)
            
                # 2. 보유 종목 매도 체크
                check_and_sell(actual_token)
            
                # 3. API 과부하 방지를 위한 대기 (1분 반복)
                print("1분 후 다시 스캔합니다...")
                time.sleep(60)
        else:
            print("오류: 발급된 데이터 내에 토큰 문자열이 없습니다.")        
    else:
        print("프로그램 초기화 실패: API 접근 권한을 얻지 못했습니다.")