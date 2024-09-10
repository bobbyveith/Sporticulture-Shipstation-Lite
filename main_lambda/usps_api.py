import xml.etree.ElementTree as ET
import requests
import os
from dotenv import load_dotenv
import xmltodict
from datetime import datetime, timezone, timedelta
import boto3
from botocore.exceptions import ClientError
import json


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
        api_key = secret_dict['username']
        api_secret = secret_dict['password']

        return api_key, api_secret

    except ClientError as e:
        # Handle the error accordingly
        raise e



def get_credentials():
    try:
        #load_dotenv()
        username, password = get_secret('uspsAPICredentials')

    except Exception as e:
        print("[X] Error getting credentials form secretsmanager!")
        print(e)

    return username, password



def decode_options(list_of_options):
    """
    Converts USPS number codes into their respective service name.

    Takes a list of dictionaries representing shipping options and updates the MailClass codes into their
    corresponding service names. Removes unnecessary keys based on the converted MailClass codes.

    Parameters:
    - list_of_options (list): A list of dictionaries containing shipping options data.

    Returns:
    - list: An updated list of dictionaries representing shipping options with service names and cleaned data.

    The function iterates through each shipping option dictionary in the input list and updates the MailClass
    codes into their respective service names. It then removes unnecessary keys based on the converted MailClass
    codes to provide a more refined and organized shipping options list.
    """
    
    # Mapping dictionary for MailClass codes to service names
    mailclass_mapping = {
        "1": "Priority Mail Express",
        "2": "Priority Mail",
        "3": "USPS Ground Advantage",
        "4": "Standard Mail",
        "5": "Periodicals",
        "6": "USPS Ground Advantage, LIVES, Offshore",
        "7": "USPS Ground Advantage (1 to 70lbs)",
        "9": "USPS Ground Advantage (1 to 70lbs)",
    }

    for option in list_of_options:
        mailclass = option.get("MailClass")
        if mailclass in mailclass_mapping:
            option["MailClass"] = f"{mailclass_mapping[mailclass]} {option.get('CommitmentName', '')}".rstrip()
            option.pop("CommitmentName", None)
            option.pop("NonExpeditedDestType", None)
        else:
            option["MailClass"] = "Bug --> MailClass num missing from translate_exp_options()"

    return list_of_options



def get_standard_options(response_dict):
    """
    Extracts standard delivery options from the USPS response dictionary and refines the data.

    Parameters:
    - response_dict (dict): A dictionary containing the USPS API response.

    Returns:
    - list: A list of dictionaries representing cleaned standard delivery options.
        Each dictionary contains the following keys:
        - 'MailClass': The mail service type.
        - 'NonExpeditedDestType': Number representing streed address vs PO Box.
        - 'SvcStdDays': The number of standard delivery days needed.
        - 'DeliveryDate': The scheduled delivery date.

    The function filters out non-standard delivery options and only includes options that 
    deliver to street addresses.
    """

    # Extracting a list of standard delivery options from the response_dict and their delivery dates
    ship_options_list_raw = response_dict["SDCGetLocationsResponse"]["NonExpedited"]

    cleaned_options_list = []

    for ship_option in ship_options_list_raw:
        # Shipping Option data will be stored in a dict
        cleaned_option = {}

        # only options that are street address delivery ("1") apply
        if ship_option["NonExpeditedDestType"] == "1":
            #filling the dict with the information we care about
            cleaned_option["MailClass"] = ship_option["MailClass"]
            cleaned_option["NonExpeditedDestType"] = ship_option["NonExpeditedDestType"]
            cleaned_option["SvcStdDays"] = ship_option["SvcStdDays"]
            cleaned_option["DeliveryDate"] = ship_option["SchedDlvryDate"]

            # add the shipping option to the list of cleaned options
            cleaned_options_list.append(cleaned_option)

    
    final_options_list = decode_options(cleaned_options_list)

    return final_options_list



