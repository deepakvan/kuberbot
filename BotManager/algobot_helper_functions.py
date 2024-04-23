import datetime
import threading
from time import sleep
import pandas_ta as ta
import pandas as pd
from binance.error import ClientError
pd.set_option('display.max_columns', None)

from . import models

volume = 4  # volume for one order (if its 10 and leverage is 10, then you put 1 usdt to one position)
leverage = 3      # total usdt is 5*2=10 usdt
order_type = 'ISOLATED'  # type is 'ISOLATED' or 'CROSS'

def round_with_padding(value, round_digits):
    value_str = str(value)
    if '.' not in value_str:
        return value_str
    split_value_str = value_str.split('.')
    zeros = (round_digits - len(split_value_str[1]))*'0' if len(split_value_str[1])<round_digits else ''
    new_value = split_value_str[0] + '.' + split_value_str[1][:round_digits] + zeros
    return new_value

def increase_decimal_by_1(number):
    # Convert the number to a string to handle trailing zeros and precision
    number_str = str(number)

    # If the number has no decimal part (i.e., ends with '.0'), simply add '.1' to it
    if '.' not in number_str:
        return round(number + 0.1, 10)

    # Split the number into integer and decimal parts
    integer_part, decimal_part = number_str.split('.')

    # Increase the decimal part by 1
    decimal_len=len(decimal_part)
    decimal_add='0.'+'0'*(decimal_len-1) + '1'
    #print('number - ',number_str,'decimal add - ',decimal_add)
    # Reconstruct the number as a float
    result = round(float(number_str) + float(decimal_add),decimal_len)
    return result


def decrease_decimal_by_1(number):
    # Convert the number to a string to handle trailing zeros and precision
    number_str = str(number)

    if number==0:
        return 0
    # If the number has no decimal part (i.e., ends with '.0'), simply add '.1' to it
    if '.' not in number_str:
        return round(number - 0.1, 10)

    # Split the number into integer and decimal parts
    integer_part, decimal_part = number_str.split('.')

    # Increase the decimal part by 1
    decimal_len=len(decimal_part)
    decimal_add='0.'+'0'*(decimal_len-1) + '1'
    #  print('number - ',number_str,'decimal add - ',decimal_add)
    #  Reconstruct the number as a float
    result = round(float(number_str) - float(decimal_add),decimal_len)

    return result

def get_balance_usdt(client):
    print("----fetching Balance")
    models.BotLogs(description=f'----fetching Balance').save()
    try:
        response = client.balance(recvWindow=10000)
        for elem in response:
            if elem['asset'] == 'USDT':
                return float(elem['balance'])

    except ClientError as error:
        print(
            "----fetching Balance Found error. status: {}, error code: {}, error message: {}".format(
                error.status_code, error.error_code, error.error_message
            )
        )
        models.BotLogs(description="----fetching Balance Found error. status: {}, error code: {}, error message: {}".format(
                error.status_code, error.error_code, error.error_message
            )).save()

def all_usdt_pairs(client):
    # Fetch exchange info to get all symbols
    exchange_info = client.exchange_info()

    # Filter USDT futures pairs
    usdt_futures_pairs = [symbol['symbol'] for symbol in exchange_info['symbols'] if symbol['quoteAsset'] == 'USDT']
    return  usdt_futures_pairs

def fetch_historical_data(client_obj, symbol, interval='5m',limit=1000):
    print("----fetching Historical data")
    models.BotLogs(description=f'----fetching Historical Data').save()
    try:
        resp = pd.DataFrame(client_obj.klines(symbol, interval,limit=limit))
        resp = resp.iloc[:, :6]
        resp.columns = ['Time', 'open', 'high', 'low', 'close', 'volume']
        resp = resp.set_index('Time')
        resp.index = pd.to_datetime(resp.index, unit='ms')
        resp = resp.astype(float)
        return resp
    except ClientError as error:
        print(
            "----fetching Historical data Found error. status: {}, error code: {}, error message: {}".format(
                error.status_code, error.error_code, error.error_message
            )
        )
        models.BotLogs(description="----fetching Historical data Found error. status: {}, error code: {}, error message: {}".format(
                error.status_code, error.error_code, error.error_message
            )).save()



