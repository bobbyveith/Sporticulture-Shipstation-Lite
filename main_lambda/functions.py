import json, os, time, pyfiglet, requests
from shipstation_local.api import *
from classes import Order
from pytz import timezone
import re
import boto3
from botocore.exceptions import ClientError
import json
import datetime


__author__ = "Bobby Veith"
__company__ = "Sporticulture"


def print_banner():
    """
        Print the banner for the ShipStation Automation script.

        Args:
            None
        Return:
            None
    """
    banner = "ShipStation Automation"
    ascii_banner = pyfiglet.figlet_format(banner)
    print(ascii_banner)

def print_green(text):
    """
    Prints the given text in green color.

    Parameters:
    - text (str): The text to be printed.

    Returns:
    - None
    """
    # ANSI escape code for green color
    green_color_code = '\033[92m'
    
    # ANSI escape code to reset color back to default
    reset_color_code = '\033[0m'
    
    # Print the text in green color
    print(f"{green_color_code}{text}{reset_color_code}")

def print_red(text):
    """
    Prints the given text in red color.

    Parameters:
    - text (str): The text to be printed.

    Returns:
    - None
    """
    # ANSI escape code for red color
    red_color_code = '\033[91m'
    
    # ANSI escape code to reset color back to default
    reset_color_code = '\033[0m'
    
    # Print the text in red color
    print(f"{red_color_code}{text}{reset_color_code}")

def print_yellow(text):
    """
    Prints the given text in yellow color.

    Parameters:
    - text (str): The text to be printed.

    Returns:
    - None
    """
    # ANSI escape code for yellow color
    yellow_color_code = '\033[93m'
    
    # ANSI escape code to reset color back to default
    reset_color_code = '\033[0m'
    
    # Print the text in yellow color
    print(f"{yellow_color_code}{text}{reset_color_code}")




def load_order():
    file_path = '/Users/bobbyveith/Downloads/Sporticulture-SS-Automation/events/main_lambda_event.json'
    
    with open(file_path, 'r') as file:
        data = json.load(file)
    
    order = json.loads(data['Records'][0]['Body'])
    
    if isinstance(order, dict):
        return order
    return json.loads(order)



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


def connect_to_api():
    """
        Connect to the ShipStation API using the API keys stored in the .env file.

        Args:
            None
        Return:
            list: A list of ShipStation connection objects.
    """
    # Load API keys from .env file
    #load_dotenv()

    # ======== ACCOUNTS =================
    # Nuveau account
    api_key, api_secret  = get_secret('sporticulture_shipstation')
    
    # ===================================

    # Connect to the ShipStation API
    ss_client = ShipStation(key=api_key, secret=api_secret)

    return ss_client




def get_tag_id(tag_reason: str):
    """
    Returns the tag_id corresponding to the specified tag reason for the given order.

    Tags are created on the front end of each ShipStation account and are automatically assigned
    a unique tag_id. This function retrieves the tag_id based on the order's store name and the
    specified tag reason.

    Parameters:
    - order_object: The order object containing information about the order, including the store name.
    - tag_reason (str): The reason for applying the tag, such as "Multi-Order".

    Returns:
    - int or None: The tag_id corresponding to the specified tag reason and store name. Returns None
    if the tag_id is not available for the given store name and tag reason combination.
    """

    # Keys are shipstation accounts and secondary keys are tag_reasons
    account_tag_id_mapping = {
        
        "Multi-Order"           : 55810,
        "No-Dims"               : 55811,
        "Ready"                 : 55809,
        "No SS Carrier Rates"   : 55812,
        "Expedited"             : 55476,
        "Amazon"                : 55813,
        "No-Warehouse"          : 55827
    }


    tag_id = account_tag_id_mapping.get(tag_reason, False)

    return tag_id




