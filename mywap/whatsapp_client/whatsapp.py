import sys

sys.dont_write_bytecode = True

import base64
import datetime
import json
from threading import Thread

import traceback

import websocket
import curve25519
import pyqrcode

import pprint
from .utilities import *
from encoding.whatsapp_binary_reader import whatsappReadBinary
from encoding.whatsapp_binary_writter import whatsappWriteBinary

import datetime


class WhatsAppWebClient:
    websocketIsOpened = False
    onOpenCallback = None
    onMessageCallback = None
    onCloseCallback = None
    activeWs = None
    websocketThread = None
    messageQueue = {}  # maps message tags (provided by WhatsApp) to more information (description and callback)

    login_data = {
        "clientId": None,
        "serverRef": None,
        "privateKey": None,
        "publicKey": None,
        "key": {
            "encKey": None,
            "macKey": None
        }
    }
    connInfo = {
        "clientToken": None,
        "serverToken": None,
        "browserToken": None,
        "secret": None,
        "sharedSecret": None,
        "me": None
    }

    def __init__(self):
        websocket.enableTrace(True)
        self.data_server = ""
        self.message_tag = None
        self.message_content = None
        self.connect()

    @staticmethod
    def _save_json(data, path):
        with open(path, 'w') as outfile:
            json.dump(data, outfile, indent=4)

    @staticmethod
    def _save_contacts(contacts):
        contact_data = []

        for contact in contacts:
            value = {"user": contact[0],
                     "jid": contact[1].get("jid", None),
                     "short": contact[1].get("short", None),
                     "name": contact[1].get("name", None)}

            contact_data.append(value)

            WhatsAppWebClient._save_json(contact_data, "data/contacts.json")

    @staticmethod
    def _save_last_message(messages, type):

        messages_data = []

        for message in messages:
            value = {message["key"]["id"]: {"user": message["key"].get("remoteJid",None),
                                            "message": message.get("message", None),
                                            "date_time": datetime.datetime.fromtimestamp(
                                                float(message["messageTimestamp"])).isoformat()}}
            messages_data.append(value)

        WhatsAppWebClient._save_json(messages_data, "data/" + type + "_messages.json")

    @staticmethod
    def _verify_hmac(hmac_valid, data):

        if hmac_valid != data:
            raise ValueError("Hmac mismatch")

    def _save(self, process_data):

        if type(process_data[1]) is dict:
            if process_data[1].get("type", "") == "contacts":
                self._save_contacts(process_data[2])
            elif process_data[1].get("add", "") == "last":
                self._save_last_message(process_data[2], "last")
            elif process_data[1].get("add", "") == "before":
                self._save_last_message(process_data[2], "before")

    def onOpen(self, ws):
        print("Connection with whatsapp server")

    def onError(self, ws, error):
        print(error)

    def onClose(self, ws):
        print("WhatsApp backend Websocket closed.")

    def _onLogin(self):

        self.login_data["serverRef"] = json.loads(self.message_content)["ref"]
        self.login_data["privateKey"] = curve25519.Private()
        self.login_data["publicKey"] = self.login_data["privateKey"].get_public()

        qrCodeContents = self.login_data["serverRef"] + "," + base64.b64encode(
            self.login_data["publicKey"].serialize()) + "," + self.login_data["clientId"]
        big_code = pyqrcode.create(qrCodeContents, error='L', version=27, mode='binary')
        big_code.png('qr/code.png', scale=2)

        print("set server id: " + self.login_data["serverRef"])
        print("qr code contents: " + qrCodeContents)
        print(big_code)

    def _read_receive_data(self):
        processedData = ""
        if self.message_content != "":
            hmac_valid = HmacSha256(self.login_data["key"]["macKey"], self.message_content[32:])
            self._verify_hmac(hmac_valid, self.message_content[:32])

            decryptedMessage = AESDecrypt(self.login_data["key"]["encKey"], self.message_content[32:])

            try:
                processedData = whatsappReadBinary(decryptedMessage, True)
            except:
                processedData = {"traceback": traceback.format_exc().splitlines()}
            finally:
                self._save(processedData)

    def _onConnection(self, load_data):
        if isinstance(load_data, list) and len(load_data) > 0:  # check if the result is an array
            print(json.dumps(load_data))

            if load_data[0] == "Conn":

                self.connInfo["clientToken"] = load_data[1]["clientToken"]
                self.connInfo["serverToken"] = load_data[1]["serverToken"]
                self.connInfo["browserToken"] = load_data[1]["browserToken"]
                self.connInfo["me"] = load_data[1]["wid"]

                self.connInfo["secret"] = base64.b64decode(load_data[1]["secret"])
                self.connInfo["sharedSecret"] = self.login_data["privateKey"].get_shared_key(
                    curve25519.Public(self.connInfo["secret"][:32]), lambda a: a)

                sse = self.connInfo["sharedSecretExpanded"] = HKDF(self.connInfo["sharedSecret"], 80)

                hmac_valid = HmacSha256(sse[32:64], self.connInfo["secret"][:32] + self.connInfo["secret"][64:])

                self._verify_hmac(hmac_valid, self.connInfo["secret"][32:64])

                keysEncrypted = sse[64:] + self.connInfo["secret"][64:]
                keysDecrypted = AESDecrypt(sse[:32], keysEncrypted)

                self.login_data["key"]["encKey"] = keysDecrypted[:32]
                self.login_data["key"]["macKey"] = keysDecrypted[32:64]

            elif load_data[0] == "Stream":
                pass
            elif load_data[0] == "Props":
                pass

    def onMessage(self, ws, message):
        try:
            self.data_server = message.split(",", 1)
            self.message_tag = self.data_server[0]
            self.message_content = self.data_server[1]

            if self.message_tag in self.messageQueue:
                pend = self.messageQueue[self.message_tag]
                if pend["desc"] == "_login":
                    self._onLogin()
            else:
                try:
                    load_data = json.loads(self.message_content)
                except ValueError as e:
                    self._read_receive_data()
                else:
                    self._onConnection(load_data)
        except:
            print(traceback.format_exc())

    def connect(self):
        self.activeWs = websocket.WebSocketApp("wss://w1.web.whatsapp.com/ws",
                                               on_message=self.onMessage,
                                               on_error=self.onError,
                                               on_open=self.onOpen,
                                               on_close=self.onClose,
                                               header={"Origin: https://web.whatsapp.com"})

        self.websocketThread = Thread(target=self.activeWs.run_forever)
        self.websocketThread.daemon = True
        self.websocketThread.start()

    def generateQRCode(self, callback=None):
        tag = str(getTimestamp())

        self.login_data["clientId"] = base64.b64encode(os.urandom(16))
        self.messageQueue[tag] = {"desc": "_login", "callback": callback}
        message = tag + ',["admin","init",[0,2,9929],["Chromium at ' + datetime.datetime.now().isoformat() + '","Chromium"],"' + \
                  self.login_data["clientId"] + '",true]'

        self.activeWs.send(message)

    def send_message_whatsapp(self, _data, tag):
        data = json.loads(_data)
        """
        payload = tag + json.dumps(['action', None, [{'key': {'fromMe': True,
                                                              'id': '6CDE639D52E1ED9C097C',
                                                              'remoteJid': '573227409582@s.whatsapp.net'},
                                                      'message': {
                                                          'conversation': 'Message sent by github.com/Rhymen/go-whatsapp'},
                                                      'messageTimestamp': '1532905824',
                                                      'status': 'PENDING'}]])

        payload = json.dumps(["action", {'epoch': 1, 'type': 'relay'}, [{"key": {"remoteJid": data["to"], "FromMe":True}}, {"message": {"conversation": data["text"]}}, {"messageTimestamp": getTimestamp()}, {"status":"PENDING"}]])
        info = WhatsAppEncrypt(self.login_data["key"]["encKey"], self.login_data["key"]["macKey"], payload)

        gg = whatsappWriteBinary(info)

        # info= encryptmessage(str(getTimestamp()), payload, {"encKey": self.login_data["key"]["encKey"], 'macKey': self.login_data["key"]["macKey"]})
        self.activeWs.send(gg)
        """
        pass

    def disconnect(self):
        self.activeWs.send(
            'goodbye,,["admin","Conn","disconnect"]')  # WhatsApp server closes connection automatically when client wants to disconnect
    # time.sleep(0.5)
    # self.activeWs.close()
