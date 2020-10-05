"""Module for processing data from ICOs."""

import pandas as pd
from datetime import datetime, timedelta
from exchange_adresses import ADRESS_LIST
import pytz
import requests
import json
import time


def _sum_dict_values(d1, d2, lambda_sum=lambda x, y: x + y):
    """Sum que values of correspondent key of two dictionaries."""
    res = d1.copy()
    for key, val in d2.items():
        try:
            res[key] = lambda_sum(res[key], val)
        except KeyError:
            res[key] = val
    return res


def _check_if_holder(
    contract_adress,
    list_exchance=ADRESS_LIST,
    api_key='NYBDRYT4RGH7I7PGTBKYVBVVZMQ15B4B34',
):
    """"""
    if contract_adress in list_exchance:
        return False
    payload = {
        'module': 'proxy',
        'action': 'eth_getCode',
        'address': contract_adress,
        'tag': 'latest',
        'apikey': api_key,
    }
    request = requests.get('https://api.etherscan.io/api', params=payload)
    result = request.json().get('result')
    time.sleep(1)
    if not result or result == '0x':
        return True
    elif len(result) != '0x':
        return False


def _get_biggest_holder(dict_cumsum_percentage):
    list_sorted_days = sorted(dict_cumsum_percentage.keys())
    dict_percentage_holders = {}
    for day in list_sorted_days:
        # print(day)
        dict_current_day = dict_cumsum_percentage.get(day)
        # print(dict_current_day)
        if len(dict_current_day) == 0:
            dict_percentage_holders[day] = 0
        else:
            found_holder = False
            while not found_holder:
                if len(dict_current_day) == 0:
                    dict_percentage_holders[day] = [None, 0]
                    break
                else:
                    max_key = max(dict_current_day, key=dict_current_day.get)
                    if _check_if_holder(max_key):
                        # print(max_key)
                        found_holder = True
                        # print(max_key, dict_current_day.get(max_key))
                        dict_percentage_holders[day] = [
                            max_key,
                            dict_current_day.get(max_key),
                        ]
                    else:
                        # print(f'Deleting: {max_key}')
                        del dict_current_day[max_key]
    return dict_percentage_holders


def _filter_df_for_training_days(df, date_col, ico_start_date, ico_end_date):
    if ico_start_date:
        return df.loc[
            (df[date_col] >= ico_start_date) & (df[date_col] < ico_end_date)
        ]
    else:
        print('First define ICO start date.')


def _set_dataframe_max_date(df, date_col, max_date):
    df_max_date = df.copy()
    df_max_date[date_col] = pd.to_datetime(df_max_date[date_col]).dt.date
    return df_max_date[df_max_date[date_col] < max_date]