def tag_order(order_object, tag_reason: str):
    """
    Tags a specific order with a specified message to be seen on ShipStation's front end

    Params: 

    Valid Reasons List:
        "Multi-Order" : Use when multiple items are in one order
    """

    # Returns the specific tag ID for the relevant SS account & reason
    tag_id = get_tag_id(tag_reason)
    if not tag_id:
        raise ValueError(f"Invalid tag reason: {tag_reason}")

    # Set the payload
    payload = {
        "orderId": order_object.order_id,
        "tagId": tag_id
    }

    try:
        # URL & Headers are included in the shipstation_client session
        response = order_object.ss_client.post(endpoint="/orders/addtag", data=json.dumps(payload))
        response.raise_for_status()

        response_json = response.json()
        # If code in 200 range, but not successful
        if response_json["success"] == False:
            raise requests.HTTPError(f'Request in 200 but Success = False')
        
        return True

    except Exception as e:
        print_yellow("[!] Warning: Could not tag order! ")
        print(response.status_code)
        print(response.text)
        print(e)

        return False




def check_if_multi_order(order_object):
    """
    Analyzes the provided order object to determine whether it qualifies as a multi-order, double-order, complex-order, or neither.

    - A multi-order is defined as an order that contains more than one item with different SKUs.
    - A double-order is defined as an order where at least one item has a quantity greater than one.
    - A complex-order is defined as an order where the total quantity of all items is 4 or greater.

    Args:
        order_object (Order): The order object to be analyzed.

    Returns:
        None: The function modifies the `order_object` in place, updating its attributes.
    """
    total_quantity = 0

    # Check for multi-order and calculate total quantity
    if len(order_object.items) > 1:
        order_object.is_multi_order = True

    for item_object in order_object.items:
        item_quantity = item_object.quantity
        total_quantity += item_quantity

        # Check for double-order
        if item_quantity > 1:
            order_object.is_double_order = True
    
    # Check for complex-order
    if total_quantity >= 4:
        order_object.is_complex_order = True
    



def set_ship_date(order):
    '''
    Sets the ship date for an order based on the store name and specific conditions.

    This function determines the ship date for an order by considering the store name and specific conditions such as 
    whether the order is from Amazon or other predefined stores. It adjusts the ship date based on the current time, 
    whether the order contains assembly items, and weekends.

    Args:
        order (Order): The order object containing details about the order.

    Returns:
        None: The function modifies the `order` object in place, updating its `Shipment.ship_date` attribute.
    '''
    def ship_date_for_amazon(order):
        '''
        This function sets the ship date based on the order details, 
        current time, and whether the order is an assembly item.
        '''
        
        # Define the timezone for Eastern Time (ET)
        eastern = timezone('US/Eastern')
        
        # Get the current time in Eastern Time
        current_time = datetime.datetime.now(eastern)
        
        # Check if the order contains an assembly item
        is_assembly_order = any(item.sku[0].isdigit() for item in order.items)

        # Define 11 AM cutoff time in Eastern Time
        cutoff_time = current_time.replace(hour=11, minute=0, second=0, microsecond=0)

        # If it's before 11 AM Eastern
        if current_time < cutoff_time:
            if is_assembly_order:
                ship_date = current_time + datetime.timedelta(days=1)  # Tomorrow
            else:
                ship_date = current_time  # Today
        else:
            # After 11 AM, ship date is tomorrow regardless of assembly status
            ship_date = current_time + datetime.timedelta(days=1)

        # Adjust if ship_date falls on a weekend (Saturday or Sunday)
        if ship_date.weekday() == 5:  # Saturday
            ship_date += datetime.timedelta(days=2)  # Move to Monday
        elif ship_date.weekday() == 6:  # Sunday
            ship_date += datetime.timedelta(days=1)  # Move to Monday

        # Format the ship date as YYYY-MM-DD and assign it to the order
        order.Shipment.ship_date = ship_date.strftime('%Y-%m-%d')
        
        return order
    
    def set_ship_date_to_tomorrow(order):
        '''
        Sets the ship date to tomorrow if the current day is a weekend
        If tomorrow is a weekend, it sets the ship date to the next monday
        '''
        ship_date = datetime.datetime.now() + datetime.timedelta(days=1)
        if ship_date.weekday() == 5:  # Saturday
            ship_date += datetime.timedelta(days=2)  # Move to Monday
        elif ship_date.weekday() == 6:  # Sunday
            ship_date += datetime.timedelta(days=1)  # Move to Monday
        order.Shipment.ship_date = ship_date.strftime('%Y-%m-%d')

    irrelevant_stores = ["TC EDI", "Sporticulture",]
    if order.store_name in irrelevant_stores:
        pass
    
    stores_set_to_tomorrow = ["JoAnn Fabric & Crafts", "Sharper Image", "Stadium Allstars"]
    if order.store_name in stores_set_to_tomorrow:
        set_ship_date_to_tomorrow(order)

    if order.store_name == "Amazon":
        ship_date_for_amazon(order)

    # No return statement needed as the function modifies the order object in place




