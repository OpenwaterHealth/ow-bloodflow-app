# processing/visualize_data.py
from __future__ import annotations
import argparse
from dataclasses import dataclass, field
from typing import List, Tuple, Optional

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt


# ─────────────────────────────────────────────────────────────────────────────
# Utility / math
# ─────────────────────────────────────────────────────────────────────────────

def _moments(bins: np.ndarray, histos: np.ndarray, power: int) -> np.ndarray:
    """
    bins:  (1, 1024)
    histos:(n_cam, n_time, 1024)
    returns (n_cam, n_time)
    """
    s0, s1, _ = histos.shape
    m = np.zeros((s0, s1))
    num = (bins ** power) * histos  # (n_cam, n_time, 1024) broadcast
    m[:, :] = np.sum(num, axis=2) / np.clip(np.sum(histos, axis=2), 1e-9, None)
    return m


def _readdata(csv_path: str) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """
    Load one CSV (columns: cam_id, frame_id, <1024 histo words>, temperature, sum)
    Returns:
      histos      -> (n_cam, n_time, 1024)
      camera_inds -> (n_cam,)
      timept      -> (n_time,) (absolute frame index with rollover handled)
      temperature -> (n_time,) per-row temp (first camera’s sequence; used only for parity)
    """
    FRAME_ID_MAX = 256

    x = np.asarray(pd.read_csv(csv_path))
    # find first good row where frame_id==1
    # (kept from original script; adjust if your CSV starts elsewhere)
    ind1 = np.where(x[:, 1] == 1)[0][0]
    x = x[ind1:, :]

    camera = x[:, 0].astype(int)
    frame_id = x[:, 1].astype(int)
    temperature = x[:, 1026]

    camera_inds = np.unique(camera)
    n_cam = len(camera_inds)

    # handle rollover
    rollovers = np.insert(np.cumsum(np.diff(frame_id) < 0), 0, 0)
    timept_abs = rollovers * FRAME_ID_MAX + frame_id
    n_time = int(np.max(timept_abs))

    histos = np.zeros((n_cam, n_time, 1024), dtype=float)
    for i in range(x.shape[0]):
        cam_idx = int(np.where(camera_inds == camera[i])[0])
        t_idx = int(timept_abs[i] - 1)
        histos[cam_idx, t_idx, :] = x[i, 2:1026]

    return histos, camera_inds, timept_abs, temperature


def _plot_birmingham(
    BFI: np.ndarray, BVI: np.ndarray, f_hz: float,
    camera_inds: np.ndarray, nmodules: int, legend: Tuple[str, str],
    t1: float = 0.0, t2: float = 0.0
):
    """
    Layout matches your original (Left/Right columns, far sensor on top mapping).
    BFI/BVI shape: (n_cam_total, n_time)
    camera_inds:   (n_cam_per_module,)
    """
    t = np.arange(BFI.shape[1], dtype=float) / float(f_hz)
    if t2 <= t1 or t2 == 0:
        t2 = t[-1]
    ind1 = int(f_hz * t1)
    ind2 = int(f_hz * t2)

    n_cam_per_module = int(len(camera_inds))
    ncameras = n_cam_per_module  # per module
    fig, ax = plt.subplots(nrows=ncameras, ncols=nmodules, figsize=(12, 8), sharex=True)

    if ncameras == 1 and nmodules == 1:
        ax = np.array([[ax]])

    # Birmingham vertical remap (far sensor on top)
    def _row_map(i: int) -> int:
        if i == 0: return 0
        if i == 1: return 2
        if i == 2: return 3
        if i == 3: return 1
        return i

    for j in range(nmodules):  # module: 0=Left, 1=Right
        for i in range(ncameras):
            m = _row_map(i)
            ind_cam = ncameras * j + i

            ax1 = ax[m, j]
            line1 = ax1.plot(t[ind1:ind2], BFI[ind_cam, ind1:ind2], linewidth=2, label=legend[0])
            ax2 = ax1.twinx()
            line2 = ax2.plot(t[ind1:ind2], BVI[ind_cam, ind1:ind2], linewidth=1, label=legend[1])

            # Optional invert like original:
            if legend[0].lower() == "contrast":
                ax1.invert_yaxis()
            if legend[1].lower() == "mean":
                ax2.invert_yaxis()

            lines = line1 + line2
            labels = [l.get_label() for l in lines]
            ax1.legend(lines, labels, fontsize=8, loc="upper right")
            ax1.set_ylabel(f"Camera {int(camera_inds[i])}")

    if nmodules >= 1:
        ax[0, 0].set_title("Left")
    if nmodules >= 2:
        ax[0, 1].set_title("Right")
    ax[-1, 0].set_xlabel("Time (s)")
    if nmodules >= 2:
        ax[-1, 1].set_xlabel("Time (s)")

    plt.tight_layout()
    plt.show()


