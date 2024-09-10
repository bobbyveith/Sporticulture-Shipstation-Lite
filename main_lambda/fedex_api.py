import json
import requests
from unicodedata import normalize
from datetime import datetime
import boto3
from botocore.exceptions import ClientError



def create_fedex_session():
    session = requests.Session()
    access_token = get_access_token(session)

    if access_token:

        header = {
            'x-customer-transaction-id' : '123456123456',
            'content-type': "application/json",
            'x-locale': "en_US",
            'authorization': f"Bearer {access_token}"
            }

        session.headers.update(header)
        return session

    else:
        print(f"[X] Failed to get Fedex Access Token")
        return None



def get_secret(secret_name):
    """
    Retrieve the API key and secret from AWS Secrets Manager.

    Parameters:
    secret_name (str): The name of the secret in AWS Secrets Manager.

    Returns:
    tuple: A tuple containing the api_key and api_secret as strings.
    """
    # Create a Secrets Manager client
    client = boto3.client('secretsmanager')

    try:
        # Get the secret value from Secrets Manager
        get_secret_value_response = client.get_secret_value(SecretId=secret_name)

        # Parse the secret JSON string and extract the keys
        secret_dict = json.loads(get_secret_value_response['SecretString'])
        api_key = secret_dict['api_key']
        api_secret = secret_dict['api_secret']

        return api_key, api_secret

    except ClientError as e:
        # Handle the error accordingly
        raise e
    


def get_api_keys():

    #load_dotenv()

    #prod keys
    client_id, client_secret = get_secret('fedexAPICredentials')

    return client_id, client_secret


def get_access_token(session):
    """
    Retrieve the access token from the FedEx OAuth2.0 API.

    This function sends a POST request to the FedEx OAuth2.0 token endpoint
    to obtain an access token using client credentials flow.

    Returns:
    - str or None: The access token if retrieved successfully, else None.

    Raises:
    - requests.HTTPError: If the request to the FedEx API fails.
    - Exception: If any other error occurs during the request.

    Note:
    The function uses the client ID and client secret obtained from the
    `get_api_keys` function to authenticate the request.
    """
    # API token URL sandbox
    #url = "https://apis-sandbox.fedex.com/oauth/token"

    #API oauth2.0 url production
    url = 'https://apis.fedex.com/oauth/token'

    client_id , client_secret = get_api_keys()

    # Set the payload
    payload = f'grant_type=client_credentials&client_id={client_id}&client_secret={client_secret}'
    

    headers = {
        'Content-Type': "application/x-www-form-urlencoded"
        }
    try:
        response = session.post(url, data=payload, headers=headers, timeout=10)
        response.raise_for_status() # raises error if not 200 status

        access_token = response.json()["access_token"]
        print("[+] Fedex 0Auth token request successful!")
    
    except Exception as e:
        print("[X] Could not retrieve fedex access_token")
        print(f"Error: {e}")
        access_token = None


    return access_token



def set_payload(order):
    """
    Set the payload for a FedEx shipment request based on order details.

    This function reads a JSON file containing a FedEx shipment request payload template.
    It updates specific fields in the payload based on the provided `orderObject` and
    returns the updated payload.

    Args:
    - orderObject: An object containing order details such as shipping information.

    Returns:
    - dict: The updated FedEx shipment request payload.

    Notes:
    The function reads the JSON file specified by `json_file` and modifies specific fields
    in the payload template based on the provided `orderObject`. It updates recipient address
    details, shipment date, package weight, and package dimensions.
    """
    #location of fedex json payload template
    json_file = 'main_lambda/fedex.json'

    with open(json_file, 'r') as file:
        payload = json.load(file)

        payload["requestedShipment"]["shipper"]["address"]["postalCode"] = order.Shipment.warehouse.postal_code
        payload["requestedShipment"]["shipper"]["address"]["stateOrProvinceCode"] = order.Shipment.warehouse.state
        payload["requestedShipment"]["shipper"]["address"]["countryCode"] = order.Shipment.warehouse.country

        payload["requestedShipment"]["recipient"]["address"]["postalCode"] =  order.Customer.ship_to.postal_code[:5]
        payload["requestedShipment"]["recipient"]["address"]["stateOrProvinceCode"] =  order.Customer.ship_to.state
        payload["requestedShipment"]["recipient"]["address"]["countryCode"] = order.Customer.ship_to.country
        
        payload["requestedShipment"]["shipDateStamp"] = order.Shipment.ship_date  #YYYY-MM-DD
        payload["requestedShipment"]["requestedPackageLineItems"][0]["weight"]["value"] = float(order.Shipment.weight['value'] / 16) #convert ounce to pounds

    return payload



