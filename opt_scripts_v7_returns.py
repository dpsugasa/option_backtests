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
from datetime import datetime
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

path2 = "C:\\Users\\dpsugasa\\WorkFiles\\option_backtests\\options"
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
    path = f"C:\\Users\\dpsugasa\\WorkFiles\\option_backtests\\options\\{direct}"
    dirs = os.listdir(path)
    for file in dirs:
        curr_path = fr'C:\Users\dpsugasa\Workfiles\option_backtests\options\{direct}/{file}'
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
        tot_ser[file]['port_val'] = tot_ser[file].sum(axis=1)/b_size_adj
        
        #        tot_ser[file]['port_val'] = tot_ser[file].sum(axis=1)

        
    
        root_tkr = m[file, i]['COMPANY_CORP_TICKER'].item()
        file_name = file.replace('.csv','')
        trace1 = go.Scatter(
                    x = tot_ser[file]['port_val'].index,
                    y = tot_ser[file]['port_val'].values,
                    name = f'{root_tkr}_Options',
                    line = dict(
                            color = ('#4155f4'),
                            width = 2))        
           
        layout  = {'title' : f'{file_name}_{date_now}',
                       'xaxis' : {'title' : 'Date', 'type': 'date'},
                       'yaxis' : {'title' : 'Returns'},
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
        py.iplot(figure, filename =\
                 f'option_backtest/{root_tkr}/{file_name}/{file_name}_{date_now}')
    
    b = {}
    for file in dirs:
        b[file] = create_trace(tot_ser[file]['port_val'], file)
            
        root_tkr = n[file]['COMPANY_CORP_TICKER'].item()
        file_name = file.replace('.csv','')    
        layout  = {'title' : f'{root_tkr}_All_Flavors',
                           'xaxis' : {'title' : 'Date', 'type': 'date'},
                           'yaxis' : {'title' : 'Returns'},
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
        data = list(b.values())
        figure = go.Figure(data=data, layout=layout)
        py.iplot(figure, filename =\
                     f'option_backtest/{root_tkr}/{root_tkr}_All_Flavors_{date_now}')    

    print ("Time to complete:", datetime.now() - start_time)


    
    
    

    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
