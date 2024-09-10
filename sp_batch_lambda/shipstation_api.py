import datetime
import time
from decimal import Decimal
import json
import pprint
import requests
import base64
from models import *
from constants import *


class ShipStation(ShipStationBase):
    """
    Handles the details of connecting to and querying a ShipStation account.
    """

    def __init__(self, key=None, secret=None, debug=False):
        """
        Connecting to ShipStation required an account and a
        :return:
        """

        if key is None:
            raise AttributeError("Key must be supplied.")
        if secret is None:
            raise AttributeError("Secret must be supplied.")

        self.url = "https://ssapi.shipstation.com"

        self.key = key
        self.secret = secret
        self.orders = []
        self.timeout = 15.0
        self.debug = debug
        self.session = requests.Session()

        encoded_credentials = base64.b64encode(f'{self.key}:{self.secret}'.encode('utf-8')).decode('utf-8')
        header = {
            'Authorization': f'Basic {encoded_credentials}',
            'Content-Type': 'application/json'
        }

        self.session.headers.update(header)
        self.session.hooks["response"] = self.api_calls
    
    def api_calls(self, r, *args, **kwargs):
        calls_left = r.headers.get('X-Rate-Limit-Remaining')
        time_left = r.headers.get('X-Rate-Limit-Reset')
        if int(calls_left) <= 2:
            time.sleep(int(time_left))

    def add_order(self, order):
        self.require_type(order, ShipStationOrder)
        self.orders.append(order)

    def get_orders(self):
        return self.orders

    def submit_orders(self):
        for order in self.orders:
            self.post(endpoint="/orders/createorder", data=json.dumps(order.as_dict()))

    def get(self, endpoint="", payload=None):
        url = "{}{}".format(self.url, endpoint)
        r = self.session.get(
            url, auth=(self.key, self.secret), params=payload, timeout=self.timeout
        )
        if self.debug:
            pprint.PrettyPrinter(indent=4).pprint(r.json())

        return r

    def post(self, endpoint="", data=None):
        url = "{}{}".format(self.url, endpoint)
        headers = {"content-type": "application/json"}
        r = self.session.post(
            url,
            auth=(self.key, self.secret),
            data=data,
            headers=headers,
            timeout=self.timeout,
        )
        if self.debug:
            pprint.PrettyPrinter(indent=4).pprint(r.json())

        return r

    def put(self, endpoint="", data=None):
        url = "{}{}".format(self.url, endpoint)
        headers = {"content-type": "application/json"}
        r = self.session.put(
            url,
            auth=(self.key, self.secret),
            data=data,
            headers=headers,
            timeout=self.timeout,
        )
        if self.debug:
            pprint.PrettyPrinter(indent=4).pprint(r.json())

        return r

    def fetch_orders(self, parameters={}):
        """
            Query, fetch, and return existing orders from ShipStation

            Args:
                parameters (dict): Dict of filters to filter by.

            Raises:
                AttributeError: parameters not of type dict
                AttributeError: invalid key in parameters dict.

            Returns:
                A <Response [code]> object.

            Examples:
                >>> ss.fetch_orders(parameters={'order_status': 'shipped', 'page': '2'})
        """
        self.require_type(parameters, dict)
        invalid_keys = set(parameters.keys()).difference(ORDER_LIST_PARAMETERS)

        if invalid_keys:
            raise AttributeError(
                "Invalid order list parameters: {}".format(", ".join(invalid_keys))
            )

        valid_parameters = {
            self.to_camel_case(key): value for key, value in parameters.items()
        }

        return self.get(endpoint="/orders/list", payload=valid_parameters)

    def fetch_webhook(self, batch_id):
            '''
            Fetches orders based off of a webhook payload. 
            '''
            return self.get(endpoint=f"/orders?importBatch={batch_id}")
