import MetaTrader5 as mt5
import pandas as pd
import numpy as np
import datetime
from datetime import datetime as dt
from sklearn.linear_model import LinearRegression

#Need to check sl and TP on open orders.
#Some have mysteriously dissapeared on orders

def open_order(buy_sell):
	global symbols
	bid = round(mt5.symbol_info(sym).bid, mt5.symbol_info(sym).digits) #Test to see prices exist
	if bid == 0:
		DF = pd.DataFrame(mt5.copy_ticks_from(sym, (dt.today()), 1, mt5.COPY_TICKS_ALL))
		if len (DF) > 0:
			bid = DF.tail(1)['ask'][0]
	if bid > 0:
		if buy_sell == 'Buy':
			order_type = mt5.ORDER_TYPE_BUY
			sl = round(mt5.symbol_info(sym).bid - seg, mt5.symbol_info(sym).digits)
			tp = round(mt5.symbol_info(sym).ask + seg, mt5.symbol_info(sym).digits)
			if mt5.symbol_info(sym).bid > tp:
				tp = mt5.symbol_info(sym).bid + mt5.symbol_info(sym).point #Fix for tp less than bid price
		elif buy_sell == 'Sell':
			order_type = mt5.ORDER_TYPE_SELL
			sl = round(mt5.symbol_info(sym).bid + seg, mt5.symbol_info(sym).digits)
			tp = round(mt5.symbol_info(sym).ask - seg, mt5.symbol_info(sym).digits)
			if mt5.symbol_info(sym).bid < tp: 
				tp = mt5.symbol_info(sym).bid - mt5.symbol_info(sym).point #Fix for tp less than bid price


		volume = round(int(((mt5.account_info().balance/100)*percent)/bid/mt5.symbol_info(sym).volume_step)*mt5.symbol_info(sym).volume_step, mt5.symbol_info(sym).digits)
		if volume > mt5.symbol_info(sym).volume_max:
			volume = mt5.symbol_info(sym).volume_max
			#Need to know better volume amount with leverage and margins

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
			if result.retcode != 10009:
				if sym in symbols:
					symbols = symbols.drop(sym) #Using this for the moment until a sl formula and other bug fixes can be found.
				else:
					break
			target = result.retcode
			print (result.comment, buy_sell, sym)


#Open EMA values file
try:
	LR_Values = pd.read_csv('LR_Values.csv', index_col=0)
except:
	print ('No LR_Values.csv found, run calc_ema prior to running the Expert Advisor')

#Sort values to highest cash return
LR_Values = LR_Values.sort_values(by=['max_cash'], ascending=False)
symbols = LR_Values.index


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

		#Check current EMA values
		#DataFrame cleanup
		DF = pd.DataFrame(mt5.copy_ticks_from(sym, (dt.today()), 1000000, mt5.COPY_TICKS_ALL)) #Need to do a final simulation test to verify correct LR_Values
		if len(DF) > 0 and sym not in open_sym and len(open_sym) < (100/percent):
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