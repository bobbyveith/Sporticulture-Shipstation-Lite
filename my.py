import boto3

sqs = boto3.client('sqs')

def fetch_message_from_queue(queue_url):
    response = sqs.receive_message(
        QueueUrl=queue_url,
        MaxNumberOfMessages=1,
        WaitTimeSeconds=10
    )
    return response.get('Messages', [])


messages = fetch_message_from_queue('https://sqs.us-east-2.amazonaws.com/982081062525/SporticultureOrderQueue')

print(messages)