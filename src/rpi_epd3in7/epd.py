"""epd2in7 - e-paper display library for the Waveshare 2.7inch e-Paper HAT """
# Copyright (C) 2018 Elad Alfassa <elad@fedoraproject.org>
# This file has been heavily modified by Elad Alfassa for adding features,
# cleaning up the code, simplifying the API and making it more pythonic
# original copyright information below:

##
#  @filename   :   epd2in7.py
#  @brief      :   Implements for e-paper library
#  @author     :   Yehui from Waveshare
#
#  Copyright (C) Waveshare     July 31 2017
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documnetation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to  whom the Software is
# furished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS OR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.
from __future__ import unicode_literals, division, absolute_import

import time
import spidev
import logging
from .lut import LUT
import RPi.GPIO as GPIO

# Pin definition
RST_PIN = 17
DC_PIN = 25
CS_PIN = 8
BUSY_PIN = 24

# Display resolution
EPD_WIDTH = 280
EPD_HEIGHT = 480
EPD_DPI = 150 # pixels per inch

# EPD3IN7 commands
# Specifciation: https://www.waveshare.com/w/upload/archive/7/71/20210723055746%213.7inch_e-Paper_Specification.pdf
GATE_SET = 0x01
POWER_OFF = 0x02
GATE_VOLTAGE_SET = 0x03
SOURCE_VOLTAGE_SET = 0x04
DEEP_SLEEP = 0x10
DATA_ENTRY_SEQUENCE_SET = 0x11
SW_RESET = 0x12
AUTO_WRITE_REGULAR_PATTERN_RED_RAM = 0x46
AUTO_WRITE_REGULAR_PATTERN_BW_RAM = 0x47
AWRP_BW = 0X47
INTERNAL_SENSOR_COMMAND = 0x18
INTERNAL_SENSOR_WRITE = 0x1A
INTERNAL_SENSOR_READ = 0x1B
MASTER_ACTIVATION = 0x20
DISPLAY_UPDATE_CONTROL_2 = 0x22
WRITE_RAM_BW = 0x24
WRITE_RAM_RED = 0x26
DISPLAY_OPTION_SET = 0x37
VCOM_VALUE = 0x2C
BORDER_SET = 0x3C
BOOSTER_SET = 0x0C
LUT_VALUE = 0x32
RAM_X_SET = 0x44
RAM_Y_SET = 0x45
RAM_X_COUNTER = 0x4E
RAM_Y_COUNTER = 0x4F


