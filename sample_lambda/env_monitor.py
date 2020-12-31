import logging
import os
import boto3
import json

logger = logging.getLogger()
logger.setLevel(logging.INFO)

def get_env_temperature():
    dynamodb = boto3.resource('dynamodb', region_name=os.environ['Region'])
    table = dynamodb.Table(os.environ['TableName'])
    
    response = table.get_item(Key = {os.environ['PartitionKey']: os.environ['PartitionName']})
    logger.info(response)
    temperature = response["Item"]["temperature"]
    
    return float(temperature)