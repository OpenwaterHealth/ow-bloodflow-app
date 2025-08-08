# data_processing.py
import csv
import os
import struct
import argparse
import numpy as np
from typing import Dict, Tuple, List

try:
    # Accelerated CRC implementation if available
    from omotion.utils import util_crc16 as _crc16
except ImportError:
    import binascii
    def _crc16(buf: memoryview) -> int:
        return binascii.crc_hqx(buf, 0xFFFF)

# ─── Constants ──────────────────────────────────────────────
HISTO_SIZE_WORDS = 1024
HISTO_BYTES = HISTO_SIZE_WORDS * 4
PACKET_HEADER_SIZE = 6
PACKET_FOOTER_SIZE = 3
HISTO_BLOCK_SIZE = 1 + 1 + HISTO_BYTES + 4 + 1
MIN_PACKET_SIZE = PACKET_HEADER_SIZE + PACKET_FOOTER_SIZE + HISTO_BLOCK_SIZE

SOF, SOH, EOH, EOF = 0xAA, 0xFF, 0xEE, 0xDD

# ─── Struct formats ─────────────────────────────────────────
_U32  = struct.Struct("<I")
_U16  = struct.Struct("<H")
_F32  = struct.Struct("<f")
_HDR  = struct.Struct("<BBI")
_BLK_HEAD = struct.Struct("<BB")

def _get_u32(buf: memoryview, offset: int) -> int:
    return _U32.unpack_from(buf, offset)[0]

def _crc_matches(pkt: memoryview, crc_expected: int) -> bool:
    return _crc16(pkt) == crc_expected


class DataProcessor:
    """Parses raw histogram .bin files into CSV format."""

    def parse_histogram_packet(self, pkt: memoryview) -> Tuple[
        Dict[int, np.ndarray], Dict[int, int], Dict[int, float], int]:
        """Returns histograms, frame-ids, temperatures, bytes_consumed."""

        if len(pkt) < MIN_PACKET_SIZE:
            raise ValueError("Packet too small")

        sof, pkt_type, pkt_len = _HDR.unpack_from(pkt, 0)
        if sof != SOF or pkt_type != 0x00:
            raise ValueError("Bad header")

        if pkt_len > len(pkt):
            raise ValueError("Truncated packet")

        payload_end = pkt_len - PACKET_FOOTER_SIZE
        off = PACKET_HEADER_SIZE

        hists: Dict[int, np.ndarray] = {}
        ids:   Dict[int, int] = {}
        temps: Dict[int, float] = {}

        mv = pkt
        while off < payload_end:
            soh, cam_id = _BLK_HEAD.unpack_from(mv, off)
            if soh != SOH:
                raise ValueError("Missing SOH")
            off += _BLK_HEAD.size

            hist = np.frombuffer(mv, dtype=np.uint32,
                                 count=HISTO_SIZE_WORDS,
                                 offset=off)
            off += HISTO_BYTES

            temp = _F32.unpack_from(mv, off)[0]
            off += 4

            if mv[off] != EOH:
                raise ValueError("Missing EOH")
            off += 1

            last_word = hist[-1]
            frame_id = (last_word >> 24) & 0xFF
            hist = hist.copy()
            hist[-1] = last_word & 0x00_FFFF_FF

            hists[cam_id] = hist
            ids[cam_id] = frame_id
            temps[cam_id] = temp

        crc_expected = _U16.unpack_from(mv, off)[0]
        off += 2
        if mv[off] != EOF:
            raise ValueError("Missing EOF")

        if not _crc_matches(mv[:off-3], crc_expected):
            raise ValueError("CRC mismatch")

        return hists, ids, temps, pkt_len

    def process_bin_file(self, src_bin: str, dst_csv: str,
                         start_offset: int = 0,
                         batch_rows: int = 4096) -> None:
        """Convert binary → CSV."""
        with open(src_bin, "rb") as f:
            data = memoryview(f.read())

        total_bytes = len(data)
        off = start_offset
        packet_ok = packet_fail = crc_failure = other_fail = bad_header_fail = error_count = 0
        bad_header_packets = []
        out_buf: List[List] = []

        with open(dst_csv, "w", newline="") as fcsv:
            wr = csv.writer(fcsv)
            wr.writerow(
                ["cam_id", "frame_id", *range(HISTO_SIZE_WORDS),
                 "temperature", "sum"]
            )

            while off + MIN_PACKET_SIZE <= len(data):
                try:
                    hists, ids, temps, consumed = self.parse_histogram_packet(data[off:])
                    off += consumed
                    packet_ok += 1

                    for cam, hist in hists.items():
                        row_sum = int(hist.sum(dtype=np.uint64))
                        out_buf.append(
                            [cam, ids[cam], *hist.tolist(),
                             temps[cam], row_sum]
                        )

                    if len(out_buf) >= batch_rows:
                        wr.writerows(out_buf)
                        out_buf.clear()
                except Exception as exc:
                    error_count += 1
                    if exc.args and exc.args[0] == "CRC mismatch":
                        crc_failure += 1
                    elif exc.args and exc.args[0] == "Missing SOH":
                        packet_fail += 1
                    elif exc.args and exc.args[0] == "Bad header":
                        bad_header_fail += 1
                    else:
                        other_fail += 1

                    # Resync
                    pat = b"\xAA\x00\x41"
                    old_off = off
                    off = off + 1
                    nxt = data.obj.find(pat, off)
                    if nxt != -1:
                        off = nxt
                        bad_header_packets.append((old_off, off))
                        continue
                    break

            if out_buf:
                wr.writerows(out_buf)

        total_packets = packet_ok + packet_fail + crc_failure + other_fail + bad_header_fail
        print(f"Parsed {total_packets} packets, {packet_ok} OK")


def main():
    parser = argparse.ArgumentParser(description="Process histogram .bin to .csv")
    parser.add_argument("--file", "-f", required=True, help="Input .bin file")
    parser.add_argument("--output", "-o", help="Output CSV file (optional)")
    args = parser.parse_args()

    input_file = args.file
    output_file = args.output if args.output else os.path.splitext(input_file)[0] + ".csv"

    processor = DataProcessor()
    processor.process_bin_file(input_file, output_file)


if __name__ == "__main__":
    main()
