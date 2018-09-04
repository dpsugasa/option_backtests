# -*- coding: utf-8 -*-
"""
Created on Wed Aug 22 15:14:47 2018
Part 1 creating the multi-flavored option backtests: SAN

@author: dpsugasa
"""

import os, sys
import pandas as pd
from tia.bbg import LocalTerminal
import numpy as np
from datetime import datetime, timedelta
from csv import DictReader
from collections import OrderedDict
from operator import itemgetter
import plotly
import plotly.plotly as py #for plotting
import plotly.graph_objs as go
import plotly.dashboard_objs as dashboard
import plotly.tools as tls
import plotly.figure_factory as ff
import credentials


#set the script start time
start_time = datetime.now()

#plotly function

def create_trace(df, label):
    dates = df.index 
    prices = df.values
    trace = go.Scatter(
        x = dates,
        y = prices,
        name = label,
        line = dict(width = 2,
                    #color=color,
                    )
    )
    return trace 


# set dates to grab data
start_date = '01/01/2012'
end_date = "{:%m/%d/%Y}".format(datetime.now())
date_now = "{:%m_%d_%Y}".format(datetime.now())

# Files in Option Directory

path2 = "D:\\Users\\dpsugasa\\option_backtests\\options"
dirs2 = os.listdir(path2)

#path = f"D:\\Users\\dpsugasa\\option_backtests\\options\\{direct}"
#dirs = os.listdir(path)

ts      = {} #dict for trades
tkr     = {} #dict for tickers
px      = {} #dict of original dataframes per ID
px2     = {} #final dict of a prices
temp    = {} #dict of temp dataframes
temp2   = {} #additional dict of temp dataframes 
tot_ser = {} #df for all options series per strategy
m       = {} #df for option ref data
n       = {} #temp df
quants= []


