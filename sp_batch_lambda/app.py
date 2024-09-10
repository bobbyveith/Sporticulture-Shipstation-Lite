import json
import traceback

# Local Imports
from main import process_batch

def lambda_handler(event, context):
    try:
        # # Extract the unique ID from pathParameters
        # unique_id = event['pathParameters']['uniqueid']
        
        # # Extract the body and parse it as JSON
        # body = json.loads(event['body'])
        # resource_url = body['resource_url']

        # # if unique_id == '12345' and resource_url == 'test':
        # #     return {
        # #         'statusCode': 200,
        # #         'body': json.dumps({'message': 'Test successful'}),x
        # #     }
        
        # # Pass the unique ID, resource URL, and resource type to the main processing function
        #processed_orders = process_batch(unique_id, resource_url)
        processed_orders = process_batch()

        # Return a successful response
        return {
            'statusCode': 200,
            'body': json.dumps("Orders Processed Successfully") #json.dumps(processed_orders, indent=4)  # Pretty-print with indentation
        }

    except Exception as e:
        # Capture the traceback
        error_message = f"Some Issue happened inside batch_lambda process_batch() --> {e}"
        traceback_str = traceback.format_exc()

        # Return the error message with the traceback
        return {
            'statusCode': 500,
            'body': f'{error_message}\nTraceback:\n{traceback_str}'
        }