def is_po_box_delivery(order):
    """
    Checks if order is being delivered to a PO Box Address

    Args:
        order (object): The order object from Order()

    Return:
        (bool) True is order is delivering to PO Box: else False
    """
    customer_address = order.Customer.ship_to.street1

    if "PO Box".upper() in customer_address.upper():
        return True
    return False




def list_packages(dict_of_shipstation_clients):
    '''
    Retrieves a list of Shipstation packageCodes for the specified carrier.
    Used for Development only

    Args: 
        (dict) : Keys = SS_stores, 
    '''
    print(dict_of_shipstation_clients)
    
    list_of_carriers = ["ups", "fedex", "ups_walleted", "stamps_com"]

    package_codes = {}
    for store_name, ss_client in dict_of_shipstation_clients.items():
        package_codes[store_name] = {}  # Initialize package_codes[store_name] here
        for carrierCode in list_of_carriers:
            try:
                response = ss_client.get(endpoint=f"/carriers/listpackages?carrierCode={carrierCode}")
                response.raise_for_status()  # Raise exception for non-200 status codes
                package_codes[store_name][carrierCode] = response.json()
            except Exception as e:
                print(f"Error fetching package codes for {store_name} and {carrierCode}: {e}")
    
    return package_codes




def set_payload_for_rates(order, carrier):
        '''
        Sets payload for each carrier and handles edge case conditions

        Args: 
            order (object): the order object
            carrier (str): The name of the carrier we are setting the payload for

        Return:
            payload (dict): Returns the correct payload for each condition
        '''
        payload = {
                        "carrierCode": carrier,
                        "serviceCode": None,
                        "packageCode": "package",
                        "fromPostalCode": order.Shipment.warehouse.postal_code,
                        "fromcity": order.Shipment.warehouse.city,
                        "fromState": order.Shipment.warehouse.state.upper(),
                        "fromWarehouseId": order.Shipment.advanced_options['warehouse_id'],
                        "toState": order.Customer.ship_to.state.title(),
                        "toCountry": order.Customer.ship_to.country if order.Customer.ship_to.country in ["US", "CA"] else 'US',
                        "toPostalCode": order.Customer.ship_to.postal_code,
                        "toCity": order.Customer.ship_to.city.title(),
                        "weight": {
                            "value": order.Shipment.weight["value"],
                            "units": "ounces"
                        },
                        "dimensions": {
                            "units": "inches",
                            "length": int(order.Shipment.dimensions['length']),
                            "width": int(order.Shipment.dimensions['width']),
                            "height": int(order.Shipment.dimensions['height'])
                        },
                        "confirmation": order.Shipment.confirmation,
                        "residential": order.Customer.ship_to.residential
                    }

        return payload




def get_rates_for_all_carriers(order):
    """
        Fetch the list of carriers and services from the ShipStation API.

        Args:
            shipstation (ShipStation): The ShipStation connection object.
        Return:
            None
    """
    # Get list of carriers applicable for the order
    list_of_carriers = order.list_of_carriers
    try:
        for carrier in list_of_carriers:
            try:
                payload = set_payload_for_rates(order, carrier)

            # Usually raised when dimensions info is not provided for the order object --> TypeError for int() cannot take NoneType
            except TypeError as e:
                print(e)
                tag_order(order, "No-Dims")
                return False

            try:
                response = order.ss_client.post(endpoint="/shipments/getrates", data=json.dumps(payload))
                # Usually raised when package details aren't valid for specific carrier
                if response.status_code == 500:
                    continue
                response.raise_for_status()  # Raises a HTTPError if the status is 4xx, 5xx

                # If the request is successful, no exception is raised
                response_json = response.json()
                for service in response_json:
                    order.mapping_services[service['serviceName']] = service['serviceCode']
                    total_cost = round(service['shipmentCost'] + service['otherCost'], 2)
                    service_tuple = (service['serviceName'], total_cost)

                    if carrier in order.rates:
                        order.rates[carrier].append(service_tuple)
                    else:
                        order.rates[carrier] = [service_tuple]

            
            except requests.exceptions.RequestException as e:
                print(f"An error occurred: {e}")
                return False
        
        # If rates obtained for all carriers
        return True
    
    except Exception as e:
        print(e)
        return False
    



