import MetaTrader5 as mt5
import pandas as pd
import numpy as np
import datetime
from datetime import datetime as dt
from sklearn.linear_model import LinearRegression

#open LR_values if exists
try:
	EMA_Values = pd.read_csv('LR_Values.csv')
	EMA_Values.index = EMA_Values['Unnamed: 0']
	EMA_Values = EMA_Values.drop(['Unnamed: 0'], axis=1)
except:
	EMA_Values = pd.DataFrame(columns=['LinReg','sample', 'seg','max_cash'])


mt5.initialize()

#Get all symbols
#symbols = [sym.name for sym in mt5.symbols_get()] #revert later
#symbols = [i for i in symbols if i not in EMA_Values.index] #revert later

symbols = ['BTCUSD', 'ETHUSD', 'BCHUSD', 'XRPUSD', 'LTCUSD']

if len(symbols) == 0:
	symbols = [sym.name for sym in mt5.symbols_get()]
#Need to set an update feature, timestamp for outdated EMA calcs

sample_rates = ['1min', '5min', '15min', '60min']

#Loop through all symbols
for sym in symbols:
	#Number of decimal places
	digits = mt5.symbol_info(sym).digits

	#Set value to determine optimum cash after second level
	max_cash = 1

	#Final list of entries that have a return more than 1
	results_list = []

	#Database dict for different sample rates
	databases = {}

	#Fixes for no entries in data
	backdate = 0
	for backdate in range(31):
		#Convert dates to UTC
		utc_start = datetime.datetime.utcnow().date() - datetime.timedelta(days=backdate)
		utc_finish = utc_start - datetime.timedelta(days=1)
		utc_to = dt(int(utc_start.strftime("%Y")), int(utc_start.strftime("%m")), int(utc_start.strftime("%d")))
		utc_from = dt(int(utc_finish.strftime("%Y")), int(utc_finish.strftime("%m")), int(utc_finish.strftime("%d")))

		#Second level dates
		utc_start = utc_start - datetime.timedelta(days=1)
		utc_finish = utc_start - datetime.timedelta(days=1)
		utc_to_L2 = utc_from
		utc_from_L2 = dt(int(utc_finish.strftime("%Y")), int(utc_finish.strftime("%m")), int(utc_finish.strftime("%d")))
		DF_master = pd.DataFrame(mt5.copy_ticks_range(sym, utc_from, utc_to, mt5.COPY_TICKS_INFO))
		DF_L2_master = pd.DataFrame(mt5.copy_ticks_range(sym, utc_from_L2, utc_to_L2, mt5.COPY_TICKS_INFO))
		if len(DF_master) > 0 and len(DF_L2_master) > 0:

			#Segments for sl and tp
			segments = [round((i * (DF_master['bid'].max()-DF_master['bid'].min())/10), digits) for i in range(1,6)]

			#Sample size for EMA calcs
			for sample in sample_rates:

				#Clean Dataframe and set 1 minute EMA calculations
				DF = DF_master.copy()
				DF = DF.drop(['volume', 'last', 'time_msc', 'flags', 'volume_real'], axis=1) #Need to set as definition
				DF.index = pd.to_datetime(DF['time'], unit='s')
				DF_1min = DF.drop_duplicates(subset='time', keep="first")
				DF_1min = DF_1min.resample(sample).fillna("ffill").dropna().drop('time', axis=1)
				for LinReg in range(2,10):
					for size in range(len(DF_1min)-LinReg):
						y = pd.DataFrame(DF_1min['ask'][size:size+LinReg])
						X = pd.DataFrame(range(size, size+LinReg))
						model = LinearRegression()
						model.fit(X,y)
						pred_B = model.predict([[size+LinReg+2]])
						DF_1min['LinReg_B_'+str(LinReg)] = pred_B[0][0]
						DF_1min['LinReg_A_'+str(LinReg)] = DF_1min['LinReg_B_'+str(LinReg)].shift(-1)
				DF_2 = DF.drop_duplicates(subset='time', keep="first")
				DF_2 = DF_2.drop(['time'], axis=1)
				DF = DF_2.combine_first(DF_1min)
				DF = DF.round(digits)

				#Level 2 DataFrame and and set 1 minute EMA calculations
				DF_L2 = DF_L2_master.copy()
				DF_L2 = DF_L2.drop(['volume', 'last', 'time_msc', 'flags', 'volume_real'], axis=1) #Need to set as definition
				DF_L2.index = pd.to_datetime(DF_L2['time'], unit='s')
				DF_1min = DF_L2.drop_duplicates(subset='time', keep="first")
				DF_1min = DF_1min.resample(sample).fillna("ffill").dropna().drop('time', axis=1)
				for LinReg in range(2,10):
					for size in range(len(DF_1min)-LinReg):
						y = pd.DataFrame(DF_1min['ask'][size:size+LinReg])
						X = pd.DataFrame(range(size, size+LinReg))
						model = LinearRegression()
						model.fit(X,y)
						pred_B = model.predict([[size+LinReg+2]])
						DF_1min['LinReg_B_'+str(LinReg)] = pred_B[0][0]
						DF_1min['LinReg_A_'+str(LinReg)] = DF_1min['LinReg_B_'+str(LinReg)].shift(-1)
				DF_2 = DF_L2.drop_duplicates(subset='time', keep="first")
				DF_2 = DF_2.drop(['time'], axis=1)
				DF_L2 = DF_2.combine_first(DF_1min)
				DF_L2 = DF_L2.round(digits)
				databases[sample] = DF
				databases[sample+'_L2'] = DF_L2

			print (sym)

			#EMA and Segment calculations
			for LinReg in range (2,10):
				for seg in segments:
					for sample in sample_rates:
						DF_test = databases[sample] #Need to set as definition
						DF_test['start'] = DF_test.query('LinReg_A_'+str(LinReg)+'>LinReg_B_'+str(LinReg))['ask']
						DF_test['buy'] = DF_test['start'].notnull()
						DF_test['start'] = DF_test['start'].fillna(DF_test.query('LinReg_A_'+str(LinReg)+'<LinReg_B_'+str(LinReg))['ask'])
						cash = 1000.00

						while DF_test['start'].count() > 0:
							if DF_test['buy'][DF_test['start'].first_valid_index()] == True:
								DF_test['bid_min_max'] = DF_test['bid'].cummax()
								DF_test['sl'] = DF_test['bid_min_max']-seg
								DF_test['tp'] = DF_test['start'].loc[DF_test['start'].first_valid_index()]+seg
								DF_test['stop'] = DF_test.query('tp<bid or sl>bid')['bid']
							elif DF_test['buy'][DF_test['start'].first_valid_index()] == False:
								DF_test['bid_min_max'] = DF_test['bid'].cummin()
								DF_test['sl'] = DF_test['bid_min_max']+seg
								DF_test['tp'] = DF_test['start'].loc[DF_test['start'].first_valid_index()]-seg
								DF_test['stop'] = DF_test.query('tp>bid or sl<bid')['bid']
							start = DF_test['start'][DF_test['start'].first_valid_index()]
							if DF_test['stop'].count() > 0:
								stop = DF_test['stop'][DF_test['stop'].first_valid_index()]
								if DF_test['buy'][DF_test['start'].first_valid_index()] == True:
									cash = round(cash * (stop/start), 2)
								elif DF_test['buy'][DF_test['start'].first_valid_index()] == False:
									cash = round(cash + (cash * (1-(stop/start))), 2)
								DF_test.drop(DF_test.loc[DF_test.index <= DF_test['stop'].first_valid_index()].index, inplace=True)
								if cash < 900:
									break
							else:
								break
						if cash > 1:
							results_list.append({'LinReg' : LinReg, 'sample' : sample, 'seg': seg, 'cash' : cash})

			for level_2 in results_list:

				#Dictionary values from level 1 tests
				LinReg = level_2['LinReg']
				seg = level_2['seg']
				sample = level_2['sample']

				DF_test = databases[sample+'_L2'] #Need to set as definition
				DF_test['start'] = DF_test.query('LinReg_A_'+str(LinReg)+'>LinReg_B_'+str(LinReg))['ask']
				DF_test['buy'] = DF_test['start'].notnull()
				DF_test['start'] = DF_test['start'].fillna(DF_test.query('LinReg_A_'+str(LinReg)+'<LinReg_B_'+str(LinReg))['ask'])
				cash = 1000.00

				#Check results on level 2
				while DF_test['start'].count() > 0:
					if DF_test['buy'][DF_test['start'].first_valid_index()] == True:
						DF_test['bid_min_max'] = DF_test['bid'].cummax()
						DF_test['sl'] = DF_test['bid_min_max']-seg
						DF_test['tp'] = DF_test['start'].loc[DF_test['start'].first_valid_index()]+seg
						DF_test['stop'] = DF_test.query('tp<bid or sl>bid')['bid']
					else:
						DF_test['bid_min_max'] = DF_test['bid'].cummin()
						DF_test['sl'] = DF_test['bid_min_max']+seg
						DF_test['tp'] = DF_test['start'].loc[DF_test['start'].first_valid_index()]-seg
						DF_test['stop'] = DF_test.query('tp>bid or sl<bid')['bid']
					start = DF_test['start'][DF_test['start'].first_valid_index()]
					if DF_test['stop'].count() > 0:
						stop = DF_test['stop'][DF_test['stop'].first_valid_index()]
						if DF_test['buy'][DF_test['start'].first_valid_index()] == True:
							cash = round(cash * (stop/start), 2)
						else:
							cash = round(cash + (cash * (1-(stop/start))), 2)
						DF_test.drop(DF_test.loc[DF_test.index <= DF_test['stop'].first_valid_index()].index, inplace=True)
						if cash < 900:
							break
					else:
						break

				#write EMA_Values
				if cash > 1000.00 and (level_2['cash']/1000) * cash > max_cash:
					max_cash = (level_2['cash']/1000) * cash
					print ('Value found', sym, 'LinReg:', LinReg, 'sample rate:', sample, 'TP and SL segments:', seg, '2 day simulated cash:', max_cash)
					EMA_Values.loc[sym] = {'LinReg' : LinReg, 'sample' : sample, 'seg' : seg, 'max_cash' : max_cash}
					EMA_Values.to_csv('LR_Values.csv')
			break
		if backdate == 30:
			break

