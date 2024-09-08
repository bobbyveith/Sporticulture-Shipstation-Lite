


#====== Set Product Dims from API ======
def get_product_info(order_object, product_id):
    """
    Fetches product information from ShipStation using the provided product ID.

    Args:
        order_object (Order): The order object containing the ShipStation client.
        product_id (str): The ID of the product to fetch information for.

    Returns:
        dict: A dictionary containing the product information if successful, None otherwise.
    """
    try:
        response = order_object.ss_client.get(endpoint=f"/products/{product_id}")
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Error fetching product information for product ID {product_id}: {e}")
        return None



def get_product_dimensions(order_object, product_id):
    """
    Fetches product dimensions from ShipStation using the provided product ID.

    Args:
        order_object (Order): The order object containing the ShipStation client.
        product_id (str): The ID of the product to fetch information for.

    Returns:
        dict: A dictionary containing the product's length, width, and height.
            Returns None if the product information couldn't be fetched.
    """
    product_info = get_product_info(order_object, product_id)
    
    if product_info is None:
        return None
    
    dimensions = {
        "length": product_info.get("length"),
        "width": product_info.get("width"),
        "height": product_info.get("height")
    }
    
    return dimensions



def set_product_dimensions(order: Order) -> bool:
    """
    Sets the product dimensions for an order by fetching the information from ShipStation
    and updating the order.Shipment.dimensions attribute.

    Args:
        order (Order): The order object to update with product dimensions.

    Returns:
        bool: True if dimensions were successfully set, False otherwise.
    """
    # Assuming the first item's product_id is representative for the whole order
    if not order.items:
        print("No items in the order")
        return False

    product_id = order.items[0].product_id
    dimensions = get_product_dimensions(order, str(product_id))

    if dimensions is None:
        print(f"Could not fetch dimensions for product ID {product_id}")
        return False

    # Update order.Shipment.dimensions with the fetched dimensions
    order.Shipment.dimensions = {
        "length": float(dimensions["length"]),
        "width": float(dimensions["width"]),
        "height": float(dimensions["height"]),
        "units": "inches"
    }

    return True
#=========================================