def set_product_dimensions(order):

    def get_prefix(sku):
        # Get the key for product_size_mapping based on sku prefix
        prefix_mapping = {
            "1216FL3D": "12x18",
            "1216F3D": "12x18",
            "1216U3D": "12x18",
            "17523F": "17.5x23",
            "2335F": "23x35",
            "1212F": "12x12",
            "1218F": "12x18",
            "832F": "8x32",
            "912F": "9x12",
            "624F": "6x24",
            "28F": "2x8"
        }
        for key, value in prefix_mapping.items():
            if sku.startswith(key):
                return value
        return None
    

    product_size_mapping = {
        "12x18": {"length": 16, "width": 20, "height": 2, "weight": 80},
        "11x14": {"length": 16, "width": 20, "height": 2, "weight": 80},
        "17.5x23": {"length": 19, "width": 25, "height": 2, "weight": 96},
        "16x20": {"length": 19, "width": 25, "height": 2, "weight": 96},
        "16x24": {"length": 19, "width": 25, "height": 2, "weight": 96},
        "22x34": {"length": 26, "width": 38, "height": 2, "weight": 128},
        "23x35": {"length": 26, "width": 38, "height": 2, "weight": 128},
        "23x36": {"length": 26, "width": 38, "height": 2, "weight": 128},
        "22x28": {"length": 31, "width": 23, "height": 2, "weight": 96},
        "6x24": {"length": 26, "width": 38, "height": 2, "weight": 32},
        "8x32": {"length": 39, "width": 13, "height": 2, "weight": 80},
        "8x10": {"length": 13, "width": 13, "height": 2, "weight": 16},
        "9x12": {"length": 13, "width": 13, "height": 2, "weight": 16},
        "12x12": {"length": 13, "width": 13, "height": 2, "weight": 16},
        "15x40": {"length": 45, "width": 20, "height": 2, "weight": 128},
        "9x27": {"length": 45, "width": 20, "height": 2, "weight": 128},
        "2x8": {"length": 9, "width": 3, "height": 3, "weight": 16},
        "12x36": {"length": 45, "width": 20, "height": 2, "weight": 128},
        "CERSNCJ": {"length": 11, "width": 10.5, "height": 14, "weight": 71}, # 4 lbs 7 oz = 64 + 7 = 71 oz
        "INFLSCF": {"length": 7, "width": 7, "height": 7, "weight": 38}, # 2 lbs 6 oz = 32 + 6 = 38 oz
        "STRART": {"length": 12, "width": 12, "height": 3, "weight": 39}, # 2 lbs 7 oz = 32 + 7 = 39 oz
        "INFLCP": {"length": 10, "width": 6, "height": 3, "weight": 10},
        "INFLJH": {"length": 10, "width": 8, "height": 6, "weight": 46}, # 2 lbs 14 oz = 32 + 14 = 46 oz
        "INFLSB": {"length": 10, "width": 8, "height": 6, "weight": 54}, # 3 lbs 6 oz = 48 + 6 = 54 oz
        "INDLSD": {"length": 10, "width": 8, "height": 6, "weight": 51}, # 3 lbs 3 oz = 48 + 3 = 51 oz
        "CERPM": {"length": 12, "width": 12.5, "height": 13.5, "weight": 82}, # 5 lbs 2 oz = 80 + 2 = 82 oz
        "BBRIT": {"length": 7, "width": 7, "height": 5, "weight": 13},
        "CARDL": {"length": 6, "width": 4, "height": 4, "weight": 6},
        "CRDDT": {"length": 4, "width": 4, "height": 16, "weight": 12},
        "GDPWT": {"length": 5, "width": 5, "height": 3, "weight": 25}, # 1 lb 9 oz = 16 + 9 = 25 oz
        "MGLMP": {"length": 12, "width": 9, "height": 5, "weight": 67}, # 4 lbs 3 oz = 64 + 3 = 67 oz
        "SCARL": {"length": 36, "width": 12, "height": 4, "weight": 44}, # 2 lbs 12 oz = 32 + 12 = 44 oz
        "SOLTR": {"length": 14, "width": 6, "height": 6, "weight": 25}, # 1 lb 9 oz = 16 + 9 = 25 oz
        "SPOTL": {"length": 6, "width": 4, "height": 4, "weight": 6},
        "CRCCS": {"length": 9, "width": 7, "height": 1, "weight": 3.2},
        "SAND": {"length": 8.5, "width": 12.5, "height": 1, "weight": 17}, # 1 lb 1 oz = 16 + 1 = 17 oz
        "SCRT": {"length": 15, "width": 13, "height": 1, "weight": 7},
        "BPOT": {"length": 8, "width": 8, "height": 8, "weight": 18}, # 1 lb 2 oz = 16 + 2 = 18 oz
    }

    if not order.Shipment.dimensions:
        sku = order.items[0].sku
        prefix = get_prefix(sku)
        
        if prefix is None:
            for key in product_size_mapping.keys():
                if sku.startswith(key):
                    prefix = key
                    break
        
        if prefix is None:
            return False
        
        size_dict = product_size_mapping[prefix]

        length = size_dict['length']
        width = size_dict['width']
        height = size_dict['height']
        weight = size_dict['weight']

        # Set the dimensions and weight for the order_object
        order.Shipment.dimensions = {"units": "inches", "length": length, "width": width, "height": height}
        order.Shipment.weight = {"value": weight, "units": "ounces", 'weight_units': 1}
        return True
    

