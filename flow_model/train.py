import torch
import time
from .experiment import Experiment


def validate(data, loss_fn, model, device):
    vl = 0.

    with torch.no_grad():
        for (x0, t, y, u, lengths) in data:
            sort_idxs = torch.argsort(lengths, descending=True)

            x0 = x0[sort_idxs]
            t = t[sort_idxs]
            y = y[sort_idxs]
            u = u[sort_idxs]
            lengths = lengths[sort_idxs]

            u = torch.nn.utils.rnn.pack_padded_sequence(u,
                                                        lengths,
                                                        batch_first=True,
                                                        enforce_sorted=True)

            x0 = x0.to(device)
            t = t.to(device)
            y = y.to(device)
            u = u.to(device)

            y_pred = model(t, x0, u)
            vl += loss_fn(y, y_pred).item()

    return vl / len(data)


def train_step(example, loss_fn, model, optimizer, device):
    x0, t, y, u, lengths = example

    sort_idxs = torch.argsort(lengths, descending=True)

    x0 = x0[sort_idxs]
    t = t[sort_idxs]
    y = y[sort_idxs]
    u = u[sort_idxs]
    lengths = lengths[sort_idxs]

    u = torch.nn.utils.rnn.pack_padded_sequence(u,
                                                lengths,
                                                batch_first=True,
                                                enforce_sorted=True)

    x0 = x0.to(device)
    t = t.to(device)
    y = y.to(device)
    u = u.to(device)

    optimizer.zero_grad()

    y_pred = model(t, x0, u)
    loss = loss_fn(y, y_pred)

    loss.backward()
    optimizer.step()

    return loss.item()


class EarlyStopping:

    def __init__(self, es_patience, es_delta=0.):
        self.patience = es_patience
        self.delta = es_delta

        self.best_val_loss = float('inf')
        self.counter = 0
        self.early_stop = False
        self.best_model = False

    def step(self, val_loss):
        self.best_model = False

        if self.best_val_loss - val_loss > self.delta:
            self.best_val_loss = val_loss
            self.best_model = True
            self.counter = 0
        else:
            self.counter += 1

        if self.counter >= self.patience:
            self.early_stop = True


def train(experiment: Experiment, model, loss_fn, optimizer, sched,
          early_stop: EarlyStopping, train_dl, val_dl, test_dl, device,
          max_epochs):
    header_msg = f"{'Epoch':>5} :: {'Loss (Train)':>16} :: " \
        f"{'Loss (Val)':>16} :: {'Loss (Test)':>16} :: {'Best (Val)':>16}"

    print(header_msg)
    print('=' * len(header_msg))

    start = time.time()

    for epoch in range(max_epochs):
        model.train()
        for example in train_dl:
            train_step(example, loss_fn, model, optimizer, device)

        model.eval()
        train_loss = validate(train_dl, loss_fn, model, device)
        val_loss = validate(val_dl, loss_fn, model, device)
        test_loss = validate(test_dl, loss_fn, model, device)

        sched.step(val_loss)
        early_stop.step(val_loss)

        print(
            f"{epoch + 1:>5d} :: {train_loss:>16e} :: {val_loss:>16e} :: " \
            f"{test_loss:>16e} :: {early_stop.best_val_loss:>16e}"
        )

        if early_stop.best_model:
            experiment.save_model(model)

        experiment.register_progress(train_loss, val_loss, test_loss,
                                     early_stop.best_model)

        if early_stop.early_stop:
            break

    train_time = time.time() - start
    experiment.save(train_time)

    return train_time
