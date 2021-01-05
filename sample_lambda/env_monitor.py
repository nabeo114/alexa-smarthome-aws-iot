import logging
import os
import boto3
import json

logger = logging.getLogger()
logger.setLevel(logging.INFO)

class EnvMonitor:
    def __init__(self):
        self.dynamodb = boto3.resource('dynamodb', region_name=os.environ['Region'])
        self.table = self.dynamodb.Table(os.environ['TableName'])

        self.update_data()

    def get_temperature(self):
        self.update_data()
        return float(self.temperature)

    def get_humidity(self):
        self.update_data()
        return float(self.humidity)

    def get_pressure(self):
        self.update_data()
        return float(self.pressure)

    def update_data(self):
        response = self.table.get_item(Key = {os.environ['PartitionKey']: os.environ['PartitionName']})
        logger.info(response)
        self.temperature = response["Item"]["temperature"]
        self.humidity = response["Item"]["humidity"]
        self.pressure = response["Item"]["pressure"]
