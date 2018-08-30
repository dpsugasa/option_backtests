# -*- coding: utf-8 -*-
"""
Created on Wed Aug 22 15:14:47 2018
Part 1 creating the multi-flavored option backtests: SAN

@author: dpsugasa
"""

import pandas as pd
from tia.bbg import LocalTerminal
import numpy as np
from datetime import datetime
from operator import itemgetter
#import matplotlib
#import matplotlib.pyplot as plt
import plotly
import plotly.plotly as py #for plotting
import plotly.graph_objs as go
import plotly.dashboard_objs as dashboard
plotly.tools.set_credentials_file(username='dpsugasa', api_key='yuwwkc1sb0')
import plotly.tools as tls
import plotly.figure_factory as ff
tls.embed('https://plot.ly/~dpsugasa/1/')


#set the script start time
start_time = datetime.now()

trade_sheet = pd.read_csv(r'D:\Users\dpsugasa\Desktop\SAN_options/default_SAN.csv')
trade_sheet.Date = pd.to_datetime(trade_sheet.Date)
trade_sheet.Expiry = pd.to_datetime(trade_sheet.Expiry)
trade_sheet = trade_sheet.drop('Vol', axis=1)
trade_sheet['Amount'] = trade_sheet['Amount']/100

opt_tickers = trade_sheet['Ticker'].unique().tolist()
#current_opts = opt_tickers[-int((len(opt_tickers)/6)):] #takes the most recent options; 6 trades
#hist_opts = opt_tickers[:-int((len(opt_tickers)/6))] #takes the historical options
opt1_qtty = 2325

# set dates, securities, and fields
start_date = '01/01/2012'
end_date = "{:%m/%d/%Y}".format(datetime.now())
IDs = opt_tickers
fields = ['LAST PRICE']

d = {} #dict of original dataframes per ID
d2 = {} #final dict of a prices
temp = {} #dict of temp dataframes
temp2 = {} #additional dict of temp dataframes

#get initial prices in 'd', create a temp dataframe with entry/exit dates,
#   price, and expiry for each ticker
for name in IDs:
    d[name] = LocalTerminal.get_historical(name, fields, start_date, end_date,
                                             period = 'DAILY').as_frame()
    d[name].columns = d[name].columns.droplevel()
    d[name] = d[name].fillna(method = 'ffill')
    temp[name] = trade_sheet.loc[trade_sheet.Ticker == name][['Date',
        'Amount', 'Expiry', 'Direction','Shares']]
    temp[name].index = temp[name].Date
    temp[name] = temp[name].drop('Date', axis=1)
    
#because some of the price info does not extend to maturity, make new pricing
#    dataframes that have the full price set, including expiry value = 'd2'
    