# Set leverage for the needed symbol. You need this bcz different symbols can have different leverage
def set_leverage(client,symbol, level):
    print("----setting Leverage")
    models.BotLogs(description=f'----Setting Leverage').save()
    try:
        response = client.change_leverage(
            symbol=symbol, leverage=level, recvWindow=6000
        )
        print(response)
    except ClientError as error:
        print(
            "----setting Leverage Found error. status: {}, error code: {}, error message: {}".format(
                error.status_code, error.error_code, error.error_message
            )
        )
        models.BotLogs(description="----setting Leverage Found error. status: {}, error code: {}, error message: {}".format(
                error.status_code, error.error_code, error.error_message
            )).save()

# The same for the margin type
def set_mode(client, symbol, order_type):
    print("----Setting Mode ")
    models.BotLogs(description=f'----Setting Mode').save()
    #print("inside set mode function")
    try:
        response = client.change_margin_type(
            symbol=symbol, marginType=order_type, recvWindow=6000
        )
        print(response)
    except ClientError as error:
        print(
            "----Setting Mode Found error. status: {}, error code: {}, error message: {}".format(
                error.status_code, error.error_code, error.error_message
            )
        )
        models.BotLogs(description="----Setting Mode Found error. status: {}, error code: {}, error message: {}".format(
                error.status_code, error.error_code, error.error_message
            )).save()

# Price precision. BTC has 1, XRP has 4
def get_price_precision(client, symbol):
    resp = client.exchange_info()['symbols']
    for elem in resp:
        if elem['symbol'] == symbol:
            return elem['pricePrecision']

# Amount precision. BTC has 3, XRP has 1
def get_qty_precision(client, symbol):
    resp = client.exchange_info()['symbols']
    for elem in resp:
        if elem['symbol'] == symbol:
            return elem['quantityPrecision']

def remove_pending_orders_repeated(client):
    print("----Removing Pending Orders ")
    models.BotLogs(description="----Removing Pending Orders").save()
    while True:
        try:
            minutes = datetime.datetime.now().minute
            if minutes % 15 == 0:
                sleep(60)
            pos = get_pos(client)
            #print(f'You have {len(pos)} opened positions:\n{pos}')
            if len(pos) == 0:
                #sleep(10)
                ord = check_orders(client)
                # print(ord)
                # removing stop orders for closed positions
                for elem in ord:
                    if not elem in pos:
                        print(elem, "order removed by pending order close function")
                        sleep(1)
                        close_open_orders(client, elem)
            sleep(60)
        except ClientError as error:
            print(
                "----Removing Pending Orders  Found error. status: {}, error code: {}, error message: {}".format(
                    error.status_code, error.error_code, error.error_message
                )
            )
            models.BotLogs(description="----Removing Pending Orders  Found error. status: {}, error code: {}, error message: {}".format(
                    error.status_code, error.error_code, error.error_message
                )).save()
            sleep(60)
            continue
        except:
            models.BotLogs(description="----Error in Removing Pending Orders ").save()
            sleep(60)
            continue


def modify_sl_from_previous_candle(client, order_details, qty):
    print("----Modify Stoploss ")
    models.BotLogs(description=f'----Modify Stoploss').save()
    sleep(60*5)
    df = fetch_historical_data(client, order_details['symbol'], '5m', 2)
    df=df.iloc[-2,:]
    print(df)
    print("old price of order ",order_details['stopPrice'], order_details['side'])
    new_price = None
    if order_details['side']=='BUY':
        new_high=increase_decimal_by_1(df['high'])
        print("new high in sell", new_high)
        if float(order_details['stopPrice'])>new_high:
            new_price=new_high
    elif order_details['side'] == 'SELL':
        new_low = decrease_decimal_by_1(df['low'])
        print("new low price ",new_low)
        if float(order_details['stopPrice'])<new_low:
            new_price=new_low
    print(new_price,type(new_price))

    # Cancel the existing stop-loss order
    if new_price:
        try:
            response = client.get_open_orders(
                symbol=order_details['symbol'], orderId=int(order_details['orderId']),recvWindow=2000
            )
            print(response)
            current_price = float(client.ticker_price(order_details['symbol'])['price'])
            price_condition=False
            if order_details['side'] == 'BUY' and current_price<new_price:
                price_condition=True
            elif order_details['side'] == 'SELL' and current_price>new_price:
                price_condition=True
            if response and price_condition:
                client.cancel_order(
                    symbol=order_details['symbol'], orderId=int(order_details['orderId']),recvWindow=2000)

                # Create a new stop-loss order with the updated price
                try:
                    # sl_price = decrease_decimal_by_1(round(signal[1]['SL'], price_precision))
                    resp2 = client.new_order(
                        symbol=order_details['symbol'],
                        side=order_details['side'],
                        type='STOP_MARKET',
                        quantity=qty,
                        timeInForce='GTC',
                        stopPrice=new_price,
                        closePosition=True)
                    # Assuming the new order was created successfully, return its details
                    # return resp2
                    print("sl modified")
                    print(resp2)
                except Exception as e:
                    print("----Modify Stoploss  Error modifying stop-loss order:", e)
                    # return None

        except Exception as e:
            print("----Modify Stoploss  Error canceling order:", e)
            #return None

