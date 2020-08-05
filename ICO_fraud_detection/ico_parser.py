"""Module for processing data from ICOs."""

import pandas as pd
from datetime import datetime, timedelta
import pytz


class ICOParser:
    def __init__(self, path_to_csv, ico_start_date=None, fraud_flag=None):
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
        df['block_timestamp'] = pd.to_datetime(df.block_timestamp)
        df.set_index('block_timestamp', inplace=True)
        df['transactions'] = 1

        self.fraud_flag = fraud_flag
        self.df = df.copy()
        self.df_resample_day = df.resample('D').sum()
        self.df_resample_hour = df.resample('H').sum()
        self.ico_start_date = datetime.strptime(ico_start_date, '%d/%m/%Y').replace(tzinfo=pytz.UTC)
        self.ico_end_date = None
    
    def define_ico_start_date(self):
        change_series = self.df_resample_day['transactions'].pct_change()
        if self.ico_start_date:
                self.ico_end_date = self.ico_start_date + timedelta(days=60)
        else:    
            for index, value in change_series.iteritems():

                if value > 50:

                    if index - timedelta(days=5) in change_series.index:
                        self.ico_start_date = index - timedelta(days=5)
                        self.ico_end_date = self.ico_start_date + timedelta(days=60)
                    else:
                        self.ico_start_date = change_series.index.min()
                        self.ico_end_date = self.ico_start_date + timedelta(days=60)
                    print(self.ico_start_date)
                    break

    def filter_df_for_training_days(self):
        if self.ico_start_date:
            return self.df_resample_day.loc[
                (self.df_resample_day.index >= self.ico_start_date )&(
                 self.df_resample_day.index < self.ico_end_date )]
        else:
            print('First define ICO start date.')
    
    def filter_df_for_training_hours(self):
        if self.ico_start_date:
            return self.df_resample_hour.loc[
                (self.df_resample_hour.index >= self.ico_start_date)&(
                 self.df_resample_hour.index < self.ico_end_date)] 
        else:
            print('First define ICO start date.')