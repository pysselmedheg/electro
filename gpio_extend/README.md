
# GPIO Extender

This is a gpio extender using the good ol' trick with a 74xx595 shift register for output, and 74xx165 shift register for input. The intended usage is as debug output for a Raspberry Pi Pico, but it can of course be used with other mcus.

## GP Output

The output is (up to) 32 bit, arranged as 4 bytes. There is a R2R-DAC for each byte and a pin socket with the byte as digital and analog. There is also a LED for each bit.

## GP Input

The input is (up to) 32 bit, arranged as 4 bytes. Each byte has a pin socket, and a jumper to set pull up or down for the byte.

## Serial interface

The serial interface has four digital pins:
  - pclk    : frame sync
  - sclk    : serial clock
  - ser_in  : input into the gpio extender (for GPO)
  - ser_out : output from the gpio extender (for GPI)

Negative edge on pclk:
  - GPIs are sampled.
  
Positive edge on sclk:
  - GPI data is shifted out from the GPIO extender.
  - GPO data is shifted in to the GPIO extender.
  
Positive edge on pclk:
  - GPOs are updated with new data.

## Python Driver

The python folder contains a driver for Micropython on Raspberry Pi Pico. It uses two state machines in a PIO for the communication.
Surprisingly, it can handle the interface at cpu_clk/3 bps, ie 125MHz/3 = 41.7 MHz. 

TODO: Description of driver. Until then RTFS.


  


