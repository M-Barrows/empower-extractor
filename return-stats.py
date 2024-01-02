import pandas as pd
import numpy as np
import scipy as sp
import yfinance as yf
from datetime import datetime
import matplotlib.pyplot as plt
import matplotlib as mpl
from scipy.interpolate import make_interp_spline


data = pd.read_csv('empower-transactions-details.csv')
data['totalUnits'] = round(data.groupby("sdioId")['actySumUnits'].cumsum(),5)
data['totalContributions'] = round(data.groupby("sdioId")['actySumAmt'].cumsum(),5)

ticker_dates = data.groupby("sdioId")['effDate'].aggregate(['min','max']).reset_index()

symbols = list(ticker_dates['sdioId'].unique())
tickers = yf.Tickers(symbols)
# first_date, last_date = min(pd.to_datetime(ticker_dates['min'])),max(pd.to_datetime(ticker_dates['max']))
historical_price = tickers.download(interval="1d",period="6y")['Close'].reset_index().melt(id_vars='Date',var_name='sdioId', value_name='closePrice')
historical_price['Date'] = pd.to_datetime(historical_price['Date'].dt.strftime('%d-%b-%Y'))
data['effDate'] = pd.to_datetime(data['effDate'])

data = data.set_index(['effDate','sdioId'])
historical_price.columns=['effDate','sdioId','closePrice']
historical_price = historical_price.set_index(['effDate','sdioId'])
full = data.join(historical_price,)
full.sort_index()
full['totalValue'] = full['totalUnits'] * full['closePrice']
full['totalGrowth'] = full['totalValue'] - full['totalContributions']
full['growthPercent'] = (full['totalGrowth'] / full['totalContributions'])*100
full = full.reset_index()
totalContributions = full[['effDate','totalContributions','sdioId']].groupby(['effDate','sdioId']).last().reset_index().pivot(index='effDate',columns='sdioId',values='totalContributions').ffill().sum(axis=1)
totalValue = full[['effDate','totalValue','sdioId']].groupby(['effDate','sdioId']).last().reset_index().pivot(index='effDate',columns='sdioId',values='totalValue').ffill().sum(axis=1)
totalGrowth = full[['effDate','totalGrowth','sdioId']].groupby(['effDate','sdioId']).last().reset_index().pivot(index='effDate',columns='sdioId',values='totalGrowth').ffill().sum(axis=1)
growthPercent = full[['effDate','growthPercent','sdioId']].groupby(['effDate','sdioId']).last().reset_index().pivot(index='effDate',columns='sdioId',values='growthPercent').ffill()
growthPercent = growthPercent.loc[:,growthPercent.iloc[-1].ne(-100.00)]

dates = full['effDate'].unique()

plt.plot(dates,totalContributions)
plt.plot(dates,totalValue)
plt.show()