def get_exp_options(response_dict):
    """
    Extracts expedited delivery options from the USPS response dictionary and refines the data.

    Parameters:
    - response_dict (dict): A dictionary containing the USPS API response.

    Returns:
    - list: A list of dictionaries representing cleaned expedited delivery options.
        Each dictionary contains the following keys:
        - 'MailClass': The mail service type.
        - 'CommitmentName': Denotes either 1-day or 2-day shipping.
        - 'CommitmentSeq': Denotes deliver days + Street or PO Box address.
        - 'DeliveryDate': The scheduled delivery date.
        - 'CutOffTime': The cut-off time to qualify for expedited shipping for the day.

    The function filters out non-expedited options and only includes options with specific MailClass
    and CommitmentSeq values ('1' and 'A0218' for MailClass 1, '2' and 'C0200' for MailClass 2).
    """
    #print(response_dict)
    # Extracting a list of expedited delivery options from the response_dict and their delivery dates
    expedited_options_list_raw = response_dict["SDCGetLocationsResponse"]["Expedited"]["Commitment"]
    
    cleaned_options_list = []

    for ship_option in expedited_options_list_raw:

        # Grabbing only what we care about
        cleaned_option = {
            "MailClass"      : ship_option.get("MailClass", ""),
            "CommitmentName" : ship_option.get("CommitmentName", ""),
            "CommitmentSeq"  : ship_option.get("CommitmentSeq", ""),
        }

        if "Location" in ship_option:
            
            # When multiple options given, Location value is a list
            if isinstance(ship_option["Location"], list):         
                cleaned_option["DeliveryDate"] = ship_option["Location"][0]["SDD"]

            else: # When single option given, Location value is a dict             
                cleaned_option["DeliveryDate"] = ship_option["Location"]["SDD"]
        else:
            # Handle the case where "Location" is missing or empty
            cleaned_option["DeliveryDate"] = None  # Or set a default value as needed

        cleaned_options_list.append(cleaned_option)

    # Create a new list to store filtered elements
    filtered_options_list = []

    # Filter the elements based on MailClass uniqueness
    for ship_option in cleaned_options_list:
        if not any(option["MailClass"] == ship_option["MailClass"] for option in filtered_options_list):
            filtered_options_list.append(ship_option)

    # Translating some usps data codes into strings
    final_options_list = decode_options(filtered_options_list)

    return final_options_list



def get_todays_date():
    """
    Retrieves the current date and formats it as 'M/D/YYYY'.

    Returns:
    - str: The formatted current date.

    This function gets the current date using the datetime module and formats it as 'M/D/YYYY',
    where 'M' is the month without leading zeros, 'D' is the day without leading zeros, and 'YYYY' is the year.
    """
    # Get the current date
    current_date = datetime.now()

    # Format the date as 'M/D/YYYY'
    formatted_date = current_date.strftime('%-m/%-d/%Y')

    return formatted_date




def get_usps_response(ship_date, from_zip, dest_zip):
    """
    Fetches USPS API response for shipping locations based on the destination ZIP code.

    Parameters:
    - dest_zip (str): The destination ZIP code for which shipping locations are requested.

    Returns:
    - dict or None: A dictionary containing the parsed XML response if successful, or None if an error occurs.

    This function sends a POST request to the USPS API endpoint to retrieve shipping locations information
    based on the specified destination ZIP code. It uses the credentials obtained from the `get_credentials` function
    to authenticate the request.

    The API request payload includes the destination ZIP code, current date, and other required parameters
    formatted according to the USPS API documentation.

    If the API response status code is within the 200 range (successful), the XML response is parsed into
    a Python dictionary using the xmltodict library, and the parsed dictionary is returned.

    If the API response status code is not in the 200 range, a warning is printed with the response status code
    and text, and None is returned.

    In case of any exceptions during the API request or response handling, an error message is printed,
    and None is returned.
    """
    
    username, password = get_credentials()
    # Documentiation: https://www.usps.com/business/web-tools-apis/sdc-getlocations-api.pdf
    uri = "https://secure.shippingapis.com/shippingapi.dll?API=SDCGetLocations&XML="

    if ship_date is None:
        ship_date = datetime.now().strftime('%Y-%m-%d')

    ship_date_formated = datetime.strptime(ship_date, '%Y-%m-%d').strftime('%d-%b-%Y')


    xml_payload = f"<SDCGetLocationsRequest USERID='{username}' PASSWORD='{password}'><MailClass>0</MailClass><OriginZIP>{from_zip}</OriginZIP><DestinationZIP>{dest_zip}</DestinationZIP><AcceptDate>{ship_date_formated}</AcceptDate></SDCGetLocationsRequest>"

    # Build URL
    url = uri+xml_payload

    try:
        response = requests.post(url)
        
        #if status is not in 200 range then raise error
        response.raise_for_status()

        if response.status_code == 200:
            # Parse the XML response into a python dictionary using xmltodict
            xml_dict = xmltodict.parse(response.content)
            return xml_dict
            

        else: #if status code is anything else in 200 range
            print(f"[!] Warning USPS response status is: {response.status_code}")
            print(f"Response text --> {response.text}")

    except:
        print("[X] Error fetching XML Response from USPS")
        print(response.status_code)
        print(response.text)
        return None