for direct in dirs2:
    path = f"D:\\Users\\dpsugasa\\option_backtests\\options\\{direct}"
    dirs = os.listdir(path)
    for file in dirs:
        curr_path = fr'D:\Users\dpsugasa\option_backtests\options\{direct}/{file}'
        ts[file] = pd.read_csv(curr_path)
        ts[file].Date = pd.to_datetime(ts[file].Date)
        ts[file].Expiry = pd.to_datetime(ts[file].Expiry)
        ts[file] = ts[file].drop('Vol', axis=1)
        ts[file]['Amount'] = ts[file]['Amount']/100

        tkr[file] = ts[file]['Ticker'].unique().tolist()
    

        # set securities, and fields
        IDs = tkr[file]
        fields = ['LAST PRICE']

        d = {} #dict of original dataframes per ID
        d2 = {} #final dict of a prices
        temp = {} #dict of temp dataframes
        temp2 = {} #additional dict of temp dataframes
    
        ref_data = ['OPTION_ROOT_TICKER', 'OPT_MULTIPLIER', 'OPT_UNDL_PX',
                    'COMPANY_CORP_TICKER', 'CRNCY']
        

        #get initial prices in 'd', create a temp dataframe with entry/exit dates,
        #   price, and expiry for each ticker
        for name in IDs:
            d[file, name] = LocalTerminal.get_historical(name, fields, start_date, end_date,
                                                 period = 'DAILY').as_frame()
            d[file, name].columns = d[file, name].columns.droplevel()
            d[file, name] = d[file, name].fillna(method = 'ffill')
            temp[file, name] = ts[file].loc[ts[file].Ticker == name][['Date',
                'Amount', 'Expiry', 'Direction','Shares']]
            temp[file, name].index = temp[file, name].Date
            temp[file, name] = temp[file, name].drop('Date', axis=1)
            
            m[file, name] = LocalTerminal.get_reference_data(name, ref_data).as_frame()
            n[file] = LocalTerminal.get_reference_data(name, ref_data).as_frame()
        
        #set option qtty equal to $1mm USD worth of bonds so they can be compared in 'return space'
        opt_curr = n[file]['CRNCY'].item() + " CURNCY"
        curr_px = LocalTerminal.get_reference_data(opt_curr, 'PX_LAST').as_frame().values.item()
        multy = 100.00 #n[file]['OPT_MULTIPLIER'].item() Hard coding as 100 multiplier
        undl = n[file]['OPT_UNDL_PX'].item()
        bond_size = 1000000.0 #1m USD
        b_size_adj = bond_size/curr_px
        opt1_qtty = np.round(((b_size_adj)/(multy*undl)))
        
        for l in IDs:
            quants.append(opt1_qtty)
        
        
        #because some of the price info does not extend to maturity, make new pricing
        #    dataframes that have the full price set, including expiry value = 'd2'
    
        for i in IDs:
            temp2[file, i] = pd.DataFrame(np.nan, columns = ['LAST PRICE_NA'],
                                 index = pd.date_range(start = d[file, i].index[0],
                                                       end = temp[file,i]['Expiry'][-1],
                                                       freq = 'B'))
            frames = [temp2[file, i], d[file, i]]
            d2[file, i] = pd.concat(frames, join = 'outer', axis = 1)
            d2[file, i] = d2[file, i].drop(['LAST PRICE_NA'], axis = 1)
            #making sure entry and exit days are in the index
            d2[file, i].loc[temp[file, i].index[-1]] = np.nan 
            d2[file, i].loc[temp[file, i].index[0]] = np.nan
            d2[file, i] = d2[file, i].sort_index()
        
            d2[file, i] = d2[file, i].fillna(method = 'ffill')
            d2[file, i] = d2[file, i].dropna()
            d2[file, i] = d2[file, i].sort_index().truncate(after = end_date)
        
            d2[file, i]['trade'] = 0.0
            d2[file, i]['prev_pos'] = 0.0
            d2[file, i]['pos'] = 0.0
            #entry trade; 1.0 for buy, -1.0 for sell; amend price to entry price
            if temp[file, i]['Direction'][0] == 'Buy':
                d2[file, i]['trade'].loc[temp[file, i].index[0]] = 1.0
                #d2[i]['LAST PRICE'].loc[temp[i].index[0]] = temp[i]['Amount'].loc[temp[i].index[0]]
            else:
                d2[file, i]['trade'].loc[temp[file, i].index[0]] = -1.0
                #d2[i]['LAST PRICE'].loc[temp[i].index[0]] = temp[i]['Amount'].loc[temp[i].index[0]]
    
            #exit trade; current options use the final day of the series
            if temp[file, i]['Expiry'][-1] < pd.to_datetime(end_date):
                if temp[file, i]['Direction'][-1] == 'Buy':
                    d2[file, i]['trade'].loc[temp[file, i].index[-1]] = 1.0
                    d2[file, i]['LAST PRICE'].loc[temp[file, i].index[-1]] =\
                        temp[file, i]['Amount'].loc[temp[file, i].index[-1]]
                else:
                    d2[file, i]['trade'].loc[temp[file, i].index[-1]] = -1.0
                    d2[file, i]['LAST PRICE'].loc[temp[file, i].index[-1]] =\
                        temp[file, i]['Amount'].loc[temp[file, i].index[-1]]
            else:
                if temp[file, i]['Direction'][-1] == 'Buy':
                    d2[file, i]['trade'][-1] = 1.0
                else:
                    d2[file, i]['trade'][-1] = -1.0
        
    
            d2[file, i] = d2[file, i].sort_index()
        
            for z, row in d2[file, i].iterrows():
                idx_loc = d2[file, i].index.get_loc(z)
                prev = idx_loc -1
                d2[file, i]['prev_pos'].loc[z] = d2[file, i]['pos'].iloc[prev]
                if row['trade'] == 1.0:
                    d2[file, i]['pos'].loc[z] = 1.0 + d2[file, i]['prev_pos'].loc[z]
                elif row['trade'] == -1.0:
                    d2[file, i]['pos'].loc[z] = -1.0 + d2[file, i]['prev_pos'].loc[z]
                else:
                    d2[file, i]['pos'].loc[z] = d2[file, i]['prev_pos'].loc[z]
                      
            d2[file, i]['shares'] = temp[file, i]['Shares'].iloc[0]
            d2[file, i]['qtty'] = opt1_qtty
        
            d2[file, i]['cash_val'] = 0.0
            d2[file, i]['trade_val'] = d2[file, i]['trade']*d2[file, i]['shares']*\
                d2[file, i]['qtty']*d2[file, i]['LAST PRICE']
            d2[file, i]['pos_val'] = d2[file, i]['prev_pos']*d2[file, i]['shares']*\
                d2[file, i]['qtty']*d2[file, i]['LAST PRICE']
        
            for z, row in d2[file, i].iterrows():
                idx_loc = d2[file, i].index.get_loc(z)
                prev = idx_loc -1
                if row['trade'] != 0:
                    d2[file, i]['cash_val'].loc[z] =\
                                        np.negative(d2[file, i]['trade'].loc[z]* \
                                        d2[file, i]['shares'].loc[z]* \
                                        d2[file, i]['qtty'].loc[z]* \
                                        d2[file, i]['LAST PRICE'].loc[z]) +\
                                        d2[file, i]['cash_val'].iloc[prev] 
                                          
                else:
                    d2[file, i]['cash_val'].loc[z] = d2[file, i]['cash_val'].iloc[prev] 

            d2[file, i]['total_val'] = d2[file, i]['trade_val'] +\
                d2[file, i]['pos_val'] + d2[file, i]['cash_val']  
            d2[file, i] =  d2[file, i].truncate(after = end_date)           
    
    
        frames = []
        for i in IDs:   
            frames.append(d2[file, i]['total_val'])
    
        tot_ser[file] = pd.concat(frames, join='outer', axis=1)
        tot_ser[file] = tot_ser[file].fillna(method = 'ffill')
        tot_ser[file] = tot_ser[file].fillna(0)
        tot_ser[file]['port_val'] = tot_ser[file].sum(axis=1)
        tot_ser[file]['port_ret'] = tot_ser[file]['port_val']/b_size_adj

