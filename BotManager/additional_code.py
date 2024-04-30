

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