for i in opt_tickers:
    temp2[i] = pd.DataFrame(np.nan, columns = ['LAST PRICE_NA'],
                             index = pd.date_range(start = d[i].index[0],
                                                   end = temp[i]['Expiry'][-1],
                                                   freq = 'B'))
    frames = [temp2[i], d[i]]
    d2[i] = pd.concat(frames, join = 'outer', axis = 1)
    d2[i] = d2[i].drop(['LAST PRICE_NA'], axis = 1)
    #making sure entry and exit days are in the index
    d2[i].loc[temp[i].index[-1]] = np.nan#temp[i]['Amount'].loc[temp[i].index[-1]] 
    d2[i].loc[temp[i].index[0]] = np.nan#temp[i]['Amount'].loc[temp[i].index[0]]
    d2[i] = d2[i].sort_index()
    
    d2[i] = d2[i].fillna(method = 'ffill')
    d2[i] = d2[i].dropna()
    d2[i] = d2[i].sort_index().truncate(after = end_date)
    
    d2[i]['trade'] = 0.0
    d2[i]['prev_pos'] = 0.0
    d2[i]['pos'] = 0.0
    #entry trade; 1.0 for buy, -1.0 for sell; amend price to entry price
    if temp[i]['Direction'][0] == 'Buy':
        d2[i]['trade'].loc[temp[i].index[0]] = 1.0
        #d2[i]['LAST PRICE'].loc[temp[i].index[0]] = temp[i]['Amount'].loc[temp[i].index[0]]

    else:
        d2[i]['trade'].loc[temp[i].index[0]] = -1.0
        #d2[i]['LAST PRICE'].loc[temp[i].index[0]] = temp[i]['Amount'].loc[temp[i].index[0]]

    #exit trade; current options use the final day of the series
    if temp[i]['Expiry'][-1] < pd.to_datetime(end_date):
        if temp[i]['Direction'][-1] == 'Buy':
            d2[i]['trade'].loc[temp[i].index[-1]] = 1.0
            d2[i]['LAST PRICE'].loc[temp[i].index[-1]] = temp[i]['Amount'].loc[temp[i].index[-1]]
        else:
            d2[i]['trade'].loc[temp[i].index[-1]] = -1.0
            d2[i]['LAST PRICE'].loc[temp[i].index[-1]] = temp[i]['Amount'].loc[temp[i].index[-1]]
    else:
        if temp[i]['Direction'][-1] == 'Buy':
            d2[i]['trade'][-1] = 1.0
        else:
            d2[i]['trade'][-1] = -1.0
        
    
    d2[i] = d2[i].sort_index()
    
    for z, row in d2[i].iterrows():
        idx_loc = d2[i].index.get_loc(z)
        prev = idx_loc -1
        d2[i]['prev_pos'].loc[z] = d2[i]['pos'].iloc[prev]
        if row['trade'] == 1.0:
            d2[i]['pos'].loc[z] = 1.0 + d2[i]['prev_pos'].loc[z]
            #d2[i]['prev_pos'].loc[z] = d2[i]['pos'].iloc[prev]
        elif row['trade'] == -1.0:
            d2[i]['pos'].loc[z] = -1.0 + d2[i]['prev_pos'].loc[z]
            #d2[i]['prev_pos'].loc[z] = d2[i]['pos'].iloc[prev]
        else:
            d2[i]['pos'].loc[z] = d2[i]['prev_pos'].loc[z]
            #d2[i]['pos'].loc[z] = d2[i]['pos_chg'].iloc[prev]
            
    #d2[i]['pos'] = d2[i]['pos_chg'].shift() + d2[i]['trade'] 
    #d2[i]['pos'][0] = 0.0 
    
    d2[i]['shares'] = temp[i]['Shares'].iloc[0]
    d2[i]['qtty'] = opt1_qtty
    
    d2[i]['cash_val'] = 0.0
    d2[i]['trade_val'] = d2[i]['trade']*d2[i]['shares']*d2[i]['qtty']*d2[i]['LAST PRICE']
    d2[i]['pos_val'] = d2[i]['prev_pos']*d2[i]['shares']*d2[i]['qtty']*d2[i]['LAST PRICE']
    
    for z, row in d2[i].iterrows():
        idx_loc = d2[i].index.get_loc(z)
        prev = idx_loc -1
        if row['trade'] != 0:
            d2[i]['cash_val'].loc[z] = np.negative(d2[i]['trade'].loc[z]* \
                                    d2[i]['shares'].loc[z]* \
                                    d2[i]['qtty'].loc[z]* \
                                    d2[i]['LAST PRICE'].loc[z]) +\
                                    d2[i]['cash_val'].iloc[prev] 
                                      
        else:
           d2[i]['cash_val'].loc[z] = d2[i]['cash_val'].iloc[prev] 

    d2[i]['total_val'] = d2[i]['trade_val'] + d2[i]['pos_val'] + d2[i]['cash_val']  
    d2[i] =  d2[i].truncate(after = end_date)           

end = []
for i in opt_tickers:
    end.append(d2[i]['total_val'].tail(1).values)

frames = []
for i in opt_tickers:   
    frames.append(d2[i]['total_val'])

total_series = pd.concat(frames, join='outer', axis=1)
total_series = total_series.fillna(method = 'ffill')
total_series = total_series.fillna(0)
total_series['port_val'] = total_series.sum(axis=1)

trace1 = go.Scatter(
                x = total_series['port_val'].index,
                y = total_series['port_val'].values,
                name = 'San Options',
                line = dict(
                        color = ('#4155f4'),
                        width = 1.5))        
        
layout  = {'title' : 'Booty Jams',
                   'xaxis' : {'title' : 'Date', 'type': 'date'},
                   'yaxis' : {'title' : 'PNL'},
#                   'shapes': [{'type': 'rect',
#                              'x0': d[i]['scr_1y'].index[0],
#                              'y0': -2,
#                              'x1': d[i]['scr_1y'].index[-1],
#                              'y1': 2,
#                              'name': 'Z-range',
#                              'line': {
#                                      'color': '#f48641',
#                                      'width': 2,},
#                                      'fillcolor': '#f4ad42',
#                                      'opacity': 0.25,
#                                      },]
                   }
data = [trace1]
figure = go.Figure(data=data, layout=layout)
py.iplot(figure, filename = 'option_backtest/SAN_1')



print ("Time to complete:", datetime.now() - start_time)
    




    
    
    
#A = [0,0,1,0,0,-1,0]
#z = pd.DataFrame(A)
##z[1] = z[0].diff()
##z[2] = z[0].diff(-1)
#z[3] = z[0].shift()
#z[4] = z[0].shift(-1)
  
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
#    d[name] = pd.concat([d[name], temp[name]], join = 'outer', axis=1)
#    d[name] = d[name].resample('B').mean()
#    d[name] = d[name].fillna(0.00)
#    #d[name]['LP'] = d[name]['LAST PRICE'] + d[name]['Amount']
#    #d[name] = d[name].drop(['LAST PRICE','Amount'], axis = 1)
#    #d[name] = d[name].rename(columns = {'LP': 'LAST PRICE'})
#    d[name]['new'] = pd.concat([d[name]['LAST PRICE'].dropna(), d[name]['Amount'].dropna()])
