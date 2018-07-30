import sys

sys.dont_write_bytecode = True

import os
import base64
import datetime
import json
import io
from threading import Thread
from Crypto.Cipher import AES
import hashlib
import hmac
import traceback

import websocket
import curve25519
import pyqrcode

import pprint
from .utilities import *
from .whatsapp_binary_reader import whatsappReadBinary
from .whatsapp_binary_writter import whatsappWriteBinary
import uuid


def HmacSha256(key, sign):
    return hmac.new(key, sign, hashlib.sha256).digest()


def HKDF(key, length, appInfo=""):  # implements RFC 5869, some parts from https://github.com/MirkoDziadzka/pyhkdf
    key = HmacSha256("\0" * 32, key)
    keyStream = ""
    keyBlock = ""
    blockIndex = 1
    while len(keyStream) < length:
        keyBlock = hmac.new(key, msg=keyBlock + appInfo + chr(blockIndex), digestmod=hashlib.sha256).digest()
        blockIndex += 1
        keyStream += keyBlock
    return keyStream[:length]


def AESPad(s):
    bs = AES.block_size
    return s + (bs - len(s) % bs) * chr(bs - len(s) % bs)


def AESUnpad(s):
    return s[:-ord(s[len(s) - 1:])]


def AESEncrypt(key, plaintext):  # like "AESPad"/"AESUnpad" from https://stackoverflow.com/a/21928790
    plaintext = AESPad(plaintext)
    iv = os.urandom(AES.block_size)
    cipher = AES.new(key, AES.MODE_CBC, iv)
    return iv + cipher.encrypt(plaintext)


def WhatsAppEncrypt(encKey, macKey, plaintext):
    enc = AESEncrypt(encKey, plaintext)
    return enc + HmacSha256(macKey, enc)  # this may need padding to 64 byte boundary


def AESDecrypt(key, ciphertext):  # from https://stackoverflow.com/a/20868265
    iv = ciphertext[:AES.block_size]
    cipher = AES.new(key, AES.MODE_CBC, iv)
    plaintext = cipher.decrypt(ciphertext[AES.block_size:])
    return AESUnpad(plaintext)


