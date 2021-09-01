import MetaTrader5 as mt5
import pandas as pd
import numpy as np
import datetime
from datetime import datetime as dt
from sklearn.linear_model import LinearRegression

#Need to know VOLUME amount
#Need to know: Leverage and how it works


def open_order(buy_sell):
	bid = round(mt5.symbol_info(sym).bid, mt5.symbol_info(sym).digits)
	ask = round(mt5.symbol_info(sym).ask, mt5.symbol_info(sym).digits)
	if bid == 0:
		DF = pd.DataFrame(mt5.copy_ticks_from(sym, (dt.today()), 1, mt5.COPY_TICKS_ALL))
		if len (DF) > 0:
			bid = DF.tail(1)['ask'][0]
	if bid > 0:
		if buy_sell == 'Buy':
			order_type = mt5.ORDER_TYPE_BUY
			sl = round(bid - seg, mt5.symbol_info(sym).digits)
			tp = round(bid + seg, mt5.symbol_info(sym).digits)
		elif buy_sell == 'Sell':
			order_type = mt5.ORDER_TYPE_SELL
			sl = round(bid + seg, mt5.symbol_info(sym).digits)
			tp = round(bid - seg, mt5.symbol_info(sym).digits)


		volume = round(int(((mt5.account_info().balance/100)*percent)/bid/mt5.symbol_info(sym).volume_step)*mt5.symbol_info(sym).volume_step, mt5.symbol_info(sym).digits)
		if volume > mt5.symbol_info(sym).volume_max:
			volume = mt5.symbol_info(sym).volume_max

		volume = 1.00

		target = 0
		sl_count = 0
		while target != 10009:
			request = {
				"action": mt5.TRADE_ACTION_DEAL,
				"symbol": sym,
				"volume": volume,
				"type": order_type,
				"price": bid,
				"sl": sl,
				"tp": tp,
				"deviation": 0,
				"magic": 0,
				"comment": "Python script",
				"type_time": mt5.ORDER_TIME_GTC,
				"type_filling": mt5.ORDER_FILLING_IOC,
			}
			result = mt5.order_send(request)
			if result.retcode == 10016:
				sl += mt5.symbol_info(sym).point
				sl_count +=1
				if sl_count == 100:
					target = 10009
			target = result.retcode
		print (result.comment, buy_sell, sym)


#Open EMA values file
try:
	LR_Values = pd.read_csv('LR_Values.csv')
	LR_Values = LR_Values.sort_values(by=['max_cash'], ascending=False)
	LR_Values.index = LR_Values['Unnamed: 0']
	LR_Values = LR_Values.drop(['Unnamed: 0'], axis=1)
	symbols = LR_Values.index
except:
	print ('No LR_Values.csv found, run calc_ema prior to running the Expert Advisor')

#Set percentage of balance when placing orders
percent = 10

mt5.initialize()


while True:

	for sym in symbols:
		#Open orders check
		open_sym = []
		for order in mt5.positions_get():
			open_sym.append(order.symbol)
			DF = pd.DataFrame(mt5.copy_ticks_from(order.symbol, (dt.today()), 100000, mt5.COPY_TICKS_ALL))
			DF = DF[DF['time'] >= order.time]
			if len(DF) > 0:
				if order.type == 0:
					change_sl = round(DF['bid'].max() - float(LR_Values.loc[order.symbol]['seg']), mt5.symbol_info(order.symbol).digits)
				if order.type == 1:
					change_sl = round(DF['bid'].min() + float(LR_Values.loc[order.symbol]['seg']), mt5.symbol_info(order.symbol).digits)

				#Change sl
				request = {
					"action": mt5.TRADE_ACTION_SLTP,
					"position": order.ticket,
					"tp" : order.tp,
					"sl" : change_sl,
					}
				change = mt5.order_send(request)
				if change.retcode == 10009:
					print (order.symbol, 'sl changed', change_sl)
			#else:
			#	print ('empty dataframe')   #While it timeouts a bit, doesnt take long to kick back in

		#Check current EMA values
		#DataFrame cleanup
		DF = pd.DataFrame(mt5.copy_ticks_from(sym, (dt.today()), 1000000, mt5.COPY_TICKS_ALL))
		if len(DF) > 0 and sym not in open_sym:
			seg = float(LR_Values.loc[sym]['seg'])
			sample = LR_Values.loc[sym]['sample']
			LinReg = LR_Values.loc[sym]['LinReg']
			DF.index = pd.to_datetime(DF['time'], unit='s')
			DF = DF.drop(['volume', 'last', 'time_msc', 'flags', 'volume_real'], axis=1)
			DF.index = pd.to_datetime(DF['time'], unit='s')
			DF = DF.drop_duplicates(subset='time', keep="first")
			DF = DF.resample(sample).fillna("ffill").dropna().drop('time', axis=1)
			if len(DF) >= LinReg:
				y = pd.DataFrame(DF['ask'][-LinReg:])
				X = (pd.DataFrame(range(LinReg)))
				model = LinearRegression()
				model.fit(X,y)
				pred_A = model.predict([[LinReg+1]])
				pred_B = model.predict([[LinReg+2]])


				#Qualify for Buy/Sell
				if pred_B > pred_A:
					open_order('Buy')
					break

				elif pred_B < pred_A:
					open_order("Sell")
					break