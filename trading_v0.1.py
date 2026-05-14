import time
import requests
import json
from datetime import datetime

# 설정 변수 (예시값)
ACCESS_TOKEN = '[접근 토큰]'  # 실제 사용시 발급된 토큰으로 교체
MARKET_SELECT = '1'           # 1:코스피, 2:코스닥, 3:모두
TOP_N = '10'                  # 거래량 상위 N개 (문서는 리스트 반환, 사용시 처리)
PRICE_MAX = 100000            # 현재가 상한 (원)
DAILY_CCI_THRESHOLD = 100     # 일봉 CCI 기준
MIN_30T_CCI = -150            # 30분봉 CCI 기준 (이하)
MIN_SENTI = -30               # 신심리 기준 (이하)
BARS_LOOKBACK = 26            # 26봉 내 저점/고점 비교
UNIT_MIN = '30'               # 분봉 단위(문서에 tic_scope 등으로 전달)
BUY_QTY = '1'                 # 매수수량(문자열로 전송 필요)

# API 호출 함수들 (참고문서의 함수 정의 형식 그대로 사용)
def fn_ka00198(token, data, cont_yn='N', next_key=''):
	# 실시간종목조회순위
	host = 'https://api.kiwoom.com'
	endpoint = '/api/dostk/stkinfo'
	url =  host + endpoint
	headers = {
		'Content-Type': 'application/json;charset=UTF-8',
		'authorization': f'Bearer {token}',
		'cont-yn': cont_yn,
		'next-key': next_key,
		'api-id': 'ka00198',
	}
	response = requests.post(url, headers=headers, json=data)
	return response

def fn_ka10081(token, data, cont_yn='N', next_key=''):
	# 주식일봉차트조회요청
	host = 'https://api.kiwoom.com'
	endpoint = '/api/dostk/chart'
	url =  host + endpoint
	headers = {
		'Content-Type': 'application/json;charset=UTF-8',
		'authorization': f'Bearer {token}',
		'cont-yn': cont_yn,
		'next-key': next_key,
		'api-id': 'ka10081',
	}
	response = requests.post(url, headers=headers, json=data)
	return response

def fn_ka10080(token, data, cont_yn='N', next_key=''):
	# 주식분봉차트조회요청
	host = 'https://api.kiwoom.com'
	endpoint = '/api/dostk/chart'
	url =  host + endpoint
	headers = {
		'Content-Type': 'application/json;charset=UTF-8',
		'authorization': f'Bearer {token}',
		'cont-yn': cont_yn,
		'next-key': next_key,
		'api-id': 'ka10080',
	}
	response = requests.post(url, headers=headers, json=data)
	return response

def fn_kt10000(token, data, cont_yn='N', next_key=''):
	# 주식 매수주문
	host = 'https://api.kiwoom.com'
	endpoint = '/api/dostk/ordr'
	url =  host + endpoint
	headers = {
		'Content-Type': 'application/json;charset=UTF-8',
		'authorization': f'Bearer {token}',
		'cont-yn': cont_yn,
		'next-key': next_key,
		'api-id': 'kt10000',
	}
	response = requests.post(url, headers=headers, json=data)
	return response

def fn_kt10001(token, data, cont_yn='N', next_key=''):
	# 주식 매도주문
	host = 'https://api.kiwoom.com'
	endpoint = '/api/dostk/ordr'
	url =  host + endpoint
	headers = {
		'Content-Type': 'application/json;charset=UTF-8',
		'authorization': f'Bearer {token}',
		'cont-yn': cont_yn,
		'next-key': next_key,
		'api-id': 'kt10001',
	}
	response = requests.post(url, headers=headers, json=data)
	return response

# 보조지표 계산 유틸리티 (CCI 및 신심리 예시)
def calculate_cci(prices, period=20):
	if len(prices) < period:
		return None
	typical = [(p['high'] + p['low'] + p['close'])/3.0 for p in prices]
	sma = sum(typical[-period:]) / period
	mean_dev = sum([abs(t - sma) for t in typical[-period:]]) / period
	if mean_dev == 0:
		return 0
	last_typ = typical[-1]
	cci = (last_typ - sma) / (0.015 * mean_dev) if mean_dev != 0 else 0
	return cci

def example_sentiment_indicator(prices):
	# 신심리는 제공 API가 없으므로 임시 계산(실전에서는 전용 API/모듈 필요)
	# 여기서는 최근 등락폭을 기반한 간단한 지표로 대체
	if not prices: return 0
	recent = prices[-5:]
	change = (recent[-1]['close'] - recent[0]['close']) / max(1, recent[0]['close']) * 100
	return change  # 예: -30 이하 등 조건 비교용

