import json
import boto3
from main import main  # Assuming main.py is in the same directory and contains a function named main

sqs = boto3.client('sqs')

def lambda_handler(event, context):
    try:
        print(event)
        # Extract the body from the first record
        record = event['Records'][0]
        record_body = record['body']
        
        # Parse the JSON string in the body
        parsed_body = json.loads(record_body)
        
        # Extract the queue URL and receipt handle
        queue_url = record['eventSourceARN']
        receipt_handle = record['receiptHandle']
        
        # Pass the parsed body, queue URL, and receipt handle to the main function
        #result = main(parsed_body)

        # If result is true, delete the message from the queue
        # if result:
        #     sqs.delete_message(
        #         QueueUrl=queue_url,
        #         ReceiptHandle=receipt_handle
        #     )
        
        return {
            "statusCode": 200,
            "body": json.dumps({
                "message": "Success",
                #"result": result
            }),
        }
    except Exception as e:
        return {
            "statusCode": 500,
            "body": json.dumps({
                "message": "Error",
                "error": str(e)
            }),
        }