def get_fedex_response(order):
    """
    Retrieve FedEx shipping rates for an order from the FedEx API.

    This function sends a POST request to the FedEx rate quotes endpoint
    to obtain shipping rate information based on the provided `order_object`
    and `access_token`.

    Args:
    - order_object: An object containing details of the order to be shipped.
    - access_token (str): An access token obtained from the FedEx OAuth2.0 API.

    Returns:
    - dict or None: A dictionary containing shipping rate information if
    retrieved successfully, else None.

    Raises:
    - requests.HTTPError: If the request to the FedEx API fails.
    - Exception: If any other error occurs during the request.

    Notes:
    The function uses the access token provided to authenticate the request.
    It sends a POST request with the order details in JSON format and
    retrieves the shipping rate information in JSON format.
    """

    #sandbox URL
    #url = "https://apis-sandbox.fedex.com/rate/v1/rates/quotes"

    #production URL
    url = "https://apis.fedex.com/rate/v1/rates/quotes"

    # Initiate payload
    payload = json.dumps(set_payload(order))
    #payload = json.dumps(temp_payload())

    try:
        response = order.fedex_session.post(url, data=payload, timeout=10)

        response.raise_for_status()
        response_json = response.json()

    except Exception as e:
        print("[X] Could not retrieve fedex response")
        print(f"Error: {e}")
        response_json = None

    return response_json





def update_prices(order, shipping_options: dict):
    """
    Updates the prices in the shipping options based on the rates from Shipstation.

    Parameters:
    - order: The order object containing rate information.
    - shipping_options (dict): A dictionary representing shipping options, where each option is a dictionary
    with keys 'service_name', 'delivery_date', and 'price'.

    Returns:
    - dict: An updated dictionary of shipping options with updated prices based on Shipstation rates.

    This function first converts Shipstation rates to a dictionary format for easy lookup.
    It then iterates through each shipping option, finds the corresponding rate in the Shipstation rates dict,
    and updates the price in the shipping options with the new rate.
    """

    # Get Shipstation Rates --> convert to dict  --> clean unwanted symbols
    ss_rates_dict = {
        normalize('NFKD', key).encode('ascii', 'ignore').decode('utf-8').replace(".", ""): value
        for key, value in order.rates['fedex']
    }
    # print(f"SS_Rates simple --> {ss_rates_dict}\n")

    # print(f"Shipping options --> {shipping_options}\n")

    # Update prices in shipping_options with prices from ss_rates_dict
    options_after_price_update = []
    for option in shipping_options:

        service_name = normalize('NFKD', option['service_name']).encode('ascii', 'ignore').decode('utf-8') #gets rid of special characters in names
        if service_name in ss_rates_dict:
            option['price'] = ss_rates_dict[service_name]
            options_after_price_update.append(option)

    return options_after_price_update




def get_delivery_dates(order):
    """
    Retrieve delivery dates and shipping rates for an order from the FedEx API.

    This function obtains an access token from the FedEx API using the
    `get_access_token` function, then retrieves shipping rate information
    from the FedEx API using the `get_fedex_response` function based on
    the provided `order_object`. It processes the response data to extract
    shipping options, including service type, delivery date, and price.

    Args:
    - order_object: An object containing details of the order to be shipped.

    Returns:
    - list of dict: A list of dictionaries representing optional shipping services.
    Each dictionary contains keys 'service_type', 'delivery_date', and 'price'.

    Notes:
    The function utilizes the `get_access_token` and `get_fedex_response` functions
    to authenticate with the FedEx API and retrieve shipping rate information.
    It processes the response JSON to extract shipping options and returns them
    as a list of dictionaries.
    """
    response_json = get_fedex_response(order)

    # List of dictionaries representing the shipping options
    raw_shipping_options = response_json["output"]["rateReplyDetails"]
    clean_shipping_options = []

    for shipping_service in raw_shipping_options:
        # Create object to store data for shipping option
        shipping_option = {}
        
        # Determine the service name based on conditions
        if shipping_service["serviceName"] == 'FedEx SmartPost®':
            if order.Shipment.weight['value'] < 16:
                shipping_option["service_name"] = 'FedEx SmartPost parcel select lightweight'
            else:
                shipping_option["service_name"] = 'FedEx SmartPost parcel select'
        # Adjusts service names between Fedex API ('Fedex Ground') and Shipstation API ('FedEx Home Delivery') based on the order's residential status
        elif order.Customer.ship_to.residential and shipping_service["serviceName"] == "FedEx Ground®":
            shipping_option["service_name"] = "FedEx Home Delivery®"
        elif not order.Customer.ship_to.residential and shipping_service["serviceName"] == "FedEx Home Delivery®":
            shipping_option["service_name"] = "FedEx Ground®"
        else:
            shipping_option["service_name"] = shipping_service["serviceName"]

        # Add common data for all service names
        shipping_option["delivery_date"] = shipping_service["commit"]["dateDetail"]["dayFormat"]
        shipping_option["price"] = shipping_service["ratedShipmentDetails"][0]["totalNetFedExCharge"]

        # If single stream, remove SmartPost options
        if "SmartPost" in shipping_option["service_name"] and order.is_single_stream:
            continue
        
        clean_shipping_options.append(shipping_option)


    #------used for testing---------------
    #write_fedex_response_to_file(response_json)

    # --- end used for testing ----------


    #update dict with real ShipStation prices
    final_shipping_options = update_prices(order, clean_shipping_options)


    return final_shipping_options   #list of dictionaries showing optional shipping services