class ICOParser:
    def __init__(
        self,
        path_to_csv,
        date_column='BLOCK_TIMESTAMP',
        value_column='VALUE',
        ico_start_date=None,
        dateformat='%Y-%m-%d',
        fraud_flag=None,
        len_time_series=60,
    ):
        """Class for parsing data coming from ICO.

        Args:
            path_to_csv (str):
            ico_start_date (str, default=None):
            fraud_flag (int, default=None):

        Attributes:
            fraud_flag (int):
            df (pd.DataFrame):
            df_resample_day (pd.DataFrame):
            df_resample_hour (pd.DataFrame):
            ico_start_date (datetime.date):
            ico_end_date (datetime.date):
        """
        df = pd.read_csv(path_to_csv)
        df.sort_values(by=date_column, inplace=True)
        df['transactions'] = 1
        df_for_resample = df  # .copy()
        df[date_column] = pd.to_datetime(df[date_column]).dt.date
        df_for_resample[date_column] = pd.to_datetime(
            df_for_resample[date_column]
        )
        # df.set_index(date_column, inplace=True)

        self.len_time_series = len_time_series
        self.fraud_flag = fraud_flag
        self.df = df.copy()
        self.date_column = date_column
        self.value_column = value_column
        self.df_resample_day = df_for_resample.resample(
            'D', on=date_column
        ).sum()
        self.ico_start_date = (
            datetime.strptime(ico_start_date, dateformat)
            .replace(tzinfo=pytz.UTC)
            .date()
        )
        self.ico_end_date = None
        self.df_newbiers = None
        self.df_newbiers_resample = None
        self.dict_balance = None
        self.dict_cumsum_balance = None
        self.dict_percentage_holders = None
        self.dict_daily_new_holders = None
        self.dict_perc_biggest_holder = None
        self.dict_newbiers_ratio = None
        self.array_daily_transactions = None
        self.array_perc_new_holders = None
        self.array_biggest_holder = None
        self.array_newbiers = None
        self.array_gas_ratio = None

        ## To do:
        self.df_newbiers_resample_day = None

    def define_ico_start_date(self):
        change_series = self.df_resample_day['transactions'].pct_change()
        if self.ico_start_date:
            self.ico_end_date = self.ico_start_date + timedelta(days=60)
        else:
            for index, value in change_series.iteritems():

                if value > 50:

                    if index - timedelta(days=5) in change_series.index:
                        self.ico_start_date = index - timedelta(days=5)
                        self.ico_end_date = self.ico_start_date + timedelta(
                            days=self.len_time_series
                        )
                    else:
                        self.ico_start_date = change_series.index.min()
                        self.ico_end_date = self.ico_start_date + timedelta(
                            days=self.len_time_series
                        )
                    print(self.ico_start_date)
                    break

    def filter_df_for_training_days(self, df):
        if self.ico_start_date:
            return self.df_resample_day.loc[
                (self.df_resample_day.index >= self.ico_start_date)
                & (self.df_resample_day.index < self.ico_end_date)
            ]
        else:
            print('First define ICO start date.')

    def get_newbiers_dataframe(self):
        df_nonce_01 = self.df[self.df.NONCE.isin([1, 0])]
        list_newbiers = list(df_nonce_01.FROM_ADDRESS_BLOCKCHAIN.unique())
        self.df_newbiers = self.df[
            self.df.FROM_ADDRESS_BLOCKCHAIN.isin(list_newbiers)
        ]
        self.df_newbiers_resample = self.df_newbiers.resample(
            'D', on=self.date_column
        ).sum()

    def get_array_daily_transactions(self):
        df_resample_func = self.df_resample_day.reset_index()
        df_resample_func['BLOCK_TIMESTAMP'] = df_resample_func[
            'BLOCK_TIMESTAMP'
        ].dt.date
        self.array_daily_transactions = df_resample_func.loc[
            (df_resample_func[self.date_column] >= self.ico_start_date)
            & (df_resample_func[self.date_column] < self.ico_end_date)
        ].transactions.values

    def get_balance(self):
        """Process dataframe to extract daily balance for each individual."""
        # Define start date and days of activity
        value_column = self.value_column
        dataframe = _set_dataframe_max_date(
            self.df, self.date_column, self.ico_end_date
        )

        dataframe.set_index(self.date_column, inplace=True)
        dataframe[value_column] = dataframe[value_column].astype(float)
        start_date = dataframe.index.min()
        print(start_date)
        days_activity = (dataframe.index.max() - start_date).days
        print(days_activity)
        dict_balance = {}
        for delta in range(days_activity):
            current_date = dataframe.index.min() + timedelta(delta)
            df_current_date = dataframe.loc[dataframe.index == current_date]
            dict_user_balance = {}
            for user in set(
                list(df_current_date.FROM_ADDRESS.unique())
                + list(df_current_date.TO_ADDRESS.unique())
            ):
                to_adress_value = df_current_date.loc[
                    df_current_date.TO_ADDRESS == user
                ].VALUE.sum()
                from_adress_value = df_current_date.loc[
                    df_current_date.FROM_ADDRESS == user
                ].VALUE.sum()
                dict_user_balance[user] = to_adress_value - from_adress_value
            dict_user_balance_sorted = {
                k: v
                for k, v in sorted(
                    dict_user_balance.items(), key=lambda item: item[1]
                )
            }

            dict_balance[str(current_date)] = dict_user_balance_sorted

        self.dict_balance = dict_balance

    def get_cumsum_balance(self):
        dict_balance = self.dict_balance.copy()
        dict_cumsum_balance = {}
        list_sorted_days = sorted(dict_balance.keys())

        for index, day in enumerate(list_sorted_days):
            if index - 1 < 0:
                dict_cumsum_balance[day] = dict_balance.get(day)
            else:
                dict_current_cumsum = _sum_dict_values(
                    dict_cumsum_balance.get(list_sorted_days[index - 1]),
                    dict_balance.get(day),
                )
                dict_cumsum_balance[day] = dict_current_cumsum
        self.dict_cumsum_balance = dict_cumsum_balance

    def get_cumsum_daily_percentage(self):
        dict_cumsum_balance = self.dict_cumsum_balance.copy()
        list_sorted_days = sorted(dict_cumsum_balance.keys())
        dict_percentage_holders = {}
        for day in list_sorted_days:
            total_value = sum(
                [
                    val
                    for val in list(dict_cumsum_balance.get(day).values())
                    if val > 0
                ]
            )
            dict_current_day = dict_cumsum_balance.get(day)
            dict_daily_percentage = {}
            for user in dict_current_day.keys():
                if dict_current_day.get(user) > 0:
                    dict_daily_percentage[user] = (
                        dict_current_day.get(user) / total_value
                    )
            dict_percentage_holders[day] = dict_daily_percentage
        self.dict_percentage_holders = dict_percentage_holders

    def get_biggest_holder_dict(self):
        self.dict_perc_biggest_holder = _get_biggest_holder(
            self.dict_percentage_holders
        )

    def get_biggest_holder_array(self):
        self.array_biggest_holder = [
            value[1] for key, value in self.dict_perc_biggest_holder.items()
        ][-self.len_time_series :]

    def get_newbiers_ratio_dict(self):
        df_ratio = self.df_newbiers_resample / self.df_resample_day
        df_ratio.index = df_ratio.index.astype(str)
        df_ratio.fillna(0, inplace=True)
        self.dict_newbiers_ratio = df_ratio.transactions.to_dict()

    def get_newbiers_array(self):
        self.array_newbiers_ratio = list(self.dict_newbiers_ratio.values())[
            -self.len_time_series :
        ]

    def get_gas_ratio_array(self):
        if not self.df_newbiers_resample.empty:
            self.df_newbiers_resample['GAS_RATIO'] = (
                self.df_newbiers_resample['RECEIPT_GAS_USED']
                / self.df_newbiers_resample['GAS']
            )
            self.df_newbiers_resample.fillna(0, inplace=True)
            self.array_gas_ratio = (
                self.df_newbiers_resample.GAS_RATIO.to_list()
            )[-self.len_time_series :]

        else:
            print(
                'self.df_newbiers_resample does not exist.\nPlease run self.get_newbiers_dataframe().'
            )

    def get_daily_number_of_new_holder(self, max_date=None):
        """
        Alterar lógica para extrair dados da tabela ao invés do
        dict_cumsum_balance
        """
        dict_cumsum = self.dict_cumsum_balance.copy()
        dict_result = {}
        list_sorted_days = sorted(dict_cumsum.keys())
        if not max_date:
            max_users = len(dict_cumsum.get(max(list_sorted_days)))
        else:
            max_users = len(dict_cumsum.get(max_date))

        for day in list_sorted_days:
            total_users = len(dict_cumsum.get(day))
            dict_result[day] = {
                'total_users': total_users,
                'percentage': total_users / max_users,
            }
        self.dict_daily_new_holders = dict_result

    def get_array_perc_new_holders(self):
        self.array_perc_new_holders = [
            value.get('percentage')
            for key, value in self.dict_daily_new_holders.items()
        ][-self.len_time_series :]

    def pipeline(self):
        print('Running method: define_ico_start_date ... ')
        self.define_ico_start_date()
        print('Running method: get_newbiers_dataframe ... ')
        self.get_newbiers_dataframe()
        print('Running method: get_balance ... ')
        self.get_balance()
        print('Running method: get_cumsum_balance ... ')
        self.get_cumsum_balance()
        print('Running method: get_cumsum_daily_percentage ... ')
        self.get_cumsum_daily_percentage()
        print('Running method: get_daily_number_of_new_holder ... ')
        self.get_daily_number_of_new_holder()
        print('Running method: get_array_daily_transactions ... ')
        self.get_array_daily_transactions()
        print('Running method: get_array_perc_new_holders ... ')
        self.get_array_perc_new_holders()
        print('Running method: get_biggest_holder_dict ... ')
        self.get_biggest_holder_dict()
        print('Running method: get_biggest_holder_array ... ')
        self.get_biggest_holder_array()
        print('Running method: get_newbiers_ratio_dict ... ')
        self.get_newbiers_ratio_dict()
        print('Running method: get_newbiers_array ... ')
        self.get_newbiers_array()
        print('Running method: get_gas_ratio_array ... ')
        self.get_gas_ratio_array()


def dataset_creator(list_csv_file,):
    pass
