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
			tp = round(ask + seg, mt5.symbol_info(sym).digits)
		elif buy_sell == 'Sell':
			order_type = mt5.ORDER_TYPE_SELL
			sl = round(ask + seg, mt5.symbol_info(sym).digits)
			tp = round(bid - seg, mt5.symbol_info(sym).digits)
		volume = round(int(((mt5.account_info().balance/100)*percent)/bid/mt5.symbol_info(sym).volume_step)*mt5.symbol_info(sym).volume_step, mt5.symbol_info(sym).digits)
		if volume > mt5.symbol_info(sym).volume_max:
			volume = mt5.symbol_info(sym).volume_max
		#if volume < mt5.symbol_info(sym).volume_min:
		#	symbols = symbols.delete(sym)
		#	print ('symbol removed')
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
		if result.retcode == 10009:
			print (buy_sell, sym)
		elif result.retcode == 10016:
			print ('invalid stops', buy_sell, 'Seg:', seg, 'Ask:', ask)
			print (request)
		elif result.retcode == 10014:
			print (sym, 'min/max error')
		else:
			print (buy_sell, 'Error:', result.retcode)
			print (request)


#Open LR values file
try:
	LR_Values = pd.read_csv('LR_Values.csv')
	LR_Values = LR_Values.sort_values(by=['max_cash'], ascending=False)
	LR_Values.index = LR_Values['Unnamed: 0']
	LR_Values = LR_Values.drop(['Unnamed: 0'], axis=1)
	symbols = LR_Values.index
except:
	print ('No LR_Values.csv found, run calc_ML_LinReg prior to running the Expert Advisor')

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
					#if order.profit > 0 and change_sl < order.price_open + mt5.symbol_info(sym).point:
					#	change_sl = order.price_open + mt5.symbol_info(sym).point
				if order.type == 1:
					change_sl = round(DF['bid'].min() + float(LR_Values.loc[order.symbol]['seg']), mt5.symbol_info(order.symbol).digits)
					#if order.profit > 0 and change_sl > order.price_open - mt5.symbol_info(sym).point:
					#	change_sl = order.price_open - mt5.symbol_info(sym).point
				#Change sl
				request = {
					"action": mt5.TRADE_ACTION_SLTP,
					"position": order.ticket,
					"tp" : order.tp,
					"sl" : change_sl,
					}
				result = mt5.order_send(request)
				if result.retcode == 10009:
					print (order.symbol, 'sl changed', change_sl)
			else:
				print ('empty dataframe')

		#Check current Linear Regression values
		DF = pd.DataFrame(mt5.copy_ticks_from(sym, (dt.today()), 1000000, mt5.COPY_TICKS_ALL))
		if len(DF) > 0 and sym not in open_sym:
			seg = float(LR_Values.loc[sym]['seg'])
			sample = LR_Values.loc[sym]['sample']
			LinReg = LR_Values.loc[sym]['LinReg']
			#Dataframe cleanup
			DF.index = pd.to_datetime(DF['time'], unit='s')
			DF = DF.drop(['volume', 'last', 'time_msc', 'flags', 'volume_real'], axis=1)
			DF.index = pd.to_datetime(DF['time'], unit='s')
			DF = DF.drop_duplicates(subset='time', keep="first")
			DF = DF.resample(sample).fillna("ffill").dropna().drop('time', axis=1)

			#Predict trending direction
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
					open_order('Sell')
					break