def modify_sl_for_brokrage(client, order_details, qty):
    print("----Modify Stoploss")
    #sleep(60*5)
    current_price = float(client.ticker_price(order_details['symbol'])['price'])

    df = fetch_historical_data(client, order_details['symbol'], '5m', 2)
    df=df.iloc[-2,:]
    print(df)
    print("old price of order ",order_details['stopPrice'], order_details['side'])
    new_price = None
    if order_details['side']=='BUY':
        new_high=increase_decimal_by_1(df['high'])
        print("new high in sell", new_high)
        if float(order_details['stopPrice'])>new_high:
            new_price=new_high
    elif order_details['side'] == 'SELL':
        new_low = decrease_decimal_by_1(df['low'])
        print("new low price ",new_low)
        if float(order_details['stopPrice'])<new_low:
            new_price=new_low
    print(new_price,type(new_price))

    # Cancel the existing stop-loss order
    if new_price:
        try:
            response = client.get_open_orders(
                symbol=order_details['symbol'], orderId=int(order_details['orderId']),recvWindow=2000
            )
            print(response)
            current_price = float(client.ticker_price(order_details['symbol'])['price'])
            price_condition=False
            if order_details['side'] == 'BUY' and current_price<new_price:
                price_condition=True
            elif order_details['side'] == 'SELL' and current_price>new_price:
                price_condition=True
            if response and price_condition:
                client.cancel_order(
                    symbol=order_details['symbol'], orderId=int(order_details['orderId']),recvWindow=2000)

                # Create a new stop-loss order with the updated price
                try:
                    # sl_price = decrease_decimal_by_1(round(signal[1]['SL'], price_precision))
                    resp2 = client.new_order(
                        symbol=order_details['symbol'],
                        side=order_details['side'],
                        type='STOP_MARKET',
                        quantity=qty,
                        timeInForce='GTC',
                        stopPrice=new_price,
                        closePosition=True)
                    # Assuming the new order was created successfully, return its details
                    # return resp2
                    print("sl modified")
                    print(resp2)
                except Exception as e:
                    print("----Modify Stoploss Error modifying stop-loss order:", e)
                    # return None

        except Exception as e:
            print("----Modify Stoploss Error canceling order:", e)
            #return None