# 메인 흐름
def find_and_trade():
	# 1) 거래량 상위 종목 조회
	res = fn_ka00198(ACCESS_TOKEN, {'qry_tp': '1'})  # 1분 기준 예시
	if res.status_code != 200:
		print('ka00198 에러', res.status_code, res.text); return
	body = res.json()
	items = body.get('item_inq_rank', [])[:int(TOP_N)]
	candidates = []
	for it in items:
		try:
			stk_cd = it.get('stk_cd')
			# 2) 현재가 필터(현재가는 별도 API로 얻기도 하나 item_inq_rank에 past_curr_prc 존재)
			# past_curr_prc 예시 "+70700" 형태 -> 정수로 변환
			curr = it.get('past_curr_prc', '0').replace('+','').replace('-','')
			curr_price = int(curr) if curr.isdigit() else 0
			if curr_price <= PRICE_MAX:
				candidates.append(stk_cd)
		except Exception as e:
			continue

	# 3) 후보 종목별 조건확인 (일봉 CCI, 30분봉 CCI 및 신심리)
	final_buy = None
	for code in candidates:
		# 일봉 조회
		daily_res = fn_ka10081(ACCESS_TOKEN, {'stk_cd': code, 'base_dt': datetime.now().strftime('%Y%m%d'), 'upd_stkpc_tp': '1'})
		if daily_res.status_code != 200:
			continue
		daily_body = daily_res.json()
		daily_list = daily_body.get('stk_dt_pole_chart_qry', [])
		# 변환: 각 원소에서 open_pric/high_pric/low_pric/cur_prc 등 숫자 추출
		daily_prices = []
		for d in reversed(daily_list):  # 오래된 -> 최신
			try:
				daily_prices.append({
					'open': float(d.get('open_pric', '0').replace('+','').replace('-','') or 0),
					'high': float(d.get('high_pric', '0').replace('+','').replace('-','') or 0),
					'low': float(d.get('low_pric', '0').replace('+','').replace('-','') or 0),
					'close': float(d.get('cur_prc', '0').replace('+','').replace('-','') or 0)
				})
			except:
				continue
		cci_daily = calculate_cci(daily_prices, period=20)
		if cci_daily is None: continue
		if cci_daily > DAILY_CCI_THRESHOLD: continue

		# 분봉(30분) 조회 - base_dt 선택은 선택적
		min_res = fn_ka10080(ACCESS_TOKEN, {'stk_cd': code, 'tic_scope': UNIT_MIN, 'upd_stkpc_tp': '1'})
		if min_res.status_code != 200:
			continue
		min_body = min_res.json()
		min_list = min_body.get('stk_min_pole_chart_qry', [])
		min_prices = []
		for m in reversed(min_list):
			try:
				min_prices.append({
					'open': float(m.get('open_pric', '0').replace('+','').replace('-','') or 0),
					'high': float(m.get('high_pric', '0').replace('+','').replace('-','') or 0),
					'low': float(m.get('low_pric', '0').replace('+','').replace('-','') or 0),
					'close': float(m.get('cur_prc', '0').replace('+','').replace('-','') or 0)
				})
			except:
				continue
		cci_30 = calculate_cci(min_prices, period=20)
		if cci_30 is None: continue
		if cci_30 >= MIN_30T_CCI: continue

		senti = example_sentiment_indicator(min_prices)
		if senti > MIN_SENTI: continue

		# 26봉 내 저점 반등 시도 확인: 간단히 최근 BARS_LOOKBACK 봉에서 최저점 이후 상승한지 확인
		if len(min_prices) < BARS_LOOKBACK: continue
		window = min_prices[-BARS_LOOKBACK:]
		lows = [p['low'] for p in window]
		min_idx = lows.index(min(lows))
		# 저점 이후 최근 봉이 저점보다 높다면 반등 시도로 간주
		if min_idx < len(window)-1 and window[-1]['close'] > window[min_idx]['low']:
			final_buy = code
			break

	# 4) 매수 실행 (조건충족 시)
	if final_buy:
		print('매수 후보:', final_buy)
		order_params = {
			'dmst_stex_tp': 'KRX',  # 예시: 거래소 지정 필요(실제 종목에 맞춰 변경)
			'stk_cd': final_buy,
			'ord_qty': BUY_QTY,
			'ord_uv': '',       # 시장가 등 필요 시 가격 설정
			'trde_tp': '3',     # 예: 시장가
			'cond_uv': ''
		}
		# 실제 주문 호출은 주석 처리 (요청에 따라 활성화 가능)
		# buy_res = fn_kt10000(ACCESS_TOKEN, order_params)
		# print(buy_res.status_code, buy_res.text)
		print('매수주문 준비됨 (주석처리됨)')

	# 5) 매도 조건은 보유종목 조회 후 유사하게 처리 (생략)