from websocket import create_connection
import json

ws = create_connection("ws://localhost:2020/")


def generate_qr():
    ws.send(json.dumps({"command": "qr"}))


def send_message():
    data = {
        'attributes': {
            'epoch': '103',
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
                            'value': '57322740958@s.whatsapp.net'
                        },
                        {
                            'type': 'fromme',
                            'value': 1
                        },
                        {
                            'type': 'messageid',
                            'value': '3EB06792C2106FE24217'
                        },
                        {
                            'type': 'message',
                            'value': [
                                {
                                    'type': 'extended-message',
                                    'value': [
                                        {
                                            'type': 'text',
                                            'value': 'prova1234567890'
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
                            'value': 1481879713
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
'''