#####add bond time_series
        
'''
Create Functions
'''

#create financing function

def apply_fin(currency, spread):
    if currency == 'USD':
        return ((((z['US0001M Index']) + spread)/100)/252)*-1
    else:
        return ((((z['EUR001M Index']) + spread)/100)/252)*-1

def sharpe_ratio(returns, n=252):
    return np.round(np.sqrt(n) * (returns.mean()/returns.std()), 3)

def max_DD(prices):
    #takes cumulative returns
    max2here = prices.expanding(min_periods=1).max()
    dd2here = prices - max2here
    return np.round(dd2here.min(), 3)

# set dates, securities, and fields
start_date = '01/01/2005'
end_date = "{:%m/%d/%Y}".format(datetime.now())

IDs = []
reader = DictReader(open(r'D:\Users\dpsugasa\AT1\Tearsheets\bonds_mini.csv'))
for line in reader:
    IDs.append(line)


fin_IDs = ['EUR001M Index', 'US0001M Index']
price_fields = ['LAST PRICE', 'HIGH', 'LOW']
ref_data = ['ID_ISIN', 'CPN', 'CPN_FREQ', 'CRNCY', 'SECURITY_NAME',
            'NXT_CALL_DT', 'ISSUE_DT', 'COMPANY_CORP_TICKER']


d = {} #dict of original dataframes per ID
m = {} #reference data
n = {} #pnl data
z = {} #financing data

for i in fin_IDs:
    z[i] = LocalTerminal.get_historical(i, 'LAST PRICE', start_date, end_date, period = 'DAILY').as_frame()
    z[i].columns = z[i].columns.droplevel(-1)
    z[i] = z[i].fillna(method = 'ffill')
    
