

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

#not needed part
def monitor_signal(client,signal_list,coinpair_list):
    print("----Monitor Signal")
    #isOrderPlaced=False
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
        if not elem['symbol'] in pos:
            close_open_orders(client, elem['symbol'])
    #loss_count = recent_loss_count(client,coinpair_list)
    #print("recent losses",loss_count)
    limit_orders = []
    for signal in signal_list:
        symbol = signal[0]
        Limit_price = signal[1]['BUY_PRICE']
        set_mode(client, symbol, order_type)
        leverage = 3
        if models.StaticData.objects.exists():
            obj = models.StaticData.objects.get(static_id=1)
            leverage = int(obj.leverage)
            # print("leverage value ",type(leverage),leverage)
        set_leverage(client, symbol, leverage)  # +(loss_count*2)
        # print("leverage set")
        volume = 4
        if models.StaticData.objects.exists():
            obj = models.StaticData.objects.get(static_id=1)
            volume = int(obj.volume)
        amount = volume * leverage  # (+loss_count)
        qty_precision = get_qty_precision(client, symbol)
        qty = round(amount / Limit_price, qty_precision)
        if signal[1]['side'] == 'sell':
            #Limit_price_Trigger = signal[1]['BUY_PRICE_Trigger']
            resp1 = client.new_order(symbol=symbol, side='SELL', type='LIMIT', quantity=qty,
                                     price= Limit_price, stopPrice= Limit_price, timeInForce='GTC')
            #print(symbol, signal[1]['side'], "placing order")
            #models.BotLogs(description=f'{str(symbol)}, {str(signal)} , buy, placing order').save()
            print(resp1)
            models.BotOrders(order_id=str(resp1['orderId']), order_details=str(resp1)).save()
            models.BotLogs(description=f'{str(resp1)}').save()
            sleep(2)
            limit_orders.append([signal,resp1,qty])
        elif signal[1]['side'] == 'buy':
            # Limit_price_Trigger = signal[1]['BUY_PRICE_Trigger']
            resp1 = client.new_order(symbol=symbol, side='BUY', type='LIMIT', quantity=qty,
                                     price=Limit_price, stopPrice=Limit_price, timeInForce='GTC')
            # print(symbol, signal[1]['side'], "placing order")
            # models.BotLogs(description=f'{str(symbol)}, {str(signal)} , buy, placing order').save()
            print(resp1)
            models.BotOrders(order_id=str(resp1['orderId']), order_details=str(resp1)).save()
            models.BotLogs(description=f'{str(resp1)}').save()
            sleep(2)
            limit_orders.append([signal,resp1,qty])

    while True:
        try:
            minutes = datetime.datetime.now().minute
            seconds = datetime.datetime.now().second
            if minutes % 15 == 14 and seconds>=30 :
                for order in limit_orders:
                    if order[1]['status'] =='NEW':
                        client.cancel_order(symbol=order[1]['symbol'], orderId=int(order[1]['orderId']), recvWindow=5000)
                break
            # if isOrderPlaced:
            #     break
            for order in limit_orders:
                response = client.get_open_orders(
                    symbol=order[1]['symbol'], orderId=int(order[1]['orderId']), recvWindow=5000
                )
                if response['status'] == 'FILLED': #or response['status'] == 'PARTIALLY_FILLED':
                    place_order(client, order[0], order[2])
                    break


            # for signal in signal_list:
            #     #print(signal)
            #     current_price = float(client.ticker_price(signal[0])['price'])
            #     #print("current price from ticker",current_price,type(current_price))
            #     #condition for buy or sell then break
            #     if signal[1]['side']=='sell':
            #         if current_price<signal[1]['BUY_PRICE'] and current_price>signal[1]['last_buy_price']:
            #             #place market order order
            #             #print("inside sell condition")
            #             set_mode(client, signal[0], order_type)
            #             #print("isolated mode set")
            #             #sleep(1)
            #             leverage = 3
            #             if models.StaticData.objects.exists():
            #                 obj = models.StaticData.objects.get(static_id=1)
            #                 leverage = int(obj.leverage)
            #                 #print("leverage value ",type(leverage),leverage)
            #             set_leverage(client, signal[0], leverage) #+(loss_count*2)
            #             #print("leverage set")
            #             volume=4
            #             if models.StaticData.objects.exists():
            #                 obj = models.StaticData.objects.get(static_id=1)
            #                 volume = int(obj.volume)
            #             amount=volume*leverage #(+loss_count)
            #             #print("amount to be invested ",amount)
            #             #print('Placing order for ', signal[0])
            #             place_order(client,signal,amount)
            #             print("order placed for {0} and total money invested {1}, leverage {2} ".format(signal[0],amount,leverage))
            #             models.BotLogs(description="order placed for {0} and total money invested {1}, leverage {2} ".format(signal[0],amount,leverage)).save()
            #             isOrderPlaced=True
            #             break
            #
            #     elif signal[1]['side'] == 'buy':
            #         if current_price > signal[1]['BUY_PRICE'] and current_price < signal[1]['last_buy_price']:
            #             # place market order order
            #             # print("inside buy condition")
            #             set_mode(client, signal[0], order_type)
            #             leverage = 3
            #             if models.StaticData.objects.exists():
            #                 obj = models.StaticData.objects.get(static_id=1)
            #                 leverage = int(obj.leverage)
            #             set_leverage(client, signal[0], leverage ) #+ loss_count
            #             # print("leverage set")
            #             volume = 4
            #             if models.StaticData.objects.exists():
            #                 obj = models.StaticData.objects.get(static_id=1)
            #                 volume = int(obj.volume)
            #             amount = volume * leverage #(+ loss_count)
            #             # print('Placing order for ', signal[0])
            #             place_order(client, signal, amount)
            #             print("order placed for {0} and total money invested {1}, leverage {2} ".format(signal[0],
            #                     amount, leverage))
            #             models.BotLogs(
            #                 description="order placed for {0} and total money invested {1}, leverage {2} ".format(
            #                     signal[0], amount, leverage)).save()
            #             isOrderPlaced = True
            #             break
            #
            #     sleep(1)
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



