from classes import Address, Item, Shipment, Customer, Order
from typing import Dict


def init_order(body: Dict, ss_client: object, fedex_session: object, ups_session: object) -> Order:
    # Create Address instances for billing and shipping
    bill_to = Address(**body['Customer']['bill_to'])
    ship_to = Address(**body['Customer']['ship_to'])

    # Convert the warehouse dict in Shipment to an Address object
    warehouse_data = body['Shipment']['warehouse']
    warehouse_address = Address(**warehouse_data)
    
    # Update the Shipment data with the Address object for warehouse
    shipment_data = body['Shipment']
    shipment_data['warehouse'] = warehouse_address
    
    # Create Shipment instance
    shipment = Shipment(**shipment_data)
    
    # Create Customer instance
    customer = Customer(
        customer_id=body['Customer']['customer_id'],
        customer_username=body['Customer']['customer_username'],
        customer_email=body['Customer']['customer_email'],
        customer_notes=body['Customer']['customer_notes'],
        internal_notes=body['Customer']['internal_notes'],
        bill_to=bill_to,
        ship_to=ship_to
    )
    
    # Create Item instances
    items = [Item(**item) for item in body['items']]
    

    # Create Order instance
    order_object = Order(
        Shipment=shipment,
        Customer=customer,
        ss_client=ss_client,
        fedex_session=fedex_session,
        ups_session=ups_session,
        items=items,
        order_data_raw=body,
        order_id=body['order_id'],
        order_number=body['order_number'],
        order_key=body['order_key'],
        order_date=body['order_date'],
        create_date=body['create_date'],
        modify_date=body.get('modify_date'),
        payment_date=body.get('payment_date'),
        order_status=body['order_status'],
        order_total=body['order_total'],
        amount_paid=body['amount_paid'],
        tax_amount=body.get('tax_amount'),
        payment_method=body.get('payment_method'),
        tag_ids=body.get('tag_ids'),
        user_id=body.get('user_id'),
        externally_fulfilled=body.get('externally_fulfilled'),
        externally_fulfilled_by=body.get('externally_fulfilled_by'),
        externally_fulfilled_by_id=body.get('externally_fulfilled_by_id'),
        externally_fulfilled_by_name=body.get('externally_fulfilled_by_name'),
        label_messages=body.get('label_messages'),
        store_name=body['store_name'],
        webhook_batch_id=body['webhook_batch_id'],
        shipstation_account=body['shipstation_account'],
        warehouse_name=body['warehouse_name'],
        is_multi_order=body.get('is_multi_order', False),
        is_double_order=body.get('is_double_order', False),
        rates=body.get('rates', {}),
        winning_rate=body.get('winning_rate', {}),
        mapping_services=body.get('mapping_services', {})
    )
    
    return order_object