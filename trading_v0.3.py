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

# 설정 변수
MARKET_SELECT = '1'
TOP_N = 10
PRICE_MAX = 100000
DAILY_CCI_THRESHOLD = 100
MIN_30T_CCI = -150
MIN_SENTI = -30
BARS_LOOKBACK = 26
UNIT_MIN = '30'
BUY_QTY = '1'

# [추가] 토큰 발급 함수 (Token Generation)
def get_access_token():
    host = 'https://api.kiwoom.com'
    endpoint = '/oauth2/token'
    url = host + endpoint
    params = {
        'grant_type': 'client_credentials',
        'appkey': APP_KEY,
        'secretkey': APP_SECRET
    }
    headers = {'Content-Type': 'application/json;charset=UTF-8'}
    
    try:
        response = requests.post(url, headers=headers, json=params)
        if response.status_code == 200:
            token_data = response.json()
            print(f"토큰 발급 성공! 만료시간: {token_data.get('expires_dt')}")
            return token_data.get('access_token')
        else:
            print(f"토큰 발급 실패: {response.status_code}, {response.text}")
            return None
    except Exception as e:
        print(f"토큰 요청 중 에러 발생: {e}")
        return None

# --- API 호출 함수들 (API Wrapper Functions) ---
def fn_kiwoom_api(api_id, token, data, endpoint, cont_yn='N', next_key=''):
    host = 'https://api.kiwoom.com'
    url = host + endpoint
    headers = {
        'Content-Type': 'application/json;charset=UTF-8',
        'authorization': f'Bearer {token}',
        'cont-yn': cont_yn,
        'next-key': next_key,
        'api-id': api_id,
    }
    return requests.post(url, headers=headers, json=data)

# 보조지표 계산 및 유틸리티 함수 (생략 없이 로직 포함)
def calculate_cci(prices, period=20):
    if len(prices) < period: return None
    typical = [(p['high'] + p['low'] + p['close'])/3.0 for p in prices]
    sma = sum(typical[-period:]) / period
    mean_dev = sum([abs(t - sma) for t in typical[-period:]]) / period
    if mean_dev == 0: return 0
    return (typical[-1] - sma) / (0.015 * mean_dev)

def example_sentiment_indicator(prices):
    if not prices: return 0
    recent = prices[-5:]
    return (recent[-1]['close'] - recent[0]['close']) / max(1, recent[0]['close']) * 100

# --- 메인 로직 (Main Trading Logic) ---
def find_and_trade(token):
    if not token:
        print("유효한 토큰이 없어 프로그램을 종료합니다.")
        return

    print("거래량 상위 종목 분석 중...")
    # 1) 거래량 상위 종목 조회 (ka00198)
    res = fn_kiwoom_api('ka00198', token, {'qry_tp': '1'}, '/api/dostk/stkinfo')
    if res.status_code != 200:
        print('상위 종목 조회 에러:', res.text); return

    items = res.json().get('item_inq_rank', [])[:TOP_N]
    
    for it in items:
        stk_cd = it.get('stk_cd')
        curr = it.get('past_curr_prc', '0').replace('+','').replace('-','')
        curr_price = int(curr) if curr.isdigit() else 0
        
        if curr_price > PRICE_MAX: continue

        # 2) 일봉 CCI 확인 (ka10081)
        daily_res = fn_kiwoom_api('ka10081', token, {'stk_cd': stk_cd, 'base_dt': datetime.now().strftime('%Y%m%d'), 'upd_stkpc_tp': '1'}, '/api/dostk/chart')
        if daily_res.status_code != 200: continue
        
        # ... (중략: 일봉/분봉 CCI 및 신심리 필터링 로직) ...
        # [중요] 필터링 조건 충족 시 아래 매수 실행 부분으로 진입하게 구성

        # 임시 예시: 조건을 통과했다고 가정할 때 매수 실행
        print(f"조건 충족 종목 발견: {stk_cd}")
        order_params = {
            'dmst_stex_tp': 'KRX',
            'stk_cd': stk_cd,
            'ord_qty': BUY_QTY,
            'ord_uv': '', 
            'trde_tp': '3', # 시장가
            'cond_uv': ''
        }
        # buy_res = fn_kiwoom_api('kt10000', token, order_params, '/api/dostk/ordr')
        print(f"[{stk_cd}] 매수 주문 전송 완료 (현재 주석 처리됨)")
        break # 한 종목 매수 후 종료 (예시)

# 3. 프로그램 실행 진입점 (Execution Point)
if __name__ == "__main__":
    print("=== 키움 자동매매 프로그램 시작 ===")
    
    # 실행 시점에 토큰을 새로 발급받음
    access_token = get_access_token()
    
    if access_token:
        find_and_trade(access_token)
    else:
        print("프로그램 초기화 실패: API 접근 권한을 얻지 못했습니다.")