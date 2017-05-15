# aurora
Color sensing RGB LED wooden box project for sensors tradeshow demo.

You'll need to install python-sysfs-gpio.  To echo instructions on https://github.com/derekstavis/python-sysfs-gpio:

1. git clone https://github.com/derekstavis/python-sysfs-gpio.git
2. sudo python setup.py install

You'll also need to install Pillow.  To echo instructions on http://pillow.readthedocs.io/en/3.0.x/installation.html:

1. wget https://pypi.python.org/pypi/Pillow/4.1.1
2. python setup.py install

Finally, make sure that a fadecandy server is up and running (https://github.com/scanlime/fadecandy):

    ./fcserver ts7970.json