# Open new order with the last price, and set TP and SL:
def place_order(client,signal,amount):  # signal =['coinpair', {"side":'sell',"BUY_PRICE":BUY_PRICE, "SL":SL,"TP":TP}]
    print("----Placing Orders ")
    models.BotLogs(description=f'----Placing Orders').save()
    print(signal[0])
    models.BotLogs(description=f'{str(signal[0])}').save()
    symbol=signal[0]
    price = float(client.ticker_price(symbol)['price'])
    #print("current price ",price)
    qty_precision = get_qty_precision(client, symbol)
    #print("qty_precision ", qty_precision)
    price_precision = get_price_precision(client, symbol)
    #print("price precision",price_precision)
    qty = round(amount/price, qty_precision)
    #print("qty", qty)
    if signal[1]['side'] == 'buy':
        try:
            resp1 = client.new_order(symbol=symbol, side='BUY', type='MARKET', quantity=qty)  # price=price, timeInForce='GTC',
            print(symbol, signal[1]['side'], "placing order")
            models.BotLogs(description=f'{str(symbol)}, {str(signal)} , buy, placing order').save()
            print(resp1)
            models.BotOrders(order_id=str(resp1['orderId']), order_details=str(resp1)).save()
            models.BotLogs(description=f'{str(resp1)}').save()
            sleep(2)
            sl_price = decrease_decimal_by_1(round(signal[1]['SL'], price_precision))
            sl_price_trigger = increase_decimal_by_1(sl_price)
            print("stop loss price in buy order  - ",
                  decrease_decimal_by_1(round_with_padding(signal[1]['SL'], price_precision)),sl_price,
                  sl_price_trigger)
            resp2 = client.new_order(symbol=symbol, side='SELL', type='STOP', quantity=qty, timeInForce='GTC',
                                     stopPrice=sl_price_trigger, price=sl_price) #closePosition=True)
            print(resp2)
            models.BotOrders(order_id=str(resp2['orderId']), order_details=str(resp2)).save()
            models.BotLogs(description=f'{str(resp2)}').save()
            #threading.Thread(target=modify_sl, args=(client, resp2, qty)).start()
            sleep(2)
            tp_price = round(signal[1]['TP'], price_precision)
            tp_price_trigger = decrease_decimal_by_1(tp_price)
            print("tp price in buy order  - ", tp_price, tp_price_trigger)
            resp3 = client.new_order(symbol=symbol, side='SELL', type='TAKE_PROFIT', quantity=qty, timeInForce='GTC',
                                     stopPrice=tp_price_trigger, price=tp_price) #closePosition=True)
            print(resp3)
            models.BotOrders(order_id=str(resp3['orderId']), order_details=str(resp3)).save()
            models.BotLogs(description=f'{str(resp3)}').save()
        except ClientError as error:
            print(
                "----Placing Orders buy side  Found error. status: {}, error code: {}, error message: {}".format(
                    error.status_code, error.error_code, error.error_message
                )
            )
            models.BotLogs(description="----Placing Orders buy side  Found error. status: {}, error code: {}, error message: {}".format(
                    error.status_code, error.error_code, error.error_message
                )).save()
    if signal[1]['side'] == 'sell':
        try:
            resp1 = client.new_order(symbol=symbol, side='SELL', type='MARKET', quantity=qty) # price=price,timeInForce='GTC'
            print(symbol, signal[1]['side'], "placing order")
            models.BotLogs(description=f'{str(symbol)}, {str(signal)} , sell side placing order').save()
            print(resp1)
            models.BotOrders(order_id=str(resp1['orderId']), order_details=str(resp1)).save()
            models.BotLogs(description=f'{str(resp1)}').save()
            sleep(2)
            sl_price = increase_decimal_by_1(round(signal[1]['SL'], price_precision))
            sl_price_trigger = decrease_decimal_by_1(sl_price)
            print("stop loss price in sell order  - ",
                  increase_decimal_by_1(round_with_padding(signal[1]['SL'], price_precision)),sl_price, sl_price_trigger)
            resp2 = client.new_order(symbol=symbol, side='BUY', type='STOP', quantity=qty, timeInForce='GTC',
                                     stopPrice=sl_price_trigger, price=sl_price)#closePosition=True)
            # #, workingType="CONTRACT_PRICE" or MARK_PRICE
            print(resp2)
            models.BotOrders(order_id=str(resp2['orderId']), order_details=str(resp2)).save()
            models.BotLogs(description=f'{str(resp2)}').save()
            #threading.Thread(target=modify_sl, args=(client, resp2, qty)).start()
            sleep(2)
            tp_price = round(signal[1]['TP'], price_precision)
            tp_price_trigger = increase_decimal_by_1(tp_price)
            print("tp price in sell order  - ", tp_price, tp_price_trigger)
            resp3 = client.new_order(symbol=symbol, side='BUY', type='TAKE_PROFIT', quantity=qty, timeInForce='GTC',
                                     stopPrice=tp_price_trigger,price=tp_price) #closePosition=True)
            print(resp3)
            models.BotOrders(order_id=str(resp3['orderId']), order_details=str(resp3)).save()
            models.BotLogs(description=f'{str(resp3)}').save()
        except ClientError as error:
            print(
                "----Placing Orders sell side Found error. status: {}, error code: {}, error message: {}".format(
                    error.status_code, error.error_code, error.error_message
                )
            )
            models.BotLogs(description="----Placing Orders sell side Found error. status: {}, error code: {}, error message: {}".format(
                    error.status_code, error.error_code, error.error_message
                )).save()

# Your current positions (returns the symbols list):
def get_pos(client):
    #print("----Getting Positions ")
    #models.BotLogs(description="----Getting Positions ").save()
    try:
        resp = client.get_position_risk()
        pos = []
        for elem in resp:
            if float(elem['positionAmt']) != 0:
                pos.append(elem['symbol'])
        return pos
    except ClientError as error:
        print(
            "----Getting Positions Found error. status: {}, error code: {}, error message: {}".format(
                error.status_code, error.error_code, error.error_message
            )
        )
        models.BotLogs(description="----Getting Positions Found error. status: {}, error code: {}, error message: {}".format(
                error.status_code, error.error_code, error.error_message
            )).save()

