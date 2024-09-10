import boto3
import json, time
from botocore.exceptions import ClientError

# imported from shipstation_layer (lambda layer)
from shipstation_api import ShipStation

def get_account_name(unique_id):
    account_name_map = {
        "stallion": "Stallion",
        "winningstreak": "Winning Streak",
        "sporticulture": "Sporticulture"
    }

    account_name = account_name_map.get(unique_id)
    return account_name


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
        Connect to the ShipStation API using the API keys retrieved from Secrets Manager.

        Args:
            uniqueID
        Return:
            object: A ShipStation connection objects.
    """

    # Account Credentials
    api_key, api_secret = get_secret('sporticulture_shipstation')

    # Connect to the ShipStation API
    ss_client = ShipStation(key=api_key, secret=api_secret)
    return ss_client


def get_batch_id(resource_url):
    """
    Extract the importBatch number from the given ShipStation URL.

    Parameters:
    resource_url (str): The URL containing the importBatch parameter.

    Returns:
    str: The importBatch number extracted from the URL.
    """
    # Find the start of the importBatch value
    import_batch_start = resource_url.find('=') + 1

    # Extract and return everything after the "="
    return resource_url[import_batch_start:]


def fetch_order_count(ss_client, max_retries=10, delay=5):
    """
    Fetches the total number of orders from ShipStation.

    Args:
        ss_client (ShipStation): The ShipStation connection object.
        max_retries (int): Maximum number of retries.
        delay (int): Delay between retries in seconds.

    Returns:
        int: The total number of pages (total orders divided by 250).
    """
    for attempt in range(max_retries):
        try:
            params = {'order_status': 'awaiting_shipment', 'page': 1, 'page_size': 1}
            response = ss_client.fetch_orders(parameters=params)
            response.raise_for_status()  # Raises an HTTPError for bad responses (4xx/5xx)
            
            # Extract the total number of orders from the JSON response
            total_orders = response.json().get('total', 0)
            return total_orders
        except Exception as e:
            print(f"[X] Attempt {attempt+1} failed with error: {e}")
            time.sleep(delay)  # Wait before retrying
    return None





def fetch_orders_with_retry(ss_client, total_orders, max_retries=10, delay=5):
    """
    Attempts to fetch all orders with a specified number of retries for each page.

    Args:
        ss_client (ShipStation): The ShipStation connection object.
        total_orders (int): The total number of orders to fetch.
        max_retries (int): Maximum number of retries for each page.
        delay (int): Delay between retries in seconds.

    Returns:
        list: A list of all orders (parsed from the response JSON).
    """
    num_of_pages = (total_orders // 250) + 1
    all_orders = []

    for page in range(1, num_of_pages + 1):
        for attempt in range(max_retries):
            try:
                params = {
                    'order_status': 'awaiting_shipment', 
                    'page': page,
                    'page_size': 250
                }
                
                response = ss_client.fetch_orders(parameters=params)
                response.raise_for_status()  # Raises an HTTPError for bad responses (4xx/5xx)
                
                # Extract the list of orders from the JSON response
                orders = response.json().get("orders", [])
                all_orders.extend(orders)
                break  # Exit the retry loop if the request is successful
            except Exception as e:
                print(f"[X] Attempt {attempt+1} for page {page} failed with error: {e}")
                time.sleep(delay)  # Wait before retrying
        else:
            print(f"[X] Failed to fetch page {page} after {max_retries} attempts.")
            return None  # Return None if any page fails after max retries

    return all_orders




def parse_customer_data(order_data):
    '''
    Extracts customer-related data from the order_data payload.

    This function takes the order_data dictionary, which contains detailed order information,
    and extracts the fields related to the customer. It handles potential missing keys by using 
    the `.get()` method, which returns `None` if the key is not present.

    Args:
        order_data (dict): The dictionary containing the order information.

    Returns:
        dict: A dictionary containing customer-related data, including customer ID, 
            username, email, notes, and addresses for billing and shipping.
    '''
    customer_data = {
        'customer_id': order_data.get('customer_id', None),
        'customer_username': order_data.get('customer_username', None),
        'customer_email': order_data.get('customer_email', None),
        'customer_notes': order_data.get('customer_notes', None),
        'internal_notes': order_data.get('internal_notes', None)
    }
    return customer_data




def parse_shipment_data(order_data):
    """
    Extracts shipment-related data from the order_data payload.

    This function takes the order_data dictionary, which contains detailed order information,
    and extracts the fields related to the shipment. It handles potential missing keys by using
    the `.get()` method, which returns `None` if the key is not present in the order_data.

    Args:
        order_data (dict): The dictionary containing the order information.

    Returns:
        dict: A dictionary containing shipment-related data, including shipping service details,
            gift information, carrier codes, package details, and other shipment-specific fields.
            If a key is not present in the order_data, the value is set to `None`.
    """
    
    shipment_data = {
        'ship_by_date': order_data.get("ship_by_date", None),
        'is_gift': order_data.get("gift", None),
        'gift_message': order_data.get("gift_message", None),
        'requested_shipping_service': order_data.get("requested_shipping_service", None),
        'shipping_amount': order_data.get("shipping_amount", None),
        'carrier_code': order_data.get("carrier_code", None),
        'service_code': order_data.get("service_code", None),
        'package_code': order_data.get("package_code", None),
        'confirmation': order_data.get("confirmation", None),
        'ship_date': order_data.get("ship_date", None),
        'hold_until_date': order_data.get("hold_until_date", None),
        'weight': order_data.get("weight", None),
        'dimensions': order_data.get("dimensions", None),
        'insurance_options': order_data.get("insurance_options", None),
        'international_options': order_data.get("international_options", None),
        'advanced_options': order_data.get("advanced_options", None),
    }

    return shipment_data




def parse_order_data(order_data):
    """
    Extracts order-related data from the order_data payload.

    This function takes the order_data dictionary, which contains detailed order information,
    and extracts the fields related to the order itself, such as order ID, order number, 
    dates, status, and payment details. It handles potential missing keys by using the `.get()` 
    method, which returns `None` if the key is not present in the order_data.

    Args:
        order_data (dict): The dictionary containing the order information.

    Returns:
        dict: A dictionary containing order-related data, including order ID, number, dates,
            status, total amount, paid amount, tax amount, and payment method. If a key is 
            not present in the order_data, the value is set to `None`.
    """
    
    order_data_parsed = {
        'order_id': order_data.get("order_id", None),
        'order_number': order_data.get("order_number", None),
        'order_key': order_data.get("order_key", None),
        'order_date': order_data.get("order_date", None),
        'create_date': order_data.get("create_date", None),
        'modify_date': order_data.get("modify_date", None),
        'payment_date': order_data.get("payment_date", None),
        'order_status': order_data.get("order_status", None),
        'order_total': order_data.get("order_total", None),
        'amount_paid': order_data.get("amount_paid", None),
        'tax_amount': order_data.get("tax_amount", None),
        'payment_method': order_data.get("payment_method", None),
        'tag_ids': order_data.get("tag_ids", None),
        'user_id': order_data.get("user_id", None),
        'externally_fulfilled': order_data.get("externally_fulfilled", None),
        'externally_fulfilled_by': order_data.get("externally_fulfilled_by", None),
        'externally_fulfilled_by_id': order_data.get("externally_fulfilled_by_id", None),
        'externally_fulfilled_by_name': order_data.get("externally_fulfilled_by_name", None),
        'label_messages': order_data.get("label_messages", None)
    }
    
    return order_data_parsed




def get_warehouse(warehouse_id):
    """
    Retrieves the name of the warehouse based on the provided warehouse ID.

    This function maps a warehouse ID to its corresponding warehouse name. The mapping includes IDs 
    from all ShipStation accounts that use this application. If the warehouse ID is not found in the 
    mapping, the function returns `None`.

    Args:
        warehouse_id (int): The ID of the warehouse.

    Returns:
        str or None: The name of the warehouse if found, otherwise `None`.
    """
    warehouse_id_map = {
        590152: {'ss_account': 'sporticulture', 'warehouse': "Sporticulture"},
        791225: {'ss_account': 'sporticulture', 'warehouse': "Stallion Wholesale"}

    }

    warehouse_name = warehouse_id_map.get(warehouse_id, None)

    return warehouse_name




def get_store_name(store_id):
    """
    Retrieves the name of the store (sales channel) based on the provided store ID.

    This function maps a store ID to its corresponding store name. The mapping includes IDs 
    from all ShipStation accounts that use this application. If the store ID is not found in the 
    mapping, the function returns `None`.

    Args:
        store_id (int): The ID of the store (sales channel).

    Returns:
        str or None: The name of the store if found, otherwise `None`.
    """
    store_id_map = {
        315885: {'ss_account': 'sporticulture', 'store_name': 'Amazon'},
        341077: {'ss_account': 'sporticulture', 'store_name': 'HSN'},
        332340: {'ss_account': 'sporticulture', 'store_name': 'JoAnn Fabric & Crafts'},
        264327: {'ss_account': 'sporticulture', 'store_name': 'Manual Orders'},
        333906: {'ss_account': 'sporticulture', 'store_name': 'Replacement'},
        336544: {'ss_account': 'sporticulture', 'store_name': 'Sharper Image'},
        307866: {'ss_account': 'sporticulture', 'store_name': 'Sporticulture'},
        320975: {'ss_account': 'sporticulture', 'store_name': 'Sporticulture Wholesale'},
        319722: {'ss_account': 'sporticulture', 'store_name': 'Stadium Allstars'},
        337523: {'ss_account': 'sporticulture', 'store_name': 'TC EDI'},
        334045: {'ss_account': 'sporticulture', 'store_name': 'Walmart Wholesale'}
    }
    
    store_name = store_id_map.get(store_id, None)

    return store_name




def send_order_to_queue(order_object, sqs_client):
    """
    Sends the order to the appropriate SQS queue based on the shipstation_account.

    This function determines the correct SQS queue to send the order message to, 
    based on the shipstation_account of the order_object. The message is then sent 
    to the identified queue, along with metadata that includes the current queue name 
    and shipstation_account. The function returns a boolean indicating the success of 
    the operation.

    Args:
        order_object: The order object that contains all order details, including the 
                    shipstation_account attribute.
        sqs_client: The Boto3 SQS client used to interact with Amazon SQS.

    Returns:
        bool: True if the message was sent successfully, False otherwise.
        None: If the shipstation_account is not found in the queue mapping.

    Raises:
        ValueError: If the shipstation_account is not found in the queue mapping.
    """

    queue_name = 'SporticultureOrderQueue'

    # Get the URL of the target queue
    queue_url = sqs_client.get_queue_url(QueueName=queue_name)['QueueUrl']

    # Prepare the message body
    message_body = json.dumps(order_object.as_dict())

    # Include metadata with the message
    message_attributes = {
        'CurrentQueue': {
            'DataType': 'String',
            'StringValue': queue_name
        },
        'ShipStationAccount': {
            'DataType': 'String',
            'StringValue': "Sporticulture"
        }
    }

    # Send the message to the SQS queue
    response = sqs_client.send_message(
        QueueUrl=queue_url,
        MessageBody=message_body,
        MessageAttributes=message_attributes
    )

    # Validate if the message was sent successfully
    if response['ResponseMetadata']['HTTPStatusCode'] == 200:
        return True
    else:
        return False




def temp_order():

    # order = [{'orderId': 373751305, 'orderNumber': '114-7520265-1129052', 'orderKey': '114-7520265-1129052', 'orderDate': '2024-09-05T05:26:49.0000000', 'createDate': '2024-09-05T06:26:00.1600000', 'modifyDate': '2024-09-05T06:27:04.4400000', 'paymentDate': '2024-09-05T05:26:49.0000000', 'shipByDate': '2024-09-06T17:00:00.0000000', 'orderStatus': 'awaiting_shipment', 'customerId': 178996597, 'customerUsername': '5qvz04xhz9s1t6z@marketplace.amazon.com', 'customerEmail': '5qvz04xhz9s1t6z@marketplace.amazon.com', 'billTo': {'name': 'Paul Christopher Erdman', 'company': None, 'street1': '5629 N CROW DR', 'street2': '', 'street3': '', 'city': 'ELOY', 'state': 'AZ', 'postalCode': '85131-3186', 'country': 'US', 'phone': '+1 346-307-9643 ext. 61225', 'residential': None, 'addressVerified': None}, 'shipTo': {'name': 'Paul C Erdman', 'company': '', 'street1': '5629 N CROW DR', 'street2': '', 'street3': '', 'city': 'ELOY', 'state': 'AZ', 'postalCode': '85131-3186', 'country': 'US', 'phone': '+1 346-307-9643 ext. 61225', 'residential': True, 'addressVerified': 'Address validated successfully'}, 'items': [{'orderItemId': 1202218626703, 'lineItemKey': '108747413757521', 'sku': 'SCARLBAL', 'name': 'NFL Baltimore Ravens - Scarecrow', 'imageUrl': 'https://m.media-amazon.com/images/I/616rjsXJfRL.jpg', 'weight': {'value': 44.0, 'units': 'ounces', 'WeightUnits': 1}, 'quantity': 1, 'unitPrice': 39.99, 'taxAmount': 3.88, 'shippingAmount': 0.0, 'warehouseLocation': 'Sporticulture', 'options': [], 'productId': 22332917, 'fulfillmentSku': 'SCARLBAL', 'adjustment': False, 'upc': '840331402155', 'createDate': '2024-09-05T06:26:00.11', 'modifyDate': '2024-09-05T06:26:00.11'}], 'orderTotal': 43.87, 'amountPaid': 43.87, 'taxAmount': 3.88, 'shippingAmount': 0.0, 'customerNotes': None, 'internalNotes': None, 'gift': False, 'giftMessage': None, 'paymentMethod': 'Other', 'requestedShippingService': 'Standard Std US D2D Dom', 'carrierCode': 'ups_walleted', 'serviceCode': 'ups_ground', 'packageCode': 'package', 'confirmation': 'none', 'shipDate': None, 'holdUntilDate': None, 'weight': {'value': 44.0, 'units': 'ounces', 'WeightUnits': 1}, 'dimensions': {'units': 'inches', 'length': 36.0, 'width': 12.0, 'height': 4.0}, 'insuranceOptions': {'provider': None, 'insureShipment': False, 'insuredValue': 0.0}, 'internationalOptions': {'contents': None, 'customsItems': None, 'nonDelivery': None}, 'advancedOptions': {'warehouseId': 590152, 'nonMachinable': False, 'saturdayDelivery': False, 'containsAlcohol': False, 'mergedOrSplit': False, 'mergedIds': [], 'parentId': None, 'storeId': 315885, 'customField1': '09/13/2024 06:59:59', 'customField2': '', 'customField3': '', 'source': 'amazon', 'billToParty': None, 'billToAccount': None, 'billToPostalCode': None, 'billToCountryCode': None, 'billToMyOtherAccount': 661125}, 'tagIds': None, 'userId': None, 'externallyFulfilled': False, 'externallyFulfilledBy': None, 'externallyFulfilledById': None, 'externallyFulfilledByName': None, 'labelMessages': None}
    # ]
    order = [{'orderId': 373704169, 'orderNumber': 'CBSD1255102-1', 'orderKey': '5838552334584', 'orderDate': '2024-09-04T20:36:14.0000000', 'createDate': '2024-09-04T21:14:17.8500000', 'modifyDate': '2024-09-04T21:15:15.8200000', 'paymentDate': '2024-09-04T20:36:14.0000000', 'shipByDate': None, 'orderStatus': 'awaiting_shipment', 'customerId': 137131315, 'customerUsername': '7061651816696', 'customerEmail': 'logistics@knocking.com', 'billTo': {'name': 'Knocking Order', 'company': None, 'street1': None, 'street2': None, 'street3': None, 'city': None, 'state': None, 'postalCode': None, 'country': None, 'phone': None, 'residential': None, 'addressVerified': None}, 'shipTo': {'name': 'Jimmy Harris', 'company': None, 'street1': '109 OAKWOOD ST', 'street2': '', 'street3': None, 'city': 'HIGH POINT', 'state': 'NC', 'postalCode': '27262-4831', 'country': 'US', 'phone': None, 'residential': True, 'addressVerified': 'Address validated successfully'}, 'items': [{'orderItemId': 1202218542306, 'lineItemKey': '14477092323576', 'sku': 'CARDLMIA', 'name': 'NFL Miami Dolphins - LED Car Door Light', 'imageUrl': 'https://cdn.shopify.com/s/files/1/1849/5863/products/Miami-Dolphins-LED-Car-Door-Light-Ad-Collage-Square.jpg?v=1631553936', 'weight': {'value': 6.0, 'units': 'ounces', 'WeightUnits': 1}, 'quantity': 1, 'unitPrice': 9.97, 'taxAmount': 0.0, 'shippingAmount': 0.0, 'warehouseLocation': 'Sporticulture', 'options': [{'name': 'Ships by', 'value': 'Sep 09, 2024'}, {'name': ' dpx order item id', 'value': '119780118'}], 'productId': 11692066, 'fulfillmentSku': 'CARDLMIA', 'adjustment': False, 'upc': '810028056282', 'createDate': '2024-09-04T21:14:17.82', 'modifyDate': '2024-09-04T21:14:17.82'}], 'orderTotal': 9.97, 'amountPaid': 9.97, 'taxAmount': 0.0, 'shippingAmount': 0.0, 'customerNotes': '_purchase_order: CBSD1255102-1<br/>_purchase_order_source: Knocking<br/>_dpx_purchase_order_id: 48055953<br/>_dpx_token: c40763cade0deec4cec2a6f549cd6c', 'internalNotes': None, 'gift': False, 'giftMessage': None, 'paymentMethod': '', 'requestedShippingService': 'Standard', 'carrierCode': 'ups_walleted', 'serviceCode': 'ups_ground_saver', 'packageCode': 'package', 'confirmation': 'none', 'shipDate': None, 'holdUntilDate': None, 'weight': {'value': 6.0, 'units': 'ounces', 'WeightUnits': 1}, 'dimensions': {'units': 'inches', 'length': 6.0, 'width': 4.0, 'height': 4.0}, 'insuranceOptions': {'provider': None, 'insureShipment': False, 'insuredValue': 0.0}, 'internationalOptions': {'contents': None, 'customsItems': None, 'nonDelivery': None}, 'advancedOptions': {'warehouseId': 590152, 'nonMachinable': False, 'saturdayDelivery': False, 'containsAlcohol': False, 'mergedOrSplit': False, 'mergedIds': [], 'parentId': None, 'storeId': 307866, 'customField1': None, 'customField2': None, 'customField3': None, 'source': 'shopify', 'billToParty': None, 'billToAccount': None, 'billToPostalCode': None, 'billToCountryCode': None, 'billToMyOtherAccount': 661125}, 'tagIds': None, 'userId': None, 'externallyFulfilled': False, 'externallyFulfilledBy': None, 'externallyFulfilledById': None, 'externallyFulfilledByName': None, 'labelMessages': None}]

    return order

def temp_sporticulture_order():
    order = [{'orderId': 363991552, 'orderNumber': 'EDI2024008225', 'orderKey': 'EDI2024008225', 'orderDate': '2024-08-05T11:05:47.3630000', 'createDate': '2024-08-05T11:06:06.6100000', 'modifyDate': '2024-08-19T14:23:18.9400000', 'paymentDate': '2024-08-05T11:05:47.3630000', 'shipByDate': None, 'orderStatus': 'awaiting_shipment', 'customerId': None, 'customerUsername': None, 'customerEmail': None, 'billTo': {'name': ' ', 'company': None, 'street1': None, 'street2': None, 'street3': None, 'city': None, 'state': None, 'postalCode': None, 'country': None, 'phone': None, 'residential': None, 'addressVerified': None}, 'shipTo': {'name': 'Store 173 - Lubbock Canyon West', 'company': None, 'street1': '5017 MILWAUKEE AVE STE 100', 'street2': '', 'street3': None, 'city': 'LUBBOCK', 'state': 'TX', 'postalCode': '79407-3810', 'country': 'US', 'phone': None, 'residential': False, 'addressVerified': 'Address validated successfully'}, 'items': [{'orderItemId': 1202206261366, 'lineItemKey': None, 'sku': 'INFLCSFTT', 'name': 'Collegiate Texas Tech Red Raiders - Inflatable Crazy Sports Fan', 'imageUrl': None, 'weight': {'value': 38.0, 'units': 'ounces', 'WeightUnits': 1}, 'quantity': 8, 'unitPrice': 0.0, 'taxAmount': None, 'shippingAmount': None, 'warehouseLocation': 'Stallion Wholesale', 'options': [], 'productId': 26513362, 'fulfillmentSku': 'INFLCSFTT', 'adjustment': False, 'upc': None, 'createDate': '2024-08-05T11:05:47.363', 'modifyDate': '2024-08-05T11:05:47.363'}], 'orderTotal': 0.0, 'amountPaid': 0.0, 'taxAmount': 0.0, 'shippingAmount': 0.0, 'customerNotes': None, 'internalNotes': None, 'gift': False, 'giftMessage': None, 'paymentMethod': None, 'requestedShippingService': 'UPS', 'carrierCode': 'ups', 'serviceCode': 'ups_ground', 'packageCode': 'package', 'confirmation': 'none', 'shipDate': None, 'holdUntilDate': None, 'weight': {'value': 288.0, 'units': 'ounces', 'WeightUnits': 1}, 'dimensions': None, 'insuranceOptions': {'provider': None, 'insureShipment': False, 'insuredValue': 0.0}, 'internationalOptions': {'contents': None, 'customsItems': None, 'nonDelivery': None}, 'advancedOptions': {'warehouseId': 791225, 'nonMachinable': False, 'saturdayDelivery': False, 'containsAlcohol': False, 'mergedOrSplit': False, 'mergedIds': [], 'parentId': None, 'storeId': 320975, 'customField1': None, 'customField2': None, 'customField3': None, 'source': 'SAMPLER STORES INC. dba RALLY HOUSE', 'billToParty': 'third_party', 'billToAccount': '692171', 'billToPostalCode': '66215', 'billToCountryCode': 'US', 'billToMyOtherAccount': 276012}, 'tagIds': [55428], 'userId': None, 'externallyFulfilled': False, 'externallyFulfilledBy': None, 'externallyFulfilledById': None, 'externallyFulfilledByName': None, 'labelMessages': None}
]

    return order


if __name__ == "__main__":
    user,secret = get_secret('sporticulture_shipstation')
    print(user)
    print(secret)