def get_warehouse_id(order):
        # 590152 = Indiana
        # 791225 = MD
        # 729388 = Walnut Springs
        # Order them longest to shortest to ensure we get the correct warehouse ID
        warehouse_id_mapping = {
            "INFL-CCSNTA": 791225,
            "1216FL3D": None,
            "CARDL-LS": 590152,
            "1216F3D": None,
            "1216U3D": None,
            "CRDP-CC": 791225,
            "INFLCSF": 590152,
            "INFLSMP": 791225,
            "17523F": 791225,
            "CCERSM": 590152,
            "INFLCP": 590152,
            "INFLJH": 590152,
            "INFLSB": 590152,
            "INFLSD": 590152,
            "1212F": 791225,
            "1218F": 791225,
            "2335F": 791225,
            "BBRIT": 791225,
            "BCHPD": 590152,
            "CARDL": 590152,
            "CERPM": 791225,
            "CERSM": 590152,
            "CERSN": 791225,
            "CRCCS": 791225,
            "CRDDT": 590152,
            "CRDPP": 791225,
            "GDPWT": 791225,
            "INFLH": 791225,
            "INFLJ": 791225,
            "INFTY": 791225,
            "MAFBL": 590152,
            "MGLMP": 590152,
            "PCRSM": 590152,
            "SCARL": 590152,
            "SOLTR": 590152,
            "SPOTL": 590152,
            "STRBL": 590152,
            "ZNCN9": 791225,
            "624F": 791225,
            "832F": 791225,
            "912F": 791225,
            "BPOT": 590152,
            "SAND": 791225,
            "SCRT": 791225,
            "PLNF": 729388,
            "PLNP": 729388,
            "PLSA": 729388,
            "28F": 791225,
            "MTS": 791225
        }

        sku = order.items[0].sku
        for key, warehouse_id in warehouse_id_mapping.items():
            if sku.startswith(key):
                return warehouse_id
        
        return False




