import re

def camel_to_snake(name: str) -> str:
    """
    Convert a camelCase string to snake_case.

    This function takes a string formatted in camelCase and converts it to snake_case by inserting 
    underscores before capital letters and converting the entire string to lowercase.

    Args:
        name (str): The camelCase string to convert.

    Returns:
        str: The converted snake_case string.

    Example:
        >>> camel_to_snake("orderItemId")
        'order_item_id'
    """
    return re.sub(r'(?<!^)(?=[A-Z])', '_', name).lower()



def convert_keys_to_snake_case(data):
    """
    Recursively convert all dictionary keys in a data structure from camelCase to snake_case.

    This function traverses a data structure (which may contain nested dictionaries or lists)
    and converts all keys in dictionaries from camelCase to snake_case using the `camel_to_snake` function.

    Args:
        data (Union[dict, list, Any]): The data structure to convert. This can be a dictionary, 
                                        a list, or any other type of data. Only dictionary keys 
                                        will be converted.

    Returns:
        Union[dict, list, Any]: The converted data structure with all dictionary keys in snake_case.

    Example:
        >>> convert_keys_to_snake_case({"orderId": 123, "orderDetails": {"orderItemId": 456}})
        {'order_id': 123, 'order_details': {'order_item_id': 456}}
    """
    if isinstance(data, dict):
        new_dict = {}
        for key, value in data.items():
            new_key = camel_to_snake(key)
            new_dict[new_key] = convert_keys_to_snake_case(value)  # Recursively apply to nested dictionaries
        return new_dict
    elif isinstance(data, list):
        return [convert_keys_to_snake_case(item) for item in data]
    else:
        return data