def get_pos_count(client):
    print("----Getting Position Count ")
    models.BotLogs(description="----Getting Position Count ").save()
    try:
        resp = client.get_position_risk()
        position = 0
        for elem in resp:
            if float(elem['positionAmt']) != 0:
                position = position + 1
        return position
    except ClientError as error:
        print(
            "----Getting Position Count Found error. status: {}, error code: {}, error message: {}".format(
                error.status_code, error.error_code, error.error_message
            )
        )
        models.BotLogs(description="----Getting Position Count Found error. status: {}, error code: {}, error message: {}".format(
                error.status_code, error.error_code, error.error_message
            )).save()


def check_orders(client):
    #print("----Checking Orders ")
    #models.BotLogs(description="----Checking Orders ").save()
    try:
        response = client.get_orders(recvWindow=10000)
        sym = []
        for elem in response:
            sym.append(elem['symbol'])
        #print("working")
        return sym
    except ClientError as error:
        print(
            "----Checking Orders Found error. status: {}, error code: {}, error message: {}".format(
                error.status_code, error.error_code, error.error_message
            )
        )
        models.BotLogs(description="----Checking Orders Found error. status: {}, error code: {}, error message: {}".format(
                error.status_code, error.error_code, error.error_message
            )).save()

# Close open orders for the needed symbol. If one stop order is executed and another one is still there
def close_open_orders(client,symbol):
    print("----Closing Open Orders")
    models.BotLogs(description="----Closing Open Orders").save()
    try:
        response = client.cancel_open_orders(symbol=symbol, recvWindow=10000)
        return response
    except ClientError as error:
        print(
            "----Closing Open Orders Found error. status: {}, error code: {}, error message: {}".format(
                error.status_code, error.error_code, error.error_message
            )
        )
        models.BotLogs(description="----Closing Open Orders Found error. status: {}, error code: {}, error message: {}".format(
                error.status_code, error.error_code, error.error_message
            )).save()


def get_signal(df):
    #print("inside get signal")
    #print(df)
    df['ema5'] = ta.ema(df['close'], 5)
    df = df.iloc[-2, :]

    # supertrend = ta.supertrend(df['high'], df['low'], df['close'], 30, 2.5)
    # trend_directions = supertrend['SUPERTd_30_2.5']
    #
    # df = df.iloc[-2,:]
    # trend_direction=trend_directions.iloc[-2]
    # #print(df)
    candleHeight = df['high'] - df['low']
    # Calculate 50 % of the candle height
    halfCandleHeight = candleHeight * 0.5
    #
    # #Detect candles where open and close are below 50 % of the candle height
    # isLowOpenClose = (df['open'] < df['low'] + halfCandleHeight) and \
    #                             (df['close'] < df['low'] + halfCandleHeight) and \
    #                             trend_direction==-1
    #
    # isHighOpenClose = (df['open'] > df['low'] + halfCandleHeight) and \
    #                  (df['close'] > df['low'] + halfCandleHeight) and \
    #                   trend_direction==1

    isShootingStarTouchingEMA = (df['open'] < df['low'] + halfCandleHeight) and \
                                (df['close'] < df['low'] + halfCandleHeight) and \
                                (df['open'] < df['ema5']) and (df['close'] < df['ema5']) and \
                                (df['high'] >= df['ema5'])

    isHammerTouchingEMA = (df['open'] > df['high'] - halfCandleHeight) and \
                          (df['close'] > df['high'] - halfCandleHeight) and \
                          (df['open'] > df['ema5']) and (df['close'] > df['ema5']) and \
                          (df['low'] <= df['ema5'])

    isEmaBuy = df['ema5'] < df['low'] and df['close']< df['open']


    # #for short trade
    # if isLowOpenClose:
    #     SLTPRatio=1.2
    #     #signal = 1
    #     BUY_PRICE = df['low']
    #     SL = df['high']  # BUY_PRICE[row]+(df['atr'][row-1]*atrmultiplier)
    #     TP = BUY_PRICE - SLTPRatio * (SL- BUY_PRICE)
    #     trade = {"side":'sell',"BUY_PRICE":BUY_PRICE, "SL":SL,"TP":TP}
    #     #print(trade)
    #     return trade
    #
    # # for long trade
    # elif isHighOpenClose:
    #     SLTPRatio = 1.2
    #     # signal = 1
    #     BUY_PRICE = df['high']
    #     SL = df['low']  # BUY_PRICE[row]+(df['atr'][row-1]*atrmultiplier)
    #     TP = BUY_PRICE + SLTPRatio * (BUY_PRICE - SL )
    #     trade = {"side": 'buy', "BUY_PRICE": BUY_PRICE, "SL": SL, "TP": TP}
    #     # print(trade)
    #     return trade

    # for short trades

    if isShootingStarTouchingEMA:
        SLTPRatio = 2  # 1:2
        # signal = 1
        BUY_PRICE = df['low']
        SL = df['high']  # BUY_PRICE[row]+(df['atr'][row-1]*atrmultiplier)
        TP = BUY_PRICE - SLTPRatio * (SL - BUY_PRICE)
        last_buy_price = BUY_PRICE - ((BUY_PRICE - TP) * 0.2)
        trade = {"side": 'sell',
                 "BUY_PRICE": BUY_PRICE,
                 "last_buy_price": last_buy_price,
                 "SL": SL,
                 "TP": TP}
        # print(trade)
        return trade

    # for long trade
    elif isHammerTouchingEMA :  #or isEmaBuy:
        SLTPRatio = 2  # 1:2
        # signal = 1
        BUY_PRICE = df['high']
        SL = df['low']  # BUY_PRICE[row]+(df['atr'][row-1]*atrmultiplier)
        TP = BUY_PRICE + SLTPRatio * (BUY_PRICE - SL)
        last_buy_price = BUY_PRICE + ((TP - BUY_PRICE) * 0.2)
        trade = {"side": 'buy',
                 "BUY_PRICE": BUY_PRICE,
                 "last_buy_price": last_buy_price,
                 "SL": SL,
                 "TP": TP}
        # print(trade)
        return trade

    return None

