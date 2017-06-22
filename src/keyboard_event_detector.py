import requests
import subprocess
import struct
import threading

# reads events from /dev/input/eventX
# needs to run as SU (super user)
# for reading key events see https://stackoverflow.com/a/16682549/2452051
# for detecting device see determine_input_device() in https://github.com/kernc/logkeys/blob/master/src/logkeys.cc

PROXY_URL = "http://localhost:8080"

BTN_DOWN_EVENT = 4
# long int, long int, unsigned short, unsigned short, unsigned int
FORMAT = 'llHHI'
EVENT_SIZE = struct.calcsize(FORMAT)

currentKeyboard = None
currentKeyboardLock = threading.Lock()


def notifyProxyOfKeyboardChange(deviceId):
    return requests.get(PROXY_URL + "/keyboard/%s" % deviceId)


# python version of determine_input_device() in https://github.com/kernc/logkeys/blob/master/src/logkeys.cc
def detectKeyboardDevices():
    rawCommandString = "grep -E 'Handlers|EV=' /proc/bus/input/devices | grep -B1 'EV=120013' | grep -Eo 'event[0-9]+'"
    out = subprocess.check_output(rawCommandString, shell=True)

    def parseKeyboard(commandOutput):
        remainingOutput = str(out)
        devices = []
        while remainingOutput.find("event") != -1:
            deviceNum = remainingOutput[remainingOutput.find("event") + 5:remainingOutput.find("\\")]
            devices.append(deviceNum)
            remainingOutput = remainingOutput[remainingOutput.find("\\") + 1:]
        return devices

    return parseKeyboard(out)


class KeyboardListener(threading.Thread):
    def __init__(self, inputDeviceID, callback):
        threading.Thread.__init__(self)
        self.inputDeviceId = inputDeviceID
        self.callback = callback

    def run(self):
        device = "/dev/input/event%s" % self.inputDeviceId
        print("Starting to listen to device '%s'" % device)
        fd = open(device, "rb")
        try:
            event = fd.read(EVENT_SIZE)
            while event:
                self.eventHandler(event)

                event = fd.read(EVENT_SIZE)

        finally:
            fd.close()

    def eventHandler(self, event):
        global currentKeyboard, currentKeyboardLock

        (tv_sec, tv_usec, type, code, value) = struct.unpack(FORMAT, event)
        if type == BTN_DOWN_EVENT and currentKeyboard != self.inputDeviceId:
            currentKeyboardLock.acquire()
            print("Changing current input device to '%s'" % self.inputDeviceId)
            currentKeyboard = self.inputDeviceId
            self.callback(self.inputDeviceId)
            currentKeyboardLock.release()


if __name__ == "__main__":
    # print(requests.post(proxyUrl + "/subscribe?url=http://localhost:8080/testSubscriber/c"))

    deviceIds = detectKeyboardDevices()
    print("Found %d devices with ids: %s" % (len(deviceIds), deviceIds))

    for deviceId in deviceIds:
        KeyboardListener(deviceId, notifyProxyOfKeyboardChange).start()
