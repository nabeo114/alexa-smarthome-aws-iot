# -*- coding: utf-8 -*-

# Copyright 2017 Amazon.com, Inc. or its affiliates. All Rights Reserved.
#
# Licensed under the Amazon Software License (the "License"). You may not use this file except in
# compliance with the License. A copy of the License is located at
#
#    http://aws.amazon.com/asl/
#
# or in the "license" file accompanying this file. This file is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, express or implied. See the License for the specific
# language governing permissions and limitations under the License.

"""Alexa Smart Home Lambda Function Sample Code.

This file demonstrates some key concepts when migrating an existing Smart Home skill Lambda to
v3, including recommendations on how to transfer endpoint/appliance objects, how v2 and vNext
handlers can be used together, and how to validate your v3 responses using the new Validation
Schema.

Note that this example does not deal with user authentication, only uses virtual devices, omits
a lot of implementation and error handling to keep the code simple and focused.
"""

import logging
import time
import json
import uuid

# Imports for v3 validation
from validation import validate_message

# Setup logger
logger = logging.getLogger()
logger.setLevel(logging.INFO)

from ac_remote import AcRemote
ac_remote = AcRemote()

from env_monitor import EnvMonitor
env_monitor = EnvMonitor()

# To simplify this sample Lambda, we omit validation of access tokens and retrieval of a specific
# user's appliances. Instead, this array includes a variety of virtual appliances in v2 API syntax,
# and will be used to demonstrate transformation between v2 appliances and v3 endpoints.
SAMPLE_APPLIANCES = [
    {
        "applianceId": "endpoint-004",
        "manufacturerName": "IR TEST (AC remote)",
        "modelName": "Smart Thermostat",
        "version": "1",
        "friendlyName": "エアコン",
        "friendlyDescription": "自宅のエアコンのリモコン制御が可能",
        "isReachable": True,
        "actions": [
            "setTargetTemperature",
            "incrementTargetTemperature",
            "decrementTargetTemperature",
            "getTargetTemperature",
            "getTemperatureReading"
        ],
        "additionalApplianceDetails": {}
    }
]

def lambda_handler(request, context):
    """Main Lambda handler.

    Since you can expect both v2 and v3 directives for a period of time during the migration
    and transition of your existing users, this main Lambda handler must be modified to support
    both v2 and v3 requests.
    """

    try:
        logger.info("Directive:")
        logger.info(json.dumps(request, indent=4, sort_keys=True))

        version = get_directive_version(request)

        if version == "3":
            logger.info("Received v3 directive!")
            if request["directive"]["header"]["name"] == "Discover":
                response = handle_discovery_v3(request)
            else:
                response = handle_non_discovery_v3(request)

        else:
            logger.info("Received v2 directive!")
            if request["header"]["namespace"] == "Alexa.ConnectedHome.Discovery":
                response = handle_discovery()
            else:
                response = handle_non_discovery(request)

        logger.info("Response:")
        logger.info(json.dumps(response, indent=4, sort_keys=True))

        #if version == "3":
            #logger.info("Validate v3 response")
            #validate_message(request, response)

        return response
    except ValueError as error:
        logger.error(error)
        raise

# v2 handlers
def handle_discovery():
    header = {
        "namespace": "Alexa.ConnectedHome.Discovery",
        "name": "DiscoverAppliancesResponse",
        "payloadVersion": "2",
        "messageId": get_uuid()
    }
    payload = {
        "discoveredAppliances": SAMPLE_APPLIANCES
    }
    response = {
        "header": header,
        "payload": payload
    }
    return response

def handle_non_discovery(request):
    request_name = request["header"]["name"]

    if request_name == "TurnOnRequest":
        header = {
            "namespace": "Alexa.ConnectedHome.Control",
            "name": "TurnOnConfirmation",
            "payloadVersion": "2",
            "messageId": get_uuid()
        }
        payload = {}
    elif request_name == "TurnOffRequest":
        header = {
            "namespace": "Alexa.ConnectedHome.Control",
            "name": "TurnOffConfirmation",
            "payloadVersion": "2",
            "messageId": get_uuid()
        }
    # other handlers omitted in this example
    payload = {}
    response = {
        "header": header,
        "payload": payload
    }
    return response

# v2 utility functions
def get_appliance_by_appliance_id(appliance_id):
    for appliance in SAMPLE_APPLIANCES:
        if appliance["applianceId"] == appliance_id:
            return appliance
    return None

def get_utc_timestamp(seconds=None):
    return time.strftime("%Y-%m-%dT%H:%M:%S.00Z", time.gmtime(seconds))

def get_uuid():
    return str(uuid.uuid4())