def get_smart_post_delivery_date(shipping_options):
    """
    Saves Smart Post Delivery Date to order object. Info will be uploaded to Shipstation front end later.
    """
    for option in shipping_options:
        if option['service_name'] == 'FedEx SmartPost parcel select' or option['service_name'] == 'FedEx SmartPost parcel select lightweight':
            smart_post_delivery_date = option['delivery_date'][:10]
        else:
            smart_post_delivery_date = "None Provided"

    smart_post_message = f"SmartPost D-Date: {smart_post_delivery_date}"
    return smart_post_message




def filter_valid_shipping_options(order, shipping_options):
    """
    Filters shipping options to include only those that will arrive on or before the latest delivery date, 
    and updates the delivery date value to a datetime object.

    Args:
        order (object): An object representing the order, which must include:
                        - `deliver_by_date` (datetime): The latest delivery date for the order.
        shipping_options (list): A list of dictionaries representing the shipping options, where each dictionary 
                                must include a 'delivery_date' key with a value in the format "%Y-%m-%dT%H:%M:%S".

    Returns:
        list: A list of dictionaries containing the valid shipping options, with the 'delivery_date' values 
            converted to datetime objects.
    """
    valid_shipping_options = []
    for option in shipping_options:
        delivery_date = datetime.strptime(option['delivery_date'], "%Y-%m-%dT%H:%M:%S")
        deliver_by_date = datetime.strptime(order.deliver_by_date, "%m/%d/%Y %H:%M:%S")

        if delivery_date <= deliver_by_date:
            # Update value with the datetime object instead of str
            option['delivery_date'] = delivery_date
            valid_shipping_options.append(option)
        else:
            continue
    return valid_shipping_options





def get_fedex_best_rate(order):
    """
    Get the best FedEx shipping rate based on the latest delivery date.

    This function retrieves all available shipping options for the provided
    `order_object` using the `get_delivery_dates` function. It then filters
    out shipping options with delivery dates beyond the specified `latest_deliver_date`.
    Finally, it returns the shipping option with the lowest price among the filtered options.

    Args:
    - order_object: An object containing details of the order to be shipped.
    - latest_deliver_date (str): The latest acceptable delivery date in 'YYYY-MM-DDTHH:MM:SS' format.

    Returns:
    - dict: A dictionary representing the best shipping option with keys 'service_type', 'delivery_date', and 'price'.

    Notes:
    The function uses the `get_delivery_dates` function to retrieve shipping options
    and filters them based on the `latest_deliver_date`. It then selects the shipping
    option with the lowest price among the filtered options and returns it.
    """

    # Ensure that fedex is applicable for this order
    rate_is_applicable = order.rates.get("fedex", False)
    if not rate_is_applicable:
        return None
    
    # Get all shipping options
    shipping_options =  get_delivery_dates(order)

    # Writing Smartpost Delivery date to object to be updated onto a field in Shipstation Front End
    smart_post_message = get_smart_post_delivery_date(shipping_options)
    order.Shipment.smart_post_date = smart_post_message

    # List of options that will arrive on time
    valid_shipping_options = filter_valid_shipping_options(order, shipping_options)

    print(f"valid_shipping_options = {valid_shipping_options}")

    # Find the best shipping option based on buisness logic
    if valid_shipping_options:
        sorted_options = sorted(valid_shipping_options, key=lambda x: x['price'])

        if order.is_single_stream:
            if sorted_options[0]['service_name'].includes("SmartPost"):
                best_option = sorted_options[1]
            else:
                best_option = sorted_options[0]
        else:
            best_option = sorted_options[0]
        
        # # Desired business logic. Willing to ship up to $0.35 more expensive if package arrives earlier than the cheapest shipping rate
        # better_options = [option for option in sorted_options if option['price'] - sorted_options[0]['price'] < 0.35 and option['delivery_date'] < sorted_options[0]['delivery_date']]
        
        # best_option = min(better_options, key=lambda x: x['delivery_date']) if better_options else sorted_options[0]
        
        best_option = sorted_options[0]
        best_option_dict = {
            "carrierCode": "fedex",
            "serviceCode": best_option["service_name"],
            "price": best_option["price"] 
        }

        return best_option_dict # Example: { "carrierCode": "fedex", "service_code: 'FedEx Ground®', "price": 8.75}
    else:
        return None

    

if __name__ == '__main__':

    order_object = None

    # access = get_access_token()
    # print(access)
    #delivery_dates = get_delivery_dates(order_object)

    print("\n")
    latest_deliver_date = '2024-03-06T18:00:00'

    possible_options = get_fedex_best_rate(2, latest_deliver_date)

    print("final output -- \n")
    print(possible_options)