# ─────────────────────────────────────────────────────────────────────────────
# Class
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class VizConfig:
    frequency_hz: float = 40.0
    dark_interval: int = 600        # frames
    noisy_bin_min: int = 10
    min_start_time: float = 0.5     # seconds to skip at the beginning
    # Calibration arrays: shape (2,8) for (module, camera_id) like original
    I_min: np.ndarray = field(default_factory=lambda: np.array(
        [[0, 0, 0, 0, 0, 0, 0, 0],
         [0, 0, 0, 0, 0, 0, 0, 0]], dtype=float))
    I_max: np.ndarray = field(default_factory=lambda: np.array(
        [[150, 300, 300, 300, 300, 300, 300, 150],
         [150, 300, 300, 300, 300, 300, 300, 150]], dtype=float))
    C_min: np.ndarray = field(default_factory=lambda: np.array(
        [[0.0]*8, [0.0]*8], dtype=float))
    C_max: np.ndarray = field(default_factory=lambda: np.array(
        [[0.2, 0.2, 0.3, 0.4, 0.4, 0.3, 0.2, 0.2],
         [0.2, 0.2, 0.3, 0.4, 0.4, 0.3, 0.2, 0.2]], dtype=float))


class DataVisualizer:
    def __init__(self, cfg: Optional[VizConfig] = None):
        self.cfg = cfg or VizConfig()

    def load(self, left_csv: str, right_csv: Optional[str] = None):
        """Load one or two CSVs → combined histos array and camera indices."""
        histosL, camsL, timeptL, tempL = _readdata(left_csv)
        ncam = len(camsL)

        if right_csv:
            histosR, camsR, timeptR, tempR = _readdata(right_csv)
            histos = np.concatenate([histosL, histosR], axis=0)
            camera_inds = np.concatenate([camsL, camsR], axis=0)
            nmodules = 2
        else:
            histos = histosL
            camera_inds = camsL
            nmodules = 1

        return histos, camera_inds, nmodules

    def compute_bfi_bvi(
        self, histos: np.ndarray, camera_inds: np.ndarray, nmodules: int
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        histos: (n_cam_total, n_time, 1024)
        returns: (BFI, BVI) each (n_cam_total, n_time-2) after dark interpolation trim
        """
        cfg = self.cfg
        n_cam_total, n_time, _ = histos.shape
        n_cam_per_module = n_cam_total // nmodules

        # pre-processing like original
        histos = histos.copy()
        histos[:, :, 0] -= 6
        histos[histos < cfg.noisy_bin_min] = 0

        # crop so last frame is dark-aligned
        ntimepts = int(cfg.dark_interval * np.floor(n_time / cfg.dark_interval) + 1)
        histos = histos[:, :ntimepts, :]

        # dark frames
        inds_dark = np.arange(0, ntimepts, cfg.dark_interval, dtype=int)
        ndark = len(inds_dark)
        histos_dark = np.zeros((n_cam_total, ndark, 1024))
        for i, idx in enumerate(inds_dark):
            histos_dark[:, i, :] = histos[:, idx, :]

        bins = np.expand_dims(np.arange(1024, dtype=float), axis=0)  # (1,1024)

        # dark stats
        u1_dark_pts = _moments(bins, histos_dark, 1)   # (n_cam_total, ndark)
        u2_dark_pts = _moments(bins, histos_dark, 2)
        var_dark_pts = u2_dark_pts - u1_dark_pts**2

        u1_dark = np.zeros((n_cam_total, ntimepts))
        var_dark = np.zeros((n_cam_total, ntimepts))
        for i in range(ndark - 1):
            ind = int(inds_dark[i])
            interval = int(inds_dark[i + 1] - ind)
            # linear interp across interval
            ramp = np.arange(interval) / max(interval - 1, 1)
            u1_dark[:, ind:ind + interval] = (
                u1_dark_pts[:, [i]] + (u1_dark_pts[:, [i + 1]] - u1_dark_pts[:, [i]]) * ramp
            )
            var_dark[:, ind:ind + interval] = (
                var_dark_pts[:, [i]] + (var_dark_pts[:, [i + 1]] - var_dark_pts[:, [i]]) * ramp
            )
        u1_dark[:, -1] = u1_dark_pts[:, -1]
        var_dark[:, -1] = var_dark_pts[:, -1]

        # laser stats
        u1 = _moments(bins, histos, 1)
        u2 = _moments(bins, histos, 2)
        mean = u1 - u1_dark
        var = u2 - u1**2 - var_dark
        std = np.sqrt(np.clip(var, 0, None))
        contrast = std / np.clip(mean, 1e-9, None)

        # quadratic interpolation to fill dark frames (like original)
        for i in range(1, ndark - 1):
            d = inds_dark[i]
            mean[:, d] = (
                (-1 / 6) * mean[:, d - 2] + (2 / 3) * mean[:, d - 1]
                + (2 / 3) * mean[:, d + 1] + (-1 / 6) * mean[:, d + 2]
            )
            contrast[:, d] = (
                (-1 / 6) * contrast[:, d - 2] + (2 / 3) * contrast[:, d - 1]
                + (2 / 3) * contrast[:, d + 1] + (-1 / 6) * contrast[:, d + 2]
            )

        # remove first/last (dark) frames
        mean = mean[:, 1:-1]
        contrast = contrast[:, 1:-1]

        # compute BFI/BVI with calibration
        BFI = np.zeros_like(contrast)
        BVI = np.zeros_like(mean)

        for mod in range(nmodules):
            for j in range(n_cam_per_module):
                idx = n_cam_per_module * mod + j
                cam_id = int(camera_inds[j])  # per-module mapping
                BFI[idx, :] = (1 - (contrast[idx, :] - cfg.C_min[mod, cam_id])
                               / np.clip(cfg.C_max[mod, cam_id] - cfg.C_min[mod, cam_id], 1e-9, None)) * 10.0
                BVI[idx, :] = (1 - (mean[idx, :] - cfg.I_min[mod, cam_id])
                               / np.clip(cfg.I_max[mod, cam_id] - cfg.I_min[mod, cam_id], 1e-9, None)) * 10.0

        return BFI, BVI

    def visualize(
        self,
        left_csv: str,
        right_csv: Optional[str] = None,
        t1: float = 0.0,
        t2: float = 0.0,
        legend: Tuple[str, str] = ("BFI", "BVI"),
        show: bool = True,
    ):
        # enforce min start time like original
        t1 = max(t1, self.cfg.min_start_time)

        histos, camera_inds, nmodules = self.load(left_csv, right_csv)
        BFI, BVI = self.compute_bfi_bvi(histos, camera_inds, nmodules)

        _plot_birmingham(BFI, BVI, self.cfg.frequency_hz, camera_inds, nmodules, legend, t1=t1, t2=t2)

        if show:
            plt.show()


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────

def _parse_args():
    p = argparse.ArgumentParser(description="Visualize BFI/BVI from one or two CSV files")
    p.add_argument("--left", required=True, help="Left CSV path")
    p.add_argument("--right", help="Right CSV path (optional)")
    p.add_argument("--t1", type=float, default=0.0, help="Start time (s)")
    p.add_argument("--t2", type=float, default=0.0, help="End time (s), 0 for full")
    p.add_argument("--freq", type=float, default=40.0, help="Acquisition frequency (Hz)")
    p.add_argument("--dark-interval", type=int, default=600, help="Frame interval between dark frames")
    p.add_argument("--noisy-bin-min", type=int, default=10, help="Clamp bins below this to 0")
    return p.parse_args()


def main():
    args = _parse_args()
    cfg = VizConfig(
        frequency_hz=args.freq,
        dark_interval=args.dark_interval,
        noisy_bin_min=args.noisy_bin_min,
    )
    viz = DataVisualizer(cfg)
    viz.visualize(args.left, args.right, t1=args.t1, t2=args.t2)


if __name__ == "__main__":
    main()