# v3 handlers
def handle_discovery_v3(request):
    endpoints = []
    for appliance in SAMPLE_APPLIANCES:
        endpoints.append(get_endpoint_from_v2_appliance(appliance))

    response = {
        "event": {
            "header": {
                "namespace": "Alexa.Discovery",
                "name": "Discover.Response",
                "payloadVersion": "3",
                "messageId": get_uuid()
            },
            "payload": {
                "endpoints": endpoints
            }
        }
    }
    return response

def handle_non_discovery_v3(request):
    request_namespace = request["directive"]["header"]["namespace"]
    request_name = request["directive"]["header"]["name"]

    if request_namespace == "Alexa.PowerController":
        if request_name == "TurnOn":
            value = "ON"
            ac_remote.set_power_on()
        else:
            value = "OFF"
            ac_remote.set_power_off()

        response = {
            "context": {
                "properties": [
                    {
                        "namespace": "Alexa.PowerController",
                        "name": "powerState",
                        "value": value,
                        "timeOfSample": get_utc_timestamp(),
                        "uncertaintyInMilliseconds": 0
                    }
                ]
            },
            "event": {
                "header": {
                    "namespace": "Alexa",
                    "name": "Response",
                    "payloadVersion": "3",
                    "messageId": get_uuid(),
                    "correlationToken": request["directive"]["header"]["correlationToken"]
                },
                "endpoint": {
                    "scope": {
                        "type": "BearerToken",
                        "token": "access-token-from-Amazon"
                    },
                    "endpointId": request["directive"]["endpoint"]["endpointId"]
                },
                "payload": {}
            }
        }
        return response

    elif request_namespace == "Alexa.ThermostatController":
        if request_name == "SetTargetTemperature":
            request_temperature = request["directive"]["payload"]["targetSetpoint"]["value"]
            ac_remote.set_temperature(request_temperature)
            
        elif request_name == "AdjustTargetTemperature":
            request_temperature = ac_remote.get_temperature() + request["directive"]["payload"]["targetSetpointDelta"]["value"]
            ac_remote.set_temperature(request_temperature)
            
        elif request_name == "SetThermostatMode":
            request_mode = request["directive"]["payload"]["thermostatMode"]["value"]
            
            if request_mode == "HEAT":
                ac_remote.set_mode_heat()
            elif request_mode == "COOL":
                ac_remote.set_mode_cool()

        response = {
            "event": {
                "header": {
                    "namespace": "Alexa",
                    "name": "Response",
                    "messageId": get_uuid(),
                    "correlationToken": request["directive"]["header"]["correlationToken"],
                    "payloadVersion": "3"
                },
                "endpoint": {
                    "endpointId": request["directive"]["endpoint"]["endpointId"]
                },
                "payload": {}
            },
            "context": {
                "properties": [
                    {
                        "namespace": "Alexa.ThermostatController",
                        "name": "thermostatMode",
                        "value": ac_remote.get_mode(),
                        "timeOfSample": get_utc_timestamp(),
                        "uncertaintyInMilliseconds": 0
                    },
                    {
                        "namespace": "Alexa.ThermostatController",
                        "name": "targetSetpoint",
                        "value": {
                            "value": ac_remote.get_temperature(),
                            "scale": "CELSIUS"
                        },
                        "timeOfSample": get_utc_timestamp(),
                        "uncertaintyInMilliseconds": 0
                    },
                    {
                        "namespace": "Alexa.TemperatureSensor",
                        "name": "temperature",
                        "value": {
                            "value": env_monitor.get_temperature(),
                            "scale": "CELSIUS"
                        },
                        "timeOfSample": get_utc_timestamp(),
                        "uncertaintyInMilliseconds": 0
                    }
                ]
            }
        }
        return response

    elif request_namespace == "Alexa":
        if request_name == "ReportState":
            response = {
                "event": {
                    "header": {
                        "namespace": "Alexa",
                        "name": "StateReport",
                        "messageId": get_uuid(),
                        "correlationToken": request["directive"]["header"]["correlationToken"],
                        "payloadVersion": "3"
                    },
                    "endpoint": {
                        "endpointId": request["directive"]["endpoint"]["endpointId"]
                    },
                    "payload": {}
                },
                "context": {
                    "properties": [
                        {
                            "namespace": "Alexa.ThermostatController",
                            "name": "thermostatMode",
                            "value": ac_remote.get_mode(),
                            "timeOfSample": get_utc_timestamp(),
                            "uncertaintyInMilliseconds": 0
                        },
                        {
                            "namespace": "Alexa.ThermostatController",
                            "name": "targetSetpoint",
                            "value": {
                                "value": ac_remote.get_temperature(),
                                "scale": "CELSIUS"
                            },
                            "timeOfSample": get_utc_timestamp(),
                            "uncertaintyInMilliseconds": 0
                        },
                        {
                            "namespace": "Alexa.PowerController",
                            "name": "powerState",
                            "value": ac_remote.get_power(),
                            "timeOfSample": get_utc_timestamp(),
                            "uncertaintyInMilliseconds": 0
                        },
                        {
                            "namespace": "Alexa.TemperatureSensor",
                            "name": "temperature",
                            "value": {
                                "value": env_monitor.get_temperature(),
                                "scale": "CELSIUS"
                            },
                            "timeOfSample": get_utc_timestamp(),
                            "uncertaintyInMilliseconds": 0
                        },
                        {
                            "namespace": "Alexa.EndpointHealth",
                            "name": "connectivity",
                            "value": {
                                "value": "OK"
                            },
                            "timeOfSample": get_utc_timestamp(),
                            "uncertaintyInMilliseconds": 0
                        }
                    ]
                }
            }
            return response

    elif request_namespace == "Alexa.Authorization":
        if request_name == "AcceptGrant":
            print("====== AcceptGrant directive is called. Your authorization code is :" + request["directive"]["payload"]["grant"]["code"]);
            response = {
                "event": {
                    "header": {
                        "namespace": "Alexa.Authorization",
                        "name": "AcceptGrant.Response",
                        "payloadVersion": "3",
                        "messageId": get_uuid()
                    },
                    "payload": {}
                }
            }
            return response

    # other handlers omitted in this example

