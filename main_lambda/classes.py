from dataclasses import dataclass, field, asdict
from typing import Optional, List, Dict, Union, Any
from datetime import datetime, timedelta, time
import pytz


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

    def as_dict(self):
        return asdict(self)

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

    def as_dict(self):
        return asdict(self)

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
    ship_date:                  Optional[str] = None
    is_expedited:               Optional[bool] = False

    def __post_init__(self):
        if self.ship_date is None:
            self.ship_date = self.get_default_ship_date()

        if self.requested_shipping_service.startswith("Express") or self.requested_shipping_service.startswith("Expedited"):
            self.is_expedited = True

    @staticmethod
    def get_default_ship_date():
        est = pytz.timezone('US/Eastern')
        now = datetime.now(est)
        noon = datetime.combine(now.date(), time(12, 0)).replace(tzinfo=est)
        weekday = now.weekday()  # Monday is 0 and Sunday is 6

        if now < noon and weekday < 5:  # Weekday before noon
            return now.strftime('%Y-%m-%d')
        elif now >= noon and weekday in [4, 5, 6]:  # Friday, Saturday, or Sunday after noon
            next_monday = now + timedelta(days=(7 - weekday))
            return next_monday.strftime('%Y-%m-%d')
        elif now >= noon and weekday in [0, 1, 2, 3]:  # Monday to Thursday after noon
            tomorrow = now + timedelta(days=1)
            return tomorrow.strftime('%Y-%m-%d')
        else:
            return None

@dataclass
class Order:
    Shipment:                           Shipment
    Customer:                           Customer
    ss_client:                          Optional[object]
    fedex_session:                      Optional[object]
    ups_session:                        Optional[object]
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
    trading_partner:                    str = field(init=False)
    list_of_carriers:                   List[str] = field(init=False)
    deliver_by_date:                    str = field(init=False)
    product_type:                       Optional[str] = None
    is_single_stream:                   bool = field(init=False)
    is_multi_order:                     bool = False
    is_double_order:                    bool = False
    is_complex_order:                   bool = False
    rates:                              Dict = field(default_factory=dict)
    winning_rate:                       Dict = field(default_factory=dict)
    mapping_services:                   Dict = field(default_factory=dict)

    def __post_init__(self):
        # Set deliver_by_date based on Shipment.advanced_options['custom_field_1']
        if self.Shipment.advanced_options and self.Shipment.advanced_options.get('custom_field_1'):
            self.deliver_by_date = self.Shipment.advanced_options['custom_field_1']
        else:
            self.deliver_by_date = (datetime.now() + timedelta(days=7)).strftime('%m/%d/%Y %H:%M:%S')

        # If certain products are found in the order, set is_single_stream to True --> (surepost and ground saver note allowed)
        single_stream_skus = ["MGLMP", "SCARL", "CER"]
        self.is_single_stream = any(
            item.sku.startswith(tuple(single_stream_skus)) for item in self.items
        )


        # Modify Shipment based on warehouse value
        self.update_shipment_based_on_warehouse()
        # Set trading partner
        self.set_trading_partner()

    def set_trading_partner(self):

        if self.store_name == "TC EDI":
            if self.order_number.startswith("DS"):
                self.trading_partner = "Fanatics"
                self.list_of_carriers = ["External Account"]
            elif self.order_number.startswith("7"):
                self.trading_partner = "Target"
                self.list_of_carriers = ["External Account"]
            elif self.order_number.startswith("3"):
                self.trading_partner = "Rally House"
                self.list_of_carriers = ["Automated on Shipstation UI"]
        
        elif self.store_name == "Amazon":
            self.trading_partner = "Amazon"
            self.list_of_carriers = ["ups", "fedex", "stamps_com", "ups_walleted"]

        elif self.store_name == "JoAnn Fabric & Crafts":
            self.trading_partner = "JoAnn"
            self.list_of_carriers = ["Automated on Shipstation UI"]

        elif self.store_name == "Sporticulture":
            cbs_keywords = ["CBSD", "RSAD", "AMSD"]
            for word in cbs_keywords:
                if word in self.order_number:
                    self.trading_partner = "CBS"
                    self.list_of_carriers = ["ups", "ups_walleted", "fedex", "stamps_com"]
                    break
                else:
                    self.trading_partner = "Sporticulture"
                    self.list_of_carriers = ["ups", "ups_walleted", "fedex", "stamps_com"]

        
        elif self.store_name == "Sharper Image":
            self.trading_partner = "Sharper Image"
            self.list_of_carriers = ["Automated on Shipstation UI"]
        
        elif self.store_name == "Stadium Allstars":
            self.trading_partner = "Stadium Allstars"
            self.list_of_carriers = ["Automated on Shipstation UI"]
        
        elif self.store_name == "Sporticulture Wholesale":
            self.trading_partner = "Sporticulture Wholesale"
        
        elif self.store_name == "Walmart Wholesale":
            self.trading_partner = "Walmart"
            self.list_of_carriers = []

        else: 
            self.trading_partner = "Unknown"
            self.list_of_carriers = []
        

    def update_shipment_based_on_warehouse(self):
        # Initialize warehouse attributes using warehouse name
        if self.warehouse_name['warehouse'] == "Stallion Wholesale":
            self.Shipment.warehouse.postal_code = "46203"
            self.Shipment.warehouse.city = "INDIANAPOLIS"
            self.Shipment.warehouse.state = "IN"
            self.Shipment.warehouse.country = "US"
            self.Shipment.warehouse.street1 = "1435 E NAOMI ST"
            self.Shipment.warehouse.phone = "3174064033"
            self.Shipment.warehouse.residential = False
            self.Shipment.warehouse.name = "Stallion Wholesale"

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