class EPD(object):
    DPI = EPD_DPI
    MODE_4GRAY = 'L'
    MODE_1GRAY = '1'
    GRAY1 = 0xFF  # white
    GRAY2 = 0xC0  # Close to white
    GRAY3 = 0x80  # Close to black
    GRAY4 = 0x00  # black

    def __init__(self, partial_refresh_limit=32):
        """ Initialize the EPD class.
        `partial_refresh_limit` - number of partial refreshes before a full refrersh is forced
        `fast_frefresh` - enable or disable the fast refresh mode,
                          see smart_update() method documentation for details"""
        self.width = EPD_WIDTH
        """ Display width, in pixels """
        self.height = EPD_HEIGHT
        """ Display height, in pixels """
        self.partial_refresh_limit = partial_refresh_limit
        """ number of partial refreshes before a full refrersh is forced """

        self._last_frame = None
        self._partial_refresh_count = 0
        self._init_performed = False
        self.spi = spidev.SpiDev()
        self.lut = LUT

        self.log = logging.getLogger(__name__)

    def digital_write(self, pin, value):
        return GPIO.output(pin, value)

    def digital_read(self, pin):
        return GPIO.input(pin)

    def delay_ms(self, delaytime):
        time.sleep(delaytime / 1000.0)

    def send_command(self, command):
        self.digital_write(DC_PIN, 0)
        self.digital_write(CS_PIN, 0)
        self.spi.writebytes([command])
        self.digital_write(CS_PIN, 1)

    def send_data(self, data):
        self.digital_write(DC_PIN, 1)
        self.digital_write(CS_PIN, 0)
        self.spi.writebytes([data])
        self.digital_write(CS_PIN, 1)

    def send_data2(self, data):
        self.digital_write(DC_PIN, 1)
        self.digital_write(CS_PIN, 0)
        self.spi.writebytes2(data)
        self.digital_write(CS_PIN, 1)

    def reset(self):
        """ Module reset """
        self.digital_write(RST_PIN, 1)
        self.delay_ms(200)
        self.digital_write(RST_PIN, 0)
        self.delay_ms(5)
        self.digital_write(RST_PIN, 1)
        self.delay_ms(200)

    def sleep(self):
        """Put the chip into a deep-sleep mode to save power.
        The deep sleep mode would return to standby by hardware reset.
        Use EPD.reset() to awaken and use EPD.init() to initialize. """
        self.send_command(0X50)  # DEEP_SLEEP_MODE
        self.send_data(0xf7)
        self.send_command(POWER_OFF)  # power off
        self.send_command(0X07)  # deep sleep
        # deep sleep requires 0xa5 as a "check code" parameter
        self.send_data(0xA5)

        self.delay_ms(2000)
        self.log.debug("spi end")
        self.spi.close()

        self.log.debug("close 5V, Module enters 0 power consumption ...")
        GPIO.output(RST_PIN, 0)
        GPIO.output(DC_PIN, 0)

        GPIO.cleanup()

    def init(self, fast=True):
        """ Preform the hardware initialization sequence """
        # Interface initialization:
        GPIO.setmode(GPIO.BCM)
        GPIO.setwarnings(False)
        GPIO.setup(RST_PIN, GPIO.OUT)
        GPIO.setup(DC_PIN, GPIO.OUT)
        GPIO.setup(CS_PIN, GPIO.OUT)
        GPIO.setup(BUSY_PIN, GPIO.IN)

        self.spi.open(0, 0)
        self.spi.max_speed_hz = 32000000
        self.spi.mode = 0b00
        # EPD hardware init start
        self.reset()

        self.send_command(SW_RESET)
        self.delay_ms(300)

        self.send_command(AUTO_WRITE_REGULAR_PATTERN_RED_RAM)
        self.send_data(0xF7)
        self.wait_until_idle()
        self.send_command(AUTO_WRITE_REGULAR_PATTERN_BW_RAM)
        self.send_data(0xF7)
        self.wait_until_idle()

        self.send_command(GATE_SET)  # setting gaet number
        self.send_data2([
            0xDF,
            0x01,
            0x00
        ])

        self.send_command(GATE_VOLTAGE_SET)  # set gate voltage
        self.send_data(0x00)

        self.send_command(SOURCE_VOLTAGE_SET)  # set source voltage
        self.send_data2([
            0x41,
            0xA8,
            0x32
        ])

        self.send_command(DATA_ENTRY_SEQUENCE_SET)  # set data entry sequence
        self.send_data(0x03)

        self.send_command(BORDER_SET)  # set border
        self.send_data(0x03)

        self.send_command(BOOSTER_SET)  # set booster strength
        self.send_data2([
            0xAE,
            0xC7,
            0xC3,
            0xC0,
            0xC0
        ])

        self.send_command(INTERNAL_SENSOR_COMMAND)  # set internal sensor on
        self.send_data(0x80)

        self.send_command(VCOM_VALUE)  # set vcom value
        self.send_data(0x44)

        # set display option, these setting turn on previous function
        self.send_command(DISPLAY_OPTION_SET)
        if fast:
            self.send_data2([
                0x00,  # can switch 1 gray or 4 gray
                0xFF,
                0xFF,
                0xFF,
                0xFF,
                0x4F,
                0xFF,
                0xFF,
                0xFF,
                0xFF,
            ])
        else:
            self.send_data2([
                0x00,  # can switch 1 gray or 4 gray
                0x00,
                0x00,
                0x00,
                0x00,
                0x00,
                0x00,
                0x00,
                0x00,
                0x00,
            ])

        # setting X direction start/end position of RAM
        self.send_command(RAM_X_SET)
        self.send_data2([
            0x00,
            0x00,
            0x17,
            0x01,
        ])

        # setting Y direction start/end position of RAM
        self.send_command(RAM_Y_SET)
        self.send_data2([
            0x00,
            0x00,
            0xDF,
            0x01,
        ])

        self.send_command(DISPLAY_UPDATE_CONTROL_2)  # Display Update Control 2
        self.send_data(0xCF)
        # EPD hardware init end
        self._init_performed = True

    def load_lut(self, lut):
        self.send_command(LUT_VALUE)
        self.send_data2(lut)

    def getbuffer(self, image, mode):
        img = image
        imwidth, imheight = img.size

        if mode == self.MODE_1GRAY:
            if(imwidth == self.width and imheight == self.height):
                img = img.convert(mode)
            elif(imwidth == self.height and imheight == self.width):
                # image has correct dimensions, but needs to be rotated
                img = img.rotate(90, expand=True).convert(mode)
            else:
                logging.warning("Wrong image dimensions: must be " +
                                str(self.width) + "x" + str(self.height))
                # return a blank buffer
                return [0x00] * (int(self.width/8) * self.height)

            buf = bytearray(img.tobytes('raw'))

        if mode == self.MODE_4GRAY:
            buf = [0xFF] * (int(self.width / 4) * self.height)
            pixels = img.load()
            i = 0

            for x in range(imwidth):
                for y in range(imheight):
                    newx = y
                    newy = imwidth - x - 1
                    if(pixels[x, y] == 0xC0):
                        pixels[x, y] = 0x80
                    elif (pixels[x, y] == 0x80):
                        pixels[x, y] = 0x40
                    i = i + 1
                    if(i % 4 == 0):
                        buf[int((newx + (newy * self.width))/4)] = ((pixels[x, y-3] & 0xc0) | (
                            pixels[x, y-2] & 0xc0) >> 2 | (pixels[x, y-1] & 0xc0) >> 4 | (pixels[x, y] & 0xc0) >> 6)
        return buf

    def display(self, image):
        """ Display a full frame, doing a full screen refresh """
        if not self._init_performed:
            # Initialize the hardware if it wasn't already initialized
            self.init()

        mode = image.mode
        image_buffer = self.getbuffer(image, mode)

        self.send_command(RAM_X_COUNTER)
        self.send_data(0x00)
        self.send_data(0x00)
        self.send_command(RAM_Y_COUNTER)
        self.send_data(0x00)
        self.send_data(0x00)

        if mode == self.MODE_1GRAY:
            self.send_command(WRITE_RAM_BW)
            self.send_data2(image_buffer)

            self.load_lut(self.lut.lut_1Gray_A2)
            self.send_command(MASTER_ACTIVATION)

        if mode == self.MODE_4GRAY:
            buf = []
            for i in range(0, (int)(self.height*(self.width/8))):
                temp3 = 0
                for j in range(0, 2):
                    temp1 = image_buffer[i*2+j]
                    for k in range(0, 2):
                        temp2 = temp1 & 0xC0
                        if(temp2 == 0xC0):
                            temp3 |= 0x01  # white
                        elif(temp2 == 0x00):
                            temp3 |= 0x00  # black
                        elif(temp2 == 0x80):
                            temp3 |= 0x00  # gray1
                        else:  # 0x40
                            temp3 |= 0x01  # gray2
                        temp3 <<= 1
                        temp1 <<= 2
                        temp2 = temp1 & 0xC0
                        if(temp2 == 0xC0):  # white
                            temp3 |= 0x01
                        elif(temp2 == 0x00):  # black
                            temp3 |= 0x00
                        elif(temp2 == 0x80):
                            temp3 |= 0x00  # gray1
                        else:  # 0x40
                            temp3 |= 0x01  # gray2
                        if(j != 1 or k != 1):
                            temp3 <<= 1
                        temp1 <<= 2
                # self.send_data(temp3)
                buf.append(temp3)

            self.send_command(WRITE_RAM_BW)
            self.send_data2(buf)

            self.send_command(RAM_X_COUNTER)
            self.send_data2([0x00, 0x00])
            self.send_command(RAM_Y_COUNTER)
            self.send_data2([0x00, 0x00])

            buf = []
            for i in range(0, (int)(self.height*(self.width/8))):
                temp3 = 0
                for j in range(0, 2):
                    temp1 = image_buffer[i*2+j]
                    for k in range(0, 2):
                        temp2 = temp1 & 0xC0
                        if(temp2 == 0xC0):
                            temp3 |= 0x01  # white
                        elif(temp2 == 0x00):
                            temp3 |= 0x00  # black
                        elif(temp2 == 0x80):
                            temp3 |= 0x01  # gray1
                        else:  # 0x40
                            temp3 |= 0x00  # gray2
                        temp3 <<= 1
                        temp1 <<= 2
                        temp2 = temp1 & 0xC0
                        if(temp2 == 0xC0):  # white
                            temp3 |= 0x01
                        elif(temp2 == 0x00):  # black
                            temp3 |= 0x00
                        elif(temp2 == 0x80):
                            temp3 |= 0x01  # gray1
                        else:  # 0x40
                            temp3 |= 0x00  # gray2
                        if(j != 1 or k != 1):
                            temp3 <<= 1
                        temp1 <<= 2
                # self.send_data(temp3)
                buf.append(temp3)

            self.send_command(WRITE_RAM_RED)
            self.send_data2(buf)

            self.load_lut(self.lut.lut_4Gray_GC)
            self.send_command(DISPLAY_UPDATE_CONTROL_2)
            self.send_data(0xC7)
            self.send_command(MASTER_ACTIVATION)

        self.wait_until_idle()

    def wait_until_idle(self):
        """ Wait until screen is idle by polling the busy pin """
        self.log.debug("Busy")
        while(self.digital_read(BUSY_PIN) == 1):      # 0: busy, 1: idle
            self.delay_ms(10)
        self.log.debug("Busy release")

    def clear(self, mode=MODE_1GRAY):
        buf = [self.GRAY1] * (int(self.width/8) * self.height)

        self.send_command(RAM_X_COUNTER)
        self.send_command(WRITE_RAM_RED)
        self.send_command(RAM_Y_COUNTER)
        self.send_command(WRITE_RAM_RED)

        self.send_command(WRITE_RAM_BW)
        self.send_data2(buf)

        if mode == self.MODE_1GRAY:
            self.load_lut(self.lut.lut_1Gray_DU)

        if mode == self.MODE_4GRAY:
            self.send_command(WRITE_RAM_RED)
            self.send_data2(buf)
            self.load_lut(self.lut.lut_4Gray_GC)
            self.send_command(DISPLAY_UPDATE_CONTROL_2)
            self.send_data(0xC7)

        self.send_command(MASTER_ACTIVATION)
        self.wait_until_idle()
