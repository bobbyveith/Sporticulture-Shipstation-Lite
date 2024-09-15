from dataclasses import dataclass, field, asdict
from typing import Optional, List, Dict, Union, Any
from datetime import datetime, timedelta


@dataclass
class Address:
    name:               Optional[str] = None
    company:            Optional[str] = None
    street1:            Optional[str] = None
    street2:            Optional[str] = None
    street3:            Optional[str] = None
    city:               Optional[str] = None
    state:              Optional[str] = None
    postal_code:        Optional[str] = None
    country:            Optional[str] = None
    phone:              Optional[str] = None
    residential:        Optional[bool] = None
    address_verified:   Optional[str] = None

@dataclass
class Item:
    order_item_id:          int
    line_item_key:          str
    sku:                    str
    name:                   str
    image_url:              str
    weight:                 Optional[Dict[str, Union[float, str]]]
    quantity:               int
    unit_price:             float
    tax_amount:             Optional[float]
    shipping_amount:        Optional[float]
    warehouse_location:     Optional[str]
    options:                Optional[List[Dict[str, str]]]
    product_id:             int
    fulfillment_sku:        Optional[str]
    adjustment:             bool
    upc:                    Optional[str]
    create_date:            str
    modify_date:            str

@dataclass
class Customer:
    customer_id:        int
    customer_username:  str
    customer_email:     str
    customer_notes:     Optional[str]
    internal_notes:     Optional[str]
    bill_to:            Address
    ship_to:            Address

@dataclass
class Shipment:
    carrier_code:               Optional[str]
    service_code:               Optional[str]
    requested_shipping_service: Optional[str]
    package_code:               Optional[str]
    confirmation:               str
    ship_date:                  Optional[str]
    ship_by_date:               Optional[str]
    weight:                     Optional[Dict[str, Union[float, str]]]
    dimensions:                 Optional[Dict[str, Union[float, str]]]
    insurance_options:          Optional[Dict[str, Union[str, bool, float]]]
    international_options:      Optional[Dict[str, Union[str, List[Dict[str, Union[str, int]]]]]]
    is_gift:                    Optional[bool]
    gift_message:               Optional[str]
    shipping_amount:            Optional[float]
    hold_until_date:            Optional[str]
    advanced_options:           Optional[Dict[str, Union[bool, str, int, None]]]
    warehouse:                  Address
    smart_post_date:            Optional[str] = None


@dataclass
class Order:
    Shipment:                           Shipment
    Customer:                           Customer
    items:                              List[Item]
    order_data_raw:                     Dict[str, Any] # Original Order Payload from Shipstation
    order_id:                           int
    order_number:                       str
    order_key:                          str
    order_date:                         str
    create_date:                        str
    modify_date:                        Optional[str]
    payment_date:                       Optional[str]
    order_status:                       str
    order_total:                        float
    amount_paid:                        float
    tax_amount:                         Optional[float]
    payment_method:                     Optional[str]
    tag_ids:                            Optional[List[int]]
    user_id:                            Optional[int]
    externally_fulfilled:               Optional[bool]
    externally_fulfilled_by:            Optional[str]
    externally_fulfilled_by_id:         Optional[str]
    externally_fulfilled_by_name:       Optional[str]
    label_messages:                     Optional[str]
    store_name:                         str
    webhook_batch_id:                   str
    shipstation_account:                str
    warehouse_name:                     Dict[str, str]
    deliver_by_date:                    str = field(init=False)
    is_multi_order:                     bool = False
    is_double_order:                    bool = False
    ss_client:                          Optional[object] = None
    fedex_session:                      Optional[object] = None
    ups_session:                        Optional[object] = None
    rates:                              Dict = field(default_factory=dict)
    winning_rate:                       Dict = field(default_factory=dict)
    mapping_services:                   Dict = field(default_factory=dict)

    def __post_init__(self):
        # Default deliver by date for orders without strict deliver by dates
        self.deliver_by_date = (datetime.now() + timedelta(days=5)).strftime('%m/%d/%Y %H:%M:%S')

        # Modify Shipment based on warehouse value
        self.update_shipment_based_on_warehouse()

    def update_shipment_based_on_warehouse(self):
        if self.warehouse_name['warehouse'] is not None:
            # Initialize warehouse attributes using warehouse name
            if self.warehouse_name['warehouse'] == "SHIPPING DEPARTMENT":
                self.Shipment.warehouse.postal_code = "46203"
                self.Shipment.warehouse.city = "INDIANAPOLIS"
                self.Shipment.warehouse.state = "IN"
                self.Shipment.warehouse.country = "US"
                self.Shipment.warehouse.street1 = "1435 E NAOMI ST"
                self.Shipment.warehouse.phone = "3174064033"
                self.Shipment.warehouse.residential = False
                self.Shipment.warehouse.name = "SHIPPING DEPARTMENT"
            
            # Shipping values are same as 'stallion'
            elif self.warehouse_name['warehouse'] == "Winning Streak":
                self.Shipment.warehouse.postal_code = "46203"
                self.Shipment.warehouse.city = "INDIANAPOLIS"
                self.Shipment.warehouse.state = "IN"
                self.Shipment.warehouse.country = "US"
                self.Shipment.warehouse.street1 = "1435 E NAOMI ST"
                self.Shipment.warehouse.phone = "3174064033"
                self.Shipment.warehouse.residential = False
                self.Shipment.warehouse.name = "SHIPPING DEPARTMENT"

            # Shipping values are same as 'stallion'
            elif self.warehouse_name['warehouse'] == "Stallion Wholesale":
                self.Shipment.warehouse.postal_code = "46203"
                self.Shipment.warehouse.city = "INDIANAPOLIS"
                self.Shipment.warehouse.state = "IN"
                self.Shipment.warehouse.country = "US"
                self.Shipment.warehouse.street1 = "1435 E NAOMI ST"
                self.Shipment.warehouse.phone = "4432667788"
                self.Shipment.warehouse.residential = False
                self.Shipment.warehouse.name = "SHIPPING DEPARTMENT"

            
            elif self.warehouse_name['warehouse'] == "Sporticulture":
                self.Shipment.warehouse.postal_code = "21738"
                self.Shipment.warehouse.city = "Glenwood"
                self.Shipment.warehouse.state = "MD"
                self.Shipment.warehouse.country = "US"
                self.Shipment.warehouse.street1 = "14812 Burntwoods Road"
                self.Shipment.warehouse.phone = "4432667788"
                self.Shipment.warehouse.residential = False
                self.Shipment.warehouse.name = "Warehouse Location 1"

    # Used to help convert to JSON later
    def as_dict(self):
        return asdict(self)