for q in IDs:
    name = list(q.values())[1]
    code = list(q.values())[0]
    
    d[name] = LocalTerminal.get_historical(code, price_fields, start_date, end_date, period = 'DAILY').as_frame()
    d[name].columns = d[name].columns.droplevel()
    d[name] = d[name].append(pd.DataFrame(data = {'LAST PRICE':100, 'HIGH':100, 'LOW':100}, index=[(d[name].index[0] + timedelta(days = -1))])).sort_index()
    d[name] = d[name].fillna(method = 'ffill')
    
    m[name] = LocalTerminal.get_reference_data(code, ref_data).as_frame()
    
    n[name] = d[name]['LAST PRICE'].pct_change().dropna().to_frame()
    n[name] = n[name].rename(columns = {'LAST PRICE': 'p_ret'})
    n[name]['c_ret'] = (m[name]['CPN'].item()/100)/252
    n[name]['cum_cpn'] = n[name]['c_ret'].expanding().sum()
    n[name]['f_ret'] = apply_fin((m[name]['CRNCY'].item()), 0.50)
    n[name]['f_ret'] = n[name]['f_ret'].fillna(method='ffill')
    n[name]['cum_f'] = n[name]['f_ret'].expanding().sum()
    n[name]['t_ret'] = n[name]['c_ret'] + n[name]['f_ret'] + n[name]['p_ret']
    n[name]['cum_ret'] = n[name]['t_ret'].expanding().sum()
        
date_now =  "{:%m_%d_%Y}".format(d[name].last_valid_index())

#SANTAN Default Protection

framez = [n['SANTAN 6.25']['cum_ret'], tot_ser['default_SAN.csv']]
hp = pd.concat(framez, join = 'outer', axis=1)
hp = hp.drop(['total_val','total_val','total_val','total_val','total_val','total_val' ], axis = 1)
hp = hp.fillna(method = 'ffill')
hp = hp.dropna()
hp['pval'] = hp['port_val'].diff().expanding().sum()
hp['pval_ret'] = hp['pval']/b_size_adj
hp['tot_ret'] = hp['pval_ret'] + hp['cum_ret']
hp['t_ret'] = hp['tot_ret'].diff()

corp_tkr = m['SANTAN 6.25']['COMPANY_CORP_TICKER'].item()
cum_ret = go.Scatter(
            x = hp['tot_ret'].index,
            y = hp['tot_ret'].values,
            xaxis = 'x1',
            yaxis = 'y1',
            mode = 'lines',
            line = dict(width=2, color= 'blue'),
            name = 'Cumulative Return',
            )
    
ann_ret = go.Bar(
            x = hp['t_ret'].resample('A').sum().index,
            y = hp['t_ret'].resample('A').sum().values,
            xaxis = 'x2',
            yaxis = 'y2',
            name = 'Annual Returns',
            marker = dict(color = 'rgb(65, 244, 103)',
                          line = dict(color='green', width=1.25))
            )
    
mon_ret = go.Bar(
            x = hp['t_ret'].resample('BM').sum().index,
            y = hp['t_ret'].resample('BM').sum().values,
            xaxis = 'x3',
            yaxis = 'y3',
            name = 'Annual Returns',
            marker  = dict(color = 'rgb(65, 244, 103)',
                           line = dict(color='green', width=1.25)))
   
table = go.Table(
            domain = dict(x=[0,0.5],
                          y = [0.55,1.0]),
            columnwidth = [30] +[33,35,33],
            columnorder = [0,1],
            header=dict(height = 15,
                        values = ['', ''],
                        line = dict(color='#7D7F80'),
                        fill = dict(color='#a1c3d1'),
                        align = ['left'] * 5),
                        cells = dict(values= [['ISIN',
                                               'Coupon',
                                               'Currency',
                                               'Issue Date',
                                               'Next Call',
                                               'Cumulative Return',
                                               'Carry Return',
                                               'Financing Cost',
                                               'Current Price',
                                               'Sharpe Ratio',
                                               'Sharpe Ratio 12',
                                               'Sharpe Ratio 52',
                                               'Max Drawdown'],
    
                                    [m['SANTAN 6.25']['ID_ISIN'].item(),
                                     m['SANTAN 6.25']['CPN'].item(),
                                     m['SANTAN 6.25']['CRNCY'].item(),
                                     m['SANTAN 6.25']['ISSUE_DT'],
                                     m['SANTAN 6.25']['NXT_CALL_DT'],
                                     np.round(hp['cum_ret'].tail(1).item(),3),
                                     np.round(n['SANTAN 6.25']['cum_cpn'].tail(1).item(),3),
                                     np.round(n['SANTAN 6.25']['cum_f'].tail(1).item(),3),
                                     np.round(d['SANTAN 6.25']['LAST PRICE'].tail(1),3),
                                     sharpe_ratio(hp['t_ret']),
                                     sharpe_ratio(hp['t_ret'].resample('BM').sum().values, 12),
                                     sharpe_ratio(hp['t_ret'].resample('W').sum().values, 52),
                                     max_DD(hp['tot_ret'])]],
                            line = dict(color='#7D7F80'),
                            fill = dict(color='#EDFAFF'),
                            align = ['left'] * 5))
