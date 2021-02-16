import MetaTrader5 as mt5
import pandas as pd
import numpy as np
import datetime
from datetime import datetime as dt

#Open EMA values file
try:
	EMA_Values = pd.read_csv('EMA_Values.csv')
	EMA_Values = EMA_Values.sort_values(by=['max_cash'], ascending=False)
	EMA_Values.index = EMA_Values['Unnamed: 0']
	EMA_Values = EMA_Values.drop(['Unnamed: 0'], axis=1)
	symbols = EMA_Values.index
except:
	print ('No EMA_Values.csv found, run calc_ema prior to running the Expert Advisor')

#Set percentage of balance when placing orders
percent = 10

mt5.initialize()


while True:

	#Open orders check
	open_sym = []
	for order in mt5.positions_get():
		open_sym.append(order.symbol)
		DF = pd.DataFrame(mt5.copy_ticks_from(order.symbol, (dt.today()), 100000, mt5.COPY_TICKS_ALL))
		DF = DF[DF['time'] >= order.time]
		if order.type == 0:
			change_sl = round(DF['bid'].max() - float(EMA_Values.loc[order.symbol]['seg']), mt5.symbol_info(order.symbol).digits)
		if order.type == 1:
			change_sl = round(DF['bid'].min() + float(EMA_Values.loc[order.symbol]['seg']), mt5.symbol_info(order.symbol).digits)
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

	#Check current EMA values
	for sym in symbols:
		#DataFrame cleanup
		DF = pd.DataFrame(mt5.copy_ticks_from(sym, (dt.today()), 100000, mt5.COPY_TICKS_ALL))
		if len(DF) > 0 and sym not in open_sym:
			EMA_A = int(EMA_Values.loc[sym]['EMA_A'])
			EMA_B = int(EMA_Values.loc[sym]['EMA_B'])
			seg = float(EMA_Values.loc[sym]['seg'])
			sample = EMA_Values.loc[sym]['sample']
			DF = DF.iloc[::-1]
			DF.index = pd.to_datetime(DF['time'], unit='s')
			DF = DF.drop(['volume', 'last', 'time_msc', 'flags', 'volume_real'], axis=1)
			DF.index = pd.to_datetime(DF['time'], unit='s')
			DF = DF.drop_duplicates(subset='time', keep="first")
			DF = DF.resample(sample).fillna("ffill").dropna().drop('time', axis=1)
			DF['EMA_A'] = DF['ask'].ewm(span=EMA_A, min_periods=EMA_A).mean()
			DF['EMA_B'] = DF['ask'].ewm(span=EMA_B, min_periods=EMA_B).mean()

			#Qualify for Buy/Sell
			if DF.tail(1)['ask'][0] > DF.tail(1)['EMA_A'][0]:
				volume = round(int(((mt5.account_info().balance/100)*percent)/mt5.symbol_info(sym).bid/mt5.symbol_info(sym).volume_step)*mt5.symbol_info(sym).volume_step, mt5.symbol_info(sym).digits)
				if volume > mt5.symbol_info(sym).volume_max:
					volume = mt5.symbol_info(sym).volume_max
				request = {
					"action": mt5.TRADE_ACTION_DEAL,
					"symbol": sym,
					"volume": volume,
					"type": mt5.ORDER_TYPE_BUY,
					"price": mt5.symbol_info(sym).bid,
					"sl": round(mt5.symbol_info(sym).bid - seg, mt5.symbol_info(sym).digits),
					"tp": round(mt5.symbol_info(sym).ask + seg, mt5.symbol_info(sym).digits),
					"deviation": 0,
					"magic": 0,
					"comment": "Python script",
					"type_time": mt5.ORDER_TIME_GTC,
					"type_filling": mt5.ORDER_FILLING_IOC,
				}
				result = mt5.order_send(request)
				if result.retcode == 10009:
					print ('Buy', sym)
				else:
					print ('Buy Error:', result.retcode)
					print (request)
					print ('bid:', mt5.symbol_info(sym).bid)
				break

			elif DF.tail(1)['ask'][0] < DF.tail(1)['EMA_B'][0]:
				volume = round(int(((mt5.account_info().balance/100)*percent)/mt5.symbol_info(sym).bid/mt5.symbol_info(sym).volume_step)*mt5.symbol_info(sym).volume_step, mt5.symbol_info(sym).digits)
				round_amount = len(str(DF.tail(1)['ask'][0]).split('.')[1])				
				if volume > mt5.symbol_info(sym).volume_max:
					volume = mt5.symbol_info(sym).volume_max				
				request = {
					"action": mt5.TRADE_ACTION_DEAL,
					"symbol": sym,
					"volume": volume,
					"type": mt5.ORDER_TYPE_SELL,
					"price": mt5.symbol_info(sym).bid,
					"sl": round(mt5.symbol_info(sym).bid + seg, mt5.symbol_info(sym).digits),#Need to fix return errors, something to do with use of bid price then ask price at close?
					"tp": round(mt5.symbol_info(sym).ask - seg, mt5.symbol_info(sym).digits),
					"deviation": 0,
					"magic": 0,
					"comment": "Python script",
					"type_time": mt5.ORDER_TIME_GTC,
					"type_filling": mt5.ORDER_FILLING_IOC,
				}
				result = mt5.order_send(request)
				if result.retcode == 10009:
					print ('Sell', sym)
				else:
					print ('Sell Error:', result.retcode)
					print (request)
					print ('bid:', mt5.symbol_info(sym).bid, 'seg:', seg)
				break