class WhatsAppWebClient:
    websocketIsOpened = False
    onOpenCallback = None
    onMessageCallback = None
    onCloseCallback = None
    activeWs = None
    websocketThread = None
    messageQueue = {}  # maps message tags (provided by WhatsApp) to more information (description and callback)

    loginInfo = {
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
        self.connect()

    def onOpen(self, ws):
        print("Connection with whatsapp server")

    def onError(self, ws, error):
        print(error)

    def onClose(self, ws):
        print("WhatsApp backend Websocket closed.")

    def onMessage(self, ws, message):
        try:
            messageSplit = message.split(",", 1)
            messageTag = messageSplit[0]
            messageContent = messageSplit[1]

            if messageTag in self.messageQueue:  # when the server responds to a client's message
                pend = self.messageQueue[messageTag]
                if pend["desc"] == "_login":
                    print("Message after login: ", message)

                    self.loginInfo["serverRef"] = json.loads(messageContent)["ref"]

                    print("set server id: " + self.loginInfo["serverRef"])

                    self.loginInfo["privateKey"] = curve25519.Private()
                    self.loginInfo["publicKey"] = self.loginInfo["privateKey"].get_public()

                    qrCodeContents = self.loginInfo["serverRef"] + "," + base64.b64encode(
                        self.loginInfo["publicKey"].serialize()) + "," + self.loginInfo["clientId"]

                    print("qr code contents: " + qrCodeContents)

                    big_code = pyqrcode.create(qrCodeContents, error='L', version=27, mode='binary')
                    big_code.png('qr/code.png', scale=2)

                    print(big_code)

            else:
                try:
                    jsonObj = json.loads(messageContent)  # try reading as json
                except ValueError as e:
                    if messageContent != "":
                        hmacValidation = HmacSha256(self.loginInfo["key"]["macKey"], messageContent[32:])
                        if hmacValidation != messageContent[:32]:
                            raise ValueError("Hmac mismatch")

                        decryptedMessage = AESDecrypt(self.loginInfo["key"]["encKey"], messageContent[32:])

                        try:
                            processedData = whatsappReadBinary(decryptedMessage, True)
                            messageType = "binary"

                        except:
                            processedData = {"traceback": traceback.format_exc().splitlines()}
                            messageType = "error"
                        finally:
                            pprint.pprint(processedData)
                            print("*" * 60)

                else:
                    if isinstance(jsonObj, list) and len(jsonObj) > 0:  # check if the result is an array
                        print(json.dumps(jsonObj))
                        if jsonObj[0] == "Conn":
                            self.connInfo["clientToken"] = jsonObj[1]["clientToken"]
                            self.connInfo["serverToken"] = jsonObj[1]["serverToken"]
                            self.connInfo["browserToken"] = jsonObj[1]["browserToken"]
                            self.connInfo["me"] = jsonObj[1]["wid"]

                            self.connInfo["secret"] = base64.b64decode(jsonObj[1]["secret"])
                            self.connInfo["sharedSecret"] = self.loginInfo["privateKey"].get_shared_key(curve25519.Public(self.connInfo["secret"][:32]), lambda a: a)


                            sse = self.connInfo["sharedSecretExpanded"] = HKDF(self.connInfo["sharedSecret"], 80)


                            hmacValidation = HmacSha256(sse[32:64],
                                                        self.connInfo["secret"][:32] + self.connInfo["secret"][64:])
                            if hmacValidation != self.connInfo["secret"][32:64]:
                                raise ValueError("Hmac mismatch")

                            keysEncrypted = sse[64:] + self.connInfo["secret"][64:]
                            keysDecrypted = AESDecrypt(sse[:32], keysEncrypted)
                            self.loginInfo["key"]["encKey"] = keysDecrypted[:32]
                            self.loginInfo["key"]["macKey"] = keysDecrypted[32:64]

                            print(
                                "set connection info: client, server and browser token secret, shared secret, enc key, mac key")
                            print("logged in as " + jsonObj[1]["pushname"] + " (" + jsonObj[1]["wid"] + ")")
                        elif jsonObj[0] == "Stream":
                            pass
                        elif jsonObj[0] == "Props":
                            pass
        except:
            print(traceback.format_exc())

    def connect(self):
        self.activeWs = websocket.WebSocketApp("wss://w1.web.whatsapp.com/ws",
                                               on_message=lambda ws, message: self.onMessage(ws, message),
                                               on_error=lambda ws, error: self.onError(ws, error),
                                               on_open=lambda ws: self.onOpen(ws),
                                               on_close=lambda ws: self.onClose(ws),
                                               header={"Origin: https://web.whatsapp.com"})

        self.websocketThread = Thread(target=self.activeWs.run_forever)
        self.websocketThread.daemon = True
        self.websocketThread.start()

    def generateQRCode(self, callback=None):
        self.loginInfo["clientId"] = base64.b64encode(os.urandom(16))
        messageTag = str(getTimestamp())
        self.messageQueue[messageTag] = {"desc": "_login", "callback": callback}
        message = messageTag + ',["admin","init",[0,2,9929],["Chromium at ' + datetime.datetime.now().isoformat() + '","Chromium"],"' + \
                  self.loginInfo["clientId"] + '",true]'
        self.activeWs.send(message)

    def send_message_whatsapp(self, _data, tag):
        data = json.loads(_data)
        from .decript import encryptmessage
        payload = json.dumps(["action", {'epoch': 1, 'type': 'relay'}, [{"key": {"remoteJid": data["to"], "FromMe":True}}, {"message": {"conversation": data["text"]}}, {"messageTimestamp": getTimestamp()}, {"status":"PENDING"}]])


        info= encryptmessage(str(getTimestamp()), payload, {"encKey": self.loginInfo["key"]["encKey"], 'macKey': self.loginInfo["key"]["macKey"]})
        self.activeWs.send(info)

    def disconnect(self):
        self.activeWs.send(
            'goodbye,,["admin","Conn","disconnect"]')  # WhatsApp server closes connection automatically when client wants to disconnect
    # time.sleep(0.5)
    # self.activeWs.close()