def update_warehouse_location(order):
        
        
        warehouse_id = get_warehouse_id(order)
        if warehouse_id is False:
            return False

        print(f"Warehouse ID: {warehouse_id}")

        if warehouse_id == 791225:
            order.Shipment.warehouse.postal_code = "21738"
            order.Shipment.warehouse.city = "Glenwood"
            order.Shipment.warehouse.state = "MD"
            order.Shipment.warehouse.country = "US"
            order.Shipment.warehouse.street1 = "14812 Burntwoods Road"
            order.Shipment.warehouse.phone = "4432667788"
            order.Shipment.warehouse.residential = False
            order.Shipment.warehouse.name = "Warehouse Location 1"

        elif warehouse_id == 729388:
            order.Shipment.warehouse.postal_code = "21738"
            order.Shipment.warehouse.city = "Glenwood"
            order.Shipment.warehouse.state = "MD"
            order.Shipment.warehouse.country = "US"
            order.Shipment.warehouse.street1 = "14812 Burntwoods Rd"
            order.Shipment.warehouse.phone = "4432667788"
            order.Shipment.warehouse.residential = False
            order.Shipment.warehouse.name = "Walnut Springs Nursery"

        elif warehouse_id == 590152 or warehouse_id is None:
            # Initialize warehouse attributes
            order.Shipment.warehouse.postal_code = "46203"
            order.Shipment.warehouse.city = "INDIANAPOLIS"
            order.Shipment.warehouse.state = "IN"
            order.Shipment.warehouse.country = "US"
            order.Shipment.warehouse.street1 = "1435 E NAOMI ST"
            order.Shipment.warehouse.phone = "3174064033"
            order.Shipment.warehouse.residential = False
            order.Shipment.warehouse.name = "Stallion Wholesale"

        else:
            return False
    





def set_multi_order_dimensions(order):
    pass


def update_advanced_options(order):
    '''
    Update settings for advanced options in place for an order depending on if anything needs to be updated.
    If nothing needs to be updated, then the order object's advanced_options will not be changed

    This function updates the advanced options for an order based on the SKU prefix and store name. 
    It sets the warehouse ID based on the SKU prefix and updates the shipping account billing information 
    based on the winning carrier if the order is from Amazon or Sporticulture.

    Args:
        order (Order): The order object containing details about the order.

    Returns:
        None: The function modifies the `order` object in place, updating its `advanced_options` attribute.
    '''

    def get_shipping_provider_id(carrier_code):
        """
        Retrieves the shipping provider ID for a given carrier code.

        This function maps carrier codes to their corresponding shipping provider IDs. 
        The carriers listed in the mapping are specific to Stallion Wholesale, including 
        their USPS account, WSN FedEx account, WSN UPS account, and the ShipStation-provided UPS account.

        Args:
            carrier_code (str): The code representing the carrier (e.g., "stamps_com", "ups", "fedex", "ups_walleted").

        Returns:
            int: The shipping provider ID corresponding to the given carrier code.

        Raises:
            KeyError: If the provided carrier code is not found in the mapping.
        """

        shipping_provider_id_mapping = {
            "stamps_com": 223479,
            "ups": 276012,
            "fedex": 223490,
            "ups_walleted": 661125
        }
        shipping_provider_id = shipping_provider_id_mapping[carrier_code]

        return shipping_provider_id


    if order.store_name == "Amazon" or order.store_name == "Sporticulture":
        # Update the Shipping Account Billing info based on the winning carrier
        winning_carrier_code = order.winning_rate["carrierCode"]
        shipping_provider_id = get_shipping_provider_id(winning_carrier_code)
        order.Shipment.advanced_options['billToParty'] = 'my_other_account'
        order.Shipment.advanced_options['billToMyOtherAccount'] = shipping_provider_id



def convert_keys_to_camel_case(data):

    def snake_to_camel(snake_str):
        components = snake_str.split('_')
        return components[0] + ''.join(x.title() for x in components[1:])

    if isinstance(data, dict):
        new_data = {}
        for k, v in data.items():
            new_key = snake_to_camel(k)
            new_data[new_key] = convert_keys_to_camel_case(v)
        return new_data
    elif isinstance(data, list):
        return [convert_keys_to_camel_case(i) for i in data]
    else:
        return data


