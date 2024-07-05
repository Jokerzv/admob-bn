import sys
import datetime
import time
import threading
import pygame
from googleapiclient import discovery
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from plyer import notification
import os.path
import pickle

class AdMobAPI:
    def __init__(self, credentials_file):
        self.credentials_file = credentials_file
        self.creds = None

        # If the token file exists
        if os.path.exists('token.pickle'):
            with open('token.pickle', 'rb') as token:
                self.creds = pickle.load(token)

        # If there are none available (or they are invalid), start the authorization process
        if not self.creds or not self.creds.valid:
            if self.creds and self.creds.expired and self.creds.refresh_token:
                self.creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    self.credentials_file,
                    scopes=['https://www.googleapis.com/auth/admob.report']
                )
                self.creds = flow.run_local_server(port=0)
            
            # Save your credentials for later use.
            with open('token.pickle', 'wb') as token:
                pickle.dump(self.creds, token)

        self.admob = discovery.build('admob', 'v1', credentials=self.creds)
        print("Успешно создана учетная запись.")

    def report_to_list_of_dictionaries(self, response):
        result = []
        for report_line in response:
            if report_line.get('row'):
                row = report_line.get('row')
                dm = {}
                if row.get('dimensionValues'):
                    for key, value in row.get('dimensionValues').items():
                        if value.get('value') and value.get('displayLabel'):
                            dm.update({key: value.get('value')})
                            dm.update({key + '_NAME': value.get('displayLabel')})
                        else:
                            dm.update({key: next(filter(None, [value.get('value'), value.get('displayLabel')]))})
                if row.get('metricValues'):
                    for key, value in row.get('metricValues').items():
                        dm.update({key: next(filter(None, [value.get('value'), value.get('microsValue'), value.get('integerValue')]))})
                result.append(dm)
        return result

    def generate_report(self, publisher_id):
        now = datetime.datetime.now()
        current_month = now.month
        current_day = now.day
        date_range = {'startDate': {'year': 2024, 'month': current_month, 'day': current_day},
                      'endDate': {'year': 2024, 'month': current_month, 'day': current_day}}
        dimensions = ['DATE', 'APP', 'PLATFORM', 'COUNTRY']
        metrics = ['ESTIMATED_EARNINGS', 'IMPRESSIONS', 'CLICKS', 'AD_REQUESTS', 'MATCHED_REQUESTS']
        sort_conditions = {'dimension': 'DATE', 'order': 'DESCENDING'}
        report_spec = {'dateRange': date_range,
                       'dimensions': dimensions,
                       'metrics': metrics,
                       'sortConditions': [sort_conditions]}
        request = {'reportSpec': report_spec}
        try:
            response = self.admob.accounts().networkReport().generate(
                parent='accounts/{}'.format(publisher_id),
                body=request).execute()
            return response
        except Exception as e:
            print("Ошибка при генерации отчета:", e)
            sys.exit(1)

    def get_monthly_total_earnings(self, publisher_id):
        raw_report = self.generate_report(publisher_id)
        report_data = self.report_to_list_of_dictionaries(raw_report)
        total_earnings = 0.0
        for data in report_data:
            if data['DATE'].startswith('2024-06'):
                total_earnings += float(data['ESTIMATED_EARNINGS'])
        return total_earnings

# The path to your OAuth 2.0 JSON file
api = AdMobAPI('*****.json')

def send_desktop_notification(title, message):
    notification.notify(
        title=title,
        message=message,
        app_name='AdMob Balance Tracker',
        timeout=1,
        app_icon="./coin.ico"
    )

def play_sound():
    pygame.mixer.init()
    pygame.mixer.music.load("payment.wav")
    pygame.mixer.music.play()
    while pygame.mixer.music.get_busy():
        time.sleep(1)

def main():
    raw_report = api.generate_report('pub-************') #  Here your ID publish google account
    report_as_list_of_dictionaries = api.report_to_list_of_dictionaries(raw_report)
    total_earnings_today = sum(float(item['ESTIMATED_EARNINGS']) for item in report_as_list_of_dictionaries)
    rounded_earnings = round(total_earnings_today / 1000000, 2)
    formatted_earnings = '{:,.2f}'.format(rounded_earnings)

    with open('earnings_history.txt', 'r') as file:
        history = file.readlines()

    last_saved_earning_2 = history[-1].strip()
    p = '{:,.2f}'.format(float(formatted_earnings) - float(last_saved_earning_2))
    formatted_earnings_text = "+" + str(p) + "$"

    send_desktop_notification("AdMob", formatted_earnings_text)
    
    sound_thread = threading.Thread(target=play_sound)
    sound_thread.start()

    with open('earnings_history.txt', 'a') as file:
        file.write(formatted_earnings + '\n')

    print("Total earnings for this month:", formatted_earnings)

if __name__ == "__main__":
    main()
