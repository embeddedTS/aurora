import opc, time, smbus, sys, signal
import Queue
import Adafruit_TCS34725
from twisted.internet import reactor
from twisted.internet.task import LoopingCall
from twisted.internet.threads import deferToThread
from sysfs.gpio import Controller, OUTPUT, INPUT, RISING, FALLING, BOTH
from PIL import Image

# GPIO PIN SETUP
LED_EN  = 64
RGB_INT = 65
PTY_BTN = 66

# TCS34725 Setup Vars
TCS34725_PERS_10_CYCLE = 0b0101

# NeoPixel LED Strip Setup
NUMLEDS = 38 
led_strip = [(0,0,0)] * NUMLEDS

gammatable = [None]*255
for i in range(len(gammatable)):
    x = i
    x = float(x) / 255
    x = float(x) ** 2.6 #2.5
    x = float(x) * 255 * 20 # Added * 10 make brighter 
    gammatable[i] = float(x)

# Aliases
usleep = lambda x: time.sleep(x/1000000.0)


# For when Ctrl+C is hit
# Mostly for development
def signal_handler(signal, frame):
    global black
    global signal_interrupted

    print("Exiting!")
    signal_interrupted = True
    led_en.reset()
    tcs.disable() 
    reactor.stop()
    client.put_pixels(black)
    client.put_pixels(black)

# Convert RGBC values from sensor to something recognizable by RGB strip
def calculate_hex_code(red, green, blue, clear):
    summ = red
    summ += green
    summ += blue
    summ += clear

    r = red
    r = float(r) / summ

    g = green
    g = float(g) / summ

    b = blue
    b = float(b) / summ

    r = float(r) * 256
    g = float(g) * 256
    b = float(b) * 256

    return (int(r),int(g),int(b))

# A miserable number of globals for running main
chilling = False
partying = False
matching = False
matching_start_time = 0

sensor_interrupted = False
button_interrupted = False
signal_interrupted = False

black = [ (0,0,0) ] * NUMLEDS
white = [ (255,255,255) ] * NUMLEDS

#tcs_interrupt_enabled = 0 # Assume it's not enabled at first
def matching_mode():
    global matching
    global matching_start_time

    matching = True
    matching_start_time = time.time()

    led_en.set()
    usleep(5000)
    r, g, b, c = tcs.get_raw_data()

    print("INT: Red: {0}, Green: {1}, Blue: {2}, Clear: {3:02X}".format(r,g,b,c))
    hr, hg, hb = calculate_hex_code(r, g, b, c)

    strip_color_r = gammatable[int(hr)] 
    strip_color_g = gammatable[int(hg)] 
    strip_color_b = gammatable[int(hb)] 

    # Chase/Wipe effect
    for i in range(len(led_strip)):
        led_strip[i] = (strip_color_r, strip_color_g, strip_color_b)
        client.put_pixels(led_strip)
        usleep(10000)

    tcs.clear_interrupt() # Turns the LED off

    # Hold the matching color for a bit
    #reactor.callLater(3, chill_mode)

    matching = False

def sensor_interrupt_event_handler():
    print "Sensor interrupt event handler!"
    reactor.callInThread(matching_mode)

def display_image(image):
    im = Image.open(image)
    width = im.size[0]
    height = im.size[1]
    pix = im.load()

    global chilling
    global partying
    global matching

    global button_interrupted
    global sensor_interrupted
    global signal_interrupted

    if image == "chill.jpg":
        sleep = .05 
    else:
        sleep = .01
    
    for y in range(height):
   
        if sensor_interrupted or button_interrupted or signal_interrupted:
            print "We're breaking from displaying the image! sensor: %s, button: %s, signal: %s" % (sensor_interrupted, button_interrupted, signal_interrupted)
            # Button is a little tricky. We must set this to false immediately after breaking in order to loop when threaded event fires
            button_interrupted = False
            break
 
        line = [(0,0,0)] * NUMLEDS
        for x in range(len(line)):
            line[x] = pix[x,y]
        
        client.put_pixels(line)

        time.sleep(sleep)

def chill_mode():
    global chilling

    # Offically start the chill!
    chilling = True
    display_image('chill.jpg')

    # We need to give the signal to main that we've finished chilling so that
    # we can start again.
    chilling = False

def party_mode():
    global partying
    global black
  
    # Offically start the party!
    chill = False
    partying = True

    display_image('party.jpg')

    # For when the party has finished
    partying = False
    chill = True

def button_interrupt_event_handler():
    print "Button interrupt event handler!"
    global button_interrupted
    print "Start the party mode (in thread)!"
    reactor.callInThread(party_mode)

    #button_interrupted = False

def sensor_interrupt_fired(pin, state):

    global sensor_interrupted
    global matching

    print "Sensor interrupt fired, %s" % state

    if state:
        sensor_interrupted = False
        led_en.reset() # Sets pin to high logic level

    else:
        sensor_interrupted = True
        print "sensor interrupted"
        if not matching:
            print "not matching, so go ahead and match"
            reactor.fireSystemEvent('sensor-interrupt')

        # Need to setup the trigger event again!
        reactor.addSystemEventTrigger('before', 'sensor-interrupt', sensor_interrupt_event_handler)
 
def button_pressed(pin, state):
    global partying
    global chilling
    global button_interrupted
    print "Button pressed!  State: %s" % state


    # Tied to normally open pin, 0 = button pressed
    if not state:
        button_interrupted = True
        usleep(200000) # Best results with minimal pause

        # We want to allow time  for debounce
        if not partying:
            #button_interrupted = True
            reactor.fireSystemEvent('button-interrupt')

            # Need to setup the trigger event again!
            reactor.addSystemEventTrigger('before', 'button-interrupt', button_interrupt_event_handler)

def main():
    global partying
    global chilling
    global matching
    global matching_start_time

    time_elapsed = 0
    #if matching_start_time:
    time_elapsed = time.time() - matching_start_time

    # Read the R, G, B, C color data.
    r, g, b, c = tcs.get_raw_data()
    #print("Red: {0}, Green: {1}, Blue: {2}, Clear: {3:02X}".format(r,g,b,c))
  
    if not chilling and not matching and not partying:

        # We've just finished matching colors, go back to chill
        if time_elapsed == 0 or time_elapsed > 3:
            reactor.callInThread(chill_mode)


# Init GPIO pins for use with LED Enable and Interrupts
Controller.available_pins = [LED_EN, RGB_INT, PTY_BTN]
led_en = Controller.alloc_pin(LED_EN, OUTPUT)
sensor_int = Controller.alloc_pin(RGB_INT, INPUT, sensor_interrupt_fired, BOTH)
button_int = Controller.alloc_pin(PTY_BTN, INPUT, button_pressed, FALLING)

# Create a TCS34725 instance with default integration time (2.4ms) and gain (4x)
# and setup interrupt
tcs = Adafruit_TCS34725.TCS34725()
tcs.set_persistence(TCS34725_PERS_10_CYCLE)
tcs.set_interrupt_limits(0x0002, 0xFFFF)
tcs.set_interrupt(True) # Turns LED Off

# Connect to OPC client and set all LEDs to black
client = opc.Client('localhost:7890')
client.put_pixels(black)
client.put_pixels(black)

signal.signal(signal.SIGINT, signal_handler)

reactor.addSystemEventTrigger('before', 'sensor-interrupt', sensor_interrupt_event_handler)
reactor.addSystemEventTrigger('before', 'button-interrupt', button_interrupt_event_handler)

lc = LoopingCall(main)
#lc.start(0.1)
lc.start(1)

reactor.run()