# ['CKBUSDT', {'side': 'sell', 'BUY_PRICE': 0.015424, 'BUY_PRICE_Trigger': 0.015425, 'last_buy_price': 0.015362, 'SL': 0.015681, 'SL_Trigger': 0.015681, 'TP': 0.015116, 'TP_Trigger': 0.015117, 'Trailing_stopLosses': {'Trailing_SL1': 0.015362, 'Trailing_SL_Condition1': 0.015178}}]
# calling monitor
# ----Monitor Signal
# ----Setting Mode
# ----Setting Mode Found error. status: 400, error code: -4046, error message: No need to change margin type.
# ----setting Leverage
# {'symbol': 'CKBUSDT', 'leverage': 4, 'maxNotionalValue': '1000000'}
# {'orderId': 1515809764, 'symbol': 'CKBUSDT', 'status': 'NEW', 'clientOrderId': 'k6I0uNAYJHvKBq1wgj6WJA', 'price': '0.0154240', 'avgPrice': '0.00', 'origQty': '778', 'executedQty': '0', 'cumQty': '0', 'cumQuote': '0.0000000', 'timeInForce': 'GTC', 'type': 'LIMIT', 'reduceOnly': False, 'closePosition': False, 'side': 'SELL', 'positionSide': 'BOTH', 'stopPrice': '0.0000000', 'workingType': 'CONTRACT_PRICE', 'priceProtect': False, 'origType': 'LIMIT', 'priceMatch': 'NONE', 'selfTradePreventionMode': 'NONE', 'goodTillDate': 0, 'updateTime': 1714661368967}
# ----Monitor Signal Found error. status: 400, error code: -2013, error message: Order does not exist.
# ----Monitor Signal Found error. status: 400, error code: -2013, error message: Order does not exist.
# ----Monitor Signal Found error. status: 400, error code: -2013, error message: Order does not exist.
# ----Monitor Signal Found error. status: 400, error code: -2013, error message: Order does not exist.
# ----Monitor Signal Found error. status: 400, error code: -2013, error message: Order does not exist.
# ----Monitor Signal Found error. status: 400, error code: -2013, error message: Order does not exist.
# ----Monitor Signal Found error. status: 400, error code: -2013, error message: Order does not exist.
# ----Monitor Signal Found error. status: 400, error code: -2013, error message: Order does not exist.