axis=dict(
            showline=True,
            zeroline=False,
            showgrid=True,
            mirror=True,
            ticklen=4, 
            gridcolor='#ffffff',
            tickfont=dict(size=10)
            )                        
                            
layout1 = dict(
            width=1800,
            height=750,
            autosize=True,
            title=f'SANTAN 6.25 Default Hedge - {date_now}',
            margin = dict(t=50),
            showlegend=False,   
            xaxis1=dict(axis, **dict(domain=[0.55, 1], anchor='y1', showticklabels=True)),
            xaxis2=dict(axis, **dict(domain=[0.55, 1], anchor='y2', showticklabels=True)),        
            xaxis3=dict(axis, **dict(domain=[0, 0.5], anchor='y3')), 
            yaxis1=dict(axis, **dict(domain=[0.55, 1.0], anchor='x1', hoverformat='.3f', title='Return')),  
            yaxis2=dict(axis, **dict(domain=[0, 0.5], anchor='x2', hoverformat='.3f', title = 'Return')),
            yaxis3=dict(axis, **dict(domain=[0.0, 0.5], anchor='x3', hoverformat='.3f', title = 'Return')),
            plot_bgcolor='rgba(228, 222, 249, 0.65)')
    
fig1 = dict(data = [table, cum_ret, ann_ret, mon_ret], layout=layout1)
py.iplot(fig1, filename = f'AT1/Hedged/{corp_tkr}/SANTAN 6.25_Default Hedged')

#Santander put spread

framez2 = [n['SANTAN 6.25']['cum_ret'], tot_ser['beta12_ps_SAN.csv']]
hp2 = pd.concat(framez2, join = 'outer', axis=1)
hp2 = hp2.drop(['total_val','total_val','total_val','total_val','total_val','total_val' ], axis = 1)
hp2 = hp2.fillna(method = 'ffill')
hp2 = hp2.dropna()
hp2['pval'] = hp2['port_val'].diff().expanding().sum()
hp2['pval_ret'] = hp2['pval']/b_size_adj
hp2['tot_ret'] = hp2['pval_ret'] + hp2['cum_ret']
hp2['t_ret'] = hp2['tot_ret'].diff()

corp_tkr = m['SANTAN 6.25']['COMPANY_CORP_TICKER'].item()
cum_ret = go.Scatter(
            x = hp2['tot_ret'].index,
            y = hp2['tot_ret'].values,
            xaxis = 'x1',
            yaxis = 'y1',
            mode = 'lines',
            line = dict(width=2, color= 'blue'),
            name = 'Cumulative Return',
            )
    
ann_ret = go.Bar(
            x = hp2['t_ret'].resample('A').sum().index,
            y = hp2['t_ret'].resample('A').sum().values,
            xaxis = 'x2',
            yaxis = 'y2',
            name = 'Annual Returns',
            marker = dict(color = 'rgb(65, 244, 103)',
                          line = dict(color='green', width=1.25))
            )
    
mon_ret = go.Bar(
            x = hp2['t_ret'].resample('BM').sum().index,
            y = hp2['t_ret'].resample('BM').sum().values,
            xaxis = 'x3',
            yaxis = 'y3',
            name = 'Annual Returns',
            marker  = dict(color = 'rgb(65, 244, 103)',
                           line = dict(color='green', width=1.25)))
   
