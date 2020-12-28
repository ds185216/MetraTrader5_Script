import MetaTrader5 as mt5
import pandas as pd
import numpy as np
import datetime
from datetime import datetime as dt

#Open ema values file
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


#While True:


#Throw in open orders check here
open_sym = []
for order in mt5.positions_get():
	open_sym.append(order.symbol)
	#Incomplete
	#requires to check min/max ask price to compare for sl


for sym in symbols:
	#DataFrame cleanup
	DF = pd.DataFrame(mt5.copy_ticks_from(sym, (dt.today()), 100000, mt5.COPY_TICKS_ALL))
	if len(DF) > 0 and sym not in open_sym:
		EMA_A = int(EMA_Values.loc[sym]['EMA_A'])
		EMA_B = int(EMA_Values.loc[sym]['EMA_B'])
		seg = float(EMA_Values.loc[sym]['seg'])
		DF = DF.iloc[::-1]
		DF.index = pd.to_datetime(DF['time'], unit='s')
		DF = DF.drop(['volume', 'last', 'time_msc', 'flags', 'volume_real'], axis=1) #Need to set as definition
		DF.index = pd.to_datetime(DF['time'], unit='s')
		DF = DF.drop_duplicates(subset='time', keep="first")
		DF = DF.resample("1min").fillna("ffill").dropna().drop('time', axis=1)
		DF['EMA_A'] = DF['ask'].ewm(span=EMA_A, min_periods=EMA_A).mean()
		DF['EMA_B'] = DF['ask'].ewm(span=EMA_B, min_periods=EMA_B).mean()

		#Qualify for buy/sell
		if DF.tail(1)['ask'][0] > DF.tail(1)['EMA_A'][0]:
			request = {
				"action": mt5.TRADE_ACTION_DEAL,
				"symbol": sym,
				"volume": round(int(((mt5.account_info().balance/100)*percent)/DF.tail(1)['ask'][0]/mt5.symbol_info(sym).volume_step)*mt5.symbol_info(sym).volume_step, mt5.account_info().currency_digits),
				"type": mt5.ORDER_TYPE_BUY, #Buy
				"price": DF.tail(1)['ask'][0],
				"sl": DF.tail(1)['ask'][0] - seg,
				"tp": DF.tail(1)['ask'][0] + seg,
				"deviation": 0,
				"magic": 0,
				"comment": "Python script",
				"type_time": mt5.ORDER_TIME_GTC,
				"type_filling": mt5.ORDER_FILLING_IOC, #Either FOK or IOC, RETURN will change open orders
			}
			result = mt5.order_send(request)
			if result.retcode == 10009:
				print ('Buy', sym)
			else:
				print ('Buy Error:', result.retcode)
			break

		elif DF.tail(1)['ask'][0] < DF.tail(1)['EMA_B'][0]:
			request = {
				"action": mt5.TRADE_ACTION_DEAL,
				"symbol": sym,
				"volume": round(int(((mt5.account_info().balance/100)*percent)/DF.tail(1)['ask'][0]/mt5.symbol_info(sym).volume_step)*mt5.symbol_info(sym).volume_step, mt5.account_info().currency_digits),
				"type": mt5.ORDER_TYPE_SELL, #Sell
				"price": DF.tail(1)['ask'][0],
				"sl": DF.tail(1)['ask'][0] + seg,
				"tp": DF.tail(1)['ask'][0] - seg,
				"deviation": 0,
				"magic": 0,
				"comment": "Python script",
				"type_time": mt5.ORDER_TIME_GTC,
				"type_filling": mt5.ORDER_FILLING_IOC, #Either FOK or IOC, RETURN will change open orders
			}
			result = mt5.order_send(request)
			if result.retcode == 10009:
				print ('Sell', sym)
			else:
				print ('Sell Error:', result.retcode)
			break


#result = mt5.order_send(request)
#print (result.retcode)
#position_id = result.order

# request={
#     "action": mt5.TRADE_ACTION_DEAL,
#     "symbol": symbol,
#     "volume": lot,
#     "type": mt5.ORDER_TYPE_SELL,
#     "position": position_id, <---------------------------------------
#     "price": price,
#     "deviation": deviation,
#     "magic": 234000,
#     "comment": "python script close",
#     "type_time": mt5.ORDER_TIME_GTC,
#     "type_filling": mt5.ORDER_FILLING_RETURN,
# }