
from machine import Pin, mem32
import rp2

#
# sclk    010101010101010100000..
# rclk    110000000000000000011..
# sh_n_ld 001111111111111111100..
#
# dout    hhggffeeddccbbaa.......
# din     ......a.b.c.d.e.f.g.h..
#
# 595      s  s s s s s s s   p     #
# 165      p  s s s s s s s         # p also loads the first serial bit for 165
#

# This gpio_extender code is meant to drive 1-4 74x595 for output, and 1-4 74x165 for input.
# Preferably using 74AHCxxx for full speed. Slower versions will need added delays in the PIO code.
# RPP       595     165
# pin + 0 : RCLK    (SH_n_LD via an inverter)
# pin + 1 : SRCLK   CLK
# pin + 2 : SER     -
# pin + 3 : -       QH
# More 595s can be linked from QH' to ser on next 595.
# More 165s can be linked from QH  to ser on next 165
# 
def setup(sm_nr, pin, n_out_bits, n_in_bits = 0, irq_nr = 0, continuous_tx = False, rx_on_change = False, erase = False):
    if not (2 <= n_out_bits <= 32 and 0 <= n_in_bits <= n_out_bits):
        raise("Bad bit count")
    # continuous_tx and rx_on_change is meant to be used together, but can be used separately.
    #
    SYNC_DELAY_TX = 1   # 1*pio_tick compensates for "irq wait" finishing one tick after "irq clr".
    SYNC_DELAY_RX = 4   # Should be 4*sys_tick to compensate for io latency, but we can't delay for sys_ticks in PIO.
                        # But when prescale is 1, sys_tick == pio_tick.
    SYNC_DELAY    = min(SYNC_DELAY_TX, SYNC_DELAY_RX)  # Cancel out the smaller of the delays
    #
    @rp2.asm_pio(
        fifo_join    = rp2.PIO.JOIN_TX,
        out_shiftdir = rp2.PIO.SHIFT_LEFT, 
        out_init     = rp2.PIO.OUT_LOW,
        pull_thresh  = n_out_bits,
        sideset_init = (rp2.PIO.OUT_LOW, rp2.PIO.OUT_LOW)
        )
    def _tx():
        wrap_target()
        if continuous_tx:
            pull(noblock)          .side(1)
            mov(x, osr)            .side(1)
        else:
            pull(block)            .side(1)
        if n_out_bits != 32:
            out(y, 32 - n_out_bits).side(1)
        if n_in_bits:
            out(pins, 1)           .side(1)
            irq(0x40, irq_nr)      .side(3).delay(SYNC_DELAY_TX - SYNC_DELAY)
        label('more_bits')
        out(pins, 1)               .side(0)
        jmp(not_osre, 'more_bits') .side(2).delay(1)  # Delay because hw can't handle too high freq together with rx.
        wrap()
    #
    @rp2.asm_pio(
        fifo_join    = rp2.PIO.JOIN_RX,
        in_shiftdir  = rp2.PIO.SHIFT_RIGHT,
        push_thresh  = n_in_bits
        )
    def _rx():
        if rx_on_change:
            jmp("start")
            label("new_val")
            mov(x, status)       # Check if there's anything in RXFIFO. 
            jmp(not_x, "start")
            mov(y, isr)
            push(noblock)
            label("start")
        wrap_target()
        set(x, n_in_bits - 1)
        irq(0x20, irq_nr).delay(SYNC_DELAY_RX - SYNC_DELAY)
        label("loop")
        in_(pins, 1)
        jmp(x_dec, "loop")         .delay(1)
        if rx_on_change:
            mov(x, isr)
            jmp(x_not_y, "new_val")
        else:
            push(block)
        wrap()
    #
    PIO_BASE    = 0x50200000 + 0x00100000 * ((sm_nr + 1) // 4)
    EXECCTRL    = PIO_BASE + 0xcc + 0x18 * ((sm_nr + 1) % 4)
    DBG_CFGINFO = PIO_BASE + 0x44
    #
    if erase:
        rp2.PIO(sm_nr // 4).remove_program()
    sm_tx = rp2.StateMachine(sm_nr, _tx, out_base = Pin(pin + 2), sideset_base = Pin(pin))
    sm_tx.active(1)
    sm_rx = None
    if n_in_bits:
        # With the rx_on_change option, it's most useful to keep the rx buffer minimal. 
        # Set up the pio status register so it tells if rx fifo is empty.
        #mem32[EXECCTRL] ^= (STATUS_SEL_MASK | STATUS_N_MASK) & (mem32[EXECCTRL] ^ (RX_LEVEL << STATUS_SEL | 1 << STATUS_N))
        rpp_version = mem32[DBG_CFGINFO] >> 28
        if rpp_version == 0:
            mem32[EXECCTRL] ^= 0x1f & (0x11 ^ mem32[EXECCTRL])  # RP2040
        elif rpp_version == 1:
            mem32[EXECCTRL] ^= 0x7f & (0x41 ^ mem32[EXECCTRL])  # RP235x
        sm_rx = rp2.StateMachine(sm_nr + 1, _rx, in_base = Pin(pin + 3))
        sm_rx.active(1)
    return (sm_tx, sm_rx)


#(sm_tx, sm_rx) = setup(4, 16, 32)
#for i in range(0xffffffff): sm_tx.put(i)
#
#(sm_tx, sm_rx) = setup(sm_nr         = 4, 
#                       pin           = 16, 
#                       n_out_bits    = 32, 
#                       n_in_bits     = 32, 
#                       irq_nr        = 0, 
#                       continuous_tx = True, 
#                       rx_on_change  = True, 
#                       erase         = True)
#for i in range(0xffffffff): 
#    sm_tx.put(i)
#    sm_rx.get()
#    print("%08x  %08x" % (i, sm_rx.get()))
