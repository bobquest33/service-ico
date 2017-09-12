from locust import HttpLocust, TaskSet, task
import random
import uuid
import hashlib


class NewDepositUser(TaskSet):
    """
    This Taskset assume you have a company setup with the service activated. 
    It should also allow for unverfied users to make transactions
    Company name: load_test_1

    To run: locust -f /relative/path/to/file/locustfile.py --host=REHIVE_API_URL
    """

    def __init__(self, parent, *args, **kwargs):
        self.token = ''
        self.company_name = 'load_test_1'
        super(NewDepositUser, self).__init__(parent)

    # SIGNUP ONCE OFF FUNCTIONS
    def on_start(self):
        """ on_start is called when a Locust start before any task is scheduled """
        self.signup()
        self.set_ethereum_address()

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
            "deposit_amount": "10000",
            "deposit_currency": currency
        }
        response = self.client.post(
            "https://ico.s.services.rehive.io/api/user/icos/69/quotes/",
            headers=self.get_headers(),
            data=data
        )
        print(response.json())

    @task(4)
    def ethereum_index(self):
        """
        Task to get or generate a new public deposit address
        """
        response = self.client.get(
            "https://ethereum.s.services.rehive.io/api/1/user/",
            headers=self.get_headers()
        )

    @task(4)
    def bitcoin_index(self):
        """
        Task to get or generate a new public deposit address
        """
        response = self.client.post(
            "https://bitcoin.s.services.rehive.com/api/1/user/",
            headers=self.get_headers()
        )      

    def get_headers(self):
        return {
            'Authorization': "token " + self.token
        }


class WebsiteUser(HttpLocust):
    task_set = NewDepositUser
    min_wait = 6000
    max_wait = 10000