def recent_loss_count(client,coinpair_list):
    print("----Recent Losses")
    models.BotLogs(description="----Recent Losses ").save()
    df = pd.DataFrame()
    try:
        for ticker in coinpair_list:
            data = client.get_all_orders(symbol=ticker)
            da = pd.DataFrame(data)
            #print(da)
            if not da.empty:
                da=da[da['status']=='FILLED']
                da['time']=pd.to_datetime(da['time'], unit='ms')
                da['updateTime'] = pd.to_datetime(da['updateTime'], unit='ms')
                df = pd.concat([df, da], axis=0, ignore_index=True, sort=False)
        losscount = 0
        if not df.empty:
            df = df.sort_values(by='updateTime', ascending=False)
            #print(df)
            for index,row in df.iterrows():
                # if row['origType']=='TAKE_PROFIT_MARKET':
                #     return losscount
                # elif row['origType']=='STOP_MARKET':
                #     losscount = losscount + 1

                if row['origType']=='STOP_MARKET':
                    return losscount
                elif row['origType']=='TAKE_PROFIT_MARKET':
                    losscount = losscount + 1

    except ClientError as error:
        print(
            "----Recent Losses Found error. status: {}, error code: {}, error message: {}".format(
                error.status_code, error.error_code, error.error_message
            )
        )

    except :
        print("error in recent losses")
    return 0

