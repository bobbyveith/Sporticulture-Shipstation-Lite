import functions
import ups_api
from usps_api import get_usps_best_rate
from fedex_api import get_fedex_best_rate, create_fedex_session

from init_object import init_order

import traceback, json




__author__ = "Bobby Veith"
__company__ = "Sporticulture"

# =================== GLOBAL VARIABLES =========================
# For orders that failed the process on their first attemp
retry_list = []

# =================== CORE PROGRAM FUNCTIONS =============================

def initial_setup(order_data):
    '''
    This function is used to set up the program and intiated the data into python object
    '''
    # Set up the progam and get the list of orders and csv for customer logging
    functions.print_banner()

    print("======= Starting Initial Setup =======")
    # Connect to the ShipStation API
    print("Connecting to the ShipStation API...")
    ss_client = functions.connect_to_api()
    print("[+] Connected to the ShipStation API!\n\n")

    # Other Sessions
    fedex_session = create_fedex_session()
    ups_session = ups_api.create_ups_session()

    print(f"order_data: {order_data}")
    # Initialize the order object
    order = init_order(order_data, ss_client, fedex_session, ups_session)

    # Sets order attributes as needed
    functions.check_if_multi_order(order)

    successful = functions.set_product_dimensions(order)
    if not successful:
        tag = functions.tag_order(order, "No-Dims")
        print(f"[X] No dimensions available for order {order.order_number}")
        raise ValueError(f"No dimensions available for order {order.order_number}")
    
    functions.set_ship_date(order)

    return order




def initialize_order(order):
    print(f"[+] Starting Initialization for order: {order.order_key} | {order.store_name['store_name']}")
    print("\n")
    # Multi Orders have unique conditions for setting the Dimensions
    if order.is_multi_order or order.is_double_order or order.is_complex_order:
        print("This is a multi, double, or complex order")
        if not functions.tag_order(order, "Multi-Order"):
            print("[-] Warning: Could not tag order as multi-order")

    if not order.deliver_by_date:
        failure = (order, "No-DeliveryDate")
        retry_list.append(failure)
        return False
    return True




def get_shipping_rates(order):
    # Get rates for all carriers from ShipStation
    print("\n[+] Getting Shipstation rates for all carriers...")
    # Function fails if not dimenstions for order, function tags order with "No_Dims"
    if not functions.get_rates_for_all_carriers(order):
        functions.print_yellow("[!] Warning: Could not get carrier rates for order, skipping\n")
        # failure = (order, "No SS Carrier Rates") # Can be added in addition to "No-Dims Tag"
        # retry_list.append(failure)
        return False
    return True



def set_winning_rate(order):
    # When delivery to a PO Box, must use USPS shipping only
    if functions.is_po_box_delivery(order):
        if "stamps_com" not in order.list_of_carriers:
            return False
        order.winning_rate =  get_usps_best_rate(order)
        return True
    
    # Get winning UPS rate
    if "ups" in order.list_of_carriers or "ups_walleted" in order.list_of_carriers:
        ups_best = ups_api.get_ups_best_rate(order)
        if ups_best is False:
            failure = (order, "No UPS Rate")
            retry_list.append(failure)
            return False
        print(f"[+] UPS best rate: {ups_best}")
    else:
        ups_best = None


    # Get winning USPS rate
    if "stamps_com" in order.list_of_carriers:
        usps_best = get_usps_best_rate(order)
        if usps_best is False:
            failure = (order, "No USPS Rate")
            retry_list.append(failure)
            return False
        print(f"[+] USPS best rate: {usps_best}")
    else:
        usps_best = None    

    # Get winning FedEx rate
    if "fedex" in order.list_of_carriers:
        fedex_best = get_fedex_best_rate(order)
        if fedex_best is False:
            failure = (order, "No Fedex Rate")
            retry_list.append(failure)
            return False
        print(f"[+] FedEx best rate: {fedex_best}")
    else:
        fedex_best = None


    # Compare all the winning rates against each other and update winniner to order.winning_rate
    functions.get_champion_rate(order, ups_best=ups_best, fedex_best=fedex_best, usps_best=usps_best)
    print(f"[+] Champion rate: {order.winning_rate}")
    return True



def update_order(order):
    print("\n---------- Setting shipping for orders ----------")
        # Set the shipping for the order
    print("\n[+] Updating order: ", order.order_key)
    success = functions.create_or_update_order(order)
    if success:
        functions.tag_order(order, "Ready")
        functions.print_green("[+] Successfully Updated Carrier on Shipstation")
    else:
        functions.print_red(f"[X] Order shipping update not successful {order.order_key}")
        failure = (order, "Shipping not set")
        retry_list.append(failure)

    print("------------next order---------------------\n\n")
    return True


def main(order_data):


    global retry_list
    retry_list = []

    def full_program(order):
        if not initialize_order(order):
            return False
        
        if order.store_name == "Amazon" or order.store_name == "Sporticulture":
            successful = functions.update_warehouse_location(order)
            if not successful:
                # Variable not needed, just returns bool so..
                tag = functions.tag_order(order, "No-Warehouse")
                return False
            
            if not get_shipping_rates(order):
                return False

            if not set_winning_rate(order):
                return False
            
        if not update_order(order):
            return False
        return True
    
    def half_program(order):
        if order.store_name['store_name'] == "Amazon" or order.store_name['store_name'] == "Sporticulture":
            if not set_winning_rate(order):
                return False
        
        if not update_order(order):
            return False
        return True

# =======   START OF MAIN LOGIC   ========
    
    order = initial_setup(order_data)
    # print(f"order object: {order}\n\n")
    # raise Exception("test")


    valid_trading_partners = ["Amazon", "Rally House", "JoAnn", "CBS", "Sharper Image", "Stadium Allstars", "Sporticulture"]
    if order.trading_partner in valid_trading_partners:
        if order.Shipment.is_expedited:
            functions.tag_order(order, "Expedited")
        successful = full_program(order)
        if not successful:
            return False
        return True
    else:
        print(f"Order {order.order_key} not in valid trading partners")
        

    # Orders added to retry_list within the core functions
    if retry_list: # Global var
        reattempt_list = retry_list.copy()
        retry_list = []
        # If orders fail on second attempt, tag them and give up
        for order, reason in reattempt_list: # list of tuples
            functions.print_yellow(f"[!] Retrying Order: {order.order_key} because {reason}")
            if reason == "No-DeliveryDate" or reason == "No SS Carrier Rates":
                successful = full_program(order)
                if not successful:
                    functions.tag_order(order, reason)
                    functions.print_yellow("[!] Order tagged..")
            
            if reason == "No UPS Rate" or reason == "No USPS Rate" or reason == "No Fedex Rate":
                successful = half_program(order)
                if not successful:
                    functions.tag_order(order, reason)
                    functions.print_yellow("[!] Order tagged..")
            
            if reason == "Shipping not set":
                successful = update_order(order)
                if not successful:
                    functions.tag_order(order, reason)
                    functions.print_yellow("[!] Order tagged..")


if __name__ == "__main__":
    try:
        file_path = "events/local_main.json"
        with open(file_path, 'r') as file:
            order_data = json.load(file)

        main(order_data)
    except Exception as e:
        print("An error occurred:")
        print(traceback.format_exc())
        quit(1)