def set_payload_for_update_order(order_object):
    # Update the advanced options for the order if neccessary
    update_advanced_options(order_object)

    payload = {
        "orderNumber": order_object.order_number,
        "orderKey": order_object.order_key,
        "orderDate": order_object.order_date,
        "paymentDate": order_object.payment_date,
        "shipByDate": order_object.Shipment.ship_date,
        "orderStatus": order_object.order_status,
        "customerId": order_object.Customer.customer_id,
        "customerUsername": order_object.Customer.customer_username,
        "customerEmail": order_object.Customer.customer_email,
        "billTo": order_object.Customer.bill_to.as_dict(),
        "shipTo": order_object.Customer.ship_to.as_dict(),
        "items": [item.as_dict() for item in order_object.items],
        "amountPaid": order_object.amount_paid,
        "taxAmount": order_object.tax_amount,
        "shippingAmount": order_object.Shipment.shipping_amount,
        "customerNotes": order_object.Customer.customer_notes,
        "internalNotes": order_object.Customer.internal_notes,
        "gift": order_object.Shipment.is_gift,
        "giftMessage": order_object.Shipment.gift_message,
        "paymentMethod": order_object.payment_method,
        "requestedShippingService": order_object.winning_rate["serviceCode"],
        "carrierCode": order_object.winning_rate["carrierCode"],
        "serviceCode": order_object.mapping_services[order_object.winning_rate["serviceCode"]],
        "packageCode": order_object.Shipment.package_code,
        "confirmation": order_object.Shipment.confirmation,
        "shipDate": order_object.Shipment.ship_date,
        "weight": order_object.Shipment.weight,
        "dimensions": {
            "length": order_object.Shipment.dimensions['length'], 
            "width": order_object.Shipment.dimensions['width'],
            "height": order_object.Shipment.dimensions['height'],
            "units": "inches"
            },
        "insuranceOptions": order_object.Shipment.insurance_options,
        "internationalOptions": order_object.Shipment.international_options,
        "advancedOptions": order_object.Shipment.advanced_options,
        "tagIds": order_object.tag_ids, 
    }

    # Convert payload keys to camelCase
    payload = convert_keys_to_camel_case(payload)

    return payload




def create_or_update_order(order_object: Order) -> bool:  
    """
    Create or update an order in ShipStation.

    Args:
        order_object (Order): The Order object containing all necessary data.
    Return:
        bool: True if the request is successful, False otherwise.
    """
    payload = set_payload_for_update_order(order_object)

    try:
        # URL & Headers are included in the shipstation_client Session
        response = order_object.ss_client.post(endpoint="/orders/createorder", data=json.dumps(payload))
        response.raise_for_status()  # Raises an exception for HTTP error codes
        # Optionally, process the response or return True to indicate success
        #print("Order created or updated successfully:", response.json())
        return True
    except requests.exceptions.RequestException as e:
        print(f"An error occurred: {e}")
        return False




def get_champion_rate(order, ups_best: tuple = None, usps_best: tuple = None, fedex_best: tuple = None):
    """
    Finds the overall best shipping rate among multiple carriers based on the winning rates.

    Parameters:
    - order (Order object): An object representing the order details.
    - ups_best (tuple or None): A tuple containing UPS's best rate information or None if UPS rate is not available.
    - usps_best (tuple or None): A tuple containing USPS's best rate information or None if USPS rate is not available.
    - fedex_best (tuple or None): A tuple containing FedEx's best rate information or None if FedEx rate is not available.

    Returns:
    - None: The function updates the order object's winning_rate attribute with the champion rate.

    This function takes the winning rates of all the carriers and compares them against each other to find the overall best rate.
    It considers the warehouse ID of the order to determine which carriers to include in the comparison.
    It includes rates from UPS, USPS, and FedEx (if available).
    The function then selects the champion rate based on the lowest price among the eligible rates and updates the order object with this rate.
    """
    
    list_of_rates = [rate for rate in [ups_best, usps_best, fedex_best] if rate is not None]


    champion_rate = min(list_of_rates, key=lambda x: x["price"])
    order.winning_rate = champion_rate # Example:  {'carrierCode': 'ups', 'serviceCode': 'UPS® Ground', 'price': 12.62}

    return None



if __name__ == "__main__":
    print("[X] This file is not meant to be executed directly. Check for the main.py file.")
    quit(1)