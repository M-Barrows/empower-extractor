from dotenv import load_dotenv
from os import getenv
import requests
from datetime import datetime
import pandas as pd
from tqdm import tqdm
import argparse
from colorama import Fore

parser = argparse.ArgumentParser(
    prog="Empower Extractor",
    description="An unofficial CLI tool enabling easy export of detailed transaction records from your Empower Retirement Account",
    epilog="Made with ❤️ by CodeAndCoffee"
)
parser.add_argument("-s","--start", help="Start date when searching for transactions (ex: 12-Dec-2023)")
parser.add_argument("-e","--end", help="End date when searching for transactions (ex: 25-Dec-2023)")
parser.add_argument("-f","--env_file_name",default='.env', help ="[Default: .env]Name of file containing COOKIE, GAID, and INDID")
parser.add_argument("-o","--output_file_name",default='empower-transactions-details.csv')
parser.add_argument("--overwrite",action='store_true',help="Overwrite the output file if it exists")

args = parser.parse_args()


load_dotenv(args.env_file_name)

DTYPE_CONVERSIONS = {
    'effDate':str,
    'sdioId':str,
    'fundLegalName':str,
    'actySumAmt':float,
    'invPullBuyValue':float,
    'actySumUnits':float,
}

TRANSACTION_TYPE_ENDPOINT_MAP = {
    "C": "contributions",
    "D": "dividends",
    "F": "fees",
    "TI": "transfers",
}

def get_transactions(start_date:str,end_date:str):
    """ Start Date must be in form %d-%d-%Y (01-Jan-2020)"""

    return requests.get(f"https://participant.empower-retirement.com/participant-web-services/rest/transactionhistory/summary",
                        headers={"Cookie":getenv('COOKIE')},
                        params={
                            "gaId":getenv('GAID'),
                            "indId":getenv('INDID'),
                            "startDate":start_date,
                            "endDate":end_date
                                },
                                timeout=20)

def get_details(transaction_id:int,transaction_type:str,eff_date:str):
    return requests.get(f"https://participant.empower-retirement.com/participant-web-services/rest/transactionHistoryDetails/{transaction_type}",
                        headers={"Cookie":getenv('COOKIE')},
                        params={
                            'gaId':getenv('GAID'),
                            'indId':getenv('INDID'),
                            'eventId':transaction_id,
                            'effDate':eff_date,
                            "loadVestingSchedule":True
                        },
                        timeout=20)

def process_dividends(data:object):
    df = pd.DataFrame(data)
    df = df.loc[:,('effDate','sdioId','fundLegalName','actySumAmt','invPullBuyValue','actySumUnits','isisRefMeaning')]
    df = df.astype(DTYPE_CONVERSIONS)
    return df

def process_contributions(data:object):
    df_full=pd.DataFrame()
    for val in data:
        df = pd.DataFrame(val['contribDetlDTO'])
        df = df.loc[:,('cashEffDate','sdioId','fundLegalName','amount','shareValue','units')]
        df.columns = ['effDate','sdioId','fundLegalName','actySumAmt','invPullBuyValue','actySumUnits']
        df['effDate'] = val['cashEffDate']
        df['isisRefMeaning'] = 'Contribution'
        df_full = pd.concat([df_full,df])
    df_full['actySumAmt'] = df_full['actySumAmt'].apply(lambda x: x.replace('$','').replace(',',''))
    df_full['invPullBuyValue'] = df_full['invPullBuyValue'].apply(lambda x: x.replace('$','').replace(',',''))
    df_full = df_full.astype(DTYPE_CONVERSIONS)

    return df_full

def process_fees(data:object):
    df = pd.DataFrame(data)
    df = df.loc[:,('effDate','sdioId','legalName','amount','price','units')]
    df.columns = ['effDate','sdioId','fundLegalName','actySumAmt','invPullBuyValue','actySumUnits']
    df['isisRefMeaning'] = 'Fee'
    df = df.astype(DTYPE_CONVERSIONS)
    return df

def process_transfers(data:object):
    outflow = pd.DataFrame(data['transfersFrom']) 
    inflow = pd.DataFrame(data['transfersTo'])

    outflow = outflow.loc[:,('effDate','sdioId','fundLegalName','cumulativeAmt','accumUnitValue','units')]
    inflow = inflow.loc[:,('effDate','sdioId','fundLegalName','cumulativeAmt','accumUnitValue','units')]

    outflow.columns = ['effDate','sdioId','fundLegalName','actySumAmt','invPullBuyValue','actySumUnits']
    inflow.columns = ['effDate','sdioId','fundLegalName','actySumAmt','invPullBuyValue','actySumUnits']

    outflow['isisRefMeaning'] = 'Transfer'
    inflow['isisRefMeaning'] = 'Transfer'

    outflow['invPullBuyValue'] = outflow['invPullBuyValue'].apply(lambda x: x.replace('$','').replace(',',''))
    inflow['invPullBuyValue'] = inflow['invPullBuyValue'].apply(lambda x: x.replace('$','').replace(',',''))



    outflow = outflow.astype(DTYPE_CONVERSIONS)
    inflow = inflow.astype(DTYPE_CONVERSIONS)


    outflow['actySumAmt'] = outflow['actySumAmt'].apply(lambda x: -1*x)
    outflow['actySumUnits'] = outflow['actySumUnits'].apply(lambda x: -1*x)

    return pd.concat([outflow,inflow])

TRANSACTION_TYPE_CALLBACK_MAP = {
    "C": process_contributions,
    "D": process_dividends,
    "F": process_fees,
    "TI": process_transfers,
}

if __name__ == '__main__':
    print("Extracting transaction list...")
    transactions = get_transactions(args.start,args.end).json()
    df = pd.DataFrame()
    print((f"Extracting details for {len(transactions)} transactions from that time period..."))
    for transaction in tqdm(transactions):
        processing_func = TRANSACTION_TYPE_CALLBACK_MAP.get(transaction['category'])
        df = pd.concat([df,processing_func(get_details(transaction['eventId'],TRANSACTION_TYPE_ENDPOINT_MAP.get(transaction['category']),transaction['effdate']).json())])
    try:
        df.to_csv(args.output_file_name,sep=',',index=False,mode="x")
    except FileExistsError as e:
        print(args.overwrite)
        if args.overwrite:
            df.to_csv(args.output_file_name,sep=',',index=False,mode="w")
        elif input("Output file already exists. Overwrite? [y/N]")=="y":
            df.to_csv(args.output_file_name,sep=',',index=False,mode="w")
        else:
            print(Fore.RED + "The file you specified as an output already exists. \n Please specify another one or rename your existing file.")