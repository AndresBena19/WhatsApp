from websocket import create_connection
import json
import time
ws = create_connection("ws://localhost:2020/")

def getTimestamp():
    return int(time.time());


def generate_qr():
    ws.send(json.dumps({"command": "qr"}))


def send_message():
    data1 = {
        'attributes': {
            'epoch': '1',
            'type': 'relay'
        },
        'elements': 6,
        'name': 'action',
        'children': [
            {
                'attributes': {

                },
                'elements': 2,
                'name': 'message',
                'children': [
                    [
                        {
                            'type': 'jid',
                            'value': '573227409582@s.whatsapp.net'
                        },
                        {
                            'type': 'fromme',
                            'value': 1
                        },
                        {
                            'type': 'messageid',
                            'value': '3EB06792C2106FE24545'
                        },
                        {
                            'type': 'message',
                            'value': [
                                {
                                    'type': 'extended-message',
                                    'value': [
                                        {
                                            'type': 'text',
                                            'value': 'Muy buenas tardes'
                                        },
                                        {
                                            'type': 'context',
                                            'value': None
                                        }
                                    ]
                                }
                            ]
                        },
                        {
                            'type': 'timestamp',
                            'value': str(getTimestamp())
                        },
                        {
                            'type': 'status',
                            'value': 1
                        }
                    ]
                ]
            }
        ]
    }

    ws.send(json.dumps({"command": "send", "data": json.dumps({"to":'573227409582@s.whatsapp.net' ,"text": "hola"})}))




def close():
    ws.close()


def menu():
    print("\t1. Generate QR")
    print("\t2. Send Menssage")
    print("\t3. End connection")


while True:
    menu()
    opcionMenu = input("option >> ")

    if opcionMenu == 1:
        generate_qr()

    elif opcionMenu == 2:
        send_message()

    elif opcionMenu == 3:
        close()

'''
Get the members of group

437.--109,,["query","GroupMetadata","xxxxx-yyyyyy@g.us"]


https://github.com/Enrico204/whatsapp-decoding/blob/master/PROTOCOL.md
'''