# v3 utility functions
def get_endpoint_from_v2_appliance(appliance):
    endpoint = {
        "endpointId": appliance["applianceId"],
        "manufacturerName": appliance["manufacturerName"],
        "friendlyName": appliance["friendlyName"],
        "description": appliance["friendlyDescription"],
        "displayCategories": [],
        "cookie": appliance["additionalApplianceDetails"],
        "capabilities": []
    }
    endpoint["displayCategories"] = get_display_categories_from_v2_appliance(appliance)
    endpoint["capabilities"] = get_capabilities_from_v2_appliance(appliance)
    return endpoint

def get_directive_version(request):
    try:
        return request["directive"]["header"]["payloadVersion"]
    except:
        try:
            return request["header"]["payloadVersion"]
        except:
            return "-1"

def get_endpoint_by_endpoint_id(endpoint_id):
    appliance = get_appliance_by_appliance_id(endpoint_id)
    if appliance:
        return get_endpoint_from_v2_appliance(appliance)
    return None

def get_display_categories_from_v2_appliance(appliance):
    model_name = appliance["modelName"]
    if model_name == "Smart Thermostat": displayCategories = ["THERMOSTAT"]
    else: displayCategories = ["OTHER"]
    return displayCategories

def get_capabilities_from_v2_appliance(appliance):
    model_name = appliance["modelName"]
    if model_name == "Smart Thermostat":
        capabilities = [
            {
                "type": "AlexaInterface",
                "interface": "Alexa.ThermostatController",
                "version": "3",
                "properties": {
                    "supported": [
                        { "name": "targetSetpoint" },
                        { "name": "thermostatMode" }
                    ],
                    "proactivelyReported": True,
                    "retrievable": True
                },
                "configuration": {
                    "supportedModes": [ "HEAT", "COOL" ],
                    "supportsScheduling": False
                }
            },
            {
                "type": "AlexaInterface",
                "interface": "Alexa.PowerController",
                "version": "3",
                "properties": {
                    "supported": [
                        { "name": "powerState" }
                    ],
                    "proactivelyReported": True,
                    "retrievable": True
                }
            },
            {
                "type": "AlexaInterface",
                "interface": "Alexa.TemperatureSensor",
                "version": "3",
                "properties": {
                    "supported": [
                        { "name": "temperature" }
                    ],
                    "proactivelyReported": True,
                    "retrievable": True
                }
            }
        ]
    else:
        # in this example, just return simple on/off capability
        capabilities = [
            {
                "type": "AlexaInterface",
                "interface": "Alexa.PowerController",
                "version": "3",
                "properties": {
                    "supported": [
                        { "name": "powerState" }
                    ],
                    "proactivelyReported": True,
                    "retrievable": True
                }
            }
        ]

    # additional capabilities that are required for each endpoint
    endpoint_health_capability = {
        "type": "AlexaInterface",
        "interface": "Alexa.EndpointHealth",
        "version": "3",
        "properties": {
            "supported":[
                { "name":"connectivity" }
            ],
            "proactivelyReported": True,
            "retrievable": True
        }
    }
    alexa_interface_capability = {
        "type": "AlexaInterface",
        "interface": "Alexa",
        "version": "3"
    }
    capabilities.append(endpoint_health_capability)
    capabilities.append(alexa_interface_capability)
    return capabilities