table = go.Table(
            domain = dict(x=[0,0.5],
                          y = [0.55,1.0]),
            columnwidth = [30] +[33,35,33],
            columnorder = [0,1],
            header=dict(height = 15,
                        values = ['', ''],
                        line = dict(color='#7D7F80'),
                        fill = dict(color='#a1c3d1'),
                        align = ['left'] * 5),
                        cells = dict(values= [['ISIN',
                                               'Coupon',
                                               'Currency',
                                               'Issue Date',
                                               'Next Call',
                                               'Cumulative Return',
                                               'Carry Return',
                                               'Financing Cost',
                                               'Current Price',
                                               'Sharpe Ratio',
                                               'Sharpe Ratio 12',
                                               'Sharpe Ratio 52',
                                               'Max Drawdown'],
    
                                    [m['SANTAN 6.25']['ID_ISIN'].item(),
                                     m['SANTAN 6.25']['CPN'].item(),
                                     m['SANTAN 6.25']['CRNCY'].item(),
                                     m['SANTAN 6.25']['ISSUE_DT'],
                                     m['SANTAN 6.25']['NXT_CALL_DT'],
                                     np.round(hp2['cum_ret'].tail(1).item(),3),
                                     np.round(n['SANTAN 6.25']['cum_cpn'].tail(1).item(),3),
                                     np.round(n['SANTAN 6.25']['cum_f'].tail(1).item(),3),
                                     np.round(d['SANTAN 6.25']['LAST PRICE'].tail(1),3),                                     
                                     sharpe_ratio(hp2['t_ret']),
                                     sharpe_ratio(hp['t_ret'].resample('BM').sum().values, 12),
                                     sharpe_ratio(hp['t_ret'].resample('W').sum().values, 52),
                                     max_DD(hp2['tot_ret'])]],
                            line = dict(color='#7D7F80'),
                            fill = dict(color='#EDFAFF'),
                            align = ['left'] * 5))
axis=dict(
            showline=True,
            zeroline=False,
            showgrid=True,
            mirror=True,
            ticklen=4, 
            gridcolor='#ffffff',
            tickfont=dict(size=10)
            )                        
                            
layout1 = dict(
            width=1800,
            height=750,
            autosize=True,
            title=f'SANTAN 6.25 Put Spread Hedge - {date_now}',
            margin = dict(t=50),
            showlegend=False,   
            xaxis1=dict(axis, **dict(domain=[0.55, 1], anchor='y1', showticklabels=True)),
            xaxis2=dict(axis, **dict(domain=[0.55, 1], anchor='y2', showticklabels=True)),        
            xaxis3=dict(axis, **dict(domain=[0, 0.5], anchor='y3')), 
            yaxis1=dict(axis, **dict(domain=[0.55, 1.0], anchor='x1', hoverformat='.3f', title='Return')),  
            yaxis2=dict(axis, **dict(domain=[0, 0.5], anchor='x2', hoverformat='.3f', title = 'Return')),
            yaxis3=dict(axis, **dict(domain=[0.0, 0.5], anchor='x3', hoverformat='.3f', title = 'Return')),
            plot_bgcolor='rgba(228, 222, 249, 0.65)')
    
fig1 = dict(data = [table, cum_ret, ann_ret, mon_ret], layout=layout1)
py.iplot(fig1, filename = f'AT1/Hedged/{corp_tkr}/SANTAN 6.25_Put Spread Hedged')

#SOCGEN with put spread
framez3 = [n['SOCGEN 6']['cum_ret'], tot_ser['beta12_ps_GLE.csv']]
hp3 = pd.concat(framez3, join = 'outer', axis=1)
hp3 = hp3.drop(['total_val','total_val','total_val','total_val','total_val','total_val' ], axis = 1)
hp3 = hp3.fillna(method = 'ffill')
hp3 = hp3.dropna()
hp3['pval'] = hp3['port_val'].diff().expanding().sum()
hp3['pval_ret'] = hp3['pval']/b_size_adj
hp3['tot_ret'] = hp3['pval_ret'] + hp3['cum_ret']
hp3['t_ret'] = hp3['tot_ret'].diff()

corp_tkr = m['SOCGEN 6']['COMPANY_CORP_TICKER'].item()
cum_ret = go.Scatter(
            x = hp3['tot_ret'].index,
            y = hp3['tot_ret'].values,
            xaxis = 'x1',
            yaxis = 'y1',
            mode = 'lines',
            line = dict(width=2, color= 'blue'),
            name = 'Cumulative Return',
            )
    
