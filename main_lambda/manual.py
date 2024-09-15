import sys
import os
import time
# Add the parent directory to the Python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from sp_batch_lambda.main import process_batch

from sp_batch_lambda.main import process_batch
from main_lambda.main import main


def manual_run():
    order_list = process_batch()


    for order in order_list:
        
        if order.order_number.startswith("DS"):
            if len(order.items) > 1 or order.items[0].quantity > 1:
                continue
            if order.tag_ids is not None and 55809 in order.tag_ids:
                continue
            main(order)
            time.sleep(0.25)

    return True



if __name__ == "__main__":

    success = manual_run()
    if success:
        print("======All orders processed======\n\n")
    else:
        print("======Some orders failed======\n\n")