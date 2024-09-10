#from functions import connect_to_api, get_batch_id, fetch_orders_with_retry, get_store_name
import functions
from classes import Order, Customer, Address, Item, Shipment # Comes from shipstation_layer (lambda_layer)
from utils import convert_keys_to_snake_case
import json

import boto3



# Initialize the SQS client to send order messages downstream the serverless architecture
sqs_client = boto3.client('sqs')


def process_batch():

    # Create connnection with shipstation
    # Client has built in functionality. Module for client lives in shiptation_layer (lambda_layer)
    ss_client = functions.connect_to_api()

    # Get total orders from the shipstation account 
    total_orders = functions.fetch_order_count(ss_client)
    print(f"Total orders: {total_orders}")

    # Fetch all orders from the shipstation account
    orders = functions.fetch_orders_with_retry(ss_client, total_orders)
    print(f"Orders: {len(orders)}")

    if orders:
        for order_data_raw in orders:
            # Tag id for "Ready to Ship"
            if order_data_raw.get('tagIds') is not None and 55809 in order_data_raw['tagIds']:
                print(f"Order {order_data_raw['orderNumber']} is already processed")
                continue
            
            # Convert keys from camelCase to snake_case
            order_data = convert_keys_to_snake_case(order_data_raw)

            # Create Address objects for bill_to and ship_to
            bill_to_address = Address(**order_data['bill_to'])
            ship_to_address = Address(**order_data['ship_to'])
            # Initialize an empty Address for warehouse
            warehouse_address = Address()

            # Initialize nested classes and extract customer data for Customer
            customer_data = functions.parse_customer_data(order_data)
            customer = Customer(
                bill_to=bill_to_address,
                ship_to=ship_to_address,
                **customer_data
            )

            # Extrace shipment related data and initialize Shipment
            shipment_data = functions.parse_shipment_data(order_data)
            shipment = Shipment(
                            warehouse=warehouse_address,
                            **shipment_data
                        )

            # Packs multiple Item objects whenever there are multiple item dictionaries in order_data['items']
            items = [Item(**item_data) for item_data in order_data['items']]

            # Initialize the Order class by unpacking the dictionary
            order = functions.parse_order_data(order_data)
            order_object = Order(
                Shipment=shipment,
                Customer=customer,
                items=items,
                shipstation_account='Sporticulture',
                webhook_batch_id = None,
                warehouse_name=functions.get_warehouse(order_data['advanced_options'].get('warehouse_id', None)),
                store_name=functions.get_store_name(order_data['advanced_options'].get('store_id', None)),
                order_data_raw= order_data,
                **order
            )

            successful = functions.send_order_to_queue(order_object, sqs_client)
            if successful:
                print(f"Order {order_object.order_key} sent to queue successfully")
                continue
            else:
                print(f"Order {order_object.order_key} failed to send to queue")
                continue



        return {"message": "[+] All orders sent to queue Successfully"}
    return {
            'statusCode': 504,
            'body': json.dumps('Failed to fetch data from ShipStation API after maximum retries.')
            }



if __name__ == "__main__":
    process_batch()