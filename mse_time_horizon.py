import torch
from meta import Meta

import pandas as pd
import seaborn as sns
import numpy as np
import matplotlib.pyplot as plt

from argparse import ArgumentParser
from os.path import dirname, isfile

plt.rc('axes', labelsize=18)
TICK_SIZE=12
plt.rc('xtick', labelsize=TICK_SIZE)
plt.rc('ytick', labelsize=TICK_SIZE)

PREFIX='mse_time_horizon_'


def parse_args():
    ap = ArgumentParser()
    ap.add_argument('path', type=str, help="Path to .pth file")
    ap.add_argument('--t_max', type=float, default=100)
    ap.add_argument('--n_t_steps', type=float, default=50)
    ap.add_argument('--n_mc', type=int, default=100)
    ap.add_argument('--force', action='store_true')

    return ap.parse_args()


def main():
    args = parse_args()

    meta: Meta = torch.load(args.path, map_location=torch.device('cpu'))
    print(meta)
    fname = PREFIX + meta.train_id.hex + '.csv'

    if args.force or not isfile(fname):
        loss_vals = compute_loss_vals(args, meta)
        loss_vals.to_csv(fname)
    else:
        loss_vals = pd.read_csv(fname)

    fig, ax = plt.subplots(figsize=(6, 5), dpi=120)

    sns.lineplot(x='Time horizon', y='Loss', data=loss_vals, ax=ax)
    ax.set_yscale('log')
    fig.tight_layout()
    fig.savefig(PREFIX + meta.train_id.hex + '.pdf')

    plt.show()


def compute_loss_vals(args, meta):
    meta.set_root(dirname(__file__))
    model = meta.load_model()
    model.eval()

    generator: TrajectoryGenerator = meta.generator
    delta = generator._delta

    th_vals = np.linspace(meta.data_time_horizon, args.t_max, args.n_t_steps)
    loss_vals = []

    for time_horizon in th_vals:
        n_samples = int(250 * time_horizon / meta.data_time_horizon)

        for _ in range(args.n_mc):
            x0, t, y, u = generator.get_example(
                    time_horizon=time_horizon,
                    n_samples=n_samples)

            x0_feed, t_feed, u_feed = pack_model_inputs(x0, t, u, delta)
            y_pred = meta.predict(model, t_feed, x0_feed, u_feed)
            sq_error = np.square(y - np.flip(y_pred, 0))
            loss = np.mean(np.sum(sq_error, axis=1))

            loss_vals.append([time_horizon, loss])

    return pd.DataFrame(loss_vals, columns=['Time horizon', 'Loss'])


if __name__ == '__main__':
    main()