def is_delivery_before_latest(delivery_date, latest_delivery_date):
    """
    Checks if a delivery date is before or on the latest delivery date, accounting for time zones.

    Parameters:
    - delivery_date (str): The delivery date in the format 'YYYY-MM-DD'.
    - latest_delivery_date (str): The latest delivery date in the format 'YYYY-MM-DDTHH:MM:SSZ',
    where 'THH:MM:SSZ' represents the time in UTC.

    Returns:
    - bool: True if the delivery date is before or on the latest delivery date, False otherwise.

    This function converts the date strings to datetime objects and compares them,
    considering time zones to ensure accurate date comparisons.
    """
    # Convert delivery_date to datetime object with correct format
    delivery_dt = datetime.strptime(delivery_date, '%Y-%m-%d')

    # Convert latest_delivery_date to datetime object with correct format
    latest_delivery_dt = datetime.strptime(latest_delivery_date, '%m/%d/%Y %H:%M:%S')

    # Convert delivery date to UTC timezone (assuming delivery_date is in EST)
    delivery_dt_utc = delivery_dt.replace(tzinfo=timezone.utc) - timedelta(hours=5)

    # Convert latest_delivery_date to UTC timezone (assuming UTC time zone)
    latest_delivery_dt_utc = latest_delivery_dt.replace(tzinfo=timezone.utc)

    # Compare the dates
    return delivery_dt_utc <= latest_delivery_dt_utc



def get_valid_options(usps_response, latest_delivery_date):
    """
    Filters and returns valid shipping options based on USPS response and a latest delivery date.

    Parameters:
    - usps_response (dict): A dictionary containing USPS shipping options data.
    - latest_delivery_date (str): The latest acceptable delivery date in 'YYYY-MM-DD' format.

    Returns:
    - list: A list of dictionaries representing valid shipping options.
    Each dictionary contains shipping option details such as DeliveryDate, MailClass, etc.

    This function first filters expedited and standard shipping options from the USPS response.
    It then combines these options into one list and eliminates options that won't arrive on time
    based on the latest delivery date provided.

    Note: The functions get_exp_options and get_standard_options are assumed to be defined elsewhere
    and are used to filter expedited and standard options from the USPS response, respectively.
    """

    #get expedited and standard options
    filtered_expidited_options = get_exp_options(usps_response)

    filtered_standard_options = get_standard_options(usps_response)
    

    #combine options into one list
    shipping_options = filtered_expidited_options + filtered_standard_options
    #print(f"Shipping Options = {shipping_options}")

    valid_shipping_options = []
    #eliminate shipping options that wont arrive on time
    for option in shipping_options:

        delivery_date = option["DeliveryDate"]

        # If this shippment will arrive on time, append to list
        if is_delivery_before_latest(delivery_date, latest_delivery_date):
            # Convert to datetime for future comparisons
            option["DeliveryDate"] = datetime.strptime(delivery_date, "%Y-%m-%d")
            valid_shipping_options.append(option)

    return valid_shipping_options



def get_delivery_date(service_name: str, valid_shipping_options: list):
    """
    Get the delivery date for a specified service name from a list of valid shipping options.

    Parameters:
    - service_name (str): The name of the shipping service to find the delivery date for.
    - valid_shipping_options (list): A list of dictionaries representing valid shipping options.
    Each dictionary should have keys 'MailClass' and 'DeliveryDate' indicating the mail class
    and its corresponding delivery date.

    Returns:
    - str: The delivery date for the specified service name.

    Raises:
    - KeyError: If the service name is not found in the valid shipping options.
    """
    for option in valid_shipping_options:

        # If this shipping option is the one we want
        if option["MailClass"] == service_name:
            return option["DeliveryDate"]
        
        else:
            # Keep looking for the shipping option we want the Delivery Date for
            continue

    # If Shipstation shipping service not in USPS API options
    return None




