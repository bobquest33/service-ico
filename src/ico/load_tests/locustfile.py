from locust import HttpLocust, TaskSet, task
import random
import uuid
import hashlib
import gevent
import time
import os


class NewDefaultICOUser(TaskSet):
    """
    This Taskset assume you have a company setup with the service activated.
    It should also allow for unverfied users to make transactions

    Locust version: pip install locustio==0.8a2

    To run: locust -f /relative/path/to/file/locustfile.py --host=REHIVE_API_URL
    Using invoke: inv.run-load-test HOST COMPANY_ID ICO_ID
    """

    def __init__(self, parent, *args, **kwargs):
        self.token = ''
        self.company_name = os.environ.get("ICO_COMPANY_ID")
        self.ico_id = os.environ.get("ICO_ID")
        self.ethereum_service_url = os.environ.get("ETHEREUM_SERVICE_API")
        self.bitcoin_service_url = os.environ.get("BITCOIN_SERVICE_API")
        self.ico_service_url = os.environ.get("SERVICE_API")
        super(NewDefaultICOUser, self).__init__(parent)

    # SIGNUP ONCE OFF FUNCTIONS
    def on_start(self):
        """ on_start is called when a Locust start before any task is scheduled """
        self.signup()

    def signup(self):
        """
        Generates a unique email address and signs the user up
        """
        unique_hex = hashlib.sha256(bytes(str(uuid.uuid4()), encoding='utf-8')).hexdigest()
        signup_json = {
            "first_name": "Zergling",
            "last_name": "McZergles",
            "email": "zerg+" + str(unique_hex) + '@rehive.com',
            "company": self.company_name,
            "password1": "1234qwer",
            "password2": "1234qwer",
        }
        response = self.client.post("auth/register/", signup_json)
        json = response.json()
        self.token = json['data']['token']

    def set_ethereum_address(self):
        data = {
            "address": "1234567",
        }
        response = self.client.post(
            "user/bitcoin-accounts/",
            headers=self.get_headers(),
            data=data
        )

    # TASKS
    @task(8)
    def index(self):
        """
        Simple basline task to get user from Rehive
        """
        response = self.client.get("user/", headers=self.get_headers())

    @task(1)
    def get_ico_quote(self):
        """
        Task for hitting the quote endpoint. Randomly chooses XBT or ETH
        The deposit amount should be fine for either
        """
        random_num = random.randint(0, 1)
        random_deposit = random.randint(10000, 1000000)
        currency = "XBT"
        if (random_num == 0):
            currency = "ETH"
        data = {
            "deposit_amount": random_deposit,
            "deposit_currency": currency
        }
        response = self.client.post(
            self.ico_service_url + "user/icos/" + self.ico_id + "/quotes/",
            headers=self.get_headers(),
            data=data
        )
        if response.ok:
            json = response.json()
            print(json)
            gevent.spawn(self._async_quote_polling, json['data']['id'])

    @task(4)
    def ethereum_index(self):
        """
        Task to get or generate a new public deposit address
        """
        response = self.client.get(
            self.ethereum_service_url + "user/",
            headers=self.get_headers()
        )

    @task(4)
    def bitcoin_index(self):
        """
        Task to get or generate a new public deposit address
        """
        response = self.client.post(
            self.bitcoin_service_url + "user/",
            headers=self.get_headers()
        )

    @task(2)
    def get_transactions(self):
        response = self.client.get(
            "transactions/?page=1&page_size=26&orderby=-created",
            headers=self.get_headers()
        )

    def _async_quote_polling(self, quote_id):
        # using `with` prevents locust from making an entry in its report
        url = self.ico_service_url + 'user/icos/' + str(self.ico_id) + '/purchases/?quote__id=' + str(quote_id)
        # Now poll for an ACTIVE status
        timeout = 10 * 60
        end_time = time.time() + timeout
        while time.time() < end_time:
            r = self.client.get(
                url,
                headers=self.get_headers()
            )
            gevent.sleep(10)  # Poll every 10 seconds

    def get_headers(self):
        return {
            'Authorization': "token " + self.token
        }


class WebsiteUser(HttpLocust):
    task_set = NewDefaultICOUser
    min_wait = 6000
    max_wait = 10000
