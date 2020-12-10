import MetaTrader5 as mt5
import pandas as pd
import numpy as np
import datetime
from datetime import datetime as dt

#open EMA_values if exists
try:
	EMA_Values = pd.read_csv('EMA_Values.csv')
except:
	EMA_Values = pd.DataFrame()


mt5.initialize()

#Convert dates to UTC
utc_start = datetime.datetime.utcnow().date()
utc_finish = utc_start - datetime.timedelta(days=2)
utc_to = dt(int(utc_start.strftime("%Y")), int(utc_start.strftime("%m")), int(utc_start.strftime("%d")))
utc_from = dt(int(utc_finish.strftime("%Y")), int(utc_finish.strftime("%m")), int(utc_finish.strftime("%d")))

#Second level dates
utc_start = utc_start - datetime.timedelta(days=4)
utc_finish = utc_start - datetime.timedelta(days=3)
utc_to_L2 = dt(int(utc_start.strftime("%Y")), int(utc_start.strftime("%m")), int(utc_start.strftime("%d")))
utc_from_L2 = dt(int(utc_finish.strftime("%Y")), int(utc_finish.strftime("%m")), int(utc_finish.strftime("%d")))

#Get all symbols
symbols = [sym.name for sym in mt5.symbols_get()]

#Loop through all symbols
for sym in symbols:

	#Set value to determine optimum cash after second level
	max_cash = 1

	#Final list of entries that have a return more than 1
	results_list = []

	#Create DataFrames
	DF = pd.DataFrame(mt5.copy_ticks_range(sym, utc_from, utc_to, mt5.COPY_TICKS_INFO))
	DF_L2 = pd.DataFrame(mt5.copy_ticks_range(sym, utc_from_L2, utc_to_L2, mt5.COPY_TICKS_INFO))

	#Fixes if no entries in data
	if len(DF) != 0:

		#Segments for sl and tp
		segments = [i * (DF['bid'].max()-DF['bid'].min())/10 for i in range(1,10)]

		#Clean Dataframe and set 1 minute EMA calculations
		DF = DF.drop(['volume', 'last', 'time_msc', 'flags', 'volume_real'], axis=1) #Need to set as definition
		DF.index = pd.to_datetime(DF['time'], unit='s')
		DF_1min = DF.drop_duplicates(subset='time', keep="first")
		DF_1min = DF_1min.resample("1min").fillna("ffill").dropna().drop('time', axis=1)
		for i in range(2,11):
			DF_1min['EMA_'+str(i)] = DF_1min['ask'].ewm(span=i, min_periods=i).mean()
		DF_2 = DF.drop_duplicates(subset='time', keep="first")
		DF_2 = DF_2.drop(['time'], axis=1)
		DF = DF_2.combine_first(DF_1min)

		#Level 2 DataFrame and and set 1 minute EMA calculations
		DF_L2 = DF.drop(['volume', 'last', 'time_msc', 'flags', 'volume_real'], axis=1) #Need to set as definition
		DF_L2.index = pd.to_datetime(DF_L2['time'], unit='s')
		DF_1min = DF_L2.drop_duplicates(subset='time', keep="first")
		DF_1min = DF_1min.resample("1min").fillna("ffill").dropna().drop('time', axis=1)
		for i in range(2,11):
			DF_1min['EMA_'+str(i)] = DF_1min['ask'].ewm(span=i, min_periods=i).mean()
		DF_2 = DF.drop_duplicates(subset='time', keep="first")
		DF_2 = DF_2.drop(['time'], axis=1)
		DF_L2 = DF_2.combine_first(DF_1min)

		#EMA and Segment calculations
		for EMA_A in range (2,11):
			for EMA_B in range(2,11):
				for seg in segments:
					DF_test = DF.copy() #Need to set as definition
					DF_test['start'] = DF_test.query('ask>EMA_'+str(EMA_A))['ask']
					DF_test['buy'] = DF_test['start'].notnull()
					DF_test['start'] = DF_test['start'].fillna(DF_test.query('ask<EMA_'+str(EMA_B))['ask'])
					cash = 1

					while DF_test['start'].count() > 0:
						if DF_test['buy'][DF_test['start'].first_valid_index()] == True:
							DF_test['bid_min_max'] = DF_test['bid'].cummax()
							DF_test['sl'] = DF_test['bid_min_max']-seg
							DF_test['tp'] = DF_test['start'].loc[DF_test['start'].first_valid_index()]+seg
						else:
							DF_test['bid_min_max'] = DF_test['bid'].cummin()
							DF_test['sl'] = DF_test['bid_min_max']+seg
							DF_test['tp'] = DF_test['start'].loc[DF_test['start'].first_valid_index()]-seg
						DF_test['stop'] = DF_test.query('tp<bid or sl>bid')['bid']
						start = DF_test['start'][DF_test['start'].first_valid_index()]
						if DF_test['stop'].count() > 0:
							stop = DF_test['stop'][DF_test['stop'].first_valid_index()]
							if DF_test['buy'][DF_test['start'].first_valid_index()] == True:
								cash = cash * (stop/start)
							else:
								cash = cash + (cash * (1-(stop/start)))
							DF_test.drop(DF_test.loc[DF_test.index <= DF_test['stop'].first_valid_index()].index, inplace=True)
							if cash < 0.9:
								break
						else:
							break
					if cash > 1:
						results_list.append({'EMA_A' : EMA_A, 'EMA_B' : EMA_B, 'seg': seg, 'cash' : cash})


	for level_2 in results_list:

		#Dictionary values from level 1 tests
		EMA_A = level_2['EMA_A']
		EMA_B = level_2['EMA_B']
		seg = level_2['seg']

		DF_test = DF_2.copy() #Need to set as definition
		DF_test['start'] = DF_test.query('ask>EMA_'+str(EMA_A))['ask']
		DF_test['buy'] = DF_test['start'].notnull()
		DF_test['start'] = DF_test['start'].fillna(DF_test.query('ask<EMA_'+str(EMA_B))['ask'])
		cash = 1

		#Check results on level 2
		while DF_test['start'].count() > 0:
			if DF_test['buy'][DF_test['start'].first_valid_index()] == True:
				DF_test['bid_min_max'] = DF_test['bid'].cummax()
				DF_test['sl'] = DF_test['bid_min_max']-seg
				DF_test['tp'] = DF_test['start'].loc[DF_test['start'].first_valid_index()]+seg
			else:
				DF_test['bid_min_max'] = DF_test['bid'].cummin()
				DF_test['sl'] = DF_test['bid_min_max']+seg
				DF_test['tp'] = DF_test['start'].loc[DF_test['start'].first_valid_index()]-seg
			DF_test['stop'] = DF_test.query('tp<bid or sl>bid')['bid']
			start = DF_test['start'][DF_test['start'].first_valid_index()]
			if DF_test['stop'].count() > 0:
				stop = DF_test['stop'][DF_test['stop'].first_valid_index()]
				if DF_test['buy'][DF_test['start'].first_valid_index()] == True:
					cash = cash * (stop/start)
				else:
					cash = cash + (cash * (1-(stop/start)))
				DF_test.drop(DF_test.loc[DF_test.index <= DF_test['stop'].first_valid_index()].index, inplace=True)
				if cash < 0.9:
					break
			else:
				break

		#write EMA_Values
		if cash > 1 and level_2['cash'] * cash > max_cash:
			max_cash = level_2['cash'] * cash
			print ('Value found', sym, 'EMA_A:', EMA_A, 'EMA_B:', 'EMA_B', 'TP and SL segments:', seg, '2 day simulated cash:', max_cash)
			hold = pd.DataFrame({'EMA_A' : EMA_A, 'EMA_B' : EMA_B, 'seg': seg, 'max_cash' : max_cash}, index = [sym])
			EMA_Values = EMA_Values.append(hold)
			EMA_Values.to_csv('EMA_Values.csv')