def format_valid_options(order, valid_shipping_options: list):
    """
    Filters and formats valid shipping options based on USPS rates and delivery dates.

    Parameters:
    - order: The order object containing shipping rates information.
    - valid_shipping_options (list): A list of valid shipping options with delivery dates.

    Returns:
    - list: A list of dictionaries representing filtered and formatted valid shipping options.
    Each dictionary contains the following keys:
        - 'service_name': The name of the shipping service.
        - 'price': The price of the shipping service.
        - 'delivery_date': The delivery date of the shipping service.

    The function iterates through USPS rates and formats valid shipping options based on specific conditions.
    If a shipping option matches certain criteria, its name, price, and delivery date are added to the result list.
    """

    # Define a mapping of ShipStation Service Names (keys) to their respective USPS API service names (values)
    service_delivery_mapping = {
        'USPS First Class Mail - Large Envelope or Flat': 'USPS Ground Advantage',
        'USPS First Class Mail - Package': 'USPS Ground Advantage',
        'USPS Priority Mail - Package': 'Priority Mail 2-Day',
        'USPS Priority Mail Express - Package': 'Priority Mail Express 2-Day',
        'USPS Ground Advantage - Package': 'USPS Ground Advantage',
    }

    # Initialize container for the formatted options: dicts
    formatted_options_list = []

    usps_rates_list = order.rates["stamps_com"]

    for option in usps_rates_list:
        service_name = option[0]
        price = option[1]

        if service_name in service_delivery_mapping:
            delivery_date = get_delivery_date(service_delivery_mapping[service_name], valid_shipping_options)
            formatted_options_list.append({
                "service_name": service_name,
                "price": price,
                "delivery_date": delivery_date
            })

    return formatted_options_list




def compare_prices(formated_options: list):
    # Filter options with non-None delivery dates
    filtered_options = [option for option in formated_options if option['delivery_date'] is not None]

    if filtered_options:
        # Find the option with the minimum price
        sorted_options = sorted(filtered_options, key=lambda x: x['price'])
        #print(f"sorted options = {sorted_options}")
        # Desired business logic. Willing to ship up to $0.35 more expensive if package arrives earlier than the cheapest shipping rate
        better_options = [option for option in sorted_options if option['price'] - sorted_options[0]['price'] < 0.35 and option['delivery_date'] < sorted_options[0]['delivery_date']]
        best_option = min(better_options, key=lambda x: x['deliveryDate']) if better_options else sorted_options[0]

        # Convert answer to dict
        if best_option:
            best_option = {"carrierCode": "stamps_com", "serviceCode": best_option["service_name"], "price": best_option["price"]}

        return best_option
    else:
        print("No valid options with delivery dates for USPS.")
        return None



def get_usps_best_rate(order):
    """
    Calculates and returns the best USPS shipping rate for an order.

    Parameters:
    - order (Order): An object of the Order class containing order details.

    Returns:
    - tuple or None: A tuple containing the best shipping option and its price, or None if USPS rates are not applicable for the order.

    This function handles the main workflow for calculating the best USPS shipping rate for an order. It checks if USPS rates are applicable for the order. If not, it returns None. 
    If rates are expected but not retrieved, it returns False. 
    Otherwise, it retrieves USPS delivery estimates, filters valid shipping options that will arrive on time, 
    formats the options, compares prices, and returns the best shipping option and its price.

    """

    # Ensure that USPS is applicable for this order
    rate_is_applicable = order.rates.get("stamps_com", False)
    if not rate_is_applicable:
        return None
    
    destination_zip = order.Customer.ship_to.postal_code[:5]
    from_zip = order.Shipment.warehouse.postal_code
    ship_date = order.Shipment.ship_date

    #get USPS delivery estimates response for the order
    usps_response = get_usps_response(ship_date, from_zip, destination_zip)
    
    # If not able to get valid USPS response, break from this function
    if usps_response == None:
        return False


    # Get list of options that will arrive on time
    valid_shipping_options = get_valid_options(usps_response, order.deliver_by_date)
    # print("---Valid USPS API Shipping Options---\n")
    # print(valid_shipping_options)

    # Get list of options that combined SS_rates with USPS_delivery times
    formated_options = format_valid_options(order, valid_shipping_options)
    # print("---Formatted USPS API Shipping Options---\n")
    # print(formated_options)


    # Find the lowest price from the valid options
    best_shipping_option = compare_prices(formated_options)
    #print(f"Best Price --->  {best_shipping_option}\n")
    #print(best_shipping_option)

    return best_shipping_option # Example: {'carrierCode': 'stamps_com', 'serviceCode': 'USPS First Class Mail - Package', 'price': 4.31}


if __name__ == "__main__":

    dest_zip = "89123"

    #get USPS response for the order
    usps_response = get_usps_response(dest_zip)

    #get the shipping options
    print(get_exp_options(usps_response))
    print("------\n")
    print(get_standard_options(usps_response))