def monitor_signal(client,signal_list,coinpair_list):
    print("----Monitor Signal")
    isOrderPlaced=False
    models.BotLogs(description="----Monitor Signal").save()
    if len(signal_list)==0:
        print("no signal")
        models.BotLogs(description="no signal").save()
        return None
    pos = get_pos(client)
    if len(pos) != 0:
        return None
    ord = check_orders(client)
    # print("old orders ",ord)
    # removing stop orders for closed positions
    for elem in ord:
        if not elem in pos:
            close_open_orders(client, elem)
    #loss_count = recent_loss_count(client,coinpair_list)
    #print("recent losses",loss_count)
    # for signal in signal_list:
    #     print(signal)
    #     if signal[1]['side'] == 'sell':
    #         signal[1]['last_buy_price'] = signal[1]['BUY_PRICE'] - ((signal[1]['BUY_PRICE'] - signal[1]['TP']) * 0.2)
    #         print("last buy price is :- ", signal)
    #     elif signal[1]['side'] == 'buy':
    #         signal[1]['last_buy_price'] = signal[1]['BUY_PRICE'] + ((signal[1]['TP'] - signal[1]['BUY_PRICE']) * 0.2)
    #         print("last buy price is :- ", signal)

    while True:
        try:
            minutes = datetime.datetime.now().minute
            seconds = datetime.datetime.now().second
            if minutes % 15 == 14 and seconds>=30 :
                break
            if isOrderPlaced:
                break
            for signal in signal_list:
                #print(signal)
                #df = fetch_historical_data(client, signal[0], '5m', 1)
                #print(df)
                #print("working point")
                current_price = float(client.ticker_price(signal[0])['price'])
                #print("current price from ticker",current_price,type(current_price))
                # print("pair",signal[0])
                # print("signal ",signal[1])
                # print("buy price ", signal[1]['BUY_PRICE'])
                # print("sl ", signal[1]['SL'])
                # print("tp ", signal[1]['TP'])
                #condition for buy or sell then break
                if signal[1]['side']=='sell':
                    #last_buy_price=signal[1]['BUY_PRICE'] - ((signal[1]['BUY_PRICE'] - signal[1]['TP'])*0.2)
                    #print("last buy price is :- ",signal[1]['last_buy_price'])
                    if current_price<signal[1]['BUY_PRICE'] and current_price>signal[1]['last_buy_price']:
                        #place market order order
                        #print("inside sell condition")
                        set_mode(client, signal[0], order_type)
                        #print("isolated mode set")
                        #sleep(1)
                        leverage = 3
                        if models.StaticData.objects.exists():
                            obj = models.StaticData.objects.get(static_id=1)
                            leverage = int(obj.leverage)
                        set_leverage(client, signal[0], leverage) #+loss_count
                        #print("leverage set")
                        volume=4
                        if models.StaticData.objects.exists():
                            obj = models.StaticData.objects.get(static_id=1)
                            volume = int(obj.volume)
                        amount=volume*leverage #(+loss_count)
                        #print("amount to be invested ",amount)
                        #sleep(1)
                        #print('Placing order for ', signal[0])
                        place_order(client,signal,amount)
                        print("order placed for {0} and total money invested {1}, leverage {2} ".format(signal[0],amount,leverage))
                        models.BotLogs(description="order placed for {0} and total money invested {1}, leverage {2} ".format(signal[0],amount,leverage)).save()
                        isOrderPlaced=True
                        break

                elif signal[1]['side'] == 'buy':
                    #last_buy_price = signal[1]['BUY_PRICE'] + ((signal[1]['TP'] - signal[1]['BUY_PRICE']) * 0.2)
                    #print("last buy price is :- ", last_buy_price)
                    if current_price > signal[1]['BUY_PRICE'] and current_price < signal[1]['last_buy_price']:
                        # place market order order
                        # print("inside buy condition")
                        set_mode(client, signal[0], order_type)
                        # print("isolated mode set")
                        # sleep(1)
                        leverage = 3
                        if models.StaticData.objects.exists():
                            obj = models.StaticData.objects.get(static_id=1)
                            leverage = obj.leverage
                        set_leverage(client, signal[0], leverage ) #+ loss_count
                        # print("leverage set")
                        volume = 4
                        if models.StaticData.objects.exists():
                            obj = models.StaticData.objects.get(static_id=1)
                            volume = obj.volume
                        amount = volume * leverage #(+ loss_count)
                        #print("amount to be invested ", amount)
                        # sleep(1)
                        # print('Placing order for ', signal[0])
                        place_order(client, signal, amount)
                        print("order placed for {0} and total money invested {1}, leverage {2} ".format(signal[0],
                                amount, leverage))
                        models.BotLogs(
                            description="order placed for {0} and total money invested {1}, leverage {2} ".format(
                                signal[0], amount, leverage)).save()
                        isOrderPlaced = True
                        break

                sleep(1)
        except ClientError as error:
            print(
                "----Monitor Signal Found error. status: {}, error code: {}, error message: {}".format(
                    error.status_code, error.error_code, error.error_message
                )
            )
            models.BotLogs(
                description="----Monitor Signal Found error. status: {}, error code: {}, error message: {}".format(
                    error.status_code, error.error_code, error.error_message
                )).save()
            sleep(5)
            continue
        except :
            print("error in monitor signal")
            models.BotLogs(description="error in monitor signal").save()
            sleep(5)
            continue
    return None