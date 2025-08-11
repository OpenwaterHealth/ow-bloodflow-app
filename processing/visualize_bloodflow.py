"""
VisualizeBloodflow: compute and plot BFI/BVI from OpenWater histogram CSVs.

Usages:
  - As a module/class from Qt:
        viz = VisualizeBloodflow(left_csv, right_csv)  # right_csv optional
        viz.compute()
        bfi, bvi, camera_inds = viz.get_results()
        # (optionally) viz.plot(); viz.show()

  - CLI:
        python visualize_bloodflow.py --left path/to/left.csv --right path/to/right.csv \
            --t1 0.0 --t2 120 --save out.png
"""

from __future__ import annotations
import argparse
from dataclasses import dataclass, field
from typing import Optional, Tuple, List

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt


@dataclass
class VisualizeBloodflow:
    left_csv: str
    right_csv: Optional[str] = None

    # Display/time window
    t1: float = 0.0
    t2: float = 120.0

    # Acquisition constants
    frequency_hz: int = 40
    dark_interval: int = 600
    noisy_bin_min: int = 10

    # Calibration (8 cams per module)
    I_min: np.ndarray = field(default_factory=lambda: np.array(
        [[0, 0, 0, 0, 0, 0, 0, 0],
         [0, 0, 0, 0, 0, 0, 0, 0]], dtype=float))
    I_max: np.ndarray = field(default_factory=lambda: np.array(
        [[150, 300, 300, 300, 300, 300, 300, 150],
         [150, 300, 300, 300, 300, 300, 300, 150]], dtype=float))
    C_min: np.ndarray = field(default_factory=lambda: np.array(
        [[0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
         [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]], dtype=float))
    C_max: np.ndarray = field(default_factory=lambda: np.array(
        [[0.4, 0.4, 0.45, 0.55, 0.55, 0.45, 0.4, 0.4],
         [0.4, 0.4, 0.45, 0.55, 0.55, 0.45, 0.4, 0.4]], dtype=float))

    # Internals (populated after compute)
    _BFI: Optional[np.ndarray] = field(default=None, init=False)
    _BVI: Optional[np.ndarray] = field(default=None, init=False)
    _camera_inds: Optional[np.ndarray] = field(default=None, init=False)
    _nmodules: int = field(default=0, init=False)

    # --------------------------
    # Public API
    # --------------------------
    def compute(self) -> None:
        """Load CSV(s), compute BFI/BVI, keep results in members."""
        # Don’t display the first ~20 frames at 40Hz by default
        self.t1 = max(self.t1, 0.5)

        # read first module
        histos, camera_inds, timept, temperature = self._readdata(self.left_csv)
        nmodules = 1
        ncameras = len(camera_inds)

        # maybe read second module
        if self.right_csv:
            histos2, camera_inds2, timept2, temperature2 = self._readdata(self.right_csv)
            histos = np.concatenate((histos, histos2), axis=0)
            camera_inds = np.concatenate((camera_inds, camera_inds2), axis=0)
            # temperature/timept not used beyond alignment
            nmodules = 2

        # baseline adjust & noise floor
        histos = histos.astype(float, copy=False)
        histos[:, :, 0] -= 6
        histos[histos < self.noisy_bin_min] = 0

        # crop data so that final frame is dark
        ntimepts = int(self.dark_interval * np.floor(histos.shape[1] / self.dark_interval) + 1)
        histos = histos[:, :ntimepts, :]

        # get dark histograms (every dark_interval frames)
        inds_dark = np.arange(0, ntimepts, self.dark_interval)
        ndark = len(inds_dark)
        histos_dark = np.zeros((len(camera_inds), ndark, 1024), dtype=float)
        for i in range(ndark):
            histos_dark[:, i, :] = histos[:, int(inds_dark[i]), :]

        # dark stats
        bins = np.expand_dims(np.arange(1024, dtype=float), axis=0)
        temp1 = self._moments(bins, histos_dark, 1)
        temp2 = self._moments(bins, histos_dark, 2)
        tempv = temp2 - temp1 ** 2

        u1_dark = np.zeros((len(camera_inds), ntimepts), dtype=float)
        var_dark = np.zeros((len(camera_inds), ntimepts), dtype=float)

        # interpolate dark stats across frames for ALL cams/modules
        for i in range(ndark - 1):
            ind = int(inds_dark[i])
            interval = inds_dark[i + 1] - ind
            ramp = np.arange(interval) / (interval - 1) if interval > 1 else np.zeros(1)
            for j in range(len(camera_inds)):
                u1_dark[j, ind:(ind + interval)] = temp1[j, i] + (temp1[j, i + 1] - temp1[j, i]) * ramp
                var_dark[j, ind:(ind + interval)] = tempv[j, i] + (tempv[j, i + 1] - tempv[j, i]) * ramp

        u1_dark[:, -1] = temp1[:, -1]
        var_dark[:, -1] = tempv[:, -1]

        # laser stats
        u1 = self._moments(bins, histos, 1)
        u2 = self._moments(bins, histos, 2)
        mean = u1 - u1_dark
        var = (u2 - u1 ** 2) - var_dark
        std = np.sqrt(np.clip(var, 0.0, None))

        # Safe contrast
        contrast = np.divide(std, mean, out=np.zeros_like(std), where=mean > 0)

        # quadratic interpolation to fill in dark frames
        for i in range(1, ndark - 1):
            mean[:, inds_dark[i]] = (-1/6) * mean[:, inds_dark[i] - 2] + (2/3) * mean[:, inds_dark[i] - 1] \
                                    + (2/3) * mean[:, inds_dark[i] + 1] + (-1/6) * mean[:, inds_dark[i] + 2]
            contrast[:, inds_dark[i]] = (-1/6) * contrast[:, inds_dark[i] - 2] + (2/3) * contrast[:, inds_dark[i] - 1] \
                                        + (2/3) * contrast[:, inds_dark[i] + 1] + (-1/6) * contrast[:, inds_dark[i] + 2]

        # remove first and last (dark) frames
        mean = mean[:, 1:-1]
        contrast = contrast[:, 1:-1]

        # compute BFI/BVI
        BFI = np.zeros(contrast.shape, dtype=float)
        BVI = np.zeros(mean.shape, dtype=float)
        cams_per_module = len(camera_inds) // nmodules if nmodules else len(camera_inds)

        for i in range(nmodules):
            for j in range(cams_per_module):
                ind = cams_per_module * i + j
                cam = int(camera_inds[ind])
                cden = (self.C_max[i, cam] - self.C_min[i, cam]) or 1.0
                iden = (self.I_max[i, cam] - self.I_min[i, cam]) or 1.0
                BFI[ind, :] = (1 - (contrast[ind, :] - self.C_min[i, cam]) / cden) * 10.0
                BVI[ind, :] = (1 - (mean[ind, :] - self.I_min[i, cam]) / iden) * 10.0

        # stash results
        self._BFI = BFI
        self._BVI = BVI
        self._camera_inds = camera_inds
        self._nmodules = nmodules

    def get_results(self) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Return (BFI, BVI, camera_inds). Call after compute()."""
        if self._BFI is None:
            raise RuntimeError("Call compute() before get_results().")
        return self._BFI, self._BVI, self._camera_inds

    def plot(self, legend: Tuple[str, str] = ('BFI', 'BVI')) -> plt.Figure:
        """Create the Birmingham-style plot. Returns the matplotlib Figure."""
        if self._BFI is None or self._BVI is None or self._camera_inds is None:
            raise RuntimeError("Call compute() before plot().")

        x = self._BFI
        y = self._BVI
        camera_inds = self._camera_inds
        nmodules = self._nmodules

        t = np.arange(x.shape[1], dtype=float) / self.frequency_hz
        # sanitize t2
        t1, t2 = self.t1, (t[-1] if self.t2 <= self.t1 or self.t2 == 0 else self.t2)
        ind1 = int(self.frequency_hz * t1)
        ind2 = int(self.frequency_hz * t2)

        ncameras = int(len(camera_inds) / max(nmodules, 1))
        fig, ax = plt.subplots(nrows=ncameras, ncols=max(nmodules, 1), figsize=(12, 8), squeeze=False)

        # Ensure we always have two columns (Left/Right) when two modules
        if nmodules == 1 and ax.shape[1] == 1:
            # Plot into column 0, still label as "Left"
            pass

        for j in range(nmodules or 1):
            for i in range(ncameras):
                # Birmingham far sensor on top mapping
                if i == 0:
                    m = 0
                elif i == 1:
                    m = 2
                elif i == 2:
                    m = 3
                else:
                    m = 1

                ind_cam = ncameras * j + i
                ax_mj = ax[m, j]
                line1 = ax_mj.plot(t[ind1:ind2], x[ind_cam, ind1:ind2], 'k', linewidth=2, label=legend[0])
                ax2 = ax_mj.twinx()
                line2 = ax2.plot(t[ind1:ind2], y[ind_cam, ind1:ind2], 'r', linewidth=1, label=legend[1])
                ax2.tick_params(axis='y', colors='red')

                # keep legacy inversion condition if someone passes ('contrast','mean')
                if legend[0] == 'contrast':
                    ax[m, 0].invert_yaxis()
                if legend[1] == 'mean':
                    ax2.invert_yaxis()

                lines = line1 + line2
                labels = [l.get_label() for l in lines]
                ax_mj.legend(lines, labels)
                ax_mj.set_ylabel('Camera ' + str(int(camera_inds[i])))

        # Titles/labels
        ax[0, 0].set_title('Left')
        if ax.shape[1] > 1:
            ax[0, 1].set_title('Right')
        ax[-1, 0].set_xlabel('Time (s)')
        if ax.shape[1] > 1:
            ax[-1, 1].set_xlabel('Time (s)')

        fig.tight_layout()
        return fig

    def show(self) -> None:
        """Show the current matplotlib figure."""
        plt.show()

    def save_results_csv(self, path: str) -> None:
        """Save BFI and BVI results to CSV."""
        if self._BFI is None or self._BVI is None or self._camera_inds is None:
            raise RuntimeError("Call compute() before saving results.")

        nframes = self._BFI.shape[1]
        time_s = np.arange(nframes, dtype=float) / self.frequency_hz

        rows = []
        for cam_idx, cam_id in enumerate(self._camera_inds):
            for frame_idx in range(nframes):
                rows.append({
                    "camera": int(cam_id),
                    "time_s": time_s[frame_idx],
                    "BFI": self._BFI[cam_idx, frame_idx],
                    "BVI": self._BVI[cam_idx, frame_idx],
                })

        df = pd.DataFrame(rows)
        df.to_csv(path, index=False)
        print(f"Saved results CSV: {path}")

    # --------------------------
    # Internals
    # --------------------------
    @staticmethod
    def _moments(bins: np.ndarray, histos: np.ndarray, power: int) -> np.ndarray:
        """
        bins: shape (1, 1024) or (1024,)
        histos: shape (cams, time, 1024)
        returns: (cams, time)
        """
        s = histos.shape
        m = np.zeros((s[0], s[1]), dtype=float)
        w = (bins ** power)
        for i in range(s[0]):
            numer = np.sum(w * histos[i, :, :], axis=1)
            denom = np.sum(histos[i, :, :], axis=1)
            m[i, :] = np.divide(numer, denom, out=np.zeros_like(numer, dtype=float), where=denom > 0)
        return m

    @staticmethod
    def _readdata(csv_path: str) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        FRAME_ID_MAX = 256

        x = np.array(pd.read_csv(csv_path))
        ind1 = np.where(x[:, 1] == 1)[0][0]  # 1st line in csv with good data
        x = x[ind1:, :]
        camera = x[:, 0]
        timept = x[:, 1]
        temperature = x[:, 1026]

        camera_inds = np.unique(camera)
        ncameras = len(camera_inds)
        rollovers = np.insert(np.cumsum((np.diff(timept) < 0)), 0, 0)

        timept = rollovers * FRAME_ID_MAX + timept
        ntimepts = int(np.amax(timept))

        data = np.zeros((ncameras, ntimepts, 1024), dtype=float)
        for i in range(len(camera)):
            idx = np.where(camera_inds == camera[i])[0][0]
            data[idx, int(timept[i]) - 1, :] = x[i, 2:1026]

        return data, camera_inds, timept, temperature


# --------------------------
# CLI
# --------------------------
def _build_argparser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Compute and visualize BFI/BVI from histogram CSVs.")
    p.add_argument("--left", required=True, help="Left module CSV file")
    p.add_argument("--right", help="Right module CSV file (optional)")
    p.add_argument("--t1", type=float, default=0.0, help="Start time (s), default 0.0")
    p.add_argument("--t2", type=float, default=120.0, help="End time (s). If <= t1 or 0, uses full duration")
    p.add_argument("--freq", type=int, default=40, help="Frame rate Hz (default 40)")
    p.add_argument("--dark-interval", type=int, default=600, help="Dark interval (frames) (default 600)")
    p.add_argument("--noisy-bin-min", type=int, default=10, help="Bins below this are zeroed (default 10)")
    p.add_argument("--save", help="Save figure to this path (e.g. out.png). If omitted, just shows window")
    p.add_argument("--no-show", action="store_true", help="Do not display the window (use with --save)")
    return p


def main():
    args = _build_argparser().parse_args()

    viz = VisualizeBloodflow(
        left_csv=args.left,
        right_csv=args.right,
        t1=args.t1,
        t2=args.t2,
        frequency_hz=args.freq,
        dark_interval=args.dark_interval,
        noisy_bin_min=args.noisy_bin_min,
    )
    viz.compute()
    
    if args.save:
        csv_path = args.save.rsplit(".", 1)[0] + "_results.csv"
        viz.save_results_csv(csv_path)

    # Plot
    fig = viz.plot(legend=('BFI', 'BVI'))

    # Save/Show
    if args.save:
        fig.savefig(args.save, dpi=150, bbox_inches='tight')
        print(f"Saved figure: {args.save}")
    if not args.no_show:
        viz.show()


if __name__ == "__main__":
    main()