ann_ret = go.Bar(
            x = hp3['t_ret'].resample('A').sum().index,
            y = hp3['t_ret'].resample('A').sum().values,
            xaxis = 'x2',
            yaxis = 'y2',
            name = 'Annual Returns',
            marker = dict(color = 'rgb(65, 244, 103)',
                          line = dict(color='green', width=1.25))
            )
    
mon_ret = go.Bar(
            x = hp3['t_ret'].resample('BM').sum().index,
            y = hp3['t_ret'].resample('BM').sum().values,
            xaxis = 'x3',
            yaxis = 'y3',
            name = 'Annual Returns',
            marker  = dict(color = 'rgb(65, 244, 103)',
                           line = dict(color='green', width=1.25)))
   
table = go.Table(
            domain = dict(x=[0,0.5],
                          y = [0.55,1.0]),
            columnwidth = [30] +[33,35,33],
            columnorder = [0,1],
            header=dict(height = 15,
                        values = ['', ''],
                        line = dict(color='#7D7F80'),
                        fill = dict(color='#a1c3d1'),
                        align = ['left'] * 5),
                        cells = dict(values= [['ISIN',
                                               'Coupon',
                                               'Currency',
                                               'Issue Date',
                                               'Next Call',
                                               'Cumulative Return',
                                               'Carry Return',
                                               'Financing Cost',
                                               'Current Price',                                               
                                               'Sharpe Ratio',
                                               'Sharpe Ratio 12',
                                               'Sharpe Ratio 52',
                                               'Max Drawdown'],
    
                                    [m['SOCGEN 6']['ID_ISIN'].item(),
                                     m['SOCGEN 6']['CPN'].item(),
                                     m['SOCGEN 6']['CRNCY'].item(),
                                     m['SOCGEN 6']['ISSUE_DT'],
                                     m['SOCGEN 6']['NXT_CALL_DT'],
                                     np.round(hp3['cum_ret'].tail(1).item(),3),
                                     np.round(n['SOCGEN 6']['cum_cpn'].tail(1).item(),3),
                                     np.round(n['SOCGEN 6']['cum_f'].tail(1).item(),3),
                                     np.round(d['SOCGEN 6']['LAST PRICE'].tail(1),3),                                     
                                     sharpe_ratio(hp3['t_ret']),
                                     sharpe_ratio(hp['t_ret'].resample('BM').sum().values, 12),
                                     sharpe_ratio(hp['t_ret'].resample('W').sum().values, 52),
                                     max_DD(hp3['tot_ret'])]],
                            line = dict(color='#7D7F80'),
                            fill = dict(color='#EDFAFF'),
                            align = ['left'] * 5))
axis=dict(
            showline=True,
            zeroline=False,
            showgrid=True,
            mirror=True,
            ticklen=4, 
            gridcolor='#ffffff',
            tickfont=dict(size=10)
            )                        
                            
layout1 = dict(
            width=1800,
            height=750,
            autosize=True,
            title=f'SOCGEN 6 Put Spread Hedge - {date_now}',
            margin = dict(t=50),
            showlegend=False,   
            xaxis1=dict(axis, **dict(domain=[0.55, 1], anchor='y1', showticklabels=True)),
            xaxis2=dict(axis, **dict(domain=[0.55, 1], anchor='y2', showticklabels=True)),        
            xaxis3=dict(axis, **dict(domain=[0, 0.5], anchor='y3')), 
            yaxis1=dict(axis, **dict(domain=[0.55, 1.0], anchor='x1', hoverformat='.3f', title='Return')),  
            yaxis2=dict(axis, **dict(domain=[0, 0.5], anchor='x2', hoverformat='.3f', title = 'Return')),
            yaxis3=dict(axis, **dict(domain=[0.0, 0.5], anchor='x3', hoverformat='.3f', title = 'Return')),
            plot_bgcolor='rgba(228, 222, 249, 0.65)')
    
fig1 = dict(data = [table, cum_ret, ann_ret, mon_ret], layout=layout1)
py.iplot(fig1, filename = f'AT1/Hedged/{corp_tkr}/SOCGEN 6_Put Spread Hedged')

  
print ("Time to complete:", datetime.now() - start_time)
#

    
    
    

    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
