from __future__ import print_function
import uuid
import json
from SimpleWebSocketServer import SimpleWebSocketServer, WebSocket
from whatsapp_client.whatsapp import WhatsAppWebClient
from whatsapp_client.utilities import *

clientInstances = WhatsAppWebClient()


class WhatsAppWeb(WebSocket):
    clientInstances = None

    def sendError(self, reason, tag=None):
        eprint("sending error: " + reason)

    def _send_message_text(self, data):
        tag = str(getTimestamp())
        clientInstances.send_message_whatsapp(data, tag)

    def _generate_qr(self):
        clientInstances.generateQRCode()

    def handleMessage(self):
        try:
            command = json.loads(self.data)["command"]
            if command == "qr":
                self._generate_qr()
            elif command == "send":
                data = json.loads(self.data)["data"]
                self._send_message_text(data)
        except Exception as inst:
            print(inst)

    def handleConnected(self):
        eprint(self.address, "connected to backend")

    def handleClose(self):
        eprint(self.address, "closed connection to backend")


server = SimpleWebSocketServer("", 2020, WhatsAppWeb)
eprint("whatsapp-web-backend listening on port 2020")
server.serveforever();
