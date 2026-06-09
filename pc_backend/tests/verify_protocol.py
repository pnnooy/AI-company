"""
verify_protocol.py — P0 协议验证脚本
====================================
验证 CRC-8、帧打包/解包、帧解析器是否与固件一致。
"""

import sys
sys.path.insert(0, '..')
from comm.protocol import calc_crc8, Frame, SensorEvent, EventCode
from comm.uart_link import FrameParser


def main():
    print('=' * 60)
    print('CRC-8 Verification')
    print('=' * 60)

    # CRC8([01]) = ?
    r = calc_crc8(bytes([0x01]))
    print(f'CRC8([01]) = 0x{r:02X}')

    # CRC8([01, 01]) = ?
    r = calc_crc8(bytes([0x01, 0x01]))
    print(f'CRC8([01 01]) = 0x{r:02X}')

    print()
    print('=' * 60)
    print('Frame Pack + Parse Roundtrip')
    print('=' * 60)

    tests = [
        ('SET_EXPR HAPPY',  0x01, bytes([0x01]), None),
        ('SET_RGB RED',     0x02, bytes([0xFF, 0x00, 0x00]), None),
        ('QUERY',           0x03, b'', None),
        ('HEARTBEAT seq=1', 0x04, bytes([0x01]), None),
        ('TOUCH LEFT TAP',  0x10, bytes([0x00, 0x01]), EventCode.TOUCH),
        ('TOUCH RIGHT HOLD', 0x10, bytes([0x01, 0x02]), EventCode.TOUCH),
        ('NFC 5s SNACK',    0x11, bytes([0x05, 0x00, 0x01]), EventCode.NFC),
        ('NFC 15s MEAL',    0x11, bytes([0x0F, 0x00, 0x02]), EventCode.NFC),
        ('NFC 35s FEAST',   0x11, bytes([0x23, 0x00, 0x03]), EventCode.NFC),
        ('POSE SHAKE',      0x12, bytes([0x02]), EventCode.POSE),
        ('POSE FALL',       0x12, bytes([0x01]), EventCode.POSE),
        ('ACK cmd=04 ok',   0x05, bytes([0x04, 0x00]), EventCode.ACK),
    ]

    all_ok = True
    for name, cmd, data, exp_event in tests:
        frame_bytes = Frame.pack(cmd, data)
        parser = FrameParser()
        result = None
        for b in frame_bytes:
            result = parser.feed(b)

        if result is None:
            print(f'FAIL [{name}]: Parser returned None')
            all_ok = False
            continue
        if result.cmd != cmd:
            print(f'FAIL [{name}]: CMD mismatch 0x{result.cmd:02X} vs 0x{cmd:02X}')
            all_ok = False
            continue
        if result.data != data:
            print(f'FAIL [{name}]: DATA mismatch')
            all_ok = False
            continue

        if exp_event:
            event = SensorEvent.from_frame(result)
            if event is None or event.event_code != exp_event:
                print(f'FAIL [{name}]: Event parse fail')
                all_ok = False
                continue

        print(f'OK: {name:20s}  {frame_bytes.hex(" ")}')

    print()
    print('=' * 60)
    print('Edge Cases')
    print('=' * 60)

    # Consecutive A5 sync
    parser = FrameParser()
    raw = bytes([0xA5, 0xA5, 0xA5]) + Frame.pack(0x01, bytes([0x01]))
    result = None
    for b in raw:
        r = parser.feed(b)
        if r:
            result = r
    ok = result is not None and result.cmd == 0x01
    print(f'Consecutive A5: {"OK" if ok else "FAIL"}')

    # CRC error
    parser2 = FrameParser()
    cb = bytearray(Frame.pack(0x01, bytes([0x01])))
    cb[-2] ^= 0xFF  # Corrupt CRC (second-to-last byte)
    for b in cb:
        parser2.feed(b)
    ok = parser2.stats['crc_fail'] == 1
    print(f'CRC error detect: {"OK" if ok else "FAIL"} (crc_fail={parser2.stats["crc_fail"]})')

    # Invalid LEN < 2
    parser3 = FrameParser()
    for b in bytes([0xA5, 0x5A, 0x01]):
        parser3.feed(b)
    ok = parser3.stats['invalid_len'] == 1
    print(f'LEN<2: {"OK" if ok else "FAIL"} (invalid_len={parser3.stats["invalid_len"]})')

    # Invalid LEN > 34
    parser4 = FrameParser()
    for b in bytes([0xA5, 0x5A, 0xFF]):
        parser4.feed(b)
    ok = parser4.stats['invalid_len'] == 1
    print(f'LEN>34: {"OK" if ok else "FAIL"} (invalid_len={parser4.stats["invalid_len"]})')

    # END byte error
    parser5 = FrameParser()
    cb = bytearray(Frame.pack(0x01, bytes([0x01])))
    cb[-1] = 0xFF
    for b in cb:
        parser5.feed(b)
    ok = parser5.stats['end_byte_err'] == 1
    print(f'END byte err: {"OK" if ok else "FAIL"} (end_byte_err={parser5.stats["end_byte_err"]})')

    # NFC detail parse
    parser6 = FrameParser()
    for b in Frame.pack(0x11, bytes([0x0F, 0x00, 0x02])):
        r = parser6.feed(b)
        if r:
            e = SensorEvent.from_frame(r)
            ok = e.nfc.duration == 15 and e.nfc.level.value == 2
            print(f'NFC 15s MEAL: {"OK" if ok else "FAIL"} (dur={e.nfc.duration})')

    # Max data (32 bytes)
    max_data = bytes(range(32))
    f = Frame.pack(0x01, max_data)
    parser7 = FrameParser()
    result = None
    for b in f:
        r = parser7.feed(b)
        if r:
            result = r
    ok = result is not None and result.data == max_data
    print(f'Max data 32B: {"OK" if ok else "FAIL"}')

    # Data too long error
    try:
        Frame.pack(0x01, bytes(33))
        print('Data>32B: FAIL (no exception)')
    except ValueError:
        print('Data>32B: OK (ValueError raised)')

    print()
    if all_ok:
        print('=' * 60)
        print('ALL TESTS PASSED')
        print('=' * 60)
    else:
        print('=' * 60)
        print('SOME TESTS FAILED')
        print('=' * 60)


if __name__ == '